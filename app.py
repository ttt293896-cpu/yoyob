import os
import datetime
import sqlite3
from functools import wraps
from flask import Flask, request, jsonify, session, render_template_string
from werkzeug.security import generate_password_hash, check_password_hash
import cloudinary
import cloudinary.uploader

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "super-secret-key-change-in-render-998877")

# --- הגדרות אדמין ---
ADMIN_USERNAME = os.environ.get("ADMIN_USERNAME", "admin")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "123456")

# --- חיבור ל-Cloudinary ---
if os.environ.get("CLOUDINARY_URL"):
    cloudinary.config(secure=True)
else:
    cloudinary.config(
        cloud_name=os.environ.get("CLOUDINARY_CLOUD_NAME"),
        api_key=os.environ.get("CLOUDINARY_API_KEY"),
        api_secret=os.environ.get("CLOUDINARY_API_SECRET"),
        secure=True
    )

# --- הגדרת מסד הנתונים המקומי SQLite ---
DB_FILE = "database.db"

def get_db():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    cursor = conn.cursor()
    
    # טבלת משתמשים
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            username TEXT PRIMARY KEY,
            display_name TEXT,
            password TEXT,
            avatar TEXT,
            is_admin INTEGER
        )
    ''')
    
    # טבלת חדרים
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS rooms (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            city TEXT,
            street TEXT,
            house_num TEXT
        )
    ''')
    
    # טבלת פריטים/הודעות בתוך חדרים
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS room_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            room_id INTEGER,
            text TEXT,
            image TEXT,
            created_at TEXT,
            FOREIGN KEY(room_id) REFERENCES rooms(id)
        )
    ''')
    
    # טבלת צ'אט הצעות מול האדמין
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS suggestions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            thread_user TEXT,
            sender TEXT,
            sender_display TEXT,
            sender_is_admin INTEGER,
            text TEXT,
            image TEXT,
            created_at TEXT
        )
    ''')
    conn.commit()

    # יצירת אדמין ברירת מחדל אם אינו קיים
    admin = cursor.execute("SELECT * FROM users WHERE username = ?", (ADMIN_USERNAME,)).fetchone()
    if not admin:
        cursor.execute('''
            INSERT INTO users (username, display_name, password, avatar, is_admin)
            VALUES (?, ?, ?, ?, ?)
        ''', (
            ADMIN_USERNAME,
            "מנהל המערכת",
            generate_password_hash(ADMIN_PASSWORD),
            "https://res.cloudinary.com/demo/image/upload/v1312461204/sample.jpg",
            1
        ))
        conn.commit()
    conn.close()

init_db()

# --- דקורטורים לאבטחה ---
def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if "username" not in session:
            return jsonify({"error": "לא מחובר"}), 401
        return f(*args, **kwargs)
    return decorated

def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get("is_admin"):
            return jsonify({"error": "גישה למנהל בלבד"}), 403
        return f(*args, **kwargs)
    return decorated

# --- תבנית ה-HTML והעיצוב ---
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="he" dir="rtl">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>מערכת חיפוש ומידע</title>
    <style>
        * { box-sizing: border-box; margin: 0; padding: 0; font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; }
        body { background-color: #050505; color: #ffffff; overflow: hidden; height: 100vh; width: 100vw; }
        #bg-canvas { position: fixed; top: 0; left: 0; width: 100%; height: 100%; z-index: 0; opacity: 0.35; pointer-events: none; }
        #landing-screen { position: relative; z-index: 10; height: 100vh; display: flex; flex-direction: column; justify-content: center; align-items: center; }
        .btn-main-login { background: rgba(255, 255, 255, 0.1); border: 1px solid rgba(255, 255, 255, 0.4); color: #fff; padding: 18px 50px; font-size: 1.4rem; border-radius: 50px; cursor: pointer; backdrop-filter: blur(8px); transition: all 0.3s ease; box-shadow: 0 0 25px rgba(255,255,255,0.1); }
        .btn-main-login:hover { background: #ffffff; color: #000000; box-shadow: 0 0 35px rgba(255,255,255,0.6); transform: scale(1.05); }
        .modal { display: none; position: fixed; z-index: 100; left: 0; top: 0; width: 100%; height: 100%; background: rgba(0, 0, 0, 0.85); backdrop-filter: blur(5px); justify-content: center; align-items: center; }
        .modal-content { background: #111; border: 1px solid #333; padding: 30px; border-radius: 16px; width: 90%; max-width: 420px; text-align: center; position: relative; }
        .modal-content h2 { margin-bottom: 20px; }
        .modal-content input, .modal-content textarea { width: 100%; padding: 12px; margin: 8px 0; border-radius: 8px; border: 1px solid #333; background: #1c1c1c; color: #fff; font-size: 1rem; }
        .btn-submit { width: 100%; padding: 12px; margin-top: 15px; background: #fff; color: #000; border: none; border-radius: 8px; font-weight: bold; font-size: 1rem; cursor: pointer; }
        .btn-submit:hover { background: #ddd; }
        .close-btn { position: absolute; top: 12px; left: 15px; font-size: 1.5rem; cursor: pointer; color: #888; }
        #app-screen { display: none; position: relative; z-index: 10; height: 100vh; width: 100vw; }
        #admin-add-room-btn { display: none; position: fixed; top: 25px; left: 50%; transform: translateX(-50%); width: 55px; height: 55px; border-radius: 50%; background: #ffffff; color: #000000; font-size: 2rem; font-weight: bold; border: none; cursor: pointer; box-shadow: 0 0 20px rgba(255,255,255,0.4); z-index: 20; transition: transform 0.2s; }
        #admin-add-room-btn:hover { transform: translateX(-50%) scale(1.1); }
        .center-search-container { position: absolute; top: 45%; left: 50%; transform: translate(-50%, -50%); width: 90%; max-width: 650px; text-align: center; }
        .search-box-wrapper { display: flex; background: #ffffff; border-radius: 50px; padding: 6px 10px; box-shadow: 0 10px 40px rgba(255, 255, 255, 0.15); align-items: center; }
        #main-search-input { flex: 1; border: none; outline: none; background: transparent; color: #000000; font-size: 1.15rem; padding: 12px 20px; }
        #main-search-input::placeholder { color: #666; transition: opacity 0.3s; }
        .search-btn { background: #000000; color: #ffffff; border: none; padding: 12px 28px; border-radius: 40px; font-size: 1rem; font-weight: bold; cursor: pointer; }
        .search-btn:hover { background: #222; }
        #search-results-list { margin-top: 20px; background: rgba(20, 20, 20, 0.95); border: 1px solid #333; border-radius: 14px; max-height: 280px; overflow-y: auto; display: none; text-align: right; }
        .result-item { padding: 14px 20px; border-bottom: 1px solid #2a2a2a; cursor: pointer; display: flex; justify-content: space-between; align-items: center; }
        .result-item:hover { background: #252525; }
        .result-item:last-child { border-bottom: none; }
        #room-view-modal .modal-content { max-width: 650px; max-height: 85vh; overflow-y: auto; text-align: right; }
        .room-meta { background: #1a1a1a; padding: 10px 15px; border-radius: 8px; margin-bottom: 15px; font-size: 0.9rem; color: #bbb; }
        .room-feed-item { background: #181818; border: 1px solid #2c2c2c; padding: 15px; border-radius: 10px; margin-bottom: 12px; }
        .room-feed-item img { max-width: 100%; border-radius: 8px; margin-top: 10px; }
        .profile-widget { position: fixed; bottom: 25px; left: 25px; background: rgba(20, 20, 20, 0.9); border: 1px solid #333; padding: 10px 16px; border-radius: 50px; display: flex; align-items: center; gap: 12px; cursor: pointer; z-index: 20; transition: border-color 0.2s; }
        .profile-widget:hover { border-color: #fff; }
        .profile-widget img { width: 42px; height: 42px; border-radius: 50%; object-fit: cover; border: 1px solid #555; }
        .suggestions-side-btn { position: fixed; right: 0; top: 50%; transform: translateY(-50%); background: #ffffff; color: #000000; padding: 16px 12px; border-radius: 12px 0 0 12px; font-weight: bold; cursor: pointer; z-index: 25; writing-mode: vertical-rl; text-orientation: mixed; box-shadow: -4px 0 20px rgba(255,255,255,0.2); }
        #suggestions-drawer { position: fixed; right: -380px; top: 0; width: 360px; max-width: 90vw; height: 100vh; background: #111111; border-left: 1px solid #333; z-index: 50; transition: right 0.3s ease; display: flex; flex-direction: column; padding: 20px; }
        #suggestions-drawer.open { right: 0; }
        .chat-messages { flex: 1; overflow-y: auto; margin: 15px 0; display: flex; flex-direction: column; gap: 10px; }
        .msg-bubble { background: #1f1f1f; padding: 10px 14px; border-radius: 12px; font-size: 0.95rem; max-width: 85%; }
        .msg-bubble.admin { background: #2b3a4a; align-self: flex-start; }
        .msg-bubble.user { background: #262626; align-self: flex-end; }
        .msg-bubble img { max-width: 100%; border-radius: 6px; margin-top: 6px; }
        .admin-chat-user-item { padding: 12px; background: #1b1b1b; border-radius: 8px; margin-bottom: 8px; cursor: pointer; border: 1px solid #2c2c2c; }
        .admin-chat-user-item:hover { border-color: #fff; }
    </style>
</head>
<body>

    <canvas id="bg-canvas"></canvas>

    <div id="landing-screen">
        <button class="btn-main-login" onclick="openLoginModal()">התחבר למערכת</button>
    </div>

    <div id="login-modal" class="modal">
        <div class="modal-content">
            <span class="close-btn" onclick="closeModal('login-modal')">&times;</span>
            <h2 id="auth-title">התחברות</h2>
            <input type="text" id="auth-username" placeholder="שם משתמש">
            <input type="password" id="auth-password" placeholder="סיסמה">
            <button class="btn-submit" onclick="submitAuth()">התחבר</button>
            <p style="margin-top: 15px; font-size: 0.9rem; color: #aaa; cursor: pointer;" onclick="toggleAuthMode()" id="auth-toggle-text">
                אין לך חשבון? לחץ כאן להרשמה
            </p>
        </div>
    </div>

    <div id="app-screen">
        <button id="admin-add-room-btn" title="צור חדר חדש" onclick="openModal('create-room-modal')">+</button>

        <div class="center-search-container">
            <div class="search-box-wrapper">
                <input type="text" id="main-search-input" placeholder="חיפוש לפי שם פרטי ושם משפחה..." onkeyup="if(event.key==='Enter') performSearch()">
                <button class="search-btn" onclick="performSearch()">חפש</button>
            </div>
            <div id="search-results-list"></div>
        </div>

        <div class="profile-widget" onclick="openModal('edit-profile-modal')">
            <img id="user-avatar-img" src="" alt="Profile">
            <div>
                <div id="user-display-name" style="font-weight: bold;">טוען...</div>
                <div style="font-size: 0.75rem; color: #999;">לחץ לעריכת פרופיל</div>
            </div>
        </div>

        <div class="suggestions-side-btn" onclick="toggleSuggestionsDrawer()">הצעות</div>

        <div id="suggestions-drawer">
            <div style="display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid #333; padding-bottom: 10px;">
                <h3 id="drawer-title">הצעות ופניות</h3>
                <span style="cursor: pointer; font-size: 1.4rem;" onclick="toggleSuggestionsDrawer()">&times;</span>
            </div>

            <div id="admin-threads-list" style="display:none; overflow-y:auto; flex:1; margin-top:10px;"></div>

            <div id="chat-area" style="display:flex; flex-direction:column; flex:1; overflow:hidden;">
                <button id="back-to-threads-btn" style="display:none; background:#222; color:#fff; border:none; padding:6px; border-radius:6px; margin-top:8px; cursor:pointer;" onclick="showAdminThreads()">← חזור לכל ההצעות</button>
                <div class="chat-messages" id="chat-messages-box"></div>
                <div style="border-top: 1px solid #333; padding-top: 10px;">
                    <input type="text" id="chat-text-input" placeholder="כתוב הצעה או הודעה..." style="width:100%; padding:10px; border-radius:8px; border:1px solid #333; background:#1c1c1c; color:#fff; margin-bottom:6px;">
                    <div style="display:flex; gap:6px;">
                        <input type="file" id="chat-image-input" accept="image/*" style="font-size:0.8rem; color:#aaa; flex:1;">
                        <button onclick="sendChatMessage()" style="background:#fff; color:#000; border:none; padding:8px 16px; border-radius:8px; font-weight:bold; cursor:pointer;">שלח</button>
                    </div>
                </div>
            </div>
        </div>
    </div>

    <div id="create-room-modal" class="modal">
        <div class="modal-content">
            <span class="close-btn" onclick="closeModal('create-room-modal')">&times;</span>
            <h2>יצירת חדר מידע חדש</h2>
            <input type="text" id="room-name" placeholder="שם החדר / שם מלא (למשל: יוסי ברקוביץ)">
            <input type="text" id="room-city" placeholder="עיר (למשל: תל אביב)">
            <input type="text" id="room-street" placeholder="רחוב (למשל: בן גוריון)">
            <input type="text" id="room-house-num" placeholder="מספר בית (למשל: 11)">
            <textarea id="room-desc" rows="3" placeholder="מידע / הודעה ראשונה בחדר..."></textarea>
            <label style="display:block; text-align:right; font-size:0.85rem; color:#aaa; margin-top:8px;">העלאת תמונה לחדר:</label>
            <input type="file" id="room-image" accept="image/*">
            <button class="btn-submit" id="create-room-submit" onclick="createRoom()">צור חדר</button>
        </div>
    </div>

    <div id="room-view-modal" class="modal">
        <div class="modal-content">
            <span class="close-btn" onclick="closeModal('room-view-modal')">&times;</span>
            <h2 id="view-room-title">שם החדר</h2>
            <div class="room-meta" id="view-room-meta"></div>
            <div id="view-room-items"></div>

            <div id="admin-add-to-room-section" style="display:none; border-top:1px solid #333; margin-top:20px; padding-top:15px;">
                <h4>+ הוסף מידע או תמונה לחדר זה</h4>
                <textarea id="append-room-text" rows="2" placeholder="הודעה נוספת..."></textarea>
                <input type="file" id="append-room-image" accept="image/*">
                <button class="btn-submit" onclick="appendToRoom()">הוסף לחדר</button>
            </div>
        </div>
    </div>

    <div id="edit-profile-modal" class="modal">
        <div class="modal-content">
            <span class="close-btn" onclick="closeModal('edit-profile-modal')">&times;</span>
            <h2>עריכת פרופיל אישי</h2>
            <input type="text" id="edit-display-name" placeholder="שם תצוגה חדש">
            <label style="display:block; text-align:right; font-size:0.85rem; color:#aaa; margin-top:10px;">בחר תמונת פרופיל מהמחשב/טלפון:</label>
            <input type="file" id="edit-avatar-file" accept="image/*">
            <button class="btn-submit" onclick="updateProfile()">שמור שינויים</button>
            <button onclick="logout()" style="width:100%; padding:10px; margin-top:10px; background:#331111; color:#ff6666; border:1px solid #552222; border-radius:8px; cursor:pointer;">התנתק מהמערכת</button>
        </div>
    </div>

    <script>
        const canvas = document.getElementById('bg-canvas');
        const ctx = canvas.getContext('2d');
        let width, height;
        function resizeCanvas() {
            width = canvas.width = window.innerWidth;
            height = canvas.height = window.innerHeight;
        }
        window.addEventListener('resize', resizeCanvas);
        resizeCanvas();

        const dataStreams = [
            "Michael Vance • 742 Evergreen Terrace, Springfield",
            "Sarah Jenkins • 1600 Pennsylvania Ave, Washington DC",
            "David Miller • 350 Fifth Avenue, New York, NY",
            "Emily Carter • 221B Baker St, Los Angeles, CA",
            "Robert Thorne • 404 Ocean Drive, Miami, FL",
            "Jessica Taylor • 890 Sunset Blvd, Beverly Hills, CA",
            "Daniel Brooks • 1200 Michigan Ave, Chicago, IL",
            "Sophia Martinez • 550 Bourbon Street, New Orleans, LA"
        ];

        let tick = 0;
        function drawWaves() {
            ctx.fillStyle = 'rgba(5, 5, 5, 0.25)';
            ctx.fillRect(0, 0, width, height);
            ctx.font = '14px monospace';

            for (let i = 0; i < dataStreams.length; i++) {
                const text = dataStreams[i];
                const baseY = (height / (dataStreams.length + 1)) * (i + 1);
                for (let x = 0; x < width; x += 380) {
                    const waveY = baseY + Math.sin((x + tick * 1.5 + i * 90) * 0.005) * 35;
                    const offsetX = ((x + tick * (0.8 + (i % 3) * 0.3)) % (width + 400)) - 200;
                    ctx.fillStyle = i % 2 === 0 ? 'rgba(0, 255, 170, 0.45)' : 'rgba(255, 255, 255, 0.35)';
                    ctx.fillText(text, offsetX, waveY);
                }
            }
            tick++;
            requestAnimationFrame(drawWaves);
        }
        drawWaves();

        const placeholders = [
            "חיפוש לפי שם פרטי ושם משפחה...",
            "חיפוש לפי רחוב בעיר מסוימת (למשל: תל אביב בן גוריון)...",
            "חיפוש לפי עיר, רחוב ומספר בית (למשל: תל אביב בן גוריון 11)..."
        ];
        let pIndex = 0;
        setInterval(() => {
            pIndex = (pIndex + 1) % placeholders.length;
            const input = document.getElementById('main-search-input');
            if (input) input.placeholder = placeholders[pIndex];
        }, 3200);

        let currentUser = null;
        let isRegisterMode = false;
        let currentOpenRoomId = null;
        let activeChatTargetUser = null;

        function openModal(id) { document.getElementById(id).style.display = 'flex'; }
        function closeModal(id) { document.getElementById(id).style.display = 'none'; }
        function openLoginModal() { openModal('login-modal'); }

        function toggleAuthMode() {
            isRegisterMode = !isRegisterMode;
            document.getElementById('auth-title').innerText = isRegisterMode ? 'הרשמה למערכת' : 'התחברות';
            document.querySelector('#login-modal .btn-submit').innerText = isRegisterMode ? 'צור חשבון' : 'התחבר';
            document.getElementById('auth-toggle-text').innerText = isRegisterMode ? 'כבר יש לך חשבון? התחבר' : 'אין לך חשבון? לחץ כאן להרשמה';
        }

        async function submitAuth() {
            const username = document.getElementById('auth-username').value.trim();
            const password = document.getElementById('auth-password').value.trim();
            if (!username || !password) return alert('נא למלא שם משתמש וסיסמה');

            const endpoint = isRegisterMode ? '/api/register' : '/api/login';
            const res = await fetch(endpoint, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ username, password })
            });
            const data = await res.json();
            if (data.error) return alert(data.error);

            closeModal('login-modal');
            loadUserSession();
        }

        async function loadUserSession() {
            const res = await fetch('/api/me');
            const data = await res.json();
            if (data.logged_in) {
                currentUser = data.user;
                document.getElementById('landing-screen').style.display = 'none';
                document.getElementById('app-screen').style.display = 'block';
                document.getElementById('user-display-name').innerText = currentUser.display_name;
                document.getElementById('user-avatar-img').src = currentUser.avatar;
                document.getElementById('edit-display-name').value = currentUser.display_name;

                if (currentUser.is_admin) {
                    document.getElementById('admin-add-room-btn').style.display = 'block';
                } else {
                    document.getElementById('admin-add-room-btn').style.display = 'none';
                }
            }
        }

        async function logout() {
            await fetch('/api/logout', { method: 'POST' });
            location.reload();
        }

        async function performSearch() {
            const query = document.getElementById('main-search-input').value.trim();
            if (!query) return;

            const res = await fetch(`/api/search?q=${encodeURIComponent(query)}`);
            const data = await res.json();
            const listEl = document.getElementById('search-results-list');
            listEl.innerHTML = '';

            if (!data.results || data.results.length === 0) {
                listEl.style.display = 'block';
                listEl.innerHTML = '<div style="padding:15px; color:#888;">לא נמצאו תוצאות תואמות במערכת.</div>';
                return;
            }

            if (data.results.length === 1) {
                listEl.style.display = 'none';
                openRoom(data.results[0].id);
            } else {
                listEl.style.display = 'block';
                data.results.forEach(room => {
                    const div = document.createElement('div');
                    div.className = 'result-item';
                    div.innerHTML = `
                        <div>
                            <strong>${room.name}</strong>
                            <div style="font-size:0.85rem; color:#aaa;">${room.city || ''} ${room.street || ''} ${room.house_num || ''}</div>
                        </div>
                        <span style="color:#00ffaa; font-size:0.85rem;">פתח חדר ←</span>
                    `;
                    div.onclick = () => openRoom(room.id);
                    listEl.appendChild(div);
                });
            }
        }

        async function openRoom(roomId) {
            currentOpenRoomId = roomId;
            const res = await fetch(`/api/rooms/${roomId}`);
            const room = await res.json();

            document.getElementById('view-room-title').innerText = room.name;
            document.getElementById('view-room-meta').innerText = `כתובת רשומה: ${room.city || ''} ${room.street || ''} ${room.house_num || ''}`;

            const itemsContainer = document.getElementById('view-room-items');
            itemsContainer.innerHTML = '';
            (room.items || []).forEach(item => {
                const div = document.createElement('div');
                div.className = 'room-feed-item';
                div.innerHTML = `
                    ${item.text ? `<p>${item.text}</p>` : ''}
                    ${item.image ? `<img src="${item.image}" alt="תמונה">` : ''}
                `;
                itemsContainer.appendChild(div);
            });

            if (currentUser && currentUser.is_admin) {
                document.getElementById('admin-add-to-room-section').style.display = 'block';
            }
            openModal('room-view-modal');
        }

        async function createRoom() {
            const btn = document.getElementById('create-room-submit');
            btn.innerText = 'מעלה ושומר...';
            btn.disabled = true;

            const formData = new FormData();
            formData.append('name', document.getElementById('room-name').value);
            formData.append('city', document.getElementById('room-city').value);
            formData.append('street', document.getElementById('room-street').value);
            formData.append('house_num', document.getElementById('room-house-num').value);
            formData.append('text', document.getElementById('room-desc').value);
            const imgFile = document.getElementById('room-image').files[0];
            if (imgFile) formData.append('image', imgFile);

            const res = await fetch('/api/rooms', { method: 'POST', body: formData });
            const data = await res.json();
            btn.innerText = 'צור חדר';
            btn.disabled = false;

            if (data.error) return alert(data.error);
            closeModal('create-room-modal');
            alert('החדר נוצר בהצלחה!');
        }

        async function appendToRoom() {
            const formData = new FormData();
            formData.append('text', document.getElementById('append-room-text').value);
            const imgFile = document.getElementById('append-room-image').files[0];
            if (imgFile) formData.append('image', imgFile);

            await fetch(`/api/rooms/${currentOpenRoomId}/items`, { method: 'POST', body: formData });
            document.getElementById('append-room-text').value = '';
            document.getElementById('append-room-image').value = '';
            openRoom(currentOpenRoomId);
        }

        async function updateProfile() {
            const formData = new FormData();
            formData.append('display_name', document.getElementById('edit-display-name').value);
            const avatarFile = document.getElementById('edit-avatar-file').files[0];
            if (avatarFile) formData.append('avatar', avatarFile);

            const res = await fetch('/api/profile', { method: 'POST', body: formData });
            const data = await res.json();
            if (data.success) {
                closeModal('edit-profile-modal');
                loadUserSession();
            }
        }

        function toggleSuggestionsDrawer() {
            const drawer = document.getElementById('suggestions-drawer');
            drawer.classList.toggle('open');
            if (drawer.classList.contains('open')) {
                if (currentUser.is_admin) {
                    showAdminThreads();
                } else {
                    activeChatTargetUser = currentUser.username;
                    loadChatMessages(currentUser.username);
                }
            }
        }

        async function showAdminThreads() {
            document.getElementById('admin-threads-list').style.display = 'block';
            document.getElementById('chat-area').style.display = 'none';
            document.getElementById('drawer-title').innerText = 'הצעות ממשתמשים';

            const res = await fetch('/api/suggestions/threads');
            const data = await res.json();
            const list = document.getElementById('admin-threads-list');
            list.innerHTML = '';

            if (data.threads.length === 0) {
                list.innerHTML = '<p style="color:#777; margin-top:20px;">אין הצעות חדשות עדיין.</p>';
                return;
            }

            data.threads.forEach(user => {
                const div = document.createElement('div');
                div.className = 'admin-chat-user-item';
                div.innerHTML = `<strong>הצעה מאת: ${user}</strong><div style="font-size:0.8rem; color:#aaa;">לחץ לפתיחת הצ'אט</div>`;
                div.onclick = () => {
                    activeChatTargetUser = user;
                    document.getElementById('admin-threads-list').style.display = 'none';
                    document.getElementById('chat-area').style.display = 'flex';
                    document.getElementById('back-to-threads-btn').style.display = 'block';
                    document.getElementById('drawer-title').innerText = `צ'אט עם ${user}`;
                    loadChatMessages(user);
                };
                list.appendChild(div);
            });
        }

        async function loadChatMessages(targetUser) {
            const res = await fetch(`/api/suggestions/${encodeURIComponent(targetUser)}`);
            const data = await res.json();
            const box = document.getElementById('chat-messages-box');
            box.innerHTML = '';

            data.messages.forEach(msg => {
                const div = document.createElement('div');
                div.className = `msg-bubble ${msg.sender_is_admin ? 'admin' : 'user'}`;
                div.innerHTML = `
                    <div style="font-size:0.75rem; color:#aaa; margin-bottom:4px;">${msg.sender_display}</div>
                    ${msg.text ? `<div>${msg.text}</div>` : ''}
                    ${msg.image ? `<img src="${msg.image}">` : ''}
                `;
                box.appendChild(div);
            });
            box.scrollTop = box.scrollHeight;
        }

        async function sendChatMessage() {
            const text = document.getElementById('chat-text-input').value.trim();
            const imgFile = document.getElementById('chat-image-input').files[0];
            if (!text && !imgFile) return;

            const formData = new FormData();
            formData.append('target_user', activeChatTargetUser);
            formData.append('text', text);
            if (imgFile) formData.append('image', imgFile);

            await fetch('/api/suggestions/send', { method: 'POST', body: formData });
            document.getElementById('chat-text-input').value = '';
            document.getElementById('chat-image-input').value = '';
            loadChatMessages(activeChatTargetUser);
        }

        loadUserSession();
    </script>
</body>
</html>
"""

# --- נתיבי API (Backend עם SQLite) ---

@app.route("/")
def index():
    return render_template_string(HTML_TEMPLATE)

@app.route("/api/me")
def get_me():
    if "username" not in session:
        return jsonify({"logged_in": False})
    conn = get_db()
    user = conn.execute("SELECT username, display_name, avatar, is_admin FROM users WHERE username = ?", (session["username"],)).fetchone()
    conn.close()
    if not user:
        return jsonify({"logged_in": False})
    return jsonify({
        "logged_in": True,
        "user": {
            "username": user["username"],
            "display_name": user["display_name"],
            "avatar": user["avatar"],
            "is_admin": bool(user["is_admin"])
        }
    })

@app.route("/api/register", methods=["POST"])
def register():
    data = request.json
    username = data.get("username", "").strip()
    password = data.get("password", "").strip()
    if not username or not password:
        return jsonify({"error": "חסרים פרטים"}), 400

    conn = get_db()
    existing = conn.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
    if existing:
        conn.close()
        return jsonify({"error": "שם המשתמש כבר תפוס"}), 400

    conn.execute('''
        INSERT INTO users (username, display_name, password, avatar, is_admin)
        VALUES (?, ?, ?, ?, ?)
    ''', (
        username,
        username,
        generate_password_hash(password),
        "https://res.cloudinary.com/demo/image/upload/v1312461204/sample.jpg",
        0
    ))
    conn.commit()
    conn.close()

    session["username"] = username
    session["is_admin"] = False
    return jsonify({"success": True})

@app.route("/api/login", methods=["POST"])
def login():
    data = request.json
    username = data.get("username", "").strip()
    password = data.get("password", "").strip()

    conn = get_db()
    user = conn.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
    conn.close()

    if not user or not check_password_hash(user["password"], password):
        return jsonify({"error": "שם משתמש או סיסמה שגויים"}), 401

    session["username"] = user["username"]
    session["is_admin"] = bool(user["is_admin"])
    return jsonify({"success": True})

@app.route("/api/logout", methods=["POST"])
def logout():
    session.clear()
    return jsonify({"success": True})

@app.route("/api/profile", methods=["POST"])
@login_required
def update_profile():
    updates = {}
    display_name = request.form.get("display_name", "").strip()
    if display_name:
        updates["display_name"] = display_name

    if "avatar" in request.files and request.files["avatar"].filename != "":
        upload_res = cloudinary.uploader.upload(request.files["avatar"])
        updates["avatar"] = upload_res["secure_url"]

    if updates:
        conn = get_db()
        if "display_name" in updates and "avatar" in updates:
            conn.execute("UPDATE users SET display_name = ?, avatar = ? WHERE username = ?", 
                         (updates["display_name"], updates["avatar"], session["username"]))
        elif "display_name" in updates:
            conn.execute("UPDATE users SET display_name = ? WHERE username = ?", 
                         (updates["display_name"], session["username"]))
        elif "avatar" in updates:
            conn.execute("UPDATE users SET avatar = ? WHERE username = ?", 
                         (updates["avatar"], session["username"]))
        conn.commit()
        conn.close()

    return jsonify({"success": True})

@app.route("/api/rooms", methods=["POST"])
@admin_required
def create_room():
    name = request.form.get("name", "").strip()
    city = request.form.get("city", "").strip()
    street = request.form.get("street", "").strip()
    house_num = request.form.get("house_num", "").strip()
    text = request.form.get("text", "").strip()

    if not name:
        return jsonify({"error": "חובה להזין שם לחדר"}), 400

    image_url = None
    if "image" in request.files and request.files["image"].filename != "":
        upload_res = cloudinary.uploader.upload(request.files["image"])
        image_url = upload_res["secure_url"]

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO rooms (name, city, street, house_num)
        VALUES (?, ?, ?, ?)
    ''', (name, city, street, house_num))
    room_id = cursor.lastrowid

    if text or image_url:
        cursor.execute('''
            INSERT INTO room_items (room_id, text, image, created_at)
            VALUES (?, ?, ?, ?)
        ''', (room_id, text, image_url, datetime.datetime.utcnow().isoformat()))

    conn.commit()
    conn.close()
    return jsonify({"success": True})

@app.route("/api/rooms/<int:room_id>")
@login_required
def get_room(room_id):
    conn = get_db()
    room = conn.execute("SELECT * FROM rooms WHERE id = ?", (room_id,)).fetchone()
    if not room:
        conn.close()
        return jsonify({"error": "חדר לא נמצא"}), 404

    items = conn.execute("SELECT text, image, created_at FROM room_items WHERE room_id = ?", (room_id,)).fetchall()
    conn.close()

    return jsonify({
        "id": room["id"],
        "name": room["name"],
        "city": room["city"],
        "street": room["street"],
        "house_num": room["house_num"],
        "items": [dict(item) for item in items]
    })

@app.route("/api/rooms/<int:room_id>/items", methods=["POST"])
@admin_required
def add_room_item(room_id):
    text = request.form.get("text", "").strip()
    image_url = None
    if "image" in request.files and request.files["image"].filename != "":
        upload_res = cloudinary.uploader.upload(request.files["image"])
        image_url = upload_res["secure_url"]

    if text or image_url:
        conn = get_db()
        conn.execute('''
            INSERT INTO room_items (room_id, text, image, created_at)
            VALUES (?, ?, ?, ?)
        ''', (room_id, text, image_url, datetime.datetime.utcnow().isoformat()))
        conn.commit()
        conn.close()

    return jsonify({"success": True})

@app.route("/api/search")
@login_required
def search_rooms():
    q = request.args.get("q", "").strip()
    if not q:
        return jsonify({"results": []})

    tokens = [t for t in q.split() if t]
    conn = get_db()
    rooms = conn.execute("SELECT * FROM rooms").fetchall()
    
    matched = []
    for room in rooms:
        room_id = room["id"]
        items = conn.execute("SELECT text FROM room_items WHERE room_id = ?", (room_id,)).fetchall()
        items_text = " ".join([item["text"] for item in items if item["text"]])
        
        searchable_blob = f"{room['name'] or ''} {room['city'] or ''} {room['street'] or ''} {room['house_num'] or ''} {items_text}".lower()

        if all(token.lower() in searchable_blob for token in tokens):
            matched.append({
                "id": room["id"],
                "name": room["name"],
                "city": room["city"],
                "street": room["street"],
                "house_num": room["house_num"]
            })
    conn.close()
    return jsonify({"results": matched})

@app.route("/api/suggestions/threads")
@admin_required
def get_suggestion_threads():
    conn = get_db()
    rows = conn.execute("SELECT DISTINCT thread_user FROM suggestions").fetchall()
    conn.close()
    users = [row["thread_user"] for row in rows]
    return jsonify({"threads": users})

@app.route("/api/suggestions/<target_user>")
@login_required
def get_suggestions(target_user):
    if not session.get("is_admin") and session["username"] != target_user:
        return jsonify({"error": "אין הרשאה"}), 403

    conn = get_db()
    rows = conn.execute("SELECT sender, sender_display, sender_is_admin, text, image, created_at FROM suggestions WHERE thread_user = ?", (target_user,)).fetchall()
    conn.close()

    msgs = [{
        "sender": r["sender"],
        "sender_display": r["sender_display"],
        "sender_is_admin": bool(r["sender_is_admin"]),
        "text": r["text"],
        "image": r["image"],
        "created_at": r["created_at"]
    } for r in rows]

    return jsonify({"messages": msgs})

@app.route("/api/suggestions/send", methods=["POST"])
@login_required
def send_suggestion():
    target_user = request.form.get("target_user")
    if not session.get("is_admin"):
        target_user = session["username"]

    text = request.form.get("text", "").strip()
    image_url = None
    if "image" in request.files and request.files["image"].filename != "":
        upload_res = cloudinary.uploader.upload(request.files["image"])
        image_url = upload_res["secure_url"]

    conn = get_db()
    user = conn.execute("SELECT display_name FROM users WHERE username = ?", (session["username"],)).fetchone()
    display_name = user["display_name"] if user else session["username"]

    conn.execute('''
        INSERT INTO suggestions (thread_user, sender, sender_display, sender_is_admin, text, image, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    ''', (
        target_user,
        session["username"],
        display_name,
        int(session.get("is_admin", False)),
        text,
        image_url,
        datetime.datetime.utcnow().isoformat()
    ))
    conn.commit()
    conn.close()
    return jsonify({"success": True})

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
