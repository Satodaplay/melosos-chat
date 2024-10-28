document.addEventListener('DOMContentLoaded', function() {
    const socket = io();
    const chatBox = document.getElementById('chat-box');
    const chatInput = document.getElementById('chat-input');
    const roomList = document.getElementById('room-list');
    const createChatRoomButton = document.getElementById('create-chat-room');
    const profileContainer = document.getElementById('profile-container');
    const hamburgerMenu = document.getElementById('hamburger-menu');
    const editProfileButton = document.getElementById('edit-profile');
    const changePasswordButton = document.getElementById('change-password');
    const logoutButton = document.getElementById('logout');
    const roomNameInput = document.getElementById('room-name');
    const fileInput = document.getElementById('file-input');
    const sendFileButton = document.getElementById('send-file-button');
    let currentRoom = '';

    function loadRooms() {
        fetch('/rooms')
            .then(response => response.json())
            .then(data => {
                roomList.innerHTML = '';
                for (const roomId in data) {
                    const roomItem = document.createElement('li');
                    roomItem.textContent = `${data[roomId].name} (${data[roomId].type})`;
                    roomItem.dataset.roomId = roomId;
                    roomItem.dataset.roomType = data[roomId].type;
                    roomItem.addEventListener('click', () => joinRoom(roomId, data[roomId].name, data[roomId].type));
                    roomList.appendChild(roomItem);
                }
            });
    }

    function joinRoom(roomId, roomName, roomType) {
        if (currentRoom) {
            socket.emit('leave', { room: currentRoom });
        }

        currentRoom = roomId;
        socket.emit('join', { room: roomId });
        document.getElementById('current-room').textContent = `Sala actual: ${roomName}`;

        chatBox.innerHTML = '';
    }

    createChatRoomButton.addEventListener('click', () => {
        const roomName = roomNameInput.value.trim();
        if (roomName === '') {
            alert("Por favor, ingrese un nombre para la sala.");
            return;
        }

        fetch('/create_room', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ room_name: roomName, room_type: 'chat' })
        })
        .then(response => response.json())
        .then(data => {
            joinRoom(data.room_id, data.room_name, 'chat');
            loadRooms(); // Actualizar la lista de salas
        });
    });

    chatInput.addEventListener('keydown', function(event) {
        if (event.key === 'Enter') {
            const message = chatInput.value;

            if (!currentRoom) {
                alert("Por favor, únase a una sala de chat primero.");
                return;
            }

            socket.emit('message', { room: currentRoom, message: message });
            chatInput.value = '';
        }
    });

    profileContainer.addEventListener('click', () => {
        hamburgerMenu.style.display = hamburgerMenu.style.display === 'block' ? 'none' : 'block';
    });

    editProfileButton.addEventListener('click', () => {
        window.location.href = '/profile';
    });

    changePasswordButton.addEventListener('click', () => {
        window.location.href = '/change_password';
    });

    logoutButton.addEventListener('click', () => {
        window.location.href = '/logout';
    });

    function loadProfile() {
        fetch('/profile_data')
            .then(response => response.json())
            .then(data => {
                document.getElementById('profile-username').textContent = data.username;
                if (data.photo) {
                    document.getElementById('profile-photo').src = `/uploads/${data.photo}`;
                } else {
                    document.getElementById('profile-photo').src = '/static/default-profile.png'; // Imagen de perfil predeterminada
                }
            });
    }

    socket.on('message', function(data) {
        addMessage(data.username, data.message, data.username === 'System' ? 'system' : 'bot', false);
    });

    socket.on('room_history', function(messages) {
        chatBox.innerHTML = ''; // Limpiar el chat box antes de mostrar el historial
        messages.forEach(msg => {
            addMessage(msg.username, msg.message, msg.username === 'System' ? 'system' : 'bot', false);
        });
    });

    function addMessage(user, message, type = 'user', isHtml = false) {
        const messageElement = document.createElement('div');
        messageElement.classList.add('chat-message');
        messageElement.classList.add(type);
        if (isHtml) {
            messageElement.innerHTML = message;
        } else {
            messageElement.innerHTML = `<span class="${type}">${user}:</span> ${message}`;
        }
        chatBox.appendChild(messageElement);
        chatBox.scrollTop = chatBox.scrollHeight;
    }

    sendFileButton.addEventListener('click', () => {
        const file = fileInput.files[0];
        if (file) {
            const reader = new FileReader();
            reader.onload = function(event) {
                const data = event.target.result;
                socket.emit('file', { room: currentRoom, file: data, filename: file.name });
            };
            reader.readAsDataURL(file);
        }
    });

    socket.on('file', function(data) {
        const link = document.createElement('a');
        link.href = data.file;
        link.download = data.filename;
        link.textContent = `Archivo recibido: ${data.filename}`;
        addMessage(data.username, link.outerHTML, 'file', true);
    });

    loadRooms(); // Cargar las salas disponibles al iniciar
    loadProfile(); // Cargar el perfil del usuario al iniciar

});
