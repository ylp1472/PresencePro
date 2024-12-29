from flask import render_template, url_for, flash, redirect, request, jsonify, make_response, Response
from flask_login import login_user, current_user, logout_user, login_required
from app import app, db, bcrypt
from models import Admin, Student, Attendance
from utils import encode_face, recognize_faces, generate_video_feed
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

@app.route('/video_feed')
@login_required
def video_feed():
    return Response(generate_video_feed(), mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route('/mark_attendance')
@login_required
def mark_attendance():
    return render_template('mark_attendance.html')

@app.route('/process_attendance', methods=['POST'])
@login_required
def process_attendance():
    if 'image' not in request.files:
        return 'No image file', 400
    
    file = request.files['image']
    npimg = np.fromfile(file, np.uint8)
    img = cv2.imdecode(npimg, cv2.IMREAD_COLOR)
    
    recognized_students = recognize_faces(img)
    
    for student in recognized_students:
        attendance = Attendance(student_id=student.id)
        db.session.add(attendance)
    
    db.session.commit()
    
    return jsonify([student.name for student in recognized_students])
