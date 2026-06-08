import os
from qdrant_client import QdrantClient
from qdrant_client.http import models
from dotenv import load_dotenv
from pathlib import Path

# Load credentials
load_dotenv(dotenv_path=Path("ai_engine/.env"))

def create_index():
    url = os.getenv("QDRANT_URL")
    api_key = os.getenv("QDRANT_API_KEY")
    client = QdrantClient(url=url, api_key=api_key)

    print("Creating payload index for course_code...")
    
    # We create it for both possible paths just to be safe
    for field in ["course_code", "metadata.course_code"]:
        try:
            client.create_payload_index(
                collection_name="college_courses",
                field_name=field,
                field_schema=models.PayloadSchemaType.KEYWORD,
            )
            print(f"✅ Index created for: {field}")
        except Exception as e:
            print(f"⚠️ Note for {field}: {e}")

if __name__ == "__main__":
    create_index()
