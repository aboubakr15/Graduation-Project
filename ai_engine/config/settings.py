import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# ── Project paths ──────────────────────────────────────────────────────────────
BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"

# ★ التعديل الجديد: تحديد مسار الـ Raw Materials ★
RAW_DATA_DIR = DATA_DIR / "raw"

PROCESSED_DATA_DIR = DATA_DIR / "processed"

# Create directories if they don't exist
PROCESSED_DATA_DIR.mkdir(parents=True, exist_ok=True)
RAW_DATA_DIR.mkdir(parents=True, exist_ok=True) # هيعمل فولدر raw لو ملقاهوش

# ── Vector store settings ──────────────────────────────────────────────────────
# Using Cloud Qdrant (Credentials in environment variables QDRANT_URL, QDRANT_API_KEY)
COLLECTION_NAME = "college_courses"

CHUNKS_CACHE_PATH = str(PROCESSED_DATA_DIR / "processed_chunks.jsonl")

# ── Embedding model settings — multilingual (Arabic + English) ─────────────────
EMBEDDING_MODEL = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
EMBEDDING_DEVICE = os.getenv("EMBEDDING_DEVICE", "cpu")

# ── Document processing settings ──────────────────────────────────────────────
CHUNK_SIZE = 800        
CHUNK_OVERLAP = 150     
ENABLE_OCR = True       
OCR_SPARSE_TEXT_THRESHOLD = 100
_MAX_LOADER_WORKERS = 4
# ── Retrieval settings ─────────────────────────────────────────────────────────
TOP_K_RESULTS = 4
SIMILARITY_THRESHOLD = 0.45
_ADD_BATCH_SIZE = 200

# ── LLM settings — Groq API ───────────────────────────────────────────────────
USE_GROQ = True
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
GROQ_MODEL = "llama-3.3-70b-versatile"

_default_ollama = (
    "http://host.docker.internal:11434"
    if os.path.exists("/.dockerenv")
    else "http://localhost:11434"
)
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", _default_ollama)

# ── OCR settings ───────────────────────────────────────────────────────────────
TESSERACT_CMD = os.getenv(
    "TESSERACT_PATH",
    r"C:\Program Files\Tesseract-OCR\tesseract.exe"
    if os.name == "nt"
    else "/usr/bin/tesseract",
)

SUPPORTED_EXTENSIONS = [".pdf", ".docx", ".pptx", ".txt", ".png", ".jpg", ".jpeg"]