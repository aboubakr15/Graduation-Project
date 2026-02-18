# API Documentation

This document outlines the existing API endpoints for the Graduation Project. currently, the API exposes endpoints for Authentication (JWT).

## Base URL

- Development: `http://127.0.0.1:8000`
- Production: 'https://graduation-project-production-be44.up.railway.app'

## Authentication

The project uses **JSON Web Tokens (JWT)** for authentication.

### 1. Login (Obtain Token Pair)

Authenticate a user using their email and password to obtain an access and refresh token.

- **Endpoint**: `/api/token/`
- **Method**: `POST`
- **Content-Type**: `application/json`

#### Request Body

| Field      | Type   | Required | Description |
|------------|--------|----------|-------------|
| `email` | string | Yes      | User's email address |
| `password` | string | Yes      | User's password |

**Example:**
```json
{
    "email": "student@example.com",
    "password": "TestPassword123"
}
```

#### Response (200 OK)

Returns an access token and a refresh token.

```json
{
    "refresh": "eyJ0eXAiOiJK...",
    "access": "eyJ0eXAiOiJK..."
}
```

---

### 2. Refresh Token

Obtain a new access token and a new refresh token using a valid refresh token. This should be used when the access token expires.

**Important**: With token rotation enabled, the refresh endpoint returns BOTH a new access token AND a new refresh token. The frontend MUST update the stored refresh token with the new one from the response.

- **Endpoint**: `/api/token/refresh/`
- **Method**: `POST`
- **Content-Type**: `application/json`

#### Request Body

| Field     | Type   | Required | Description |
|-----------|--------|----------|-------------|
| `refresh` | string | Yes      | The valid refresh token (from login or previous refresh) |

**Example:**
```json
{
    "refresh": "eyJ0eXAiOiJK..."
}
```

#### Response (200 OK)

Returns a new access token and a new refresh token. **Both tokens must be saved by the frontend**.

```json
{
    "access": "eyJ0eXAiOiJK...",
    "refresh": "eyJ0eXAiOiJK..."
}
```

---

### 3. Logout (Blacklist Token)

Invalidate a refresh token effectively logging the user out.

- **Endpoint**: `/api/token/blacklist/`
- **Method**: `POST`
- **Content-Type**: `application/json`

#### Request Body

| Field     | Type   | Required | Description |
|-----------|--------|----------|-------------|
| `refresh` | string | Yes      | The refresh token to blacklist |

**Example:**
```json
{
    "refresh": "eyJ0eXAiOiJK..."
}
```

#### Response (200 OK)

Returns a success status (usually empty body or success detail).

---

## Notes for Frontend Developers

1.  **Authorization Header**: For any future protected endpoints, you will need to include the access token in the header:
    `Authorization: Bearer <access_token>`
2.  **Token Expiry**:
    -   Access Token: 60 minutes
    -   Refresh Token: 1 day (renewed with each refresh call)
3.  **Token Rotation**: Refresh tokens **are rotated**. Each time you call the refresh endpoint:
    -   You receive a NEW access token AND a NEW refresh token
    -   The old refresh token is automatically blacklisted
    -   **You MUST save the new refresh token** - if you don't, you'll have to login again after 1 day
    -   This allows active users to stay logged in indefinitely as long as they refresh their tokens regularly

---

## Admin API

All Admin API endpoints are prefixed with `/admin/`.
**Permission Required**: User must have `primary_role="ADMIN"`.
**Authorization Header**: `Bearer <access_token>` is required.

### 1. Dashboard

#### Get Summary Statistics
- **Endpoint**: `/admin/dashboard/summary/`
- **Method**: `GET`
- **Description**: Returns aggregate statistics for the dashboard.
- **Response**:
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

### 2. Courses Management

#### List Courses
- **Endpoint**: `/admin/courses/`
- **Method**: `GET`
- **Query Params**: `?search=name_or_code`, `?department=id`
- **Response**: List of courses.

#### Create Course
- **Endpoint**: `/admin/courses/`
- **Method**: `POST`
- **Body**:
  ```json
  {
      "code": "CS101",
      "name": "Intro to CS",
      "credit_hours": 3,
      "department": 1,
      "description": "...",
      "prerequisites": [2, 3] 
  }
  ```

#### Update/Delete Course
- **Endpoint**: `/admin/courses/{id}/`
- **Method**: `PATCH` / `DELETE`

### 3. User Management

#### List Users
- **Endpoint**: `/admin/users/`
- **Method**: `GET`
- **Query Params**: `?role=STUDENT` / `?role=TA` / `?role=PROFESSOR`

#### Create Instructor
- **Endpoint**: `/admin/users/instructors/`
- **Method**: `POST`
- **Body**: `{ "username": "...", "email": "...", "password": "...", "full_name": "...", "department": 1 }`

#### Create Teaching Assistant
- **Endpoint**: `/admin/users/tas/`
- **Method**: `POST`
- **Body**: Same as instructor.

### 4. Announcements

#### List Announcements
- **Endpoint**: `/admin/announcements/`
- **Method**: `GET`

#### Create Announcement
- **Endpoint**: `/admin/announcements/`
- **Method**: `POST`
- **Body**:
  ```json
  {
      "title": "Exam Schedule",
      "content": "Finals start next week.",
      "is_global": true,
      "is_TODO": true, 
      "expires_at": "2024-06-01T00:00:00Z"
  }
  ```
  **Note**: Setting `is_TODO=true` will automatically create `TodoItem`s for relevant students.

### 5. Upload Center (Materials)

#### Upload Material
- **Endpoint**: `/admin/materials/upload/`
- **Method**: `POST`
- **Body**:
  ```json
  {
      "title": "Handbook",
      "file_url": "https://...",
      "material_type": "OTHER",
      "file_type": "pdf"
  }
  ```

### 6. Chat Monitoring

#### List Conversations
- **Endpoint**: `/admin/chat/`
- **Method**: `GET`

#### Get Conversation Messages
- **Endpoint**: `/admin/chat/messages/?conversation_id={id}`
- **Method**: `GET`

### 7. Notifications

#### List Notifications
- **Endpoint**: `/admin/notifications/`
- **Method**: `GET`

