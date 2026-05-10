import os
import sys
import logging
from pathlib import Path

# Setup logging to see progress in the terminal
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Add the project directory to path
sys.path.append(str(Path(__file__).resolve().parent))
from ai_engine.ai_services import get_rag_pipeline

def sync_smart():
    print("🚀 Starting SMART Sync to Qdrant Cloud...")
    pipeline = get_rag_pipeline()
    
    # 1. Fetch what's already in the cloud
    print("🔍 Checking existing files in the cloud (this may take a minute)...")
    try:
        pipeline.vector_store_manager.load_vector_store()
        existing_sources = pipeline.vector_store_manager.get_all_sources()
        print(f"✅ Found {len(existing_sources)} files already in the cloud.")
    except Exception as e:
        print(f"⚠️ Could not fetch existing sources, will sync everything: {e}")
        existing_sources = set()

    root_path = Path("ai_engine/data/raw")
    courses = [d for d in root_path.iterdir() if d.is_dir()]
    total_courses = len(courses)

    for i, course_path in enumerate(courses, 1):
        if course_path.name.lower() in ['processed', 'presentation_images']:
            continue
            
        print(f"[{i}/{total_courses}] 📂 Checking Course: {course_path.name}...")
        
        # Look for files in this course folder
        course_files = list(course_path.rglob("*"))
        new_files = [f for f in course_files if f.is_file() and str(f.resolve()) not in existing_sources]
        
        if not new_files:
            print(f"  ⏭️ Skipping {course_path.name} (All files already synced)")
            continue

        print(f"  ⬆️ Uploading {len(new_files)} new files for {course_path.name}...")
        try:
            # We process only the course folder. 
            # Note: process_documents will handle individual file checks if we use it correctly.
            pipeline.add_documents(str(course_path), course_code=course_path.name)
            print(f"✅ Finished {course_path.name}\n")
        except Exception as e:
            print(f"❌ Error syncing {course_path.name}: {e}\n")

    print("⭐ SMART SYNC COMPLETE!")

if __name__ == "__main__":
    sync_smart()
