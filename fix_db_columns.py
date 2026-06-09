import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'GraduationProject.settings')
django.setup()

from django.db import connection

def drop_column_if_exists(table_name, column_name):
    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT COUNT(*) 
            FROM information_schema.columns 
            WHERE table_schema = DATABASE() 
            AND table_name = %s 
            AND column_name = %s
        """, [table_name, column_name])
        
        if cursor.fetchone()[0] > 0:
            print(f"Dropping column '{column_name}' from table '{table_name}'...")
            try:
                cursor.execute(f"ALTER TABLE {table_name} DROP COLUMN {column_name}")
                print(f"Successfully dropped {column_name}.")
            except Exception as e:
                print(f"Failed to drop {column_name}: {e}")
        else:
            print(f"Column '{column_name}' does not exist in '{table_name}'. Skipping.")

if __name__ == '__main__':
    print("Checking for partially applied migration columns...")
    drop_column_if_exists('assignments', 'grading_type')
    drop_column_if_exists('assignments', 'model_answer_text')
    drop_column_if_exists('assignments', 'rubric')
    drop_column_if_exists('assignments', 'test_cases')
    drop_column_if_exists('student_submissions', 'submitted_text')
    print("\nCleanup complete. You can now safely run: python manage.py migrate")
