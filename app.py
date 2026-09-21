from flask import Flask, render_template, request, redirect, url_for, session
import psycopg2
import psycopg2.extras
import datetime
import os

app = Flask(__name__)
app.secret_key = 'super_secret_key_maktab'
DATABASE_URL = "postgresql://postgres.ybbhwdgluiwratvsffji:bekovali9333@aws-0-ap-southeast-2.pooler.supabase.com:6543/postgres"

SCHOOL_CLASSES = [f"{i}-{l}" for i in range(1, 12) for l in ['A', 'B', 'D', 'E']]

def get_db_connection():
    return psycopg2.connect(DATABASE_URL)

def get_student_stats():
    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cursor.execute('''
        SELECT s.id, s.name, s.class_name, 
               COUNT(a.id) as dq_count
        FROM students s
        LEFT JOIN attendance a ON s.id = a.student_id AND a.status = 'DQ'
        GROUP BY s.id
    ''')
    students = cursor.fetchall()
    conn.close()
    
    stats = []
    for s in students:
        if s['dq_count'] >= 5:
            color = "bg-red-100 text-red-900 border-red-300"
            status = "Qizil"
        elif s['dq_count'] >= 3:
            color = "bg-yellow-100 text-yellow-900 border-yellow-300"
            status = "Sariq"
        else:
            color = "bg-green-100 text-green-900 border-green-300"
            status = "Yashil"
            
        stats.append({
            'id': s['id'],
            'name': s['name'],
            'class_name': s['class_name'],
            'dq_count': s['dq_count'],
            'color': color,
            'status': status
        })
    stats.sort(key=lambda x: x['dq_count'], reverse=True)
    return stats

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/admin_login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        password = request.form.get('password')
        if password == '12345':  # Simple password for prototype
            session['is_admin'] = True
            return redirect(url_for('admin'))
        else:
            return render_template('admin_login.html', error="Parol noto'g'ri!")
    return render_template('admin_login.html')

@app.route('/admin')
def admin():
    if not session.get('is_admin'):
        return redirect(url_for('admin_login'))
    
    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    target_date = request.args.get('date', datetime.date.today().strftime('%Y-%m-%d'))
    
    cursor.execute('''
        SELECT 
            s.class_name,
            COUNT(s.id) as total_students,
            SUM(CASE WHEN a.status = 'DQ' THEN 1 ELSE 0 END) as dq_count,
            SUM(CASE WHEN a.status = 'S' THEN 1 ELSE 0 END) as s_count
        FROM students s
        LEFT JOIN attendance a ON s.id = a.student_id AND a.date = %s
        GROUP BY s.class_name
        ORDER BY s.class_name
    ''', (target_date,))
    class_rows = cursor.fetchall()
    
    daily_stats = []
    school_total = 0
    school_dq = 0
    school_s = 0
    
    class_data = {row['class_name']: dict(row) for row in class_rows}
    
    for cls_name in SCHOOL_CLASSES:
        if cls_name in class_data:
            total = class_data[cls_name]['total_students']
            dq = class_data[cls_name]['dq_count'] or 0
            s_count = class_data[cls_name]['s_count'] or 0
        else:
            total = 0
            dq = 0
            s_count = 0
            
        present = total - dq - s_count
        percent = (present / total * 100) if total > 0 else 0
        
        if total > 0:
            daily_stats.append({
                'class_name': cls_name,
                'total': total,
                'dq': int(dq),
                's': int(s_count),
                'present': int(present),
                'percent': round(percent, 1)
            })
            
            school_total += total
            school_dq += int(dq)
            school_s += int(s_count)
        
    school_present = school_total - school_dq - school_s
    school_percent = (school_present / school_total * 100) if school_total > 0 else 0
    
    school_summary = {
        'total': school_total,
        'dq': school_dq,
        's': school_s,
        'present': school_present,
        'percent': round(school_percent, 1)
    }
    conn.close()

    all_stats = get_student_stats()
    filtered_stats = [s for s in all_stats if s['status'] in ['Qizil', 'Sariq']]
    
    return render_template('admin.html', stats=filtered_stats, daily_stats=daily_stats, school_summary=school_summary, target_date=target_date)

@app.route('/admin_logout')
def admin_logout():
    session.pop('is_admin', None)
    return redirect(url_for('index'))

@app.route('/teacher_login', methods=['GET', 'POST'])
def teacher_login():
    if request.method == 'POST':
        class_name = request.form.get('class_name')
        if class_name:
            return redirect(url_for('teacher', class_name=class_name))
    
    return render_template('teacher_login.html', classes=SCHOOL_CLASSES)

@app.route('/teacher', methods=('GET', 'POST'))
def teacher():
    class_name = request.args.get('class_name')
    if not class_name or class_name not in SCHOOL_CLASSES:
        return redirect(url_for('teacher_login'))
        
    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    today = datetime.date.today().strftime('%Y-%m-%d')
    
    if request.method == 'POST':
        student_id = request.form.get('student_id')
        status = request.form.get('status')
        if student_id is not None and status is not None:
            cursor.execute('SELECT id FROM attendance WHERE student_id = %s AND date = %s', (student_id, today))
            existing = cursor.fetchone()
            if existing:
                if status == "":
                    cursor.execute('DELETE FROM attendance WHERE id = %s', (existing['id'],))
                else:
                    cursor.execute('UPDATE attendance SET status = %s WHERE id = %s', (status, existing['id']))
            else:
                if status != "":
                    cursor.execute('INSERT INTO attendance (student_id, date, status) VALUES (%s, %s, %s)', (student_id, today, status))
            conn.commit()
        return redirect(url_for('teacher', class_name=class_name))

    cursor.execute('SELECT * FROM students WHERE class_name = %s ORDER BY name', (class_name,))
    students = cursor.fetchall()
    
    cursor.execute('SELECT student_id, status FROM attendance WHERE date = %s', (today,))
    attendance = cursor.fetchall()
    att_map = {row['student_id']: row['status'] for row in attendance}
    conn.close()
    
    return render_template('teacher.html', students=students, att_map=att_map, class_name=class_name, today=today)

@app.route('/add_student', methods=['POST'])
def add_student():
    class_name = request.form.get('class_name')
    student_name = request.form.get('student_name', '').strip()
    if class_name and student_name:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT COUNT(*) FROM students WHERE class_name = %s', (class_name,))
        count = cursor.fetchone()[0]
        if count < 40:
            cursor.execute('INSERT INTO students (name, class_name) VALUES (%s, %s)', (student_name, class_name))
            conn.commit()
        conn.close()
    return redirect(url_for('teacher', class_name=class_name))

@app.route('/delete_student/<int:student_id>', methods=['POST'])
def delete_student(student_id):
    class_name = request.form.get('class_name')
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('DELETE FROM students WHERE id = %s', (student_id,))
    cursor.execute('DELETE FROM attendance WHERE student_id = %s', (student_id,))
    conn.commit()
    conn.close()
    return redirect(url_for('teacher', class_name=class_name))

@app.route('/parent', methods=['GET', 'POST'])
def parent():
    result = None
    searched = False
    
    if request.method == 'POST':
        search_name = request.form.get('search_name', '').strip().lower()
        searched = True
        if search_name:
            all_stats = get_student_stats()
            for s in all_stats:
                if search_name in s['name'].lower():
                    result = s
                    break
                    
    return render_template('parent.html', result=result, searched=searched)

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0')
