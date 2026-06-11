import os
import sys
sys.path.append('ai_engine')
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'GraduationProject.settings')
django.setup()
sys.stdout.reconfigure(encoding='utf-8')

from ai_engine.src.rag_pipeline import RAGPipeline
rag = RAGPipeline()

# Using EXACT formats from the real database!
user_courses = ["Machine Learning - AI 330", "AI 330", "AI", "Data Structure - CS 214", "CS 214", "CS"]

q = "what is machine learning?"
res = rag.query(
    question=q,
    history=[],
    selected_course=None,
    user_courses=user_courses,
    latest_blueprint=None
)

ans = res.get("answer")
has_warning = "Disclaimer:" in ans or "تنبيه:" in ans
print(f"HAS WARNING FOR ML: {has_warning}")
print(f"SOURCES FOR ML: {res.get('sources')}")

q = "what is big data?"
res = rag.query(
    question=q,
    history=[],
    selected_course=None,
    user_courses=user_courses,
    latest_blueprint=None
)

ans = res.get("answer")
has_warning = "Disclaimer:" in ans or "تنبيه:" in ans
print(f"HAS WARNING FOR BIG DATA: {has_warning}")
print(f"SOURCES FOR BIG DATA: {res.get('sources')}")
