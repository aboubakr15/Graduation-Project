import os
import sys
import logging
from pathlib import Path

# Add the ai_engine directory to sys.path so that 'src' and 'config' 
# can be imported as they were in the standalone version.
AI_ENGINE_DIR = Path(__file__).resolve().parent
if str(AI_ENGINE_DIR) not in sys.path:
    sys.path.append(str(AI_ENGINE_DIR))

# Now we can import from src and config
try:
    from src.rag_pipeline import RAGPipeline
    from dotenv import load_dotenv
except ImportError as e:
    # Fallback if the above doesn't work for some reason
    logging.error(f"AI Engine Import Error: {e}")
    raise

# Load environment variables from ai_engine/.env
load_dotenv(AI_ENGINE_DIR / ".env")

logger = logging.getLogger(__name__)

class AIService:
    _instance = None

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            logger.info("Initializing AI RAG Pipeline Service (Lazy Loading)...")
            from src.rag_pipeline import RAGPipeline
            cls._instance = RAGPipeline()
        return cls._instance

def get_rag_pipeline():
    """Helper function to get the RAG pipeline instance lazily."""
    return AIService.get_instance()
