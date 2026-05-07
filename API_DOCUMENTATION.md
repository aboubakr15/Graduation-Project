# Educational Copilot — AI API Documentation
> **Version**: 2.0  
> **Topic**: AI Services & Intelligent Automation  
> **Last Updated**: May 2026

This document focuses exclusively on the **AI-powered endpoints** within the platform, covering RAG-based chat, presentation generation, and the rubric-driven grading engine.

---

## Table of Contents

1. [AI Chat & Research Assistant (RAG)](#1-ai-chat--research-assistant-rag)
2. [AI Presentation Generator](#2-ai-presentation-generator)
3. [AI Rubric-Driven Grading (Student)](#3-ai-rubric-driven-grading-student)
4. [AI Rubric Management (Instructor)](#4-ai-rubric-management-instructor)
5. [Common AI Configuration](#5-common-ai-configuration)

---

## 1. AI Chat & Research Assistant (RAG)

The student's primary learning companion. It uses **Retrieval-Augmented Generation (RAG)** to answer questions based strictly on course materials (PDFs, PPTX, Transcripts).

### Ask AI Assistant
| Property | Value |
|----------|-------|
| **Endpoint** | `/api/student/chat/` |
| **Method** | `POST` |
| **Auth Required**| Yes (Student) |

#### Request Body
| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `content` | string | Yes | The user's question or instruction. |
| `course_id` | int | No | Specify a course context (Default: First active enrollment). |
| `conversation_id`| int | No | ID of an existing thread for context retention. |

```json
{
    "content": "Explain the concept of backpropagation using the lecture notes.",
    "course_id": 101
}
```

#### Response (200 OK)
```json
{
    "conversation_id": 45,
    "ai_message": {
        "content": "Backpropagation is the central mechanism by which neural networks learn...",
        "sources_used": [
            {"title": "Lecture 5: Deep Learning", "page": 12},
            {"title": "ML_Basics.pdf", "page": 4}
        ],
        "was_from_rag": true
    }
}
```

---

## 2. AI Presentation Generator

Integrated directly into the Chat Assistant. Users can trigger this using keywords like *"make a presentation"*, *"create slides"*, or *"PowerPoint"*.

### Flow & Interactive Logic
1. **Trigger**: User asks for a presentation in `/api/student/chat/`.
2. **Blueprint Phase**: AI generates a Markdown outline (Blueprint).
3. **Refinement**: User can give feedback ("Add more about X", "Remove slide 3").
4. **Final Generation**: Once approved, AI generates a `.pptx` file.

#### Response (with Presentation Path)
When a presentation is finalized, the chat response includes:
```json
{
    "answer": "I have generated the final presentation. You can find it here: presentations/gen_123.pptx",
    "presentation_path": "presentations/gen_123.pptx"
}
```

---

## 3. AI Rubric-Driven Grading (Student)

Allows students to submit text or code for immediate, structured evaluation against a TA-defined rubric.

### Submit for Auto-Grading
| Property | Value |
|----------|-------|
| **Endpoint** | `/api/student/rubric-submit/` |
| **Method** | `POST` |

#### Request Body
```json
{
    "assignment_id": 12,
    "submitted_text": "Insert assignment content here..."
}
```

#### Response (201 Created)
Returns the `grading_result` object nested in the submission.
```json
{
    "submission": {
        "id": 88,
        "status": "GRADED",
        "grading_result": {
            "total_score": 18.5,
            "max_score": 20.0,
            "percentage": 92.5,
            "criteria_breakdown": [
                {
                    "criteria_name": "Critical Analysis",
                    "points_awarded": 9.5,
                    "max_points": 10.0,
                    "justification": "Detailed analysis provided, but missed the final inference."
                }
            ],
            "feedback_summary": "Excellent work. Your structure is professional."
        }
    }
}
```

---

## 4. AI Rubric Management (Instructor)

Used by Professors/TAs to configure how the AI should grade.

### Create AI-Graded Assignment
| Property | Value |
|----------|-------|
| **Endpoint** | `/api/professor/rubric-assignments/` |
| **Method** | `POST` |

#### Request Body (Rubric Schema)
| Field | Description |
|-------|-------------|
| `grading_type`| `SUBJECTIVE` (Text/Essay) or `OBJECTIVE` (Code/Execution) |
| `rubric` | Array of `{criteria_name, max_points, description}` |
| `model_answer_text`| The ground truth the AI uses for comparison. |

```json
{
    "title": "Weekly Essay 1",
    "grading_type": "SUBJECTIVE",
    "rubric": [
        {"criteria_name": "Clarity", "max_points": 5, "description": "Writing flow"}
    ],
    "model_answer_text": "The ideal response should mention..."
}
```

### Trigger AI Re-grading
| Property | Value |
|----------|-------|
| **Endpoint** | `/api/professor/submissions/{id}/regrade/` |
| **Method** | `POST` |

Force the AI to re-evaluate a submission (e.g., after updating the rubric).

---

## 5. Common AI Configuration

### Model Details
* **Engine**: Llama 3.3 70B (Versatile) via Groq Cloud.
* **Temperature**: `0.1` (Low for consistent, objective results).
* **Max Tokens**: `2048` per evaluation.

### Prompt Security
* **Isolation**: User inputs are sanitized and wrapped in XML tags (`<student_submission>`) to prevent system instruction overrides (Prompt Injection).
* **Citations**: Source metadata is extracted via Vector Search (FAISS/ChromaDB) before being passed to the LLM.
