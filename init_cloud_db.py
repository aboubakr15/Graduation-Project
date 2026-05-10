import os
from qdrant_client import QdrantClient
from qdrant_client.http import models
from dotenv import load_dotenv
from pathlib import Path

# Load credentials from your ai_engine/.env
env_path = Path("ai_engine/.env")
load_dotenv(dotenv_path=env_path)

def initialize_cloud_qdrant():
    url = os.getenv("QDRANT_URL")
    api_key = os.getenv("QDRANT_API_KEY")
    collection_name = "college_courses"

    if not url or not api_key:
        print("Error: QDRANT_URL or QDRANT_API_KEY not found in ai_engine/.env")
        return

    print(f"Connecting to: {url}")
    client = QdrantClient(url=url, api_key=api_key)

    # Create the collection with 384 dimensions (matching your MiniLM model)
    client.recreate_collection(
        collection_name=collection_name,
        vectors_config=models.VectorParams(size=384, distance=models.Distance.COSINE),
    )
    
    print(f"✅ Success! Collection '{collection_name}' created in the cloud.")

if __name__ == "__main__":
    initialize_cloud_qdrant()
