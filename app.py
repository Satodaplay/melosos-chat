from flask import Flask, render_template, request, jsonify, session, redirect, url_for, send_from_directory
from flask_socketio import SocketIO, join_room, leave_room, emit
from flask_bcrypt import Bcrypt
from werkzeug.utils import secure_filename
import os
import uuid
import base64
import csv

app = Flask(__name__)
app.config['SECRET_KEY'] = 'secret!'
app.config['UPLOAD_FOLDER'] = 'uploads'
socketio = SocketIO(app)
bcrypt = Bcrypt(app)

# Ensure the upload folder exists
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

rooms = {}
room_names = {}
user_data = {}
user_credentials = {}

def load_rooms_from_csv():
    try:
        with open('data/rooms.csv', mode='r', newline='') as infile:
            reader = csv.reader(infile)
            for row in reader:
                if row:  # Asegurarse de que la fila no esté vacía
                    room_id, room_name, room_type = row
                    rooms[room_id] = {'name': room_name, 'type': room_type, 'messages': []}
                    room_names[room_id] = {'name': room_name, 'type': room_type}
    except FileNotFoundError:
        pass

def save_rooms_to_csv():
    with open('data/rooms.csv', mode='w', newline='') as outfile:
        writer = csv.writer(outfile)
        for room_id, data in room_names.items():
            writer.writerow([room_id, data['name'], data['type']])

def load_users_from_csv():
    try:
        with open('data/users.csv', mode='r', newline='') as infile:
            reader = csv.reader(infile)
            for row in reader:
                if row:  # Asegurarse de que la fila no esté vacía
                    user_id, username, user_rooms, description, photo, password = row
                    user_data[user_id] = {
                        'username': username, 
                        'rooms': user_rooms.split('|'), 
                        'description': description, 
                        'photo': photo,
                        'password': password
                    }
                    user_credentials[username] = password
    except FileNotFoundError:
        pass

def save_users_to_csv():
    with open('data/users.csv', mode='w', newline='') as outfile:
        writer = csv.writer(outfile)
        for user_id, data in user_data.items():
            writer.writerow([
                user_id, 
                data['username'], 
                '|'.join(data['rooms']), 
                data.get('description', ''), 
                data.get('photo', ''), 
                data['password']
            ])

def get_user_by_username(username):
    for user_id, data in user_data.items():
        if data['username'] == username:
            return user_id, data
    return None, None

load_rooms_from_csv()
load_users_from_csv()

@app.route('/')
def index():
    if 'username' in session:
        return render_template('index.html')
    return redirect(url_for('login'))

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        data = request.json
        username = data['username']
        password = data['password']
        
        if username in user_credentials:
            return jsonify({'success': False, 'message': 'Username already exists'})

        user_id = str(uuid.uuid4())
        user_credentials[username] = password
        user_data[user_id] = {'username': username, 'rooms': [], 'password': password}
        save_users_to_csv()
        return jsonify({'success': True})
    
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        data = request.json
        username = data['username']
        password = data['password']

        user_id, user_info = get_user_by_username(username)
        if user_info and (user_info['password'], password):
            session['username'] = username
            return jsonify({'success': True})
        return jsonify({'success': False, 'message': 'Invalid username or password'})

    return render_template('login.html')

@app.route('/logout')
def logout():
    session.pop('username', None)
    return redirect(url_for('login'))

@app.route('/rooms', methods=['GET'])
def get_rooms():
    return jsonify(room_names)

@app.route('/create_room', methods=['POST'])
def create_room():
    if 'username' not in session:
        return jsonify({'success': False, 'message': 'User not logged in'})

    data = request.json
    room_name = data['room_name']
    room_type = data['room_type']
    room_id = str(uuid.uuid4())
    rooms[room_id] = {'name': room_name, 'type': room_type, 'messages': []}
    room_names[room_id] = {'name': room_name, 'type': room_type}
    save_rooms_to_csv()
    return jsonify({"room_id": room_id, "room_name": room_name})

@socketio.on('join')
def handle_join(data):
    username = session.get('username')
    if not username:
        return

    room = data['room']
    join_room(room)
    user_id = next((uid for uid, udata in user_data.items() if udata['username'] == username), None)
    if user_id and room not in user_data[user_id]['rooms']:
        user_data[user_id]['rooms'].append(room)
        save_users_to_csv()

    emit('room_history', rooms[room]['messages'], room=request.sid)

@socketio.on('leave')
def handle_leave(data):
    username = session.get('username')
    if not username:
        return

    room = data['room']
    leave_room(room)
    
    user_id = next((uid for uid, udata in user_data.items() if udata['username'] == username), None)
    if user_id and room in user_data[user_id]['rooms']:
        user_data[user_id]['rooms'].remove(room)
        save_users_to_csv()
    
    system_message = {'username': 'System', 'message': f'{username} has left the room.'}
    rooms[room]['messages'].append(system_message)
    emit('message', system_message, to=room)

@socketio.on('message')
def handle_message(data):
    username = session.get('username')
    if not username:
        return

    room = data['room']
    message = data['message']
    full_message = {'username': username, 'message': message}

    rooms[room]['messages'].append(full_message)
    emit('message', full_message, to=room)

@socketio.on('file')
def handle_file(data):
    username = session.get('username')
    if not username:
        return

    room = data['room']
    file_data = data['file']
    filename = data['filename']
    
    # Decode the base64 file data
    file_content = base64.b64decode(file_data.split(',')[1])
    file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    
    # Save the file
    with open(file_path, 'wb') as f:
        f.write(file_content)
    
    full_message = {'username': username, 'file': url_for('download_file', filename=filename), 'filename': filename}
    rooms[room]['messages'].append(full_message)
    emit('file', full_message, to=room)

@app.route('/uploads/<filename>')
def download_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

@app.route('/profile')
def profile():
    if 'username' in session:
        return render_template('profile.html')
    return redirect(url_for('login'))

@app.route('/profile_data', methods=['GET'])
def profile_data():
    if 'username' in session:
        username = session['username']
        user_id = next((uid for uid, udata in user_data.items() if udata['username'] == username), None)
        if user_id:
            user_info = user_data[user_id]
            return jsonify({
                'username': user_info['username'],
                'description': user_info.get('description', ''),
                'photo': user_info.get('photo', '')
            })
    return jsonify({'success': False, 'message': 'User not logged in'})

@app.route('/update_profile', methods=['POST'])
def update_profile():
    if 'username' in session:
        username = session['username']
        user_id = next((uid for uid, udata in user_data.items() if udata['username'] == username), None)
        if user_id:
            user_info = user_data[user_id]
            description = request.form.get('description', '')
            photo = request.files.get('photo')
            
            if photo:
                filename = secure_filename(photo.filename)
                photo_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                photo.save(photo_path)
                user_info['photo'] = filename
            
            user_info['description'] = description
            save_users_to_csv()
            return jsonify({'success': True})
    return jsonify({'success': False, 'message': 'User not logged in'})

@app.route('/delete_account', methods=['POST'])
def delete_account():
    if 'username' in session:
        username = session['username']
        user_id = next((uid for uid, udata in user_data.items() if udata['username'] == username), None)
        if user_id:
            del user_data[user_id]
            del user_credentials[username]
            save_users_to_csv()
            session.pop('username', None)
            return jsonify({'success': True})
    return jsonify({'success': False, 'message': 'User not logged in'})

@app.route('/change_password', methods=['GET'])
def show_change_password():
    if 'username' in session:
        return render_template('change_password.html')
    return redirect(url_for('login'))

@app.route('/change_password', methods=['POST'])
def change_password():
    if 'username' not in session:
        return jsonify({'success': False, 'message': 'User not logged in'})

    data = request.json
    current_password = data.get('current_password')
    new_password = data.get('new_password')
    username = session['username']
    
    user_id, user_info = get_user_by_username(username)
    if not user_info or not bcrypt.check_password_hash(user_info['password'], current_password):
        return jsonify({'success': False, 'message': 'Contraseña actual incorrecta'})

    user_info['password'] = bcrypt.generate_password_hash(new_password).decode('utf-8')
    return jsonify({'success': True})

if __name__ == '__main__':
    socketio.run(app, host='172.16.4.37', port=5000, debug=True)

