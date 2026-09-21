import sqlite3
import os

DB_NAME = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'attendance.db')

conn = sqlite3.connect(DB_NAME)
cursor = conn.cursor()

cursor.execute('DROP TABLE IF EXISTS attendance')
cursor.execute('DROP TABLE IF EXISTS students')

cursor.execute('''
CREATE TABLE students (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    class_name TEXT NOT NULL
)
''')

cursor.execute('''
CREATE TABLE attendance (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id INTEGER,
    date TEXT,
    status TEXT,
    FOREIGN KEY(student_id) REFERENCES students(id)
)
''')

# Empty database as requested. Teachers will populate it.

conn.commit()
conn.close()
print("Database initialized completely empty.")
