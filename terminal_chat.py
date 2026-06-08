"""
EduEra Interactive Terminal Chat
================================
A direct way to chat with your AI Assistant from the terminal.
This script uses the real student001 account and database history.

Usage: python terminal_chat.py
"""
import os
import sys
import django
from pathlib import Path

# Fix Windows encoding for emojis and Arabic
sys.stdout.reconfigure(encoding='utf-8')

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'GraduationProject.settings')
django.setup()

from main.models import User, Enrollment, ChatMessage, ChatConversation
from ai_engine.ai_services import get_rag_pipeline

def start_chat():
    print("\n" + "="*80)
    print("🎓  EDUERA AI ASSISTANT - TERMINAL MODE")
    print("="*80)

    # 1. Identify User
    try:
        student = User.objects.get(username='student001')
        print(f"Logged in as: {student.full_name} (@{student.username})")
    except User.DoesNotExist:
        print("Error: student001 not found in database. Run create_test_student.py first.")
        return

    # 2. Get Authorized Courses
    enrolled_codes = list(
        Enrollment.objects.filter(
            student=student,
            status__in=[Enrollment.Status.ACTIVE, Enrollment.Status.COMPLETED]
        ).values_list('course_offering__course__code', flat=True)
    )
    print(f"Authorized Courses: {', '.join(enrolled_codes)}")
    print("Type 'exit' or 'quit' to stop.")
    print("-" * 80)

    # 3. Init Pipeline
    os.environ['EMBEDDING_DEVICE'] = 'cuda'
    rag = get_rag_pipeline()
    
    # We'll use a temporary memory list for this session's history
    chat_history = []

    while True:
        try:
            query = input("\n👤 You: ").strip()
            
            if query.lower() in ['exit', 'quit']:
                print("\n👋 Goodbye!")
                break
                
            if not query:
                continue

            print("🤖 AI is thinking...", end="\r")
            
            # Run Query
            result = rag.query(
                question=query,
                history=chat_history,
                user_courses=enrolled_codes
            )
            
            answer = result.get('answer', "I'm sorry, I encountered an error.")
            sources = result.get('sources', [])
            
            # Print Answer
            print(f"🤖 Assistant: {answer}")
            
            # Print Sources if any
            if sources:
                source_codes = {s.get('metadata', {}).get('course_code') for s in sources}
                print(f"📚 [Sources: {', '.join(filter(None, source_codes))}]")
            
            # Update local history for multi-turn context
            chat_history.append({"role": "user", "content": query})
            chat_history.append({"role": "assistant", "content": answer})
            
            # Optional: Trim history to last 10 messages
            if len(chat_history) > 10:
                chat_history = chat_history[-10:]

        except KeyboardInterrupt:
            print("\n👋 Goodbye!")
            break
        except Exception as e:
            print(f"\n❌ Error: {e}")

if __name__ == "__main__":
    start_chat()
