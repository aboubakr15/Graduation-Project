# Enviroment Setup

- python -m venv env

- .\env\Scripts\activate

- pip install -r requirements.txt

# Setup Database

```python
python manage.py makemigrations
python manage.py migrate
```

# Create Test User

```python
python create_test_user.py
```

# Start Web App

```python
python manage.py runserver
```

## Admin API Reference (Base path: `/admin/`)

| Resource         | Endpoint / Example URL                            | Methods                 | Notes                                      |
|------------------|---------------------------------------------------|-------------------------|--------------------------------------------|
| Dashboard        | `GET /admin/dashboard/summary/`                  | `GET`                   | Returns global stats for the admin panel.  |
| Courses          | `/admin/courses/`, `/admin/courses/{id}/`        | `GET, POST, PUT, PATCH, DELETE` | Full CRUD on `Course`. Supports search by `name`, `code` and filter by `department`. |
| Users            | `/admin/users/`, `/admin/users/{id}/`            | `GET, PUT, PATCH, DELETE`       | Manage users. Filter by `primary_role` via `?role=STUDENT/PROFESSOR/TA`. |
| Instructors      | `POST /admin/users/instructors/`                 | `POST`                  | Create a new professor user.               |
| TAs              | `POST /admin/users/tas/`                         | `POST`                  | Create a new TA user.                      |
| Announcements    | `/admin/announcements/`, `/admin/announcements/{id}/` | `GET, POST, PUT, PATCH, DELETE` | Admin announcements (global or per course offering). |
| Materials        | `/admin/materials/`, `/admin/materials/{id}/`    | `GET, POST, PUT, PATCH, DELETE` | Upload and manage `CourseMaterial` records (file + metadata). |
| Material upload  | `POST /admin/materials/upload/`                  | `POST`                  | Convenience endpoint for creating a material with a file. |
| Chat             | `/admin/chat/`, `/admin/chat/{id}/`              | `GET`                   | List and inspect chat conversations.       |
| Chat messages    | `GET /admin/chat/messages/?conversation_id={id}` | `GET`                   | List messages for a specific conversation. |
| Notifications    | `/admin/notifications/`, `/admin/notifications/{id}/` | `GET, PATCH`          | View notifications and mark them as read.  |

### Authentication

All admin endpoints require an authenticated user whose `primary_role` is `ADMIN`.

1. Obtain access and refresh tokens:

   ```bash
   curl -X POST http://localhost:8000/api/token/ ^
     -H "Content-Type: application/json" ^
     -d "{\"email\": \"admin@example.com\", \"password\": \"your-password\"}"
   ```

2. Use the `access` token in the `Authorization` header for all admin requests:

   ```bash
   curl -H "Authorization: Bearer YOUR_ACCESS_TOKEN" http://localhost:8000/admin/courses/
   ```

### How to Manually Test the Admin Endpoints

You can use Postman, Insomnia, or curl. Below are curl examples you can adapt.

- **List courses**

  ```bash
  curl -H "Authorization: Bearer YOUR_ACCESS_TOKEN" ^
       http://localhost:8000/admin/courses/
  ```

- **Create a course**

  ```bash
  curl -X POST http://localhost:8000/admin/courses/ ^
    -H "Authorization: Bearer YOUR_ACCESS_TOKEN" ^
    -H "Content-Type: application/json" ^
    -d "{\"code\": \"CS101\", \"name\": \"Intro to CS\", \"credit_hours\": 3, \"department\": 1}"
  ```

- **Update a course**

  ```bash
  curl -X PATCH http://localhost:8000/admin/courses/1/ ^
    -H "Authorization: Bearer YOUR_ACCESS_TOKEN" ^
    -H "Content-Type: application/json" ^
    -d "{\"name\": \"Intro to Computer Science\"}"
  ```

- **Delete a course**

  ```bash
  curl -X DELETE http://localhost:8000/admin/courses/1/ ^
    -H "Authorization: Bearer YOUR_ACCESS_TOKEN"
  ```

- **Create an instructor**

  ```bash
  curl -X POST http://localhost:8000/admin/users/instructors/ ^
    -H "Authorization: Bearer YOUR_ACCESS_TOKEN" ^
    -H "Content-Type: application/json" ^
    -d "{\"email\": \"prof@example.com\", \"full_name\": \"Prof Name\", \"password\": \"Pass123!\"}"
  ```

- **Create a course announcement**

  ```bash
  curl -X POST http://localhost:8000/admin/announcements/ ^
    -H "Authorization: Bearer YOUR_ACCESS_TOKEN" ^
    -H "Content-Type: application/json" ^
    -d "{\"title\": \"Exam Reminder\", \"content\": \"Midterm on Monday\", \"is_global\": true}"
  ```

- **Upload course material with a file**

  ```bash
  curl -X POST http://localhost:8000/admin/materials/upload/ ^
    -H "Authorization: Bearer YOUR_ACCESS_TOKEN" ^
    -F "title=Week 1 Slides" ^
    -F "description=Introduction" ^
    -F "material_type=LECTURE" ^
    -F "course_offering=1" ^
    -F "file=@path/to/file.pdf"
  ```

- **View chat conversations and messages**

  ```bash
  # Conversations
  curl -H "Authorization: Bearer YOUR_ACCESS_TOKEN" ^
       http://localhost:8000/admin/chat/

  # Messages in a conversation
  curl -H "Authorization: Bearer YOUR_ACCESS_TOKEN" ^
       "http://localhost:8000/admin/chat/messages/?conversation_id=1"
  ```

- **View and mark a notification as read**

  ```bash
  # List
  curl -H "Authorization: Bearer YOUR_ACCESS_TOKEN" ^
       http://localhost:8000/admin/notifications/

  # Mark as read
  curl -X PATCH http://localhost:8000/admin/notifications/1/ ^
    -H "Authorization: Bearer YOUR_ACCESS_TOKEN" ^
    -H "Content-Type: application/json" ^
    -d "{\"is_read\": true}"
  ```