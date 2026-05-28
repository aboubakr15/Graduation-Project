import re
import logging
import os
import tempfile
import shutil
import subprocess
from typing import Optional, List, Dict
import youtube_transcript_api

# Basic logging setup
logger = logging.getLogger(__name__)

# Optional imports for transcription fallback
try:
    import yt_dlp
    from faster_whisper import WhisperModel
    TRANSCRIPTION_AVAILABLE = True
except ImportError:
    TRANSCRIPTION_AVAILABLE = False
    logger.warning("Transcription dependencies (yt-dlp, faster-whisper) not found. Fallback disabled.")

class YouTubeProcessor:
    """Handles extraction and generation of transcripts from YouTube videos."""
    
    def __init__(self):
        self.whisper_model = None
        self.model_size = "tiny" 
        self.cache_dir = os.path.join(os.path.dirname(__file__), "..", "data", "transcript_cache")
        os.makedirs(self.cache_dir, exist_ok=True)

    def _get_cache_path(self, video_id: str) -> str:
        return os.path.join(self.cache_dir, f"{video_id}.json")

    def _load_cache(self, video_id: str) -> Optional[Dict]:
        path = self._get_cache_path(video_id)
        if os.path.exists(path):
            import json
            with open(path, 'r', encoding='utf-8') as f:
                return json.load(f)
        return None

    def _save_cache(self, video_id: str, data: Dict):
        path = self._get_cache_path(video_id)
        import json
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    @staticmethod
    def extract_video_id(url: str) -> Optional[str]:
        """Extract the video ID from a YouTube URL."""
        if not url: return None
        patterns = [
            r'v=([0-9A-Za-z_-]{11})',
            r'youtu\.be\/([0-9A-Za-z_-]{11})',
            r'embed\/([0-9A-Za-z_-]{11})',
            r'\/v\/([0-9A-Za-z_-]{11})',
            r'shorts\/([0-9A-Za-z_-]{11})'
        ]
        
        for pattern in patterns:
            match = re.search(pattern, url)
            if match:
                return match.group(1)
        return None

    def get_video_info(self, video_id: str) -> Dict:
        """Fetch video title and duration using yt-dlp."""
        default_info = {"title": "Unknown Title", "duration": "N/A"}
        if not TRANSCRIPTION_AVAILABLE:
            return default_info
            
        try:
            ydl_opts = {
                'quiet': True, 
                'no_warnings': True,
                'no_playlist': True,
                'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'nocheckcertificate': True,
            }
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(f"https://www.youtube.com/watch?v={video_id}", download=False)
                duration_secs = info.get('duration', 0)
                return {
                    "title": info.get('title', 'Unknown Title'),
                    "duration": self._format_timestamp(duration_secs) if duration_secs else "N/A"
                }
        except Exception as e:
            logger.warning(f"Failed to fetch metadata for {video_id}: {e}")
            return default_info

    def _format_timestamp(self, seconds: float) -> str:
        """Convert seconds to HH:MM:SS format."""
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"

    @staticmethod
    def _get_segment_value(segment, key):
        """Safely get a value from a segment, supporting both dict and object access."""
        try:
            return segment[key]
        except (TypeError, KeyError):
            return getattr(segment, key, None)

    def get_transcript(self, video_id: str) -> Optional[str]:
        """Fetch transcript from YouTube API and group segments.
        Stage 1: youtube-transcript-api (fastest, no download).
        Stage 2: Whisper fallback (downloads audio, slower).
        """
        # --- Stage 1: YouTube Transcript API ---
        try:
            logger.info(f"Stage 1: Trying youtube-transcript-api for {video_id}...")
            yt = youtube_transcript_api.YouTubeTranscriptApi()
            transcript_list = yt.list(video_id)
            
            try:
                transcript = transcript_list.find_transcript(['ar', 'en'])
            except:
                try:
                    transcript = transcript_list.find_generated_transcript(['ar', 'en'])
                except:
                    transcript = next(iter(transcript_list))

            if transcript:
                raw_data = transcript.fetch()
                # Normalize to list of dicts (handles both old dict format and new object format)
                normalized = []
                for seg in raw_data:
                    start = self._get_segment_value(seg, 'start')
                    text = self._get_segment_value(seg, 'text')
                    if start is not None and text is not None:
                        normalized.append({'start': float(start), 'text': str(text)})
                
                if normalized:
                    logger.info(f"Stage 1 SUCCESS: Got {len(normalized)} segments from API for {video_id}")
                    return self._group_segments(normalized)
            
            return None
            
        except Exception as e:
            logger.info(f"Stage 1 FAILED for {video_id}: {e}")
            # Whisper fallback disabled to prevent slow audio downloads
            return None

    def _group_segments(self, segments: List[Dict], interval_secs: int = 30) -> str:
        """Group transcript segments into logical time blocks."""
        if not segments:
            return ""

        grouped = []
        current_group_text = []
        if not segments: return ""
        current_group_start = segments[0]['start']
        
        for segment in segments:
            if segment['start'] - current_group_start >= interval_secs:
                ts = self._format_timestamp(current_group_start)
                text = " ".join(current_group_text).strip()
                if text:
                    grouped.append(f"[{ts}] {text}")
                
                current_group_text = [segment['text']]
                current_group_start = segment['start']
            else:
                current_group_text.append(segment['text'])
        
        if current_group_text:
            ts = self._format_timestamp(current_group_start)
            grouped.append(f"[{ts}] {' '.join(current_group_text).strip()}")
            
        return "\n".join(grouped)

    def _transcribe_fallback(self, video_id: str) -> Optional[str]:
        """Download audio and transcribe using Whisper as a fallback."""
        if not shutil.which("ffmpeg"):
            logger.error("ffmpeg not found in PATH. Transcription fallback failed.")
            return None

        logger.info(f"Starting Whisper transcription for: {video_id}")
        
        with tempfile.TemporaryDirectory() as tmpdir:
            audio_path = os.path.join(tmpdir, "audio.mp3")
            url = f"https://www.youtube.com/watch?v={video_id}"
            
            ydl_opts = {
                'format': 'm4a/bestaudio/best',
                'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'extractor_args': {'youtube': {'player_client': ['android', 'web']}},
                'postprocessors': [{
                    'key': 'FFmpegExtractAudio',
                    'preferredcodec': 'mp3',
                    'preferredquality': '128',
                }],
                'outtmpl': os.path.join(tmpdir, 'audio.%(ext)s'),
                'quiet': True,
                'no_warnings': True,
                'nocheckcertificate': True,
            }
            
            try:
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    ydl.download([url])
            except Exception as e:
                error_msg = str(e)
                if "403: Forbidden" in error_msg:
                    logger.error(f"yt-dlp download blocked (403 Forbidden). This video is likely age-restricted or restricted in this region: {video_id}")
                    # Return a special marker to indicate restriction
                    return "[ERROR: Video is age-restricted or unavailable for download. Try a different video.]"
                
                logger.error(f"yt-dlp download failed: {e}")
                return None

            try:
                if not self.whisper_model:
                    logger.info(f"Loading Whisper model ({self.model_size})...")
                    device = "cuda" if os.environ.get('EMBEDDING_DEVICE') == 'cuda' else "cpu"
                    compute_type = "float16" if device == "cuda" else "int8"
                    self.whisper_model = WhisperModel(self.model_size, device=device, compute_type=compute_type)
                
                segments, info = self.whisper_model.transcribe(audio_path, beam_size=5)
                
                whisper_segments = []
                for segment in segments:
                    whisper_segments.append({'start': segment.start, 'text': segment.text})
                
                logger.info(f"Whisper transcription done for {video_id} ({info.language})")
                return self._group_segments(whisper_segments)
                
            except Exception as e:
                logger.error(f"Whisper processing failed: {e}")
                return None

    def process_url(self, url: str) -> Optional[Dict]:
        """Complete pipeline: extract ID, get metadata, and get transcript."""
        video_id = self.extract_video_id(url)
        if not video_id:
            return None
        
        # Check Cache first
        cached_data = self._load_cache(video_id)
        if cached_data:
            logger.info(f"Using CACHED transcript for {video_id}")
            return cached_data

        # 1. Get transcript FIRST (Fastest)
        transcript = self.get_transcript(video_id)
        
        # 2. Get metadata SECOND (Slower, optional)
        info = {"title": "Unknown Title", "duration": "N/A"}
        if transcript: # Only wait for metadata if we at least have the transcript
            info = self.get_video_info(video_id)
        
        result = {
            "transcript": transcript,
            "title": info["title"],
            "duration": info["duration"],
            "video_id": video_id
        }
        
        # Save to Cache
        if transcript:
            self._save_cache(video_id, result)
            
        return result
