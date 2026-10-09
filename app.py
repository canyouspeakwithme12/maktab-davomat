from flask import Flask, render_template, request, redirect, url_for, session, send_file
import psycopg2
import psycopg2.extras
import datetime
import os
import csv
from io import BytesIO, StringIO

app = Flask(__name__)
app.secret_key = 'super_secret_key_maktab'
DATABASE_URL = "postgresql://postgres.ybbhwdgluiwratvsffji:bekovali9333@aws-0-ap-southeast-2.pooler.supabase.com:6543/postgres"

SCHOOL_CLASSES = [f"{i}-{l}" for i in range(1, 12) for l in ['A', 'B', 'D', 'E']]

def get_db_connection():
    return psycopg2.connect(DATABASE_URL)

def get_student_stats():
    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    # Endi Qizil/Sariq holat S (Sababsiz) ga qarab belgilanadi
    cursor.execute('''
        SELECT s.id, s.name, s.class_name, 
               COUNT(a.id) as s_count
        FROM students s
        LEFT JOIN attendance a ON s.id = a.student_id AND a.status = 'S'
        GROUP BY s.id
    ''')
    students = cursor.fetchall()
    conn.close()
    
    stats = []
    for s in students:
        if s['s_count'] >= 5:
            color = "bg-red-100 text-red-900 border-red-300"
            status = "Qizil"
        elif s['s_count'] >= 3:
            color = "bg-yellow-100 text-yellow-900 border-yellow-300"
            status = "Sariq"
        else:
            color = "bg-green-100 text-green-900 border-green-300"
            status = "Yashil"
            
        stats.append({
            'id': s['id'],
            'name': s['name'],
            'class_name': s['class_name'],
            's_count': s['s_count'],
            'color': color,
            'status': status
        })
    stats.sort(key=lambda x: x['s_count'], reverse=True)
    return stats

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/admin_login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        password = request.form.get('password')
        if password == '12345':  # Simple password for admin
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
    ''')
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

    # Fetch daily absentees
    cursor.execute('''
        SELECT s.name, s.class_name, a.status 
        FROM attendance a
        JOIN students s ON a.student_id = s.id
        WHERE a.date = %s AND a.status IN ('S', 'DQ')
        ORDER BY s.class_name, s.name
    ''', (target_date,))
    absentees = cursor.fetchall()

    # Fetch comments for the date
    cursor.execute('SELECT class_name, comment FROM class_comments WHERE date = %s', (target_date,))
    comments_raw = cursor.fetchall()
    comments_map = {row['class_name']: row['comment'] for row in comments_raw}

    conn.close()

    all_stats = get_student_stats()
    filtered_stats = [s for s in all_stats if s['status'] in ['Qizil', 'Sariq']]
    
    return render_template('admin.html', 
                           stats=filtered_stats, 
                           daily_stats=daily_stats, 
                           school_summary=school_summary, 
                           target_date=target_date,
                           absentees=absentees,
                           comments_map=comments_map)

@app.route('/export_excel')
def export_excel():
    if not session.get('is_admin'):
        return redirect(url_for('admin_login'))
    
    target_date = request.args.get('date', datetime.date.today().strftime('%Y-%m-%d'))
    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    
    cursor.execute('''
        SELECT s.class_name, s.name, COALESCE(a.status, 'Keldi') as status
        FROM students s
        LEFT JOIN attendance a ON s.id = a.student_id AND a.date = %s
        ORDER BY s.class_name, s.name
    ''', (target_date,))
    rows = cursor.fetchall()
    
    cursor.execute('SELECT class_name, comment FROM class_comments WHERE date = %s', (target_date,))
    comments_raw = cursor.fetchall()
    comments_map = {r['class_name']: r['comment'] for r in comments_raw}
    conn.close()
    
    # Generate CSV using utf-8-sig
    si = StringIO()
    writer = csv.writer(si)
    writer.writerow(['Sinf', 'Ism Sharifi', 'Holati (Keldi/S/DQ)', 'Sinf rahbari izohi'])
    
    last_class = None
    for r in rows:
        c_name = r['class_name']
        comment = comments_map.get(c_name, '') if c_name != last_class else ''
        last_class = c_name
        writer.writerow([c_name, r['name'], r['status'], comment])
        
    output = BytesIO()
    output.write(si.getvalue().encode('utf-8-sig'))
    output.seek(0)
    
    return send_file(output, mimetype='text/csv', as_attachment=True, download_name=f'davomat_{target_date}.csv')

@app.route('/admin_logout')
def admin_logout():
    session.pop('is_admin', None)
    return redirect(url_for('index'))

@app.route('/teacher_login', methods=['GET', 'POST'])
def teacher_login():
    error = None
    if request.method == 'POST':
        class_name = request.form.get('class_name')
        password = request.form.get('password')
        
        if class_name and password:
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute('SELECT password FROM class_auth WHERE class_name = %s', (class_name,))
            row = cursor.fetchone()
            conn.close()
            
            if row and row[0] == password:
                session[f'auth_{class_name}'] = True
                return redirect(url_for('teacher', class_name=class_name))
            else:
                error = "Parol noto'g'ri yozilgan yoki kiritilmagan!"
                
    return render_template('teacher_login.html', classes=SCHOOL_CLASSES, error=error)

@app.route('/teacher', methods=('GET', 'POST'))
def teacher():
    class_name = request.args.get('class_name')
    if not class_name or class_name not in SCHOOL_CLASSES:
        return redirect(url_for('teacher_login'))
        
    # Check session auth
    if not session.get(f'auth_{class_name}'):
         return redirect(url_for('teacher_login'))
         
    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    today = datetime.date.today().strftime('%Y-%m-%d')
    
    # 18:00 check
    now = datetime.datetime.now()
    is_locked = (now.hour >= 18)
    
    if request.method == 'POST':
        if is_locked:
            conn.close()
            return "Kechirasiz, soat 18:00 dan so'ng o'zgartirish kiritish taqiqlanadi. Ma'muriyat bilan bog'laning.", 403
            
        # Handle attendance save
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
            
        # Handle comment save
        comment = request.form.get('class_comment')
        if comment is not None:
            cursor.execute('''
                INSERT INTO class_comments (date, class_name, comment) 
                VALUES (%s, %s, %s) 
                ON CONFLICT (date, class_name) 
                DO UPDATE SET comment = EXCLUDED.comment
            ''', (today, class_name, comment))
            conn.commit()
            
        return redirect(url_for('teacher', class_name=class_name))

    cursor.execute('SELECT * FROM students WHERE class_name = %s ORDER BY name', (class_name,))
    students = cursor.fetchall()
    
    cursor.execute('SELECT student_id, status FROM attendance WHERE date = %s', (today,))
    attendance = cursor.fetchall()
    att_map = {row['student_id']: row['status'] for row in attendance}
    
    cursor.execute('SELECT comment FROM class_comments WHERE date = %s AND class_name = %s', (today, class_name))
    comment_row = cursor.fetchone()
    current_comment = comment_row['comment'] if comment_row else ""
    
    conn.close()
    
    return render_template('teacher.html', students=students, att_map=att_map, class_name=class_name, today=today, is_locked=is_locked, current_comment=current_comment)

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

@app.route('/get_passwords')
def get_passwords():
    if not session.get('is_admin'):
        return "Not allowed", 403
    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cursor.execute('SELECT class_name, password FROM class_auth ORDER BY class_name')
    data = cursor.fetchall()
    conn.close()
    text = "Sinflar uchun parollar:\\n\\n"
    for row in data:
        text += f"{row['class_name']}: {row['password']}\\n"
    return text, 200, {'Content-Type': 'text/plain; charset=utf-8'}

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0')
