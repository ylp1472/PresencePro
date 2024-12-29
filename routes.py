from flask import render_template, url_for, flash, redirect, request, jsonify, make_response, Response
from flask_login import login_user, current_user, logout_user, login_required
from app import app, db, bcrypt
from models import Admin, Student, Attendance
from utils import encode_face, recognize_faces
import cv2
import numpy as np
from datetime import datetime
import csv
from io import StringIO

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        admin = Admin.query.filter_by(username=username).first()
        if admin and bcrypt.check_password_hash(admin.password, password):
            login_user(admin)
            return redirect(url_for('dashboard'))
        else:
            flash('Login unsuccessful. Please check username and password.', 'danger')
    return render_template('login.html')

@app.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('login'))

@app.route('/')
@app.route('/dashboard')
@login_required
def dashboard():
    today = datetime.now().date()
    attendances = Attendance.query.filter(db.func.date(Attendance.timestamp) == today).all()
    return render_template('dashboard.html', attendances=attendances)

@app.route('/mark_attendance')
@login_required
def mark_attendance():
    return render_template('mark_attendance.html')

def generate_frames():
    camera = cv2.VideoCapture(0)
    if not camera.isOpened():
        print("Error: Could not open camera")
        return
    
    while True:
        success, frame = camera.read()
        if not success:
            break
        
        # Process frame for face recognition
        recognized_students = recognize_faces(frame)
        
        # Mark attendance for recognized students
        for student in recognized_students:
            today = datetime.now().date()
            existing_attendance = Attendance.query.filter(
                Attendance.student_id == student.id,
                db.func.date(Attendance.timestamp) == today
            ).first()
            
            if not existing_attendance:
                attendance = Attendance(student_id=student.id)
                db.session.add(attendance)
                try:
                    db.session.commit()
                except Exception as e:
                    db.session.rollback()
                    print(f"Error marking attendance: {e}")
        
        ret, buffer = cv2.imencode('.jpg', frame)
        frame = buffer.tobytes()
        yield (b'--frame\r\n'
              b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')

@app.route('/video_feed')
def video_feed():
    return Response(
        generate_frames(),
        mimetype='multipart/x-mixed-replace; boundary=frame'
    )


@app.route('/check_status')
def check_status():
    today = datetime.now().date()
    recent_attendance = Attendance.query.filter(
        db.func.date(Attendance.timestamp) == today
    ).order_by(Attendance.timestamp.desc()).first()
    
    if recent_attendance:
        return jsonify({
            'status': 'success',
            'message': f'Attendance marked for {recent_attendance.student.name}',
            'timestamp': recent_attendance.timestamp.strftime('%H:%M:%S')
        })
    return jsonify({
        'status': 'waiting',
        'message': 'Waiting for face detection...'
    })

@app.route('/student_management')
@login_required
def student_management():
    students = Student.query.all()
    return render_template('student_management.html', students=students)

@app.route('/add_student', methods=['GET', 'POST'])
@login_required
def add_student():
    if request.method == 'POST':
        name = request.form['name']
        registration_number = request.form['registration_number']
        image = request.files['image']
        
        if image:
            face_encoding = encode_face(image)
            if face_encoding is not None:
                student = Student(name=name, registration_number=registration_number, face_encoding=face_encoding)
                db.session.add(student)
                db.session.commit()
                flash('Student added successfully!', 'success')
                return redirect(url_for('student_management'))
            else:
                flash('No face detected in the image. Please try again.', 'danger')
        else:
            flash('Please upload an image.', 'danger')
    
    return render_template('add_student.html')

@app.route('/edit_student/<int:id>', methods=['GET', 'POST'])
@login_required
def edit_student(id):
    student = Student.query.get_or_404(id)
    if request.method == 'POST':
        student.name = request.form['name']
        student.registration_number = request.form['registration_number']
        image = request.files['image']
        
        if image:
            face_encoding = encode_face(image)
            if face_encoding is not None:
                student.face_encoding = face_encoding
            else:
                flash('No face detected in the image. Previous image retained.', 'warning')
        
        db.session.commit()
        flash('Student updated successfully!', 'success')
        return redirect(url_for('student_management'))
    
    return render_template('edit_student.html', student=student)

@app.route('/delete_student/<int:id>', methods=['POST'])
@login_required
def delete_student(id):
    student = Student.query.get_or_404(id)
    db.session.delete(student)
    db.session.commit()
    flash('Student deleted successfully!', 'success')
    return redirect(url_for('student_management'))

@app.route('/export_attendance', methods=['POST'])
@login_required
def export_attendance():
    start_date = datetime.strptime(request.form['start_date'], '%Y-%m-%d')
    end_date = datetime.strptime(request.form['end_date'], '%Y-%m-%d')
    
    attendances = Attendance.query.filter(Attendance.timestamp.between(start_date, end_date)).all()
    
    si = StringIO()
    cw = csv.writer(si)
    cw.writerow(['Student Name', 'Registration Number', 'Timestamp'])
    
    for attendance in attendances:
        cw.writerow([attendance.student.name, attendance.student.registration_number, attendance.timestamp])
    
    output = make_response(si.getvalue())
    output.headers["Content-Disposition"] = f"attachment; filename=attendance_{start_date.date()}_to_{end_date.date()}.csv"
    output.headers["Content-type"] = "text/csv"
    return output

@app.errorhandler(404)
def not_found_error(error):
    return render_template('404.html'), 404

@app.errorhandler(500)
def internal_error(error):
    db.session.rollback()
    return render_template('500.html'), 500
