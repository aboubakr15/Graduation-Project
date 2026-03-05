# API Documentation

> **Version**: 1.0  
> **Last Updated**: March 2026

This document outlines all API endpoints for the Graduation Project.

---

## Table of Contents

1. [Base URL](#base-url)
2. [Authentication](#authentication)
3. [Admin API](#admin-api)
4. [Student API](#student-api)

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
| `file_url` | string | Yes | URL to the file |
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
            "file_url": "http://...",
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

Returns detailed profile info. Same structure as `dashboard.profile`.

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

## Status Codes Summary

| Code | Description |
|------|-------------|
| 200 | OK - Request succeeded |
| 201 | Created - Resource created successfully |
| 204 | No Content - Request succeeded with no content to return |
| 400 | Bad Request - Invalid input |
| 401 | Unauthorized - Invalid or missing token |
| 403 | Forbidden - Permission denied |
| 404 | Not Found - Resource not found |

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
