"""
Quick lookup script — prints IDs needed for Postman testing.
Run with: D:\python\pytorch\ragenv\Scripts\python.exe lookup_test_data.py
"""
import sys
import types

# ragenv has native mysqlclient (MySQLdb) but GraduationProject/__init__.py
# does `import pymysql; pymysql.install_as_MySQLdb()`.
# Shim: expose a fake pymysql that delegates to MySQLdb so Django starts cleanly.
import MySQLdb as _mysqldb
fake_pymysql = types.ModuleType("pymysql")
fake_pymysql.install_as_MySQLdb = lambda: None   # no-op; native driver already loaded
fake_pymysql.connect = _mysqldb.connect
fake_pymysql.threadsafety = _mysqldb.threadsafety
sys.modules["pymysql"] = fake_pymysql

import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'GraduationProject.settings')
django.setup()

from main.models import Course, CourseOffering, Department, User, Enrollment

print("\n======= DEPARTMENTS =======")
for d in Department.objects.all():
    print(f"  ID={d.id}  code={d.code}  name={d.name}")

print("\n======= COURSES (with 'data' in name/code) =======")
for c in Course.objects.filter(name__icontains='data') | Course.objects.filter(code__icontains='data'):
    print(f"  ID={c.id}  code={c.code}  name={c.name}")

print("\n======= ALL COURSES =======")
for c in Course.objects.all():
    print(f"  ID={c.id}  code={c.code}  name={c.name}")

print("\n======= COURSE OFFERINGS (Data Science) =======")
for o in CourseOffering.objects.filter(course__name__icontains='data'):
    instructor_name = o.instructor.full_name if o.instructor else 'N/A'
    print(f"  OfferingID={o.id}  course={o.course.code}  {o.semester} {o.year}  instructor={instructor_name}")

print("\n======= PROFESSORS =======")
for u in User.objects.filter(primary_role='PROFESSOR'):
    print(f"  ID={u.id}  username={u.username}  email={u.email}  name={u.full_name}")

print("\n======= STUDENTS =======")
for u in User.objects.filter(primary_role='STUDENT')[:5]:
    print(f"  ID={u.id}  email={u.email}  name={u.full_name}")
