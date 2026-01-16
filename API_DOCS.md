# API Documentation

This document outlines the existing API endpoints for the Graduation Project. currently, the API exposes endpoints for Authentication (JWT).

## Base URL

- Development: `http://127.0.0.1:8000`
- Production: 'https://graduation-project-production-be44.up.railway.app'

## Authentication

The project uses **JSON Web Tokens (JWT)** for authentication.

### 1. Login (Obtain Token Pair)

Authenticate a user and obtain an access and refresh token.

- **Endpoint**: `/api/token/`
- **Method**: `POST`
- **Content-Type**: `application/json`

#### Request Body

| Field      | Type   | Required | Description |
|------------|--------|----------|-------------|
| `username` | string | Yes      | User's username |
| `password` | string | Yes      | User's password |

**Example:**
```json
{
    "username": "teststudent",
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

Obtain a new access token using a valid refresh token. This should be used when the access token expires.

- **Endpoint**: `/api/token/refresh/`
- **Method**: `POST`
- **Content-Type**: `application/json`

#### Request Body

| Field     | Type   | Required | Description |
|-----------|--------|----------|-------------|
| `refresh` | string | Yes      | The valid refresh token obtained during login |

**Example:**
```json
{
    "refresh": "eyJ0eXAiOiJK..."
}
```

#### Response (200 OK)

Returns a new access token.

```json
{
    "access": "eyJ0eXAiOiJK..."
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
    -   Refresh Token: 1 day
3.  **Token Rotation**: Refresh tokens are *not* rotated (checking settings `ROTATE_REFRESH_TOKENS = False`).
