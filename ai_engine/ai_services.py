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

def query_college_instructions(question: str, history: list = None) -> str:
    """
    Queries the 'college_instructions' Qdrant collection and uses OpenRouter's API
    to answer administrative questions.
    """
    import requests
    import sqlite3
    import re
    from config.settings import DATA_DIR
    
    db_path = DATA_DIR / "college_instructions.sqlite"
    if not db_path.exists():
        return "The college instructions have not been uploaded yet. Please contact administration."

    # Get SQLite Schema
    try:
        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = cursor.fetchall()
        
        schema_info = []
        for table in tables:
            table_name = table[0]
            cursor.execute(f"PRAGMA table_info('{table_name}');")
            columns = cursor.fetchall()
            col_names = [col[1] for col in columns]
            schema_info.append(f"Table: {table_name} | Columns: {', '.join(col_names)}")
        schema_text = "\n".join(schema_info)
    except Exception as e:
        logger.error(f"Error reading SQLite schema: {e}")
        return "System error: Could not access the instructions database."

    sys_prompt = (
        "You are an AI assistant for college administration. You have access to an SQLite database containing extracted tables from the college instructions.\n"
        "DATABASE SCHEMA:\n"
        f"{schema_text}\n\n"
        "CRITICAL INSTRUCTION:\n"
        "The database contains ONLY English text. If the user asks a question in Arabic, you MUST FIRST translate their intent to English internally, and only use ENGLISH words in your SQL queries.\n\n"
        "INSTRUCTIONS:\n"
        "1. To query the database, output ONLY a valid SQL query wrapped in standard markdown like this:\n"
        "```sql\nSELECT * FROM courses LIMIT 5;\n```\n"
        "2. The system will execute the query and provide the results in the next message.\n"
        "3. To search for a course, translate the Arabic name to English and search using LIKE (e.g., `WHERE course_name LIKE '%Data Structure%'`) OR search using the Course Code (e.g., `WHERE course_code LIKE '%CS%' AND course_code LIKE '%214%'`).\n"
        "4. The Course Code is the ONLY reliable way to map prerequisites! When you find a prerequisite like '112', query `WHERE course_code LIKE '%112%'` to find the prerequisite course.\n"
        "5. You MUST recursively query the database until you find the full chain of prerequisites.\n"
        "6. When you have enough information to answer the user, just provide the final answer translated back into Arabic. Do NOT output any ```sql block when giving the final answer.\n"
        "7. If the database does not contain the answer after querying, reply in Arabic: عذراً، اللائحة المرفقة لا تحتوي على معلومات كافية للإجابة على هذا السؤال. يرجى التوجه إلى شؤون الطلاب للحصول على المساعدة.\n"
    )
    
    messages = [{"role": "system", "content": sys_prompt}]
    
    if history:
        for msg in history:
            messages.append({"role": "user" if msg["is_student"] else "assistant", "content": msg["message"]})
            
    messages.append({"role": "user", "content": question})
    
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        return "System configuration error: OpenRouter API key is missing."
        
    url = "https://openrouter.ai/api/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    
    max_iterations = 10
    for iteration in range(max_iterations):
        payload = {
            "model": "deepseek/deepseek-v4-flash",
            "messages": messages,
            "temperature": 0.1
        }
        
        try:
            response = requests.post(url, headers=headers, json=payload, timeout=30)
            response.raise_for_status()
            data = response.json()
            
            if "error" in data:
                raise Exception(f"OpenRouter API returned error: {data['error']}")
                
            choices = data.get("choices", [])
            if not choices:
                raise Exception(f"No choices in OpenRouter response: {data}")
                
            reply = choices[0].get("message", {}).get("content")
            if reply is None:
                reply = ""
                
            messages.append({"role": "assistant", "content": reply})
            
            if not str(reply).strip():
                messages.append({"role": "user", "content": "Your last response was empty. You must either run a SQL query wrapped in ```sql...``` or provide the final text answer."})
                continue
            
            # Check if it wants to run SQL
            sql_match = re.search(r"```sql\s*(.*?)\s*```", str(reply), re.DOTALL | re.IGNORECASE)
            if sql_match:
                sql_query = sql_match.group(1).strip()
                try:
                    cursor.execute(sql_query)
                    rows = cursor.fetchmany(20)  # Limit to 20 rows to avoid token limit
                    if not rows:
                        sql_result = "No results found."
                    else:
                        raw_result = str(rows)
                        # Strip all non-ASCII characters (including Arabic, weird symbols, and Unicode replacement characters).
                        # The backwards/mangled text and '' symbols cause the free LLM API to silently crash.
                        # We only need the English words and numbers (like Course Codes) to trace prerequisites!
                        sql_result = re.sub(r'[^\x00-\x7F]+', '', raw_result)
                except Exception as db_err:
                    sql_result = f"SQL Error: {db_err}"
                    
                messages.append({"role": "user", "content": f"Query Result:\n{sql_result}\n\nWhat is your next step? Output another ```sql query or provide the final Arabic answer."})
                continue
                
            # Check if it provided the final answer (no SQL block)
            if "```sql" not in str(reply).lower():
                conn.close()
                return str(reply).strip()
                
            # Force it to answer or query
            messages.append({"role": "user", "content": "You must either run a SQL query wrapped in ```sql...``` or provide the final text answer."})
            
        except Exception as e:
            logger.error(f"Error in Agent loop: {e}")
            if 'conn' in locals(): conn.close()
            return f"Sorry, I encountered an error while trying to process your request. {str(e)}"
            
    if 'conn' in locals(): conn.close()
    
    # Extract just the assistant's replies to show what it was trying to do
    debug_replies = []
    for msg in messages:
        if msg["role"] == "assistant":
            debug_replies.append(msg["content"])
            
    debug_text = "\n\n".join(debug_replies[-3:]) if debug_replies else "No responses."
    return f"Agent iteration limit reached. The AI got stuck trying to resolve this. Here is what it tried last:\n{debug_text}"
