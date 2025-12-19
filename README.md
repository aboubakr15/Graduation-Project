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