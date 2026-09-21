import psycopg2

DATABASE_URL = "postgresql://postgres.ybbhwdgluiwratvsffji:bekovali9333@aws-0-ap-southeast-2.pooler.supabase.com:6543/postgres"

def init_db():
    conn = psycopg2.connect(DATABASE_URL)
    cursor = conn.cursor()

    cursor.execute('DROP TABLE IF EXISTS attendance')
    cursor.execute('DROP TABLE IF EXISTS students')

    cursor.execute('''
    CREATE TABLE students (
        id SERIAL PRIMARY KEY,
        name TEXT NOT NULL,
        class_name TEXT NOT NULL
    )
    ''')

    cursor.execute('''
    CREATE TABLE attendance (
        id SERIAL PRIMARY KEY,
        student_id INTEGER,
        date TEXT,
        status TEXT,
        FOREIGN KEY(student_id) REFERENCES students(id) ON DELETE CASCADE
    )
    ''')

    conn.commit()
    conn.close()
    print("PostgreSQL Database initialized successfully.")

if __name__ == '__main__':
    init_db()
