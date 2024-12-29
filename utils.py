import cv2
import numpy as np
from models import Student
import face_recognition

def encode_face(image_file):
    image = face_recognition.load_image_file(image_file)
    face_locations = face_recognition.face_locations(image)
    if len(face_locations) > 0:
        face_encoding = face_recognition.face_encodings(image, face_locations)[0]
        return face_encoding
    return None

def recognize_faces(frame):
    small_frame = cv2.resize(frame, (0, 0), fx=0.25, fy=0.25)
    rgb_small_frame = small_frame[:, :, ::-1]
    
    face_locations = face_recognition.face_locations(rgb_small_frame)
    face_encodings = face_recognition.face_encodings(rgb_small_frame, face_locations)
    
    recognized_students = []
    
    students = Student.query.all()
    known_face_encodings = [student.face_encoding for student in students]
    known_face_names = [student.name for student in students]
    
    for face_encoding in face_encodings:
        matches = face_recognition.compare_faces(known_face_encodings, face_encoding)
        name = "Unknown"
        
        face_distances = face_recognition.face_distance(known_face_encodings, face_encoding)
        best_match_index = np.argmin(face_distances)
        if matches[best_match_index]:
            name = known_face_names[best_match_index]
            student = next((s for s in students if s.name == name), None)
            if student:
                recognized_students.append(student)
    
    return recognized_students

def generate_video_feed():
    video_capture = cv2.VideoCapture(0)
    while True:
        success, frame = video_capture.read()
        if not success:
            break
        _, buffer = cv2.imencode('.jpg', frame)
        frame = buffer.tobytes()
        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')
    video_capture.release()
