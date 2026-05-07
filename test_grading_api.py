"""
Integration Test Script for Rubric-Driven Auto Revision Engine
==============================================================

This script tests the full flow of the grading engine by hitting the API endpoints.
It assumes the Django server is running at http://localhost:8000.

Usage:
    1. Start your server: python manage.py runserver
    2. Run this script: python test_grading_api.py

Requirements:
    - requests
"""

import requests
import json
import time

BASE_URL = "http://localhost:8000/api"

# ── CONFIGURATION ────────────────────────────────────────────────────────────
# Replace these with real credentials from your database
PROF_EMAIL = "prof@test.com"
STUDENT_EMAIL = "student@test.com"
PASSWORD = "password123"
# ─────────────────────────────────────────────────────────────────────────────

def get_tokens(email, password):
    url = f"http://localhost:8000/api/token/"
    resp = requests.post(url, json={"email": email, "password": password})
    if resp.status_code == 200:
        return resp.json()
    else:
        print(f"Failed to login {email}: {resp.text}")
        return None

def test_flow():
    print("--- Starting Grading Engine Integration Test ---")
    
    # 1. Login
    prof_tokens = get_tokens(PROF_EMAIL, PASSWORD)
    student_tokens = get_tokens(STUDENT_EMAIL, PASSWORD)
    
    if not prof_tokens or not student_tokens:
        print("Error: Could not obtain tokens. Make sure users exist and password is correct.")
        return

    prof_headers = {"Authorization": f"Bearer {prof_tokens['access']}"}
    student_headers = {"Authorization": f"Bearer {student_tokens['access']}"}

    # 2. Professor: Create Rubric Assignment
    # First, we need a Course Offering ID. For this test, we'll try to find one.
    courses_resp = requests.get(f"{BASE_URL}/professor/courses/", headers=prof_headers)
    if courses_resp.status_code != 200 or not courses_resp.json():
        print("Error: No course offerings found for the professor.")
        return
    
    offering_id = courses_resp.json()[0]['id']
    print(f"Using Course Offering ID: {offering_id}")

    assignment_data = {
        "course_offering": offering_id,
        "title": "AI Impact on Society (Rubric Test)",
        "description": "Discuss the socio-economic impacts of AI.",
        "due_date": "2025-01-01T00:00:00Z",
        "total_points": 20,
        "assignment_type": "REPORT",
        "grading_type": "SUBJECTIVE",
        "rubric": [
            {"criteria_name": "Critical Thinking", "max_points": 10, "description": "Depth of analysis."},
            {"criteria_name": "Structure", "max_points": 10, "description": "Logical flow and grammar."}
        ],
        "model_answer_text": "AI impacts society by automating jobs, improving healthcare diagnostics, and raising ethical concerns about bias and privacy."
    }

    print("Step 1: Professor creating rubric assignment...")
    asgn_resp = requests.post(f"{BASE_URL}/professor/rubric-assignments/", json=assignment_data, headers=prof_headers)
    if asgn_resp.status_code != 201:
        print(f"Failed to create assignment: {asgn_resp.text}")
        return
    
    assignment_id = asgn_resp.json()['id']
    print(f"Assignment created successfully! ID: {assignment_id}")

    # 3. Student: Submit Answer
    submission_data = {
        "assignment_id": assignment_id,
        "submitted_text": (
            "Artificial Intelligence is transforming our world. It helps doctors find diseases earlier "
            "but it also makes people worry about losing their jobs to robots. Privacy is another big "
            "issue because AI needs a lot of data to work well. Overall, it's a mix of good and bad."
        )
    }

    print("\nStep 2: Student submitting work (Auto-grading triggered)...")
    start_time = time.time()
    sub_resp = requests.post(f"{BASE_URL}/student/rubric-submit/", json=submission_data, headers=student_headers)
    duration = time.time() - start_time
    
    if sub_resp.status_code != 201:
        print(f"Failed to submit: {sub_resp.text}")
        return
    
    result_data = sub_resp.json()
    print(f"Submission successful! (AI grading took {duration:.2f}s)")
    
    # 4. Show Results
    submission = result_data['submission']
    grading = submission.get('grading_result')

    if grading:
        print("\n--- AI GRADING RESULTS ---")
        print(f"Total Score: {grading['total_score']} / {grading['max_score']} ({grading['percentage']:.1f}%)")
        print("\nCriteria Breakdown:")
        for crit in grading['criteria_breakdown']:
            print(f"- {crit['criteria_name']}: {crit['points_awarded']}/{crit['max_points']}")
            print(f"  Justification: {crit['justification']}")
        print(f"\nOverall Feedback: {grading['feedback_summary']}")
    else:
        print("\nWarning: No grading result found in response. Check server logs for AI errors.")
        if 'grading_error' in result_data:
            print(f"Grading Error: {result_data['grading_error']}")

    print("\n--- Test Completed ---")

if __name__ == "__main__":
    test_flow()
