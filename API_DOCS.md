# API Documentation

> **Version**: 1.1  
> **Last Updated**: April 2026

This document outlines all API endpoints for the Graduation Project.

---

## Table of Contents

1. [Base URL](#base-url)
2. [Authentication](#authentication)
3. [Admin API](#admin-api)
4. [Student API](#student-api)
5. [Professor API](#professor-api)
6. [Teaching Assistant API](#teaching-assistant-api)

---

## Base URL

| Environment | URL |
|-------------|-----|
| Development | `http://127.0.0.1:8000` |
| Production | `https://graduation-project-production-be44.up.railway.app` |

---

## Authentication

All protected endpoints require a JWT token in the header:
```
Authorization: Bearer <access_token>
```

### Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/token/` | Login to obtain access and refresh tokens |
| POST | `/api/token/refresh/` | Refresh expired access token |
| POST | `/api/token/blacklist/` | Logout (invalidate refresh token) |

---

### 1. Login (Obtain Token Pair)

| Property | Value |
|----------|-------|
| **Endpoint** | `/api/token/` |
| **Method** | `POST` |
| **Content-Type** | `application/json` |

#### Request Body

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `email` | string | Yes | User's email address |
| `password` | string | Yes | User's password |

```json
{
    "email": "student@example.com",
    "password": "TestPassword123"
}
```

#### Response (200 OK)

```json
{
    "refresh": "eyJ0eXAiOiJK...",
    "access": "eyJ0eXAiOiJK..."
}
```

---

### 2. Refresh Token

| Property | Value |
|----------|-------|
| **Endpoint** | `/api/token/refresh/` |
| **Method** | `POST` |
| **Content-Type** | `application/json` |

> **Important**: With token rotation enabled, the refresh endpoint returns BOTH a new access token AND a new refresh token. The frontend MUST update the stored refresh token with the new one from the response.

#### Request Body

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `refresh` | string | Yes | The valid refresh token |

```json
{
    "refresh": "eyJ0eXAiOiJK..."
}
```

#### Response (200 OK)

```json
{
    "access": "eyJ0eXAiOiJK...",
    "refresh": "eyJ0eXAiOiJK..."
}
```

---

### 3. Logout (Blacklist Token)

| Property | Value |
|----------|-------|
| **Endpoint** | `/api/token/blacklist/` |
| **Method** | `POST` |
| **Content-Type** | `application/json` |

#### Request Body

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `refresh` | string | Yes | The refresh token to blacklist |

```json
{
    "refresh": "eyJ0eXAiOiJK..."
}
```

#### Response (200 OK)

Returns success status (empty body).

---

## Notes for Frontend Developers

1. **Authorization Header**: For any protected endpoint, include:
   ```
   Authorization: Bearer <access_token>
   ```

2. **Token Expiry**:
   - Access Token: 60 minutes
   - Refresh Token: 1 day (renewed with each refresh call)

3. **Token Rotation**: Refresh tokens are rotated. Each time you call refresh:
   - You receive a NEW access token AND a new refresh token
   - The old refresh token is automatically blacklisted
   - **You MUST save the new refresh token** - if you don't, you'll have to login again after 1 day

---

# Admin API

> **Base URL**: `/admin/`  
> **Permission Required**: `primary_role="ADMIN"`  
> **Authorization Header**: `Bearer <access_token>`

---

## 1. Dashboard

### Get Summary Statistics

| Property | Value |
|----------|-------|
| **Endpoint** | `/admin/dashboard/summary/` |
| **Method** | `GET` |

#### Response

```json
{
    "total_students": 150,
    "total_courses": 12,
    "total_doctors": 5,
    "total_tas": 8,
    "gender_distribution": {
        "male_percentage": 55.5,
        "female_percentage": 44.5
    },
    "students_per_department": {
        "Computer Science": 60,
        "Information Systems": 45,
        "Software Engineering": 40,
        "Unassigned": 5
    }
}
```

---

## 2. Courses Management

### List Courses

| Property | Value |
|----------|-------|
| **Endpoint** | `/admin/courses/` |
| **Method** | `GET` |

| Query Params | Type | Description |
|-------------|------|-------------|
| `search` | string | Search by name or code |
| `department` | int | Filter by department ID |

---

### Create Course

| Property | Value |
|----------|-------|
| **Endpoint** | `/admin/courses/` |
| **Method** | `POST` |

#### Request Body

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `code` | string | Yes | Course code (e.g., "CS101") |
| `name` | string | Yes | Course name |
| `credit_hours` | int | Yes | Credit hours (1-6) |
| `department` | int | Yes | Department ID |
| `description` | string | No | Course description |
| `prerequisites` | array | No | List of prerequisite course IDs |

```json
{
    "code": "CS101",
    "name": "Intro to CS",
    "credit_hours": 3,
    "department": 1,
    "description": "Introduction to Computer Science",
    "prerequisites": []
}
```

---

### Update Course

| Property | Value |
|----------|-------|
| **Endpoint** | `/admin/courses/{id}/` |
| **Method** | `PATCH` |

---

### Delete Course

| Property | Value |
|----------|-------|
| **Endpoint** | `/admin/courses/{id}/` |
| **Method** | `DELETE` |

---

## 2.1 Course Offerings

### List Course Offerings

| Property | Value |
|----------|-------|
| **Endpoint** | `/admin/course-offerings/` |
| **Method** | `GET` |

| Query Params | Type | Description |
|-------------|------|-------------|
| `search` | string | Search by course name or code |
| `semester` | string | Filter by semester (e.g., "Fall") |
| `year` | int | Filter by year |
| `is_active` | bool | Filter by active status |

---

### Create Course Offering

| Property | Value |
|----------|-------|
| **Endpoint** | `/admin/course-offerings/` |
| **Method** | `POST` |

#### Request Body

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `course` | int | Yes | Course ID |
| `semester` | string | Yes | Semester (e.g., "Fall") |
| `year` | int | Yes | Year |
| `instructor` | int | Yes | Instructor user ID |
| `tas` | array | No | List of TA user IDs |
| `capacity` | int | No | Max capacity (default: 30) |
| `course_schedule` | array | No | Schedule array |
| `is_active` | bool | No | Is active (default: true) |

```json
{
    "course": 1,
    "semester": "Fall",
    "year": 2024,
    "instructor": 5,
    "tas": [2, 3],
    "capacity": 30,
    "course_schedule": [{"day": "Monday", "time": "10:00-11:30"}],
    "is_active": true
}
```

---

### Update Course Offering

| Property | Value |
|----------|-------|
| **Endpoint** | `/admin/course-offerings/{id}/` |
| **Method** | `PATCH` |

---

### Delete Course Offering

| Property | Value |
|----------|-------|
| **Endpoint** | `/admin/course-offerings/{id}/` |
| **Method** | `DELETE` |

---

## 2.2 Enrollments

### List Enrollments

| Property | Value |
|----------|-------|
| **Endpoint** | `/admin/enrollments/` |
| **Method** | `GET` |

| Query Params | Type | Description |
|-------------|------|-------------|
| `status` | string | Filter by status (ACTIVE, DROPPED, COMPLETED) |
| `course_offering` | int | Filter by course offering ID |
| `student` | int | Filter by student ID |

---

### Create Enrollment

| Property | Value |
|----------|-------|
| **Endpoint** | `/admin/enrollments/` |
| **Method** | `POST` |

#### Request Body

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `student` | int | Yes | Student user ID |
| `course_offering` | int | Yes | Course offering ID |
| `status` | string | Yes | Status (ACTIVE, DROPPED, COMPLETED) |
| `grade` | decimal | No | Grade (0-100) |

```json
{
    "student": 10,
    "course_offering": 1,
    "status": "ACTIVE",
    "grade": null
}
```

---

### Update Enrollment

| Property | Value |
|----------|-------|
| **Endpoint** | `/admin/enrollments/{id}/` |
| **Method** | `PATCH` |

#### Request Body

| Field | Type | Description |
|-------|------|-------------|
| `status` | string | Status (ACTIVE, DROPPED, COMPLETED) |
| `grade` | decimal | Grade (0-100) |

```json
{
    "status": "COMPLETED",
    "grade": 95.50
}
```

---

### Delete Enrollment

| Property | Value |
|----------|-------|
| **Endpoint** | `/admin/enrollments/{id}/` |
| **Method** | `DELETE` |

---

## 2.3 Department Management

### List Departments

| Property | Value |
|----------|-------|
| **Endpoint** | `/admin/departments/` |
| **Method** | `GET` |

| Query Params | Type | Description |
|-------------|------|-------------|
| `search` | string | Search by name or code |

---

### Create Department

| Property | Value |
|----------|-------|
| **Endpoint** | `/admin/departments/` |
| **Method** | `POST` |

#### Request Body

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `name` | string | Yes | Department name |
| `name_ar` | string | No | Arabic name |
| `code` | string | Yes | Department code |
| `head_of_department` | int | No | Professor user ID |

```json
{
    "name": "Computer Science",
    "name_ar": "علوم الحاسب",
    "code": "CS",
    "head_of_department": 5
}
```

> **Note**: `head_of_department` must be a professor.

---

### Update Department

| Property | Value |
|----------|-------|
| **Endpoint** | `/admin/departments/{id}/` |
| **Method** | `PATCH` |

---

### Delete Department

| Property | Value |
|----------|-------|
| **Endpoint** | `/admin/departments/{id}/` |
| **Method** | `DELETE` |

---

## 3. User Management

### List Users

| Property | Value |
|----------|-------|
| **Endpoint** | `/admin/users/` |
| **Method** | `GET` |

| Query Params | Type | Description |
|-------------|------|-------------|
| `role` | string | Filter by role (STUDENT, TA, PROFESSOR) |

---

### Create Instructor

| Property | Value |
|----------|-------|
| **Endpoint** | `/admin/users/instructors/` |
| **Method** | `POST` |

#### Request Body

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `username` | string | Yes | Username |
| `email` | string | Yes | Email address |
| `password` | string | Yes | Password |
| `full_name` | string | Yes | Full name |
| `department` | int | Yes | Department ID |
| `primary_role` | string | Yes | User Role |

---

### Create Teaching Assistant

| Property | Value |
|----------|-------|
| **Endpoint** | `/admin/users/tas/` |
| **Method** | `POST` |

#### Request Body

Same as instructor.

---

## 4. Announcements

### List Announcements

| Property | Value |
|----------|-------|
| **Endpoint** | `/admin/announcements/` |
| **Method** | `GET` |

---

### Create Announcement

| Property | Value |
|----------|-------|
| **Endpoint** | `/admin/announcements/` |
| **Method** | `POST` |

#### Request Body

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `title` | string | Yes | Announcement title |
| `content` | string | Yes | Announcement content |
| `is_global` | bool | Yes | Is global announcement |
| `is_TODO` | bool | No | Create todo items for students |
| `expires_at` | datetime | No | Expiration date |

```json
{
    "title": "Exam Schedule",
    "content": "Finals start next week.",
    "is_global": true,
    "is_TODO": true,
    "expires_at": "2024-06-01T00:00:00Z"
}
```

> **Note**: Setting `is_TODO=true` will automatically create `TodoItem`s for relevant students.

---

## 5. Upload Center (Materials)

### Upload Material

| Property | Value |
|----------|-------|
| **Endpoint** | `/admin/materials/upload/` |
| **Method** | `POST` |

#### Request Body

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `title` | string | Yes | Material title |
| `file_content` | string | Yes | The file |
| `material_type` | string | Yes | Type (LECTURE, SECTION, ASSIGNMENT_DESC, OTHER) |
| `file_type` | string | Yes | File type (pdf, pptx, docx, mp4, etc.) |

```json
{
    "title": "Handbook",
    "file_url": "https://...",
    "material_type": "OTHER",
    "file_type": "pdf"
}
```

---

## 6. Chat Monitoring

### List Conversations

| Property | Value |
|----------|-------|
| **Endpoint** | `/admin/chat/` |
| **Method** | `GET` |

---

### Get Conversation Messages

| Property | Value |
|----------|-------|
| **Endpoint** | `/admin/chat/messages/` |
| **Method** | `GET` |

| Query Params | Type | Description |
|-------------|------|-------------|
| `conversation_id` | int | Required - Conversation ID |

---

## 7. Notifications

### List Notifications

| Property | Value |
|----------|-------|
| **Endpoint** | `/admin/notifications/` |
| **Method** | `GET` |

---

## 8. Admin Profile

### Get Admin Profile

| Property | Value |
|----------|-------|
| **Endpoint** | `/admin/profile/` |
| **Method** | `GET` |

Returns admin profile info with system-wide statistics.

#### Response

```json
{
    "full_name": "Admin User",
    "email": "admin@example.com",
    "department": null,
    "profile_picture_url": null,
    "total_students": 150,
    "total_instructors": 5,
    "total_courses": 12,
    "total_tas": 8
}
```

---

### Update Admin Profile

| Property | Value |
|----------|-------|
| **Endpoint** | `/admin/profile/` |
| **Method** | `PATCH` |

#### Request Body

| Field | Type | Description |
|-------|------|-------------|
| `full_name` | string | Full name |
| `profile_picture_url` | string | Profile picture URL |

```json
{
    "full_name": "John Admin",
    "profile_picture_url": "https://..."
}
```

---

# Student API

> **Base URL**: `/api/student/`  
> **Permission Required**: `primary_role="STUDENT"`  
> **Authorization Header**: `Bearer <access_token>`

---

## 1. Dashboard

### Get Dashboard Data

| Property | Value |
|----------|-------|
| **Endpoint** | `/api/student/dashboard/` |
| **Method** | `GET` |

Returns aggregated data including profile summary, announcements, and course progress.

#### Response

```json
{
    "profile": {
        "full_name": "Shahd Shaban",
        "student_id": "20220236",
        "department": 1,
        "current_gpa": "3.80",
        "current_streak": 54,
        "profile_picture_url": null,
        "enrolled_hours": 18,
        "daily_streak_mock": {
            "Mon": true,
            "Tue": true,
            "Wed": false,
            "Thu": true,
            "Fri": false,
            "Sat": false,
            "Sun": false
        }
    },
    "portal_announcements": [
        {
            "id": 1,
            "title": "Maintenance",
            "content": "Portal down on Friday...",
            "author_name": "Admin",
            "created_at": "2024-05-01T10:00:00Z",
            "is_TODO": false,
            "time_since": "2 hours"
        }
    ],
    "course_announcements": [
        {
            "id": 2,
            "title": "Lecture Uploaded",
            "content": "Week 5 lecture is up.",
            "author_name": "Dr. Salwa",
            "created_at": "2024-05-01T12:00:00Z",
            "is_TODO": true,
            "time_since": "1 hour"
        }
    ],
    "courses_progress": [
        {
            "id": 101,
            "course_name": "Machine Learning",
            "course_code": "CS301",
            "progress": 65
        }
    ],
    "completed_courses_count": 17,
    "in_progress_courses_count": 6
}
```

---

## 2. Courses

### List Enrolled Courses

| Property | Value |
|----------|-------|
| **Endpoint** | `/api/student/courses/` |
| **Method** | `GET` |

Returns a list of active courses for the current student.

#### Response

```json
[
    {
        "id": 5,
        "course_name": "Machine Learning",
        "course_code": "CS301",
        "instructor_name": "Dr. Salwa Osman",
        "schedule": [{"day": "Tuesday", "time": "10:00-12:00"}],
        "progress": 45
    }
]
```

---

### Enroll in a Course

| Property | Value |
|----------|-------|
| **Endpoint** | `/api/student/courses/` |
| **Method** | `POST` |

#### Request Body

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `course_offering_id` | int | Yes | Course offering ID to enroll in |

```json
{
    "course_offering_id": 1
}
```

#### Response (201 Created)

```json
{
    "id": 10,
    "course_offering": 1,
    "course_name": "Machine Learning",
    "course_code": "CS301",
    "semester": "Fall",
    "year": 2024,
    "status": "ACTIVE",
    "grade": null,
    "enrollment_date": "2024-09-01T10:00:00Z"
}
```

#### Error Responses

| Status Code | Description |
|-------------|-------------|
| 400 | Already enrolled in this course |
| 400 | Course is full |
| 404 | Course offering not found |

---

### Get Course Details

| Property | Value |
|----------|-------|
| **Endpoint** | `/api/student/courses/{id}/` |
| **Method** | `GET` |

Returns detailed information about a specific course offering, including materials and assignments.

#### Response

```json
{
    "id": 5,
    "course_name": "Machine Learning",
    "course_code": "CS301",
    "instructor_name": "Dr. Salwa Osman",
    "materials": [
        {
            "id": 10,
            "title": "Lecture 1",
            "description": "Intro to ML",
            "material_type": "LECTURE",
            "file_download_url": "http://localhost:8000/api/student/materials/10/download/",
            "is_visible_to_students": true
        }
    ],
    "assignments": [
        {
            "id": 3,
            "title": "Assignment 1",
            "description": "Linear Regression",
            "due_date": "2024-11-23T23:59:00Z",
            "total_points": "10.00",
            "status": "Pending"
        }
    ]
}
```

---

## 3. Enrollments

### List All Enrollments

| Property | Value |
|----------|-------|
| **Endpoint** | `/api/student/enrollments/` |
| **Method** | `GET` |

| Query Params | Type | Description |
|-------------|------|-------------|
| `status` | string | Filter by status (ACTIVE, DROPPED, COMPLETED) |

#### Response

```json
[
    {
        "id": 5,
        "course_offering": 1,
        "course_name": "Machine Learning",
        "course_code": "CS301",
        "semester": "Fall",
        "year": 2024,
        "status": "ACTIVE",
        "grade": null,
        "enrollment_date": "2024-09-01T10:00:00Z"
    }
]
```

---

### Drop a Course

| Property | Value |
|----------|-------|
| **Endpoint** | `/api/student/enrollments/{id}/` |
| **Method** | `DELETE` |

Drops the enrollment (sets status to DROPPED).

---

## 4. Assignments & Submissions

### List Submissions

| Property | Value |
|----------|-------|
| **Endpoint** | `/api/student/submissions/` |
| **Method** | `GET` |

Returns all submissions for the current student.

#### Response

```json
[
    {
        "id": 1,
        "assignment": 3,
        "assignment_title": "Assignment 1",
        "course_name": "Machine Learning",
        "submission_date": "2024-11-20T10:00:00Z",
        "file_url": "https://...",
        "status": "SUBMITTED",
        "notes": ""
    }
]
```

---

### Submit Assignment

| Property | Value |
|----------|-------|
| **Endpoint** | `/api/student/submissions/` |
| **Method** | `POST` |

#### Request Body

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `assignment_id` | int | Yes | Assignment ID |
| `file_url` | string | No | URL to submitted file |

```json
{
    "assignment_id": 3,
    "file_url": "https://cloud.storage.com/submission.pdf"
}
```

#### Response (201 Created)

```json
{
    "id": 1,
    "assignment": 3,
    "assignment_title": "Assignment 1",
    "course_name": "Machine Learning",
    "submission_date": "2024-11-20T10:00:00Z",
    "file_url": "https://...",
    "status": "SUBMITTED",
    "notes": ""
}
```

#### Error Responses

| Status Code | Description |
|-------------|-------------|
| 400 | Missing assignment_id |
| 403 | Not enrolled in this course |
| 404 | Assignment not found |

---

## 5. Grades

### Get Student Grades

| Property | Value |
|----------|-------|
| **Endpoint** | `/api/student/grades/` |
| **Method** | `GET` |

Returns grades for completed and in-progress courses.

#### Response

```json
[
    {
        "id": 5,
        "course_name": "Machine Learning",
        "course_code": "CS301",
        "grade": "95.00",
        "status": "COMPLETED"
    },
    {
        "id": 3,
        "course_name": "Data Structures",
        "course_code": "CS201",
        "grade": "88.50",
        "status": "ACTIVE"
    }
]
```

---

## 6. To-Do List

### Get Pending Tasks

| Property | Value |
|----------|-------|
| **Endpoint** | `/api/student/todo/` |
| **Method** | `GET` |

Returns a combined list of manual to-do items and pending assignments.

#### Response

```json
[
    {
        "id": 1,
        "title": "Project Proposal",
        "description": "Due on Wednesday",
        "due_date": "2024-11-20T23:59:00Z",
        "is_completed": false,
        "priority": "HIGH",
        "course_name": "Operating System"
    }
]
```

---

### Create To-Do Item

| Property | Value |
|----------|-------|
| **Endpoint** | `/api/student/todo/` |
| **Method** | `POST` |

#### Request Body

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `title` | string | Yes | To-do title |
| `description` | string | No | Description |
| `priority` | string | No | Priority (LOW, MEDIUM, HIGH) |
| `due_date` | datetime | No | Due date |

```json
{
    "title": "Study for algorithm quiz",
    "description": "Chapter 1-5",
    "priority": "MEDIUM",
    "due_date": "2024-11-25T10:00:00Z"
}
```

---

## 7. Profile

### Get Student Profile

| Property | Value |
|----------|-------|
| **Endpoint** | `/api/student/profile/` |
| **Method** | `GET` |

Returns detailed profile info including current academic level and grades.

#### Response

```json
{
    "full_name": "Shahd Shaban",
    "student_id": "20220236",
    "department_name": "Computer Science",
    "current_gpa": "3.80",
    "student_current_level": 4,
    "current_streak": 54,
    "profile_picture_url": null,
    "enrolled_hours": 18,
    "daily_streak_mock": {
        "Mon": true,
        "Tue": true,
        "Wed": false,
        "Thu": true,
        "Fri": false,
        "Sat": false,
        "Sun": false
    },
    "grades": [
        {
            "course_name": "Machine Learning",
            "course_code": "CS301",
            "grade": "95.00",
            "status": "COMPLETED",
            "semester": "Fall",
            "year": 2024
        },
        {
            "course_name": "Data Structures",
            "course_code": "CS201",
            "grade": "88.50",
            "status": "COMPLETED",
            "semester": "Spring",
            "year": 2023
        }
    ]
}
```

---

### Update Student Profile

| Property | Value |
|----------|-------|
| **Endpoint** | `/api/student/profile/` |
| **Method** | `PATCH` |

#### Request Body

| Field | Type | Description |
|-------|------|-------------|
| `full_name` | string | Full name |
| `profile_picture_url` | string | Profile picture URL |

```json
{
    "full_name": "John Doe",
    "profile_picture_url": "https://..."
}
```

---

## 8. ChatBot

### Get Chat History

| Property | Value |
|----------|-------|
| **Endpoint** | `/api/student/chat/` |
| **Method** | `GET` |

Returns the message history of the most recent conversation.

#### Response

```json
[
    {
        "id": 1,
        "role": "USER",
        "content": "What is linear regression?",
        "timestamp": "2024-11-19T10:00:00Z"
    },
    {
        "id": 2,
        "role": "ASSISTANT",
        "content": "Linear regression is...",
        "timestamp": "2024-11-19T10:00:05Z"
    }
]
```

---

### Send Message

| Property | Value |
|----------|-------|
| **Endpoint** | `/api/student/chat/` |
| **Method** | `POST` |

#### Request Body

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `content` | string | Yes | Message content |
| `course_id` | int | No | Course offering ID (optional) |

```json
{
    "content": "Explain the last lecture.",
    "course_id": 5
}
```

#### Response

```json
{
    "user_message": {
        "id": 1,
        "role": "USER",
        "content": "Explain the last lecture.",
        "timestamp": "2024-11-19T10:00:00Z"
    },
    "ai_message": {
        "id": 2,
        "role": "ASSISTANT",
        "content": "This is a mock response to 'Explain the last lecture.'. I am a student assistant AI.",
        "timestamp": "2024-11-19T10:00:05Z"
    }
}
```

---

## 9. Notifications

### Get Notifications

| Property | Value |
|----------|-------|
| **Endpoint** | `/api/student/notifications/` |
| **Method** | `GET` |

Returns up to 50 recent notifications.

#### Response

```json
[
    {
        "id": 1,
        "title": "New Assignment",
        "message": "Assignment 2 has been posted",
        "notification_type": "ASSIGNMENT_DUE",
        "related_object_type": "Assignment",
        "related_object_id": 5,
        "is_read": false,
        "created_at": "2024-11-19T10:00:00Z"
    }
]
```

---

### Mark Notification as Read

| Property | Value |
|----------|-------|
| **Endpoint** | `/api/student/notifications/{id}/` |
| **Method** | `PATCH` |

#### Request Body

| Field | Type | Description |
|-------|------|-------------|
| `is_read` | boolean | Mark as read (true/false) |

```json
{
    "is_read": true
}
```

---

# Professor API

> **Base URL**: `/api/professor/`  
> **Permission Required**: `primary_role="PROFESSOR"`  
> **Authorization Header**: `Bearer <access_token>`

> **Note**: Professor API uses the shared **Instructor endpoints** listed below. Both `/api/professor/` and `/api/ta/` route to the same endpoint implementations.

All Professor endpoints are identical to the Instructor API endpoints. See [Instructor API](#instructor-api) for detailed documentation.

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/professor/dashboard/` | Dashboard summary |
| GET/POST | `/api/professor/courses/` | List/Create course offerings |
| GET/PATCH/DELETE | `/api/professor/courses/{id}/` | Course details |
| GET/POST | `/api/professor/materials/` | List/Upload materials |
| PATCH/DELETE | `/api/professor/materials/{id}/` | Manage material |
| GET | `/api/professor/materials/{id}/download/` | **Download material file** |
| GET/POST | `/api/professor/assignments/` | List/Create assignments |
| GET/PATCH/DELETE | `/api/professor/assignments/{id}/` | Manage assignment |
| GET | `/api/professor/submissions/` | List submissions |
| POST | `/api/professor/submissions/{id}/grade/` | Grade submission |
| GET | `/api/professor/students/` | List students |
| GET/POST | `/api/professor/announcements/` | List/Create announcements |
| PATCH/DELETE | `/api/professor/announcements/{id}/` | Manage announcement |
| GET | `/api/professor/chat/` | List conversations |
| GET | `/api/professor/chat/messages/` | Get messages |
| GET/PATCH | `/api/professor/notifications/` | List/Mark notifications |
| GET/PATCH | `/api/professor/profile/` | **Get/Update profile** |

---

# Teaching Assistant API

> **Base URL**: `/api/ta/`  
> **Permission Required**: `primary_role="TA"`  
> **Authorization Header**: `Bearer <access_token>`

> **Note**: TA API uses the shared **Instructor endpoints** listed below. Both `/api/professor/` and `/api/ta/` route to the same endpoint implementations.

All TA endpoints are identical to the Instructor API endpoints. See [Instructor API](#instructor-api) for detailed documentation.

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/ta/dashboard/` | Dashboard summary |
| GET/POST | `/api/ta/courses/` | List/Create course offerings |
| GET/PATCH/DELETE | `/api/ta/courses/{id}/` | Course details |
| GET/POST | `/api/ta/materials/` | List/Upload materials |
| PATCH/DELETE | `/api/ta/materials/{id}/` | Manage material |
| GET | `/api/ta/materials/{id}/download/` | **Download material file** |
| GET/POST | `/api/ta/assignments/` | List/Create assignments |
| GET/PATCH/DELETE | `/api/ta/assignments/{id}/` | Manage assignment |
| GET | `/api/ta/submissions/` | List submissions |
| POST | `/api/ta/submissions/{id}/grade/` | Grade submission |
| GET | `/api/ta/students/` | List students |
| GET/POST | `/api/ta/announcements/` | List/Create announcements |
| PATCH/DELETE | `/api/ta/announcements/{id}/` | Manage announcement |
| GET | `/api/ta/chat/` | List conversations |
| GET | `/api/ta/chat/messages/` | Get messages |
| GET/PATCH | `/api/ta/notifications/` | List/Mark notifications |
| GET/PATCH | `/api/ta/profile/` | **Get/Update profile** |

---

# Instructor API

> **Base URL**: `/api/instructor/`  
> **Permission Required**: `primary_role="PROFESSOR"` or `primary_role="TA"`  
> **Authorization Header**: `Bearer <access_token>`

> **Note**: Both Professor and TA use the same endpoints. The Instructor app contains all shared endpoints. Professor-specific or TA-specific endpoints can be added to their respective apps later.

---

## 1. Quick Reference

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/instructor/dashboard/` | Dashboard summary |
| GET/POST | `/api/instructor/courses/` | List/Create course offerings |
| GET/PATCH/DELETE | `/api/instructor/courses/{id}/` | Course details |
| GET/POST | `/api/instructor/materials/` | List/Upload materials |
| PATCH/DELETE | `/api/instructor/materials/{id}/` | Manage material |
| GET | `/api/instructor/materials/{id}/download/` | **Download material file** |
| GET/POST | `/api/instructor/assignments/` | List/Create assignments |
| GET/PATCH/DELETE | `/api/instructor/assignments/{id}/` | Manage assignment |
| GET | `/api/instructor/submissions/` | List submissions |
| POST | `/api/instructor/submissions/{id}/grade/` | Grade submission |
| GET | `/api/instructor/students/` | List students |
| GET/POST | `/api/instructor/announcements/` | List/Create announcements |
| PATCH/DELETE | `/api/instructor/announcements/{id}/` | Manage announcement |
| GET | `/api/instructor/chat/` | List conversations |
| GET | `/api/instructor/chat/messages/` | Get messages |
| GET/PATCH | `/api/instructor/notifications/` | List/Mark notifications |
| GET/PATCH | `/api/instructor/profile/` | **Get/Update profile** |

---

## 2. Dashboard

### Get Dashboard Data

| Property | Value |
|----------|-------|
| **Endpoint** | `/api/instructor/dashboard/` |
| **Method** | `GET` |

#### Response

```json
{
    "total_courses": 3,
    "total_students": 120,
    "pending_submissions": 15,
    "upcoming_assignments": 5,
    "recent_announcements": [
        {
            "id": 1,
            "title": "Exam Schedule",
            "content": "Finals next week...",
            "author_name": "Dr. Salwa",
            "course_name": "Machine Learning",
            "is_global": false,
            "is_TODO": false,
            "created_at": "2024-05-01T10:00:00Z"
        }
    ],
    "courses": [
        {
            "id": 1,
            "course_name": "Machine Learning",
            "course_code": "CS301",
            "semester": "Fall",
            "year": 2024,
            "instructor_name": "Dr. Salwa",
            "capacity": 30,
            "enrolled_count": 25,
            "is_active": true
        }
    ]
}
```

---

## 3. Course Offerings

### List Course Offerings

| Property | Value |
|----------|-------|
| **Endpoint** | `/api/instructor/courses/` |
| **Method** | `GET` |

Returns courses taught by the professor or assisted by the TA.

| Query Params | Type | Description |
|-------------|------|-------------|
| None | - | Returns all courses for the user |

#### Response

```json
[
    {
        "id": 1,
        "course_name": "Machine Learning",
        "course_code": "CS301",
        "semester": "Fall",
        "year": 2024,
        "instructor": 5,
        "instructor_name": "Dr. Salwa",
        "capacity": 30,
        "enrolled_count": 25,
        "course_schedule": [{"day": "Monday", "time": "10:00-11:30"}],
        "is_active": true
    }
]
```

---

### Create Course Offering

| Property | Value |
|----------|-------|
| **Endpoint** | `/api/instructor/courses/` |
| **Method** | `POST` |

#### Request Body

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `course` | int | Yes | Course ID |
| `semester` | string | Yes | Semester (e.g., "Fall") |
| `year` | int | Yes | Year |
| `instructor` | int | Yes | Instructor user ID |
| `tas` | array | No | List of TA user IDs |
| `capacity` | int | No | Max capacity (default: 30) |
| `course_schedule` | array | No | Schedule array |
| `is_active` | bool | No | Is active (default: true) |

```json
{
    "course": 1,
    "semester": "Fall",
    "year": 2024,
    "instructor": 5,
    "tas": [2, 3],
    "capacity": 30,
    "course_schedule": [{"day": "Monday", "time": "10:00-11:30"}],
    "is_active": true
}
```

---

### Get Course Details

| Property | Value |
|----------|-------|
| **Endpoint** | `/api/instructor/courses/{id}/` |
| **Method** | `GET` |

#### Response

```json
{
    "id": 1,
    "course_name": "Machine Learning",
    "course_code": "CS301",
    "semester": "Fall",
    "year": 2024,
    "instructor_name": "Dr. Salwa",
    "tas": [
        {"id": 2, "full_name": "John TA"},
        {"id": 3, "full_name": "Jane TA"}
    ],
    "capacity": 30,
    "enrolled_count": 25,
    "course_schedule": [{"day": "Monday", "time": "10:00-11:30"}],
    "is_active": true,
    "materials": [
        {
            "id": 1,
            "title": "Lecture 1",
            "description": "Intro to ML",
            "material_type": "LECTURE",
            "file_download_url": "http://localhost:8000/api/professor/materials/1/download/",
            "is_visible_to_students": true,
            "upload_date": "2024-09-01T10:00:00Z"
        }
    ],
    "assignments": [
        {
            "id": 1,
            "title": "Assignment 1",
            "due_date": "2024-11-23T23:59:00Z",
            "total_points": "10.00",
            "submission_count": 20
        }
    ],
    "enrolled_students": [
        {
            "enrollment_id": 1,
            "student_id": 10,
            "student_name": "Ahmed Ali",
            "student_email": "ahmed@example.com",
            "status": "ACTIVE",
            "grade": null
        }
    ]
}
```

---

### Update Course Offering

| Property | Value |
|----------|-------|
| **Endpoint** | `/api/instructor/courses/{id}/` |
| **Method** | `PATCH` |

#### Request Body

Same as Create. All fields optional.

---

### Delete Course Offering

| Property | Value |
|----------|-------|
| **Endpoint** | `/api/instructor/courses/{id}/` |
| **Method** | `DELETE` |

Soft delete - sets `is_active` to false.
## 4. Materials

### List Materials

| Property | Value |
|----------|-------|
| **Endpoint** | `/api/instructor/materials/` |
| **Method** | `GET` |
| **Auth** | Required |

> **Access Rules**: You will only see materials for courses where you are explicitly assigned as the Instructor or TA. Passing a `course_offering` ID for a course you do not manage will return only the courses you own or an empty array.

| Query Params | Type | Description |
|-------------|------|-------------|
| `course_offering` | int | Filter by course offering ID |

#### Response

```json
[
    {
        "id": 1,
        "course_offering": 1,
        "course_name": "Machine Learning",
        "title": "Lecture 1",
        "description": "Intro to ML",
        "material_type": "LECTURE",
        "file_download_url": "http://localhost:8000/api/professor/materials/1/download/",
        "file_type": "pdf",
        "file_size": 204800,
        "uploaded_by": 5,
        "uploaded_by_name": "Dr. Salwa",
        "upload_date": "2024-09-01T10:00:00Z",
        "is_visible_to_students": true,
        "order_index": 0
    }
]
```

---

### Upload Material (Single or Bulk)

| Property | Value |
|----------|-------|
| **Endpoint** | `/api/instructor/materials/` |
| **Method** | `POST` |
| **Content-Type** | `multipart/form-data` |
| **Auth** | Required |

> **Important**: This endpoint uploads the actual file binary. Do NOT use `application/json`.
> `file_type` and `file_size` are detected automatically — do not include them in the request.

#### Request Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `course_offering` | int | **Yes** | Course offering ID |
| `title` | string | **Yes** | Material title (if bulk, filenames will be appended to distinguish them) |
| `material_type` | string | **Yes** | `LECTURE` \| `SECTION` \| `ASSIGNMENT_DESC` \| `OTHER` |
| `file` | binary | **Yes** | The file(s) to upload. **Append multiple `file` fields to upload in bulk**. |
| `description` | string | No | Optional description |
| `is_visible_to_students` | bool | No | Default: `true` |
| `order_index` | int | No | Display order, default: `0` |

#### Allowed File Types & Size Limits

| Extension | Category | Max Size |
|-----------|----------|----------|
| `pdf`, `pptx`, `ppt`, `docx`, `doc`, `xlsx`, `xls` | Documents | 100 MB |
| `txt` | Plain text | 10 MB |
| `png`, `jpg`, `jpeg`, `gif` | Images | 20 MB |
| `zip` | Archives | 500 MB |
| `mp3` | Audio | 200 MB |
| `mp4` | Video | 2 GB |

#### Example (JavaScript `fetch` for Multiple Files)

```javascript
const formData = new FormData();
formData.append('course_offering', '1');
formData.append('title', 'Lecture 1');
formData.append('material_type', 'LECTURE');
formData.append('is_visible_to_students', 'true');

// Append multiple files to the same key
const files = fileInputElement.files;
for (let i = 0; i < files.length; i++) {
    formData.append('file', files[i]);
}

const response = await fetch('/api/instructor/materials/', {
    method: 'POST',
    headers: { 'Authorization': `Bearer ${accessToken}` },
    body: formData,
});
const materials = await response.json();
```

#### Response (201 Created)

**Note:** If you upload **one** file, the API returns a single JSON object. If you upload **multiple** files, it returns an array of objects.

```json
[
    {
        "id": 12,
        "course_offering": 1,
        "course_name": "Machine Learning",
        "title": "Lecture 1 - intro.pdf",
        "description": "Intro to ML",
        "material_type": "LECTURE",
        "file_download_url": "http://localhost:8000/api/instructor/materials/12/download/",
        "file_type": "pdf",
        "file_size": 204800,
        "uploaded_by": 5,
        "uploaded_by_name": "Dr. Salwa",
        "upload_date": "2026-04-12T00:00:00Z",
        "is_visible_to_students": true,
        "order_index": 0
    },
    {
        "id": 13,
        "title": "Lecture 1 - slides.pptx",
        "...": "..."
    }
]
```

#### Side Effects

- The files are saved on the server at `media/course_materials/<YYYY>/<MM>/<filename>`.
- If `is_visible_to_students` is `true`, a `MATERIAL_UPLOAD` **notification** is automatically created for every active enrolled student for *every* file uploaded.

#### Error Responses (Strict Atomic Validation)

If **any single file** in a bulk upload fails validation (e.g. one file is too large or unsupported), the **entire transaction is rolled back** to prevent partial/broken states.

| Status | Details |
|--------|---------|
| 400 | Single file validation error: `{"file": ["No file was submitted."]}` |
| 400 | Bulk error rollback: `{"bulk_errors": [{ "file": "malware.exe", "errors": {"file": ["Unsupported..."]} }]}` |
| 401 | Missing or invalid JWT token |

---

### Download Material File

| Property | Value |
|----------|-------|
| **Endpoint** | `/api/instructor/materials/{id}/download/` |
| **Method** | `GET` |
| **Auth** | Required |

Streams the stored file back to the client with the correct MIME type.
The file is served **inline** (browsers can display PDF/video without forcing a download).

#### Access Rules

| Role | Condition for access |
|------|---------------------|
| Professor | Must be the instructor of the course |
| TA | Must be assigned as a TA of the course |
| Student (via `/api/student/`) | Must be actively enrolled + `is_visible_to_students = true` |

#### Response (200 OK)

| Header | Example Value |
|--------|---------------|
| `Content-Type` | `application/pdf` |
| `Content-Disposition` | `inline; filename="lecture_1.pdf"` |

Body: raw file bytes (streamed in chunks, no buffering).

#### Error Responses

| Status | Description |
|--------|-------------|
| 401 | Missing or invalid JWT |
| 403 | User is not the instructor, TA, or an enrolled student |
| 404 | Material not found, or no file binary stored on this record |

---

### Update Material

| Property | Value |
|----------|-------|
| **Endpoint** | `/api/instructor/materials/{id}/` |
| **Method** | `PATCH` |
| **Content-Type** | `multipart/form-data` |
| **Auth** | Required |

> **Access Rules**: Only the Instructor or a TA assigned to this material's course can edit it. All other users (including students) receive **403 Forbidden**.

All fields are optional (partial update). Extension and size validation apply to any new file submitted.

---

### Delete Material

| Property | Value |
|----------|-------|
| **Endpoint** | `/api/instructor/materials/{id}/` |
| **Method** | `DELETE` |
| **Auth** | Required |

> **Access Rules**: Only the Instructor or a TA assigned to this material's course can delete it. All other users (including students) receive **403 Forbidden**.

Deletes the database record **and** securely removes the exact file binary from disk storage.

---

## 5. Assignments

### List Assignments

| Property | Value |
|----------|-------|
| **Endpoint** | `/api/instructor/assignments/` |
| **Method** | `GET` |

| Query Params | Type | Description |
|-------------|------|-------------|
| `course_offering` | int | Filter by course offering ID |

#### Response

```json
[
    {
        "id": 1,
        "course_offering": 1,
        "course_name": "Machine Learning",
        "title": "Assignment 1",
        "description": "Linear Regression",
        "due_date": "2024-11-23T23:59:00Z",
        "total_points": "10.00",
        "assignment_type": "REPORT",
        "submission_location": "ONLINE",
        "submission_count": 20,
        "created_at": "2024-09-01T10:00:00Z"
    }
]
```

---

### Create Assignment

| Property | Value |
|----------|-------|
| **Endpoint** | `/api/instructor/assignments/` |
| **Method** | `POST` |

#### Request Body

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `course_offering` | int | Yes | Course offering ID |
| `title` | string | Yes | Assignment title |
| `description` | string | No | Description |
| `description_material` | int | No | Related course material ID |
| `is_auto_correctable` | bool | No | Auto-correctable quiz |
| `questions` | array | No | Quiz questions (JSON) |
| `due_date` | datetime | Yes | Due date |
| `total_points` | decimal | Yes | Total points |
| `assignment_type` | string | Yes | QUIZ, EXAM, PROJECT, REPORT |
| `submission_location` | string | No | ONLINE, IN_UNIVERSITY |

```json
{
    "course_offering": 1,
    "title": "Assignment 1",
    "description": "Linear Regression",
    "due_date": "2024-11-23T23:59:00Z",
    "total_points": "10.00",
    "assignment_type": "REPORT",
    "submission_location": "ONLINE"
}
```

---

### Get Assignment Details

| Property | Value |
|----------|-------|
| **Endpoint** | `/api/instructor/assignments/{id}/` |
| **Method** | `GET` |

Returns assignment details including all submissions.

#### Response

```json
{
    "id": 1,
    "course_offering": 1,
    "course_name": "Machine Learning",
    "title": "Assignment 1",
    "description": "Linear Regression",
    "due_date": "2024-11-23T23:59:00Z",
    "total_points": "10.00",
    "assignment_type": "REPORT",
    "submission_location": "ONLINE",
    "created_by": 5,
    "created_at": "2024-09-01T10:00:00Z",
    "submissions": [
        {
            "id": 1,
            "student": 10,
            "student_name": "Ahmed Ali",
            "student_email": "ahmed@example.com",
            "submission_date": "2024-11-20T10:00:00Z",
            "file_url": "https://...",
            "status": "SUBMITTED",
            "grade": null,
            "notes": ""
        }
    ]
}
```

---

### Update Assignment

| Property | Value |
|----------|-------|
| **Endpoint** | `/api/instructor/assignments/{id}/` |
| **Method** | `PATCH` |

---

### Delete Assignment

| Property | Value |
|----------|-------|
| **Endpoint** | `/api/instructor/assignments/{id}/` |
| **Method** | `DELETE` |

---

## 6. Submissions

### List Submissions

| Property | Value |
|----------|-------|
| **Endpoint** | `/api/instructor/submissions/` |
| **Method** | `GET` |

| Query Params | Type | Description |
|-------------|------|-------------|
| `assignment_id` | int | Filter by assignment ID |
| `course_offering` | int | Filter by course offering ID |

#### Response

```json
[
    {
        "id": 1,
        "assignment": 1,
        "assignment_title": "Assignment 1",
        "course_name": "Machine Learning",
        "student": 10,
        "student_name": "Ahmed Ali",
        "student_email": "ahmed@example.com",
        "submission_date": "2024-11-20T10:00:00Z",
        "file_url": "https://...",
        "status": "SUBMITTED",
        "grade": null,
        "notes": ""
    }
]
```

---

### Grade Submission

| Property | Value |
|----------|-------|
| **Endpoint** | `/api/instructor/submissions/{id}/grade/` |
| **Method** | `POST` |

#### Request Body

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `grade` | decimal | Yes | Grade (0-100) |
| `notes` | string | No | Feedback notes |

```json
{
    "grade": "95.50",
    "notes": "Excellent work!"
}
```

#### Response

```json
{
    "id": 1,
    "assignment": 1,
    "assignment_title": "Assignment 1",
    "course_name": "Machine Learning",
    "student": 10,
    "student_name": "Ahmed Ali",
    "student_email": "ahmed@example.com",
    "submission_date": "2024-11-20T10:00:00Z",
    "file_url": "https://...",
    "status": "GRADED",
    "grade": "95.50",
    "notes": "Excellent work!"
}
```

---

## 7. Students

### List Students

| Property | Value |
|----------|-------|
| **Endpoint** | `/api/instructor/students/` |
| **Method** | `GET` |

| Query Params | Type | Description |
|-------------|------|-------------|
| `course_offering` | int | Filter by course offering ID |

#### Response

```json
[
    {
        "id": 10,
        "email": "ahmed@example.com",
        "full_name": "Ahmed Ali",
        "student_id": "20220001",
        "department": 1,
        "current_gpa": "3.50",
        "enrolled_courses": [
            {
                "enrollment_id": 1,
                "course_id": 1,
                "course_name": "Machine Learning",
                "course_code": "CS301",
                "semester": "Fall",
                "year": 2024,
                "grade": null
            }
        ]
    }
]
```

---

## 8. Announcements

### List Announcements

| Property | Value |
|----------|-------|
| **Endpoint** | `/api/instructor/announcements/` |
| **Method** | `GET` |

| Query Params | Type | Description |
|-------------|------|-------------|
| `course_offering` | int | Filter by course offering ID |

---

### Create Announcement

| Property | Value |
|----------|-------|
| **Endpoint** | `/api/instructor/announcements/` |
| **Method** | `POST` |

#### Request Body

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `title` | string | Yes | Announcement title |
| `content` | string | Yes | Announcement content |
| `course_offering` | int | No | Course offering ID (null for global) |
| `is_global` | bool | Yes | Is global announcement |
| `is_TODO` | bool | No | Create todo items for students |
| `expires_at` | datetime | No | Expiration date |

```json
{
    "title": "Exam Schedule",
    "content": "Finals will be held next week.",
    "course_offering": 1,
    "is_global": false,
    "is_TODO": false,
    "expires_at": "2024-12-01T00:00:00Z"
}
```

---

### Update Announcement

| Property | Value |
|----------|-------|
| **Endpoint** | `/api/instructor/announcements/{id}/` |
| **Method** | `PATCH` |

---

### Delete Announcement

| Property | Value |
|----------|-------|
| **Endpoint** | `/api/instructor/announcements/{id}/` |
| **Method** | `DELETE` |

---

## 9. Chat

### List Conversations

| Property | Value |
|----------|-------|
| **Endpoint** | `/api/instructor/chat/` |
| **Method** | `GET` |

Returns all chat conversations for courses taught by the instructor/TA.

#### Response

```json
[
    {
        "id": 1,
        "student": 10,
        "student_name": "Ahmed Ali",
        "course_offering": 1,
        "course_name": "Machine Learning",
        "title": "Help with assignment",
        "created_at": "2024-11-01T10:00:00Z",
        "updated_at": "2024-11-19T10:00:00Z",
        "is_archived": false,
        "last_message": {
            "role": "ASSISTANT",
            "content": "Here's the explanation...",
            "timestamp": "2024-11-19T10:00:00Z"
        },
        "unread_count": 0
    }
]
```

---

### Get Messages

| Property | Value |
|----------|-------|
| **Endpoint** | `/api/instructor/chat/messages/` |
| **Method** | `GET` |

| Query Params | Type | Description |
|-------------|------|-------------|
| `conversation_id` | int | Required - Conversation ID |

#### Response

```json
[
    {
        "id": 1,
        "conversation": 1,
        "role": "USER",
        "content": "What is linear regression?",
        "sources_used": [],
        "was_from_rag": false,
        "timestamp": "2024-11-19T10:00:00Z",
        "tokens_used": 50
    },
    {
        "id": 2,
        "conversation": 1,
        "role": "ASSISTANT",
        "content": "Linear regression is...",
        "sources_used": [1, 2],
        "was_from_rag": true,
        "timestamp": "2024-11-19T10:00:05Z",
        "tokens_used": 150
    }
]
```

---

## 10. Notifications

### Get Notifications

| Property | Value |
|----------|-------|
| **Endpoint** | `/api/instructor/notifications/` |
| **Method** | `GET` |

---

### Mark Notification as Read

| Property | Value |
|----------|-------|
| **Endpoint** | `/api/instructor/notifications/{id}/` |
| **Method** | `PATCH` |

#### Request Body

| Field | Type | Description |
|-------|------|-------------|
| `is_read` | boolean | Mark as read (true/false) |

---

## 11. Profile

### Get Instructor Profile

| Property | Value |
|----------|-------|
| **Endpoint** | `/api/instructor/profile/` |
| **Method** | `GET` |

Returns instructor profile info with teaching-related statistics.

#### Response

```json
{
    "full_name": "Dr. Salwa Osman",
    "email": "salwa@example.com",
    "department": 1,
    "profile_picture_url": null,
    "total_courses": 3,
    "total_students": 120,
    "upcoming_assignments": 5
}
```

---

### Update Instructor Profile

| Property | Value |
|----------|-------|
| **Endpoint** | `/api/instructor/profile/` |
| **Method** | `PATCH` |

#### Request Body

| Field | Type | Description |
|-------|------|-------------|
| `full_name` | string | Full name |
| `profile_picture_url` | string | Profile picture URL |

```json
{
    "full_name": "Dr. Salwa Osman",
    "profile_picture_url": "https://..."
}
```

---

## Enum Values

### User Role
- `STUDENT`
- `TA`
- `PROFESSOR`
- `ADMIN`

### Enrollment Status
- `ACTIVE`
- `DROPPED`
- `COMPLETED`

### Submission Status
- `PENDING`
- `SUBMITTED`
- `GRADED`

### Priority
- `LOW`
- `MEDIUM`
- `HIGH`

### Notification Type
- `ANNOUNCEMENT`
- `MATERIAL_UPLOAD`
- `ASSIGNMENT_DUE`
- `GRADE_POSTED`
- `GENERAL`

### Material Type
- `LECTURE`
- `SECTION`
- `ASSIGNMENT_DESC`
- `OTHER`
