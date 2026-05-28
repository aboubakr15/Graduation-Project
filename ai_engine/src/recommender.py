import logging
import urllib.parse
import traceback
import httpx
import re
import json
from typing import List, Dict, Optional

logger = logging.getLogger(__name__)

class RecommendationEngine:
    """Handles generating recommendations for courses and articles."""
    
    def __init__(self):
        pass

    def get_youtube_recommendations(self, topic: str, count: int = 3) -> List[Dict]:
        """
        Search YouTube for relevant educational videos using a manual parsing approach
        to bypass library instabilities.
        """
        if not topic or not isinstance(topic, str):
            logger.warning(f"Invalid topic provided to recommender: {topic}")
            return []

        try:
            # Check if topic is mostly Arabic
            is_arabic = any('\u0600' <= char <= '\u06FF' for char in topic)
            
            # Formulate queries
            queries = []
            if is_arabic:
                queries.append(topic)
                queries.append(f"كورس {topic}")
            else:
                queries.append(f"{topic} course")
                queries.append(topic)
            
            recommendations = []
            seen_links = set()
            
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
            }
            
            with httpx.Client(timeout=10) as client:
                for query in queries:
                    if len(recommendations) >= count:
                        break
                        
                    # Safe log query to prevent UnicodeEncodeError on CP1252 Windows consoles
                    safe_query = query.encode('ascii', errors='replace').decode('ascii') if isinstance(query, str) else query
                    logger.info(f"Manual YouTube search: {safe_query}")
                    url = f"https://www.youtube.com/results?search_query={urllib.parse.quote(query)}"
                    
                    try:
                        response = client.get(url, headers=headers)
                        response.raise_for_status()
                        
                        # Extract ytInitialData
                        match = re.search(r"var ytInitialData = ({.*?});", response.text)
                        if not match:
                            continue
                            
                        data = json.loads(match.group(1))
                        
                        # Navigate structure
                        try:
                            contents = data['contents']['twoColumnSearchResultsRenderer']['primaryContents']['sectionListRenderer']['contents']
                        except:
                            continue

                        for content in contents:
                            if 'itemSectionRenderer' in content:
                                items = content['itemSectionRenderer']['contents']
                                for item in items:
                                    if 'videoRenderer' in item:
                                        video = item['videoRenderer']
                                        video_id = video['videoId']
                                        link = f"https://www.youtube.com/watch?v={video_id}"
                                        
                                        if link not in seen_links:
                                            try:
                                                title = video['title']['runs'][0]['text']
                                                duration = video.get('lengthText', {}).get('simpleText', "N/A")
                                                
                                                recommendations.append({
                                                    "title": title,
                                                    "link": link,
                                                    "duration": duration,
                                                    "type": "YouTube Video"
                                                })
                                                seen_links.add(link)
                                                if len(recommendations) >= count:
                                                    break
                                            except:
                                                continue
                    except Exception as e:
                        safe_query = query.encode('ascii', errors='replace').decode('ascii') if isinstance(query, str) else query
                        logger.warning(f"Failed query phase for '{safe_query}': {e}")
                        continue
            
            return recommendations
        except Exception as e:
            safe_topic = topic.encode('ascii', errors='replace').decode('ascii') if isinstance(topic, str) else topic
            logger.error(f"Global error in YouTube search for topic '{safe_topic}': {e}")
            logger.error(traceback.format_exc())
            return []

    def get_all_recommendations(self, topic: str) -> Dict:
        """
        Get only YouTube recommendations.
        """
        return {
            "youtube": self.get_youtube_recommendations(topic)
        }
