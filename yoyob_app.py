import os
import json
import uuid
from flask import Flask, request, session, redirect, url_for, send_from_directory, render_template_string, jsonify
from werkzeug.utils import secure_filename
import cv2

app = Flask(__name__)
app.secret_key = "yoyob_super_secret_key_change_me"

# Cloudinary Configuration
CLOUDINARY_CLOUD_NAME = "tgu8n7hi"
CLOUDINARY_UPLOAD_PRESET = "yoyob_preset"

DATA_FILE = "yoyob_data.json"
UPLOAD_FOLDER = "uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER

LANGUAGES = {
    "עברית": {
        "dir": "rtl", "country": "ישראל", "search": "חיפוש", "create": "＋ יצירה",
        "home": "דף הבית", "yobshort": "Yobshort", "no_shorts": "אין עדיין סרטוני Yobshort. העלה סרטון וסמן אותו כ-Yobshort!", "studio": "Yoyob Studio", "content": "תוכן", "subscriptions": "מינויים", "subs_feed": "פיד מינויים", "subs_count": "מנויים", "no_subs": "עדיין לא נרשמת לאף ערוץ.",
        "liked": "סרטונים שאהבתי", "saved": "סרטונים שמורים", "settings": "הגדרות שפה", "login": "התחברות",
        "register": "הרשמה", "logout": "התנתקות",
        "no_videos": "אין עדיין סרטונים בערוץ זה או בפיד.",
        "like": "לייק", "save": "שמור", "subscribe": "הירשם כמנוי", "subscribed": "רשום כמנוי",
        "comments": "תגובות", "add_comment": "הוסף תגובה...", "send": "שלח",
        "views": "צפיות", "cats": ["הכל", "גיימינג", "מוזיקה", "תכנות", "קומדיה", "וולוגים", "חינוך"]
    },
    "English": {
        "dir": "ltr", "country": "USA", "search": "Search", "create": "＋ Create",
        "home": "Home", "yobshort": "Yobshort", "no_shorts": "No Yobshort videos yet. Upload a video and mark it as Yobshort!", "studio": "Yoyob Studio", "content": "Content", "subscriptions": "Subscriptions", "subs_feed": "Subscriptions Feed", "subs_count": "subscribers", "no_subs": "You are not subscribed to any channels yet.",
        "liked": "Liked Videos", "saved": "Saved Videos", "settings": "Language Settings", "login": "Login",
        "register": "Sign Up", "logout": "Logout",
        "no_videos": "No videos yet.",
        "like": "Like", "save": "Save", "subscribe": "Subscribe", "subscribed": "Subscribed",
        "comments": "Comments", "add_comment": "Add a comment...", "send": "Post",
        "views": "views", "cats": ["All", "Gaming", "Music", "Coding", "Comedy", "Vlogs", "Education"]
    }
}

def load_data():
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                changed = False
                for v in data.get("videos", []):
                    if "views" not in v:
                        v["views"] = 0
                        changed = True
                    if "created_at" not in v:
                        v["created_at"] = 0
                        changed = True
                    for c in v.get("comments", []):
                        if "id" not in c:
                            c["id"] = str(uuid.uuid4())
                            changed = True
                        if "likes" not in c:
                            c["likes"] = []
                            changed = True
                        if "replies" not in c:
                            c["replies"] = []
                            changed = True
                if changed:
                    save_data(data)
                return data
        except Exception:
            pass
    data = {"language": "עברית", "users": {}, "videos": []}
    save_data(data)
    return data

def save_data(data):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def migrate_thumbnails():
    if not os.path.exists(DATA_FILE):
        return
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        changed = False
        for v in data.get("videos", []):
            if "views" not in v:
                v["views"] = 0
                changed = True
            if "created_at" not in v:
                v["created_at"] = 0
                changed = True
            if not v.get("thumb_file") and v.get("web_file") and not v["web_file"].startswith("http"):
                v_path = v.get("file_path") or os.path.join(UPLOAD_FOLDER, v.get("web_file", ""))
                if os.path.exists(v_path):
                    try:
                        cap = cv2.VideoCapture(v_path)
                        success, frame = cap.read()
                        if not success or frame is None or frame.size == 0:
                            cap.set(cv2.CAP_PROP_POS_MSEC, 1000)
                            success, frame = cap.read()
                        if success and frame is not None and frame.size > 0:
                            t_name = f"thumb_{uuid.uuid4().hex}.jpg"
                            cv2.imwrite(os.path.join(UPLOAD_FOLDER, t_name), frame)
                            v["thumb_file"] = t_name
                            changed = True
                        cap.release()
                    except Exception as e:
                        print("Migration thumb error:", e)
        if changed:
            save_data(data)
    except Exception as e:
        print("Migration error:", e)

migrate_thumbnails()

def get_lang():
    lang_name = session.get("language", "עברית")
    return lang_name, LANGUAGES.get(lang_name, LANGUAGES["עברית"])

def get_notifications(data, username):
    if not username or username not in data["users"]:
        return []
    my_subs = [uname for uname, uinf in data["users"].items() if username in uinf.get("subscribers", [])]
    notifications = []
    for v in data["videos"]:
        if v["owner"] in my_subs:
            owner_name = data["users"].get(v["owner"], {}).get("channel_name", v["owner"])
            notifications.append({
                "type": "video",
                "text": f"הערוץ @{owner_name} העלה סרטון חדש: \"{v['title']}\"",
                "link": url_for('watch', vid_id=v['id']) if not v.get('is_short') else url_for('yobshort', v=v['id']),
                "time": v.get("created_at", 0)
            })
    for v in data["videos"]:
        if v["owner"] == username:
            for c in v.get("comments", []):
                if c["user"] != username:
                    c_author = data["users"].get(c["user"], {}).get("channel_name", c["user"])
                    notifications.append({
                        "type": "comment",
                        "text": f"@{c_author} הגיב בסרטון שלך \"{v['title']}\"",
                        "link": url_for('studio_comments', vid_id=v['id']),
                        "time": 0
                    })
        for c in v.get("comments", []):
            if c["user"] == username:
                for r in c.get("replies", []):
                    if r["user"] != username:
                        r_author = data["users"].get(r["user"], {}).get("channel_name", r["user"])
                        notifications.append({
                            "type": "reply",
                            "text": f"@{r_author} השיב לתגובה שלך בסרטון \"{v['title']}\"",
                            "link": url_for('watch', vid_id=v['id']) if not v.get('is_short') else url_for('yobshort', v=v['id']),
                            "time": 0
                        })
    return notifications

def build_mixed_feed(regular_videos, short_videos):
    sections = []
    r_idx = 0
    s_idx = 0
    r_len = len(regular_videos)
    s_len = len(short_videos)

    if r_len == 0 and s_len == 0:
        return sections

    if r_len == 0:
        while s_idx < s_len:
            sections.append({"type": "shorts", "items": short_videos[s_idx:s_idx + 6]})
            s_idx += 6
        return sections

    while r_idx < r_len:
        row1 = regular_videos[r_idx:r_idx + 3]
        if row1:
            sections.append({"type": "regular", "items": row1})
            r_idx += len(row1)

        if s_idx < s_len:
            s_row = short_videos[s_idx:s_idx + 6]
            sections.append({"type": "shorts", "items": s_row})
            s_idx += len(s_row)

        if r_idx < r_len:
            rows4 = regular_videos[r_idx:r_idx + 12]
            if rows4:
                sections.append({"type": "regular", "items": rows4})
                r_idx += len(rows4)

    while s_idx < s_len:
        sections.append({"type": "shorts", "items": short_videos[s_idx:s_idx + 6]})
        s_idx += 6

    return sections

HTML_BASE = """
<!DOCTYPE html>
<html lang="he" dir="{{ t.dir }}">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Yoyob</title>
    <style>
        * { box-sizing: border-box; margin: 0; padding: 0; font-family: Arial, sans-serif; }
        body { background: #0f0f0f; color: #f1f1f1; }
        a { text-decoration: none; color: inherit; }
        button, input, select, textarea { font-family: inherit; }

        header { position: sticky; top: 0; z-index: 100; background: #0f0f0f; height: 64px; display: flex; align-items: center; justify-content: space-between; padding: 0 20px; border-bottom: 1px solid #222; }
        .logo { display: flex; align-items: center; gap: 6px; font-size: 22px; font-weight: bold; }
        .logo .play { color: #ff3333; font-size: 24px; }
        .logo .country { color: #aaa; font-size: 11px; align-self: flex-start; margin-top: 4px; }

        .search-bar { display: flex; width: 45%; max-width: 550px; }
        .search-bar input { flex: 1; background: #121212; border: 1px solid #303030; color: #f1f1f1; padding: 9px 14px; border-radius: 20px 0 0 20px; outline: none; }
        [dir="rtl"] .search-bar input { border-radius: 0 20px 20px 0; }
        .search-bar button { background: #252525; border: 1px solid #303030; color: #f1f1f1; padding: 9px 18px; cursor: pointer; font-weight: bold; border-radius: 0 20px 20px 0; }
        [dir="rtl"] .search-bar button { border-radius: 20px 0 0 20px; }

        .header-actions { display: flex; align-items: center; gap: 10px; position: relative; }
        .btn { background: #272727; color: #f1f1f1; border: none; padding: 8px 14px; border-radius: 18px; cursor: pointer; font-weight: bold; font-size: 13px; display: inline-flex; align-items: center; gap: 6px; }
        .btn:hover { background: #3a3a3a; }
        .btn-accent { background: #3ea6ff; color: #0f0f0f; }
        .btn-accent:hover { background: #65b8ff; }
        .btn-red { background: #c0392b; color: white; }
        .btn-red:hover { background: #e74c3c; }
        .btn-sm { padding: 4px 10px; font-size: 11px; border-radius: 12px; }

        .notif-wrap { position: relative; display: inline-block; }
        .notif-badge { position: absolute; top: -4px; right: -4px; background: #ff3333; color: white; font-size: 10px; padding: 2px 5px; border-radius: 50%; font-weight: bold; }
        .notif-dropdown { display: none; position: absolute; left: 0; top: 45px; width: 320px; background: #1f1f1f; border: 1px solid #333; border-radius: 12px; box-shadow: 0 8px 24px rgba(0,0,0,0.8); z-index: 1000; max-height: 400px; overflow-y: auto; }
        .notif-dropdown.open { display: block; }
        .notif-header { padding: 12px 16px; border-bottom: 1px solid #2a2a2a; font-weight: bold; font-size: 14px; background: #252525; border-radius: 12px 12px 0 0; }
        .notif-item { padding: 12px 16px; border-bottom: 1px solid #2a2a2a; font-size: 13px; display: block; color: #f1f1f1; }
        .notif-item:hover { background: #2a2a2a; }
        .notif-empty { padding: 20px; text-align: center; color: #aaa; font-size: 13px; }

        .layout { display: flex; min-height: calc(100vh - 64px); }
        aside { width: 220px; background: #0f0f0f; padding: 12px; border-inline-end: 1px solid #222; flex-shrink: 0; }
        .nav-item { display: flex; align-items: center; gap: 12px; padding: 11px 14px; border-radius: 10px; margin-bottom: 4px; font-size: 14px; cursor: pointer; }
        .nav-item:hover, .nav-item.active { background: #272727; font-weight: bold; }
        .divider { height: 1px; background: #2c2c2c; margin: 12px 0; }

        main { flex: 1; padding: 16px 24px; overflow-x: hidden; }

        .cats { display: flex; gap: 8px; overflow-x: auto; padding-bottom: 16px; }
        .cat-pill { background: #272727; color: #f1f1f1; padding: 7px 14px; border-radius: 8px; font-size: 13px; white-space: nowrap; }
        .cat-pill.active { background: #f1f1f1; color: #0f0f0f; font-weight: bold; }

        .grid { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 20px; }
        @media (max-width: 1050px) { .grid { grid-template-columns: repeat(2, minmax(0, 1fr)); } }
        @media (max-width: 650px) { .grid { grid-template-columns: 1fr; } }

        .shorts-shelf { margin: 26px 0; padding: 18px 0; border-top: 1px solid #262626; border-bottom: 1px solid #262626; }
        .shorts-shelf-header { display: flex; align-items: center; justify-content: space-between; margin-bottom: 14px; }
        .shorts-shelf-title { display: flex; align-items: center; gap: 8px; font-size: 18px; font-weight: bold; }
        .shorts-shelf-badge { background: #ff3333; color: #fff; width: 26px; height: 26px; border-radius: 7px; display: inline-flex; align-items: center; justify-content: center; font-size: 13px; }
        .shorts-shelf-grid { display: grid; grid-template-columns: repeat(6, minmax(0, 1fr)); gap: 14px; }
        @media (max-width: 1200px) { .shorts-shelf-grid { grid-template-columns: repeat(4, minmax(0, 1fr)); } }
        @media (max-width: 800px) { .shorts-shelf-grid { grid-template-columns: repeat(3, minmax(0, 1fr)); } }
        @media (max-width: 520px) { .shorts-shelf-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); } }
        .short-shelf-card { display: block; cursor: pointer; }
        .short-shelf-thumb { width: 100%; aspect-ratio: 9 / 16; border-radius: 12px; position: relative; overflow: hidden; background: #161b22; border: 1px solid #2d2d2d; display: flex; align-items: center; justify-content: center; }
        .short-shelf-thumb img { width: 100%; height: 100%; object-fit: cover; transition: transform 0.25s ease; }
        .short-shelf-card:hover .short-shelf-thumb img { transform: scale(1.04); }
        .short-shelf-gradient { position: absolute; inset: 0; background: linear-gradient(to top, rgba(0,0,0,0.85) 0%, rgba(0,0,0,0.05) 45%, rgba(0,0,0,0) 100%); display: flex; flex-direction: column; justify-content: flex-end; padding: 10px; }
        .short-shelf-card-title { font-size: 13px; font-weight: bold; line-height: 1.3; color: #fff; display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden; text-shadow: 0 1px 3px rgba(0,0,0,0.8); }
        .short-shelf-card-meta { font-size: 11px; color: #ccc; margin-top: 3px; }
        .card { cursor: pointer; }
        .thumb { width: 100%; aspect-ratio: 16/9; border-radius: 14px; display: flex; flex-direction: column; align-items: center; justify-content: center; position: relative; border: 1px solid #2d2d2d; overflow: hidden; background: #161b22; }
        .thumb img.thumb-img { width: 100%; height: 100%; object-fit: cover; position: absolute; inset: 0; }
        .thumb-overlay { position: absolute; inset: 0; background: rgba(0,0,0,0.3); display: flex; align-items: center; justify-content: center; opacity: 0; transition: opacity 0.2s; }
        .card:hover .thumb-overlay { opacity: 1; }
        .thumb-play { width: 48px; height: 48px; background: #ff3333; border-radius: 50%; display: flex; align-items: center; justify-content: center; font-size: 18px; color: white; margin-bottom: 8px; position: relative; z-index: 2; }
        .thumb-overlay .thumb-play { margin-bottom: 0; }
        .thumb-title { font-size: 13px; font-weight: bold; padding: 0 12px; text-align: center; position: relative; z-index: 2; }
        .thumb-cat { position: absolute; top: 10px; right: 10px; background: rgba(0,0,0,0.75); color: #3ea6ff; padding: 3px 8px; border-radius: 6px; font-size: 11px; font-weight: bold; z-index: 3; }

        .card-info { display: flex; gap: 10px; margin-top: 10px; }
        .avatar { width: 38px; height: 38px; border-radius: 50%; display: flex; align-items: center; justify-content: center; font-weight: bold; color: white; flex-shrink: 0; overflow: hidden; cursor: pointer; }
        .avatar img { width: 100%; height: 100%; object-fit: cover; }
        .card-title { font-weight: bold; font-size: 15px; margin-bottom: 4px; line-height: 1.3; }
        .card-meta { color: #aaa; font-size: 12px; }

        .watch-wrap { max-width: 960px; margin: 0 auto; }
        video.player { width: 100%; max-height: 540px; background: #000; border-radius: 16px; outline: none; }
        .watch-title { font-size: 20px; font-weight: bold; margin: 14px 0; }
        .watch-bar { display: flex; flex-wrap: wrap; justify-content: space-between; align-items: center; gap: 12px; padding-bottom: 14px; border-bottom: 1px solid #272727; }
        .desc-box { background: #181818; padding: 14px; border-radius: 12px; margin: 14px 0; font-size: 14px; line-height: 1.5; white-space: pre-wrap; }

        .comment-form { display: flex; gap: 10px; margin: 16px 0; }
        .comment-form input { flex: 1; background: #181818; border: 1px solid #303030; color: #f1f1f1; padding: 10px 14px; border-radius: 10px; }
        .comment-item { background: #181818; padding: 12px 14px; border-radius: 10px; margin-bottom: 10px; }
        .comment-author { color: #3ea6ff; font-weight: bold; font-size: 13px; margin-bottom: 4px; display: flex; align-items: center; gap: 6px; cursor: pointer; }
        .creator-badge { background: #3ea6ff; color: #0f0f0f; font-size: 10px; padding: 2px 6px; border-radius: 6px; font-weight: bold; }
        .comment-actions { display: flex; align-items: center; gap: 8px; margin-top: 8px; }
        .reply-box { display: none; margin-top: 10px; gap: 8px; }
        .reply-box.open { display: flex; }
        .reply-box input { flex: 1; background: #101010; border: 1px solid #333; color: #f1f1f1; padding: 7px 12px; border-radius: 8px; font-size: 13px; }
        .replies-list { margin-top: 10px; padding-inline-start: 16px; border-inline-start: 2px solid #2c2c2c; display: flex; flex-direction: column; gap: 8px; }
        .reply-item { background: #121212; padding: 8px 12px; border-radius: 8px; font-size: 13px; }

        .box { max-width: 500px; margin: 30px auto; background: #181818; padding: 24px; border-radius: 16px; }
        .box h2 { margin-bottom: 16px; }
        .form-group { margin-bottom: 14px; }
        .form-group label { display: block; margin-bottom: 6px; color: #aaa; font-size: 13px; }
        .form-group input, .form-group textarea, .form-group select { width: 100%; background: #101010; border: 1px solid #303030; color: #f1f1f1; padding: 10px; border-radius: 8px; }

        .stats-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(160px, 1fr)); gap: 14px; margin: 16px 0; }
        .stat-card { background: #181818; padding: 18px; border-radius: 12px; text-align: center; }
        .stat-val { font-size: 26px; font-weight: bold; color: #3ea6ff; }
        .studio-row { display: flex; justify-content: space-between; align-items: center; background: #181818; padding: 12px 16px; border-radius: 10px; margin-bottom: 8px; gap: 12px; flex-wrap: wrap; }
        .studio-vid-info { display: flex; align-items: center; gap: 12px; }
        .studio-thumb { width: 96px; height: 54px; border-radius: 8px; background: #101010; overflow: hidden; display: flex; align-items: center; justify-content: center; flex-shrink: 0; border: 1px solid #2d2d2d; }
        .studio-thumb img { width: 100%; height: 100%; object-fit: cover; }

        .empty { text-align: center; padding: 80px 20px; color: #aaa; }
        .alert { background: #c0392b; color: white; padding: 10px 16px; border-radius: 8px; margin-bottom: 16px; text-align: center; }

        /* Modal Overlay for Channel Popup */
        .channel-modal-overlay { display: none; position: fixed; inset: 0; background: rgba(0,0,0,0.8); z-index: 2000; align-items: center; justify-content: center; padding: 20px; }
        .channel-modal-overlay.open { display: flex; }
        .channel-modal-content { background: #181818; border: 1px solid #333; border-radius: 20px; width: 100%; max-width: 850px; max-height: 90vh; overflow-y: auto; padding: 24px; position: relative; box-shadow: 0 16px 40px rgba(0,0,0,0.9); }
        .channel-modal-close { position: absolute; top: 16px; left: 16px; background: #2a2a2a; border: none; color: white; width: 36px; height: 36px; border-radius: 50%; font-size: 16px; cursor: pointer; display: flex; align-items: center; justify-content: center; }
        .channel-modal-close:hover { background: #444; }

        @media (max-width: 768px) {
            aside { display: none; }
            .search-bar { width: 40%; }
        }
    </style>
    <script>
        function toggleReply(id) {
            var el = document.getElementById('reply-box-' + id);
            if (el) {
                el.classList.toggle('open');
                if (el.classList.contains('open')) {
                    var inp = el.querySelector('input[type="text"]');
                    if (inp) inp.focus();
                }
            }
        }
        function toggleNotifications() {
            var box = document.getElementById('notifDropdown');
            if (box) box.classList.toggle('open');
        }

        // Open/Close Channel Popup Modal
        async function openChannelModal(username) {
            const overlay = document.getElementById('channelModalOverlay');
            const inner = document.getElementById('channelModalInner');
            inner.innerHTML = '<div style="text-align:center; padding:40px; color:#aaa;">טוען ערוץ...</div>';
            overlay.classList.add('open');

            try {
                const res = await fetch('/api/channel_modal/' + username);
                const html = await res.text();
                inner.innerHTML = html;
            } catch (e) {
                inner.innerHTML = '<div style="text-align:center; color:#ff3333; padding:40px;">שגיאה בטעינת ערוץ זה.</div>';
            }
        }

        function closeChannelModal() {
            document.getElementById('channelModalOverlay').classList.remove('open');
        }
    </script>
</head>
<body>

<header>
    <a href="{{ url_for('index') }}" class="logo">
        <span class="play">▶</span>
        <span>Yoyob</span>
        <span class="country">{{ t.country }}</span>
    </a>

    <form class="search-bar" action="{{ url_for('index') }}" method="get">
        <input type="text" name="q" placeholder="{{ t.search }}" value="{{ request.args.get('q', '') }}">
        <button type="submit">{{ t.search }}</button>
    </form>

    <div class="header-actions">
        {% if current_user %}
            {% set notifs = get_notifications(data, current_user) %}
            <div class="notif-wrap">
                <button type="button" class="btn" onclick="toggleNotifications()" title="עדכונים והודעות">
                    🔔 {% if notifs|length > 0 %}<span class="notif-badge">{{ notifs|length }}</span>{% endif %}
                </button>
                <div class="notif-dropdown" id="notifDropdown">
                    <div class="notif-header">🔔 עדכונים לערוצים שנרשמת / תגובות</div>
                    {% if not notifs %}
                        <div class="notif-empty">אין עדכונים חדשים כרגע.</div>
                    {% else %}
                        {% for n in notifs|reverse %}
                            <a href="{{ n.link }}" class="notif-item">{{ n.text }}</a>
                        {% endfor %}
                    {% endif %}
                </div>
            </div>
        {% endif %}

        <a href="{{ url_for('settings') }}" class="btn">⚙️</a>
        <a href="{{ url_for('upload') }}" class="btn">{{ t.create }}</a>
        {% if current_user %}
            {% set u = data.users[current_user] %}
            <button type="button" class="btn" onclick="openChannelModal('{{ current_user }}')" style="background: {{ u.avatar_color }}; color: white;">
                👤 {{ u.channel_name }}
            </button>
            <a href="{{ url_for('logout') }}" class="btn btn-red">{{ t.logout }}</a>
        {% else %}
            <a href="{{ url_for('auth') }}" class="btn btn-accent">👤 {{ t.login }}</a>
        {% endif %}
    </div>
</header>

<div class="layout">
    <aside>
        <a href="{{ url_for('index') }}" class="nav-item {{ 'active' if active_nav == 'home' else '' }}">⌂ &nbsp; {{ t.home }}</a>
        <a href="{{ url_for('yobshort') }}" class="nav-item {{ 'active' if active_nav == 'yobshort' else '' }}">📱 &nbsp; {{ t.yobshort }}</a>
        <a href="{{ url_for('studio') }}" class="nav-item {{ 'active' if active_nav in ['studio', 'studio_content'] else '' }}">🎬 &nbsp; {{ t.studio }}</a>
        {% if current_user %}
            <a href="{{ url_for('studio_content') }}" class="nav-item {{ 'active' if active_nav == 'studio_content' else '' }}" style="padding-inline-start: 32px; font-size: 13px;">📁 &nbsp; {{ t.content }}</a>
        {% endif %}
        <a href="{{ url_for('subscriptions') }}" class="nav-item {{ 'active' if active_nav == 'subs' else '' }}">▰ &nbsp; {{ t.subscriptions }}</a>
        <a href="{{ url_for('subscriptions_feed') }}" class="nav-item {{ 'active' if active_nav == 'subs_feed' else '' }}">📺 &nbsp; {{ t.subs_feed }}</a>
        <a href="{{ url_for('liked') }}" class="nav-item {{ 'active' if active_nav == 'liked' else '' }}">♡ &nbsp; {{ t.liked }}</a>
        <a href="{{ url_for('saved_videos') }}" class="nav-item {{ 'active' if active_nav == 'saved' else '' }}">💾 &nbsp; {{ t.saved }}</a>
        <div class="divider"></div>
        {% if current_user %}
            {% for uname, uinfo in data.users.items() %}
                {% if current_user in uinfo.get('subscribers', []) %}
                    <div class="nav-item" onclick="openChannelModal('{{ uname }}')">● &nbsp; {{ uinfo.channel_name }}</div>
                {% endif %}
            {% endfor %}
        {% endif %}
    </aside>

    <main>
        {{ content | safe }}
    </main>
</div>

<!-- Global Channel Modal Popup -->
<div class="channel-modal-overlay" id="channelModalOverlay" onclick="if(event.target === this) closeChannelModal();">
    <div class="channel-modal-content">
        <button type="button" class="channel-modal-close" onclick="closeChannelModal()">✕</button>
        <div id="channelModalInner"></div>
    </div>
</div>

</body>
</html>
"""

def render_page(content_html, active_nav="home", **kwargs):
    data = load_data()
    lang_name, t = get_lang()
    current_user = session.get("user")
    if current_user and current_user not in data["users"]:
        session.pop("user", None)
        current_user = None
    rendered_content = render_template_string(content_html, data=data, t=t, lang_name=lang_name, current_user=current_user, get_notifications=get_notifications, **kwargs)
    return render_template_string(HTML_BASE, content=rendered_content, data=data, t=t, current_user=current_user, active_nav=active_nav, get_notifications=get_notifications)

@app.route("/uploads/<path:filename>")
def uploaded_file(filename):
    if filename.startswith("http"):
        return redirect(filename)
    return send_from_directory(app.config["UPLOAD_FOLDER"], filename)

@app.route("/")
def index():
    data = load_data()
    _, t = get_lang()
    all_vids = list(reversed(data["videos"]))

    cat_idx = request.args.get("cat", type=int, default=0)
    q = request.args.get("q", "").strip().lower()
    channel = request.args.get("channel", "")

    if channel:
        # If any old channel links are used, open the modal via JS or fallback
        pass
    elif 0 < cat_idx < len(t["cats"]):
        chosen_cat = t["cats"][cat_idx]
        all_vids = [v for v in all_vids if v.get("category"] == chosen_cat or v.get("cat_idx") == cat_idx]

    if q:
        all_vids = [v for v in all_vids if q in v["title"].lower() or q in v.get("description", "").lower() or q in v["owner"].lower()]

    regular_videos = [v for v in all_vids if not v.get("is_short")]
    short_videos = [v for v in all_vids if v.get("is_short")]
    feed_sections = build_mixed_feed(regular_videos, short_videos)

    html = """
    <div class="cats">
        {% for c in t.cats %}
            <a href="{{ url_for('index', cat=loop.index0) }}" class="cat-pill {{ 'active' if cat_idx == loop.index0 else '' }}">{{ c }}</a>
        {% endfor %}
    </div>
    
    {% if not feed_sections %}
        <div class="empty">
            <div style="font-size: 48px; margin-bottom: 12px;">🎬</div>
            <p style="margin-bottom: 18px;">{{ t.no_videos }}</p>
            <a href="{{ url_for('upload') }}" class="btn btn-accent">{{ t.create }}</a>
        </div>
    {% else %}
        {% for sec in feed_sections %}
            {% if sec.type == 'regular' %}
                <div class="grid" style="margin-bottom: 20px;">
                    {% for v in sec['items'] %}
                        {% set owner = data.users.get(v.owner, {}) %}
                        {% set ch_name = owner.get('channel_name', v.owner) %}
                        <div class="card">
                            <a href="{{ url_for('watch', vid_id=v.id) }}">
                                <div class="thumb" style="border-color: {{ v.get('thumb_color', '#333') }};">
                                    {% if v.category %}<span class="thumb-cat">{{ v.category }}</span>{% endif %}
                                    {% if v.get('thumb_file') %}
                                        <img class="thumb-img" src="{{ url_for('uploaded_file', filename=v.thumb_file) }}" alt="{{ v.title }}">
                                        <div class="thumb-overlay"><div class="thumb-play">▶</div></div>
                                    {% else %}
                                        <video class="thumb-img" preload="metadata" muted playsinline style="object-fit:cover;"><source src="{{ url_for('uploaded_file', filename=v.get('web_file') or '') }}#t=0.5"></video>
                                        <div class="thumb-overlay"><div class="thumb-play">▶</div></div>
                                    {% endif %}
                                </div>
                            </a>
                            <div class="card-info">
                                <div class="avatar" onclick="openChannelModal('{{ v.owner }}')" style="background: {{ owner.get('avatar_color', '#16a085') }};">
                                    {% if owner.get('avatar_file') %}
                                        <img src="{{ url_for('uploaded_file', filename=owner.avatar_file) }}">
                                    {% else %}
                                        {{ ch_name[0]|upper }}
                                    {% endif %}
                                </div>
                                <div>
                                    <a href="{{ url_for('watch', vid_id=v.id) }}"><div class="card-title">{{ v.title }}</div></a>
                                    <div class="card-meta">
                                        <span onclick="openChannelModal('{{ v.owner }}')" style="cursor: pointer; color: #aaa;">{{ ch_name }}</span> • {{ v.get('views', 0) }} {{ t.views }}
                                    </div>
                                </div>
                            </div>
                        </div>
                    {% endfor %}
                </div>
            {% elif sec.type == 'shorts' %}
                <div class="shorts-shelf">
                    <div class="shorts-shelf-header">
                        <a href="{{ url_for('yobshort') }}" class="shorts-shelf-title">
                            <span class="shorts-shelf-badge">▶</span>
                            <span>{{ t.yobshort }}</span>
                        </a>
                        <a href="{{ url_for('yobshort') }}" class="btn btn-sm">{{ t.yobshort }} ←</a>
                    </div>
                    <div class="shorts-shelf-grid">
                        {% for sv in sec['items'] %}
                            {% set s_owner = data.users.get(sv.owner, {}) %}
                            {% set s_ch = s_owner.get('channel_name', sv.owner) %}
                            <a href="{{ url_for('yobshort', v=sv.id) }}" class="short-shelf-card">
                                <div class="short-shelf-thumb" style="border-color: {{ sv.get('thumb_color', '#333') }};">
                                    {% if sv.get('thumb_file') %}
                                        <img src="{{ url_for('uploaded_file', filename=sv.thumb_file) }}" alt="{{ sv.title }}">
                                    {% else %}
                                        <video style="width:100%; height:100%; object-fit:cover; position:absolute; inset:0;" preload="auto" muted playsinline><source src="{{ url_for('uploaded_file', filename=sv.get('web_file') or '') }}#t=0.5"></video>
                                        <div class="thumb-play" style="position:relative; z-index:2; margin-bottom: 24px;">▶</div>
                                    {% endif %}
                                    <div class="short-shelf-gradient">
                                        <div class="short-shelf-card-title">{{ sv.title }}</div>
                                        <div class="short-shelf-card-meta">{{ s_ch }} • {{ sv.get('views', 0) }} {{ t.views }}</div>
                                    </div>
                                </div>
                            </a>
                        {% endfor %}
                    </div>
                </div>
            {% endif %}
        {% endfor %}
    {% endif %}
    """
    return render_page(html, active_nav="home", feed_sections=feed_sections, cat_idx=cat_idx)

@app.route("/api/channel_modal/<channel_name>")
def channel_modal_api(channel_name):
    data = load_data()
    _, t = get_lang()
    user_info = data["users"].get(channel_name)
    if not user_info:
        return "<div style='padding:20px; text-align:center;'>הערוץ אינו נמצא.</div>"

    ch_name = user_info.get("channel_name", channel_name)
    ch_videos = [v for v in reversed(data["videos"]) if v["owner"] == channel_name]
    total_views = sum(v.get("views", 0) for v in ch_videos)
    subs_count = len(user_info.get("subscribers", []))
    is_sub = session.get("user") in user_info.get("subscribers", [])

    return render_template_string("""
    <div style="width: 100%;">
        <div style="width: 100%; height: 140px; background: linear-gradient(135deg, #222, #111); border-radius: 12px; border: 1px solid #2d2d2d; position: relative;"></div>

        <div style="display: flex; align-items: flex-start; justify-content: space-between; padding: 16px 4px; gap: 16px; flex-wrap: wrap; margin-top: -45px; position: relative; z-index: 2;">
            <div style="display: flex; align-items: flex-end; gap: 16px; flex-wrap: wrap;">
                <div class="avatar" style="width: 100px; height: 100px; border-radius: 50%; font-size: 40px; border: 4px solid #181818; background: {{ user_info.get('avatar_color', '#16a085') }}; box-shadow: 0 4px 14px rgba(0,0,0,0.6);">
                    {% if user_info.get('avatar_file') %}
                        <img src="{{ url_for('uploaded_file', filename=user_info.avatar_file) }}" alt="{{ ch_name }}">
                    {% else %}
                        {{ ch_name[0]|upper }}
                    {% endif %}
                </div>
                <div>
                    <h2 style="font-size: 22px; font-weight: bold; margin-bottom: 4px;">{{ ch_name }}</h2>
                    <div class="card-meta" style="font-size: 13px; color: #aaa; margin-bottom: 4px;">
                        @{{ channel_name }} &bull; <strong style="color: #f1f1f1;">{{ subs_count }}</strong> {{ t.subs_count }} &bull; <strong style="color: #f1f1f1;">{{ total_views }}</strong> {{ t.views }} בערוץ
                    </div>
                    <div style="font-size: 13px; color: #ccc;">{{ user_info.get('bio', '') }}</div>
                </div>
            </div>

            <div>
                {% if current_user and current_user != channel_name %}
                    <button type="button" id="modal-sub-btn" onclick="asyncAction('{{ url_for('subscribe_channel', owner_name=channel_name, vid_id='none') }}', handleModalSubRes)" class="btn" style="background: {{ '#333' if is_sub else '#f1f1f1' }}; color: {{ '#fff' if is_sub else '#0f0f0f' }}; padding: 9px 18px; font-size: 13px; font-weight: bold;">
                        <span id="modal-sub-txt">{{ t.subscribed if is_sub else t.subscribe }}</span>
                    </button>
                {% elif current_user == channel_name %}
                    <a href="{{ url_for('studio') }}" class="btn btn-accent" style="padding: 9px 16px; font-size: 13px;">ניהול ערוץ (Studio)</a>
                {% endif %}
            </div>
        </div>

        <div class="divider" style="margin: 16px 0;"></div>

        <h3 style="margin-bottom: 14px; font-size: 16px;">סרטוני הערוץ</h3>

        {% if not ch_videos %}
            <div class="empty" style="padding: 30px;">
                <p>אין עדיין סרטונים בערוץ זה.</p>
            </div>
        {% else %}
            <div class="grid" style="grid-template-columns: repeat(auto-fill, minmax(220px, 1fr)); gap: 14px;">
                {% for v in ch_videos %}
                    <a href="{{ url_for('watch', vid_id=v.id) }}" class="card" onclick="closeChannelModal();">
                        <div class="thumb" style="border-color: {{ v.get('thumb_color', '#333') }};">
                            {% if v.category %}<span class="thumb-cat">{{ v.category }}</span>{% endif %}
                            {% if v.get('thumb_file') %}
                                <img class="thumb-img" src="{{ url_for('uploaded_file', filename=v.thumb_file) }}" alt="{{ v.title }}">
                                <div class="thumb-overlay"><div class="thumb-play">▶</div></div>
                            {% else %}
                                <video class="thumb-img" preload="metadata" muted playsinline style="object-fit:cover;"><source src="{{ url_for('uploaded_file', filename=v.get('web_file') or '') }}#t=0.5"></video>
                                <div class="thumb-overlay"><div class="thumb-play">▶</div></div>
                            {% endif %}
                        </div>
                        <div class="card-info" style="margin-top: 6px;">
                            <div>
                                <div class="card-title" style="font-size: 13px;">{{ v.title }}</div>
                                <div class="card-meta" style="font-size: 11px;">{{ v.get('views', 0) }} {{ t.views }}</div>
                            </div>
                        </div>
                    </a>
                {% endfor %}
            </div>
        {% endif %}
    </div>

    <script>
        function handleModalSubRes(data) {
            const btn = document.getElementById('modal-sub-btn');
            const txt = document.getElementById('modal-sub-txt');
            if (btn) {
                btn.style.background = data.subscribed ? '#333' : '#f1f1f1';
                btn.style.color = data.subscribed ? '#fff' : '#0f0f0f';
            }
            if (txt) {
                txt.textContent = data.subscribed ? '{{ t.subscribed }}' : '{{ t.subscribe }}';
            }
        }
    </script>
    """, data=data, t=t, user_info=user_info, channel_name=channel_name, ch_videos=ch_videos, total_views=total_views, subs_count=subs_count, is_sub=is_sub, current_user=session.get("user"))

@app.route("/yobshort")
def yobshort():
    data = load_data()
    u = session.get("user")
    shorts = [v for v in reversed(data["videos"]) if v.get("is_short")]
    start_vid = request.args.get("v", "")

    shorts_comments_map = {}
    for v in shorts:
        c_list = []
        for c in reversed(v.get("comments", [])):
            c_author = data["users"].get(c["user"], {}).get("channel_name", c["user"])
            r_list = []
            for r in c.get("replies", []):
                r_author = data["users"].get(r["user"], {}).get("channel_name", r["user"])
                r_list.append({
                    "id": r.get("id", ""),
                    "user": r["user"],
                    "author": r_author,
                    "is_creator": (r["user"] == v["owner"]),
                    "text": r["text"]
                })
            c_list.append({
                "id": c.get("id", ""),
                "user": c["user"],
                "author": c_author,
                "is_creator": (c["user"] == v["owner"]),
                "text": c["text"],
                "likes_count": len(c.get("likes", [])),
                "liked": (u in c.get("likes", [])) if u else False,
                "replies": r_list
            })
        shorts_comments_map[v["id"]] = c_list

    shorts_comments_json = json.dumps(shorts_comments_map, ensure_ascii=False)

    html = """
    <style>
        .shorts-stage {
            height: calc(100vh - 96px);
            display: flex;
            justify-content: center;
            align-items: center;
            gap: 18px;
            position: relative;
        }
        .shorts-wrapper {
            height: 100%;
            display: flex;
            justify-content: center;
            align-items: center;
            position: relative;
            flex-shrink: 0;
        }
        .shorts-feed {
            height: 100%;
            max-height: 780px;
            aspect-ratio: 9 / 16;
            overflow-y: scroll;
            scroll-snap-type: y mandatory;
            border-radius: 22px;
            background: #000;
            box-shadow: 0 12px 40px rgba(0,0,0,0.75);
            border: 1px solid #2c2c2c;
            scrollbar-width: none;
        }
        .shorts-feed::-webkit-scrollbar { display: none; }
        .short-slide {
            width: 100%;
            height: 100%;
            scroll-snap-align: start;
            scroll-snap-stop: always;
            position: relative;
            background: #000;
            display: flex;
            align-items: center;
            justify-content: center;
            overflow: hidden;
        }
        .short-slide video {
            width: 100%;
            height: 100%;
            object-fit: cover;
            cursor: pointer;
        }
        .short-overlay {
            position: absolute;
            inset: 0;
            background: linear-gradient(to top, rgba(0,0,0,0.85) 0%, rgba(0,0,0,0) 40%, rgba(0,0,0,0.25) 100%);
            pointer-events: none;
            display: flex;
            flex-direction: column;
            justify-content: space-between;
            padding: 18px;
        }
        .short-top-badge {
            align-self: flex-start;
            background: rgba(255, 51, 51, 0.9);
            color: #fff;
            font-weight: bold;
            font-size: 12px;
            padding: 5px 12px;
            border-radius: 20px;
            letter-spacing: 0.5px;
        }
        .short-bottom {
            display: flex;
            justify-content: space-between;
            align-items: flex-end;
            gap: 12px;
            pointer-events: auto;
        }
        .short-info {
            flex: 1;
            min-width: 0;
        }
        .short-channel-row {
            display: flex;
            align-items: center;
            gap: 10px;
            margin-bottom: 8px;
            flex-wrap: wrap;
        }
        .short-channel {
            display: flex;
            align-items: center;
            gap: 8px;
            font-weight: bold;
            font-size: 14px;
            cursor: pointer;
        }
        .short-title {
            font-size: 15px;
            font-weight: bold;
            line-height: 1.35;
            margin-bottom: 4px;
            word-wrap: break-word;
        }
        .short-desc {
            font-size: 12px;
            color: #ccc;
            display: -webkit-box;
            -webkit-line-clamp: 2;
            -webkit-box-orient: vertical;
            overflow: hidden;
        }
        .short-actions {
            display: flex;
            flex-direction: column;
            align-items: center;
            gap: 14px;
        }
        .short-action-btn {
            width: 46px;
            height: 46px;
            border-radius: 50%;
            background: rgba(39, 39, 39, 0.85);
            border: 1px solid rgba(255,255,255,0.12);
            color: #fff;
            font-size: 18px;
            display: flex;
            align-items: center;
            justify-content: center;
            cursor: pointer;
            transition: transform 0.15s, background 0.15s;
        }
        .short-action-btn:hover {
            transform: scale(1.08);
            background: rgba(65, 65, 65, 0.95);
        }
        .short-action-btn.liked, .short-action-btn.saved, .short-action-btn.chat-open {
            background: #3ea6ff;
            color: #0f0f0f;
        }
        .short-action-label {
            font-size: 11px;
            font-weight: bold;
            text-align: center;
            margin-top: 3px;
            text-shadow: 0 1px 3px rgba(0,0,0,0.9);
        }
        .shorts-nav-arrows {
            display: flex;
            flex-direction: column;
            gap: 12px;
            margin-inline-start: 14px;
        }
        .shorts-arrow {
            width: 44px;
            height: 44px;
            border-radius: 50%;
            background: #272727;
            border: 1px solid #383838;
            color: #fff;
            font-size: 18px;
            cursor: pointer;
            display: flex;
            align-items: center;
            justify-content: center;
        }
        .shorts-arrow:hover { background: #3a3a3a; }

        .short-chat-panel {
            width: 360px;
            height: 100%;
            max-height: 780px;
            background: #181818;
            border: 1px solid #2c2c2c;
            border-radius: 22px;
            display: none;
            flex-direction: column;
            overflow: hidden;
            box-shadow: 0 12px 36px rgba(0,0,0,0.65);
        }
        .short-chat-panel.open {
            display: flex;
        }
        .short-chat-header {
            padding: 14px 18px;
            border-bottom: 1px solid #2a2a2a;
            display: flex;
            justify-content: space-between;
            align-items: center;
            font-weight: bold;
            font-size: 15px;
            background: #1f1f1f;
        }
        .short-chat-close {
            background: #2d2d2d;
            border: none;
            color: #fff;
            width: 30px;
            height: 30px;
            border-radius: 50%;
            cursor: pointer;
            font-size: 14px;
            display: flex;
            align-items: center;
            justify-content: center;
        }
        .short-chat-close:hover { background: #3f3f3f; }
        .short-chat-list {
            flex: 1;
            overflow-y: auto;
            padding: 14px;
            display: flex;
            flex-direction: column;
            gap: 10px;
        }
        .short-chat-empty {
            text-align: center;
            color: #888;
            margin: auto;
            font-size: 13px;
            padding: 20px;
        }
        .short-chat-item {
            background: #121212;
            padding: 10px 12px;
            border-radius: 12px;
            border: 1px solid #252525;
            font-size: 13px;
        }
        .short-chat-form {
            padding: 12px;
            border-top: 1px solid #2a2a2a;
            display: flex;
            gap: 8px;
            background: #1f1f1f;
        }
        .short-chat-form input {
            flex: 1;
            background: #101010;
            border: 1px solid #333;
            color: #f1f1f1;
            padding: 9px 12px;
            border-radius: 18px;
            font-size: 13px;
            outline: none;
        }

        @media (max-width: 900px) {
            .short-chat-panel.open {
                position: fixed;
                bottom: 0;
                left: 0;
                right: 0;
                width: 100%;
                height: 62vh;
                max-height: 62vh;
                border-radius: 20px 20px 0 0;
                z-index: 250;
            }
        }
        @media (max-width: 600px) {
            .shorts-stage { height: calc(100vh - 80px); }
            .shorts-feed { width: 100%; max-height: 100%; border-radius: 14px; }
            .shorts-nav-arrows { display: none; }
        }
    </style>

    {% if not shorts %}
        <div class="empty">
            <div style="font-size: 52px; margin-bottom: 12px;">📱</div>
            <h3 style="margin-bottom: 8px;">Yobshort</h3>
            <p style="margin-bottom: 18px;">{{ t.no_shorts }}</p>
            <a href="{{ url_for('upload') }}" class="btn btn-accent">{{ t.create }}</a>
        </div>
    {% else %}
        <div class="shorts-stage">
            <div class="shorts-wrapper">
                <div class="shorts-feed" id="shortsFeed">
                    {% for v in shorts %}
                        {% set owner = data.users.get(v.owner, {}) %}
                        {% set ch_name = owner.get('channel_name', v.owner) %}
                        {% set filename = v.get('web_file') or '' %}
                        {% set liked = current_user in v.get('likes', []) %}
                        {% set saved = current_user in v.get('saves', []) %}
                        {% set is_sub = current_user in owner.get('subscribers', []) %}
                        <div class="short-slide" id="short-{{ v.id }}" data-vid-id="{{ v.id }}">
                            <video loop playsinline {% if v.get('thumb_file') %}poster="{{ url_for('uploaded_file', filename=v.thumb_file) }}"{% endif %} onclick="this.paused ? this.play() : this.pause()">
                                <source src="{{ url_for('uploaded_file', filename=filename) }}">
                            </video>

                            <div class="short-overlay">
                                <div class="short-top-badge">📱 Yobshort</div>

                                <div class="short-bottom">
                                    <div class="short-info">
                                        <div class="short-channel-row">
                                            <div onclick="openChannelModal('{{ v.owner }}')" class="short-channel">
                                                <div class="avatar" style="width:34px; height:34px; font-size:14px; background: {{ owner.get('avatar_color', '#16a085') }};">
                                                    {% if owner.get('avatar_file') %}
                                                        <img src="{{ url_for('uploaded_file', filename=owner.avatar_file) }}">
                                                    {% else %}
                                                        {{ ch_name[0]|upper }}
                                                    {% endif %}
                                                </div>
                                                <span>@{{ ch_name }}</span>
                                            </div>
                                            {% if current_user != v.owner %}
                                                <button type="button" id="short-sub-btn-{{ v.id }}" onclick="toggleShortSub('{{ v.owner }}', '{{ v.id }}')" class="btn btn-sm" style="background: {{ '#333' if is_sub else '#f1f1f1' }}; color: {{ '#fff' if is_sub else '#0f0f0f' }}; font-weight: bold;">
                                                    <span id="short-sub-text-{{ v.id }}">{{ t.subscribed if is_sub else t.subscribe }}</span>
                                                </button>
                                            {% endif %}
                                        </div>
                                        <div class="short-title">{{ v.title }}</div>
                                        {% if v.description %}
                                            <div class="short-desc">{{ v.description }}</div>
                                        {% endif %}
                                    </div>

                                    <div class="short-actions">
                                        <div>
                                            <button type="button" id="like-btn-{{ v.id }}" onclick="toggleShortLike('{{ v.id }}')" class="short-action-btn {{ 'liked' if liked else '' }}">👍</button>
                                            <div class="short-action-label" id="like-count-{{ v.id }}">{{ v.get('likes', [])|length }}</div>
                                        </div>

                                        <div>
                                            <button type="button" id="save-btn-{{ v.id }}" onclick="toggleShortSave('{{ v.id }}')" class="short-action-btn {{ 'saved' if saved else '' }}" title="{{ t.saved }}">💾</button>
                                            <div class="short-action-label" id="save-count-{{ v.id }}">{{ v.get('saves', [])|length }}</div>
                                        </div>

                                        <div>
                                            <button type="button" id="chat-btn-{{ v.id }}" onclick="toggleShortChat('{{ v.id }}')" class="short-action-btn" title="{{ t.comments }}">💬</button>
                                            <div class="short-action-label" id="comment-count-{{ v.id }}">{{ v.get('comments', [])|length }}</div>
                                        </div>
                                    </div>
                                </div>
                            </div>
                        </div>
                    {% endfor %}
                </div>

                <div class="shorts-nav-arrows">
                    <button type="button" class="shorts-arrow" onclick="scrollShort(-1)" title="הקודם">▲</button>
                    <button type="button" class="shorts-arrow" onclick="scrollShort(1)" title="הבא">▼</button>
                </div>
            </div>

            <div class="short-chat-panel" id="shortChatPanel">
                <div class="short-chat-header">
                    <span>💬 {{ t.comments }} (<span id="chatHeaderCount">0</span>)</span>
                    <button type="button" class="short-chat-close" onclick="closeShortChat()">✕</button>
                </div>
                <div class="short-chat-list" id="shortChatList"></div>
                <form class="short-chat-form" onsubmit="submitShortComment(event)">
                    <input type="text" id="shortChatInput" placeholder="{{ t.add_comment }}" required>
                    <button type="submit" class="btn btn-accent">{{ t.send }}</button>
                </form>
            </div>
        </div>

        <script>
            const feed = document.getElementById('shortsFeed');
            const slides = document.querySelectorAll('.short-slide');
            const chatPanel = document.getElementById('shortChatPanel');
            const chatList = document.getElementById('shortChatList');
            const chatHeaderCount = document.getElementById('chatHeaderCount');
            const chatInput = document.getElementById('shortChatInput');

            const commentsStore = {{ shorts_comments_json | safe }};
            let activeShortId = slides.length ? slides[0].dataset.vidId : null;
            let openChatShortId = null;

            function escapeHtml(str) {
                const div = document.createElement('div');
                div.textContent = str || '';
                return div.innerHTML;
            }

            function scrollShort(dir) {
                if (!feed) return;
                feed.scrollBy({ top: dir * feed.clientHeight, behavior: 'smooth' });
            }

            async function toggleShortLike(vidId) {
                try {
                    const res = await fetch('/like/' + vidId, {
                        method: 'POST',
                        headers: { 'X-Requested-With': 'XMLHttpRequest' }
                    });
                    const data = await res.json();
                    if (data.redirect) {
                        window.location.href = data.redirect;
                        return;
                    }
                    if (data.ok) {
                        const btn = document.getElementById('like-btn-' + vidId);
                        const lbl = document.getElementById('like-count-' + vidId);
                        if (btn) btn.classList.toggle('liked', data.liked);
                        if (lbl) lbl.textContent = data.count;
                    }
                } catch (e) {
                    console.error(e);
                }
            }

            async function toggleShortSave(vidId) {
                try {
                    const res = await fetch('/save/' + vidId, {
                        method: 'POST',
                        headers: { 'X-Requested-With': 'XMLHttpRequest' }
                    });
                    const data = await res.json();
                    if (data.redirect) {
                        window.location.href = data.redirect;
                        return;
                    }
                    if (data.ok) {
                        const btn = document.getElementById('save-btn-' + vidId);
                        const lbl = document.getElementById('save-count-' + vidId);
                        if (btn) btn.classList.toggle('saved', data.saved);
                        if (lbl) lbl.textContent = data.count;
                    }
                } catch (e) {
                    console.error(e);
                }
            }

            async function toggleShortSub(ownerName, vidId) {
                try {
                    const res = await fetch('/subscribe/' + ownerName + '/' + vidId, {
                        method: 'POST',
                        headers: { 'X-Requested-With': 'XMLHttpRequest' }
                    });
                    const data = await res.json();
                    if (data.redirect) {
                        window.location.href = data.redirect;
                        return;
                    }
                    if (data.ok) {
                        const btn = document.getElementById('short-sub-btn-' + vidId);
                        const txt = document.getElementById('short-sub-text-' + vidId);
                        if (btn) {
                            btn.style.background = data.subscribed ? '#333' : '#f1f1f1';
                            btn.style.color = data.subscribed ? '#fff' : '#0f0f0f';
                        }
                        if (txt) {
                            txt.textContent = data.subscribed ? '{{ t.subscribed }}' : '{{ t.subscribe }}';
                        }
                    }
                } catch (e) {
                    console.error(e);
                }
            }

            function renderShortChat(vidId) {
                const list = commentsStore[vidId] || [];
                chatHeaderCount.textContent = list.length;
                if (!list.length) {
                    chatList.innerHTML = '<div class="short-chat-empty">אין עדיין תגובות לסרטון זה. היה הראשון להגיב!</div>';
                    return;
                }
                chatList.innerHTML = list.map(c => {
                    const badge = c.is_creator ? '<span class="creator-badge">יוצר הערוץ</span>' : '';
                    const likedCls = c.liked ? 'btn-accent' : '';
                    const repliesHtml = (c.replies && c.replies.length) ? (
                        '<div class="replies-list">' + c.replies.map(r => {
                            const rBadge = r.is_creator ? '<span class="creator-badge">יוצר הערוץ</span>' : '';
                            return `<div class="reply-item">
                                <div class="comment-author"><span>@${escapeHtml(r.author)}</span>${rBadge}</div>
                                <div>${escapeHtml(r.text)}</div>
                            </div>`;
                        }).join('') + '</div>'
                    ) : '';

                    return `<div class="short-chat-item">
                        <div class="comment-author"><span>@${escapeHtml(c.author)}</span>${badge}</div>
                        <div style="margin:4px 0;">${escapeHtml(c.text)}</div>
                        <div class="comment-actions">
                            <button type="button" class="btn btn-sm ${likedCls}" onclick="toggleShortCommentLike('${vidId}', '${c.id}')">👍 ${c.likes_count}</button>
                            <button type="button" class="btn btn-sm" onclick="toggleShortReplyBox('${c.id}')">💬 להגיב</button>
                        </div>
                        <form id="short-reply-box-${c.id}" class="reply-box" onsubmit="submitShortReply(event, '${vidId}', '${c.id}')">
                            <input type="text" placeholder="הגב ל-@${escapeHtml(c.author)}..." required>
                            <button type="submit" class="btn btn-sm btn-accent">{{ t.send }}</button>
                        </form>
                        ${repliesHtml}
                    </div>`;
                }).join('');
            }

            function toggleShortChat(vidId) {
                if (openChatShortId === vidId && chatPanel.classList.contains('open')) {
                    closeShortChat();
                    return;
                }
                openChatShortId = vidId;
                document.querySelectorAll('[id^="chat-btn-"]').forEach(b => b.classList.remove('chat-open'));
                const btn = document.getElementById('chat-btn-' + vidId);
                if (btn) btn.classList.add('chat-open');
                renderShortChat(vidId);
                chatPanel.classList.add('open');
            }

            function closeShortChat() {
                openChatShortId = null;
                chatPanel.classList.remove('open');
                document.querySelectorAll('[id^="chat-btn-"]').forEach(b => b.classList.remove('chat-open'));
            }

            function toggleShortReplyBox(commentId) {
                const box = document.getElementById('short-reply-box-' + commentId);
                if (box) {
                    box.classList.toggle('open');
                    if (box.classList.contains('open')) {
                        const inp = box.querySelector('input');
                        if (inp) inp.focus();
                    }
                }
            }

            async function submitShortComment(e) {
                e.preventDefault();
                if (!openChatShortId) return;
                const text = chatInput.value.trim();
                if (!text) return;
                try {
                    const res = await fetch('/comment/' + openChatShortId, {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json',
                            'X-Requested-With': 'XMLHttpRequest'
                        },
                        body: JSON.stringify({ text })
                    });
                    const data = await res.json();
                    if (data.redirect) {
                        window.location.href = data.redirect;
                        return;
                    }
                    if (data.ok && data.comment) {
                        commentsStore[openChatShortId] = commentsStore[openChatShortId] || [];
                        commentsStore[openChatShortId].unshift(data.comment);
                        chatInput.value = '';
                        renderShortChat(openChatShortId);
                        const lbl = document.getElementById('comment-count-' + openChatShortId);
                        if (lbl) lbl.textContent = data.total_comments;
                    }
                } catch (err) {
                    console.error(err);
                }
            }

            async function toggleShortCommentLike(vidId, commentId) {
                try {
                    const res = await fetch(`/like_comment/${vidId}/${commentId}`, {
                        method: 'POST',
                        headers: { 'X-Requested-With': 'XMLHttpRequest' }
                    });
                    const data = await res.json();
                    if (data.redirect) {
                        window.location.href = data.redirect;
                        return;
                    }
                    if (data.ok) {
                        const c = (commentsStore[vidId] || []).find(item => item.id === commentId);
                        if (c) {
                            c.liked = data.liked;
                            c.likes_count = data.count;
                            renderShortChat(vidId);
                        }
                    }
                } catch (err) {
                    console.error(err);
                }
            }

            async function submitShortReply(e, vidId, commentId) {
                e.preventDefault();
                const inp = e.target.querySelector('input');
                const text = inp ? inp.value.trim() : '';
                if (!text) return;
                try {
                    const res = await fetch(`/reply_comment/${vidId}/${commentId}`, {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json',
                            'X-Requested-With': 'XMLHttpRequest'
                        },
                        body: JSON.stringify({ text })
                    });
                    const data = await res.json();
                    if (data.redirect) {
                        window.location.href = data.redirect;
                        return;
                    }
                    if (data.ok && data.reply) {
                        const c = (commentsStore[vidId] || []).find(item => item.id === commentId);
                        if (c) {
                            c.replies = c.replies || [];
                            c.replies.push(data.reply);
                            renderShortChat(vidId);
                        }
                    }
                } catch (err) {
                    console.error(err);
                }
            }

            const shortViewTimers = new WeakMap();
            const countedShorts = new Set();
            slides.forEach(slide => {
                const video = slide.querySelector('video');
                if (!video) return;
                const vidId = slide.dataset.vidId;
                video.addEventListener('playing', () => {
                    if (countedShorts.has(vidId) || shortViewTimers.has(video)) return;
                    const timer = setTimeout(async () => {
                        shortViewTimers.delete(video);
                        if (video.paused || video.ended || countedShorts.has(vidId)) return;
                        countedShorts.add(vidId);
                        try {
                            await fetch(`/view/${vidId}`, {
                                method: 'POST',
                                headers: { 'X-Requested-With': 'XMLHttpRequest' }
                            });
                        } catch (err) { console.error(err); }
                    }, 2000);
                    shortViewTimers.set(video, timer);
                });
                const cancelViewTimer = () => {
                    const timer = shortViewTimers.get(video);
                    if (timer) clearTimeout(timer);
                    shortViewTimers.delete(video);
                };
                video.addEventListener('pause', cancelViewTimer);
                video.addEventListener('waiting', cancelViewTimer);
                video.addEventListener('ended', cancelViewTimer);
            });

            const observer = new IntersectionObserver((entries) => {
                entries.forEach(entry => {
                    const vid = entry.target.querySelector('video');
                    if (!vid) return;
                    if (entry.isIntersecting) {
                        vid.play().catch(() => {});
                        const newVidId = entry.target.dataset.vidId;
                        activeShortId = newVidId;
                        if (openChatShortId && openChatShortId !== newVidId) {
                            openChatShortId = newVidId;
                            document.querySelectorAll('[id^="chat-btn-"]').forEach(b => b.classList.remove('chat-open'));
                            const btn = document.getElementById('chat-btn-' + newVidId);
                            if (btn) btn.classList.add('chat-open');
                            renderShortChat(newVidId);
                        }
                    } else {
                        vid.pause();
                        vid.currentTime = 0;
                    }
                });
            }, { root: feed, threshold: 0.65 });

            slides.forEach(slide => observer.observe(slide));

            const startVid = "{{ start_vid }}";
            if (startVid) {
                const target = document.getElementById('short-' + startVid);
                if (target) target.scrollIntoView();
            }

            document.addEventListener('keydown', (e) => {
                if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') return;
                if (e.key === 'ArrowDown') { e.preventDefault(); scrollShort(1); }
                if (e.key === 'ArrowUp') { e.preventDefault(); scrollShort(-1); }
                if (e.key === 'Escape' && openChatShortId) { closeShortChat(); }
            });
        </script>
    {% endif %}
    """
    return render_page(html, active_nav="yobshort", shorts=shorts, start_vid=start_vid, shorts_comments_json=shorts_comments_json)

@app.route("/watch/<vid_id>")
def watch(vid_id):
    data = load_data()
    video = next((v for v in data["videos"] if v["id"] == vid_id), None)
    if not video:
        return redirect(url_for("index"))

    filename = video.get("web_file") or os.path.basename(video.get("file_path", ""))

    html = """
    <div class="watch-wrap">
        {% set owner = data.users.get(video.owner, {}) %}
        {% set ch_name = owner.get('channel_name', video.owner) %}

        <video class="player" id="watch-video-player" controls autoplay data-vid-id="{{ video.id }}" {% if video.get('thumb_file') %}poster="{{ url_for('uploaded_file', filename=video.thumb_file) }}"{% endif %}>
            <source src="{{ url_for('uploaded_file', filename=filename) }}">
            הדפדפן שלך לא תומך בניגון וידאו.
        </video>

        <div class="watch-title">{{ video.title }}</div>

        <div class="watch-bar">
            <div style="display:flex; align-items:center; gap:12px;">
                <div class="avatar" onclick="openChannelModal('{{ video.owner }}')" style="width:44px; height:44px; background: {{ owner.get('avatar_color', '#16a085') }};">
                    {% if owner.get('avatar_file') %}
                        <img src="{{ url_for('uploaded_file', filename=owner.avatar_file) }}">
                    {% else %}
                        {{ ch_name[0]|upper }}
                    {% endif %}
                </div>
                <div>
                    <div onclick="openChannelModal('{{ video.owner }}')" style="font-weight:bold; font-size:15px; cursor:pointer;">{{ ch_name }}</div>
                    <div class="card-meta"><span id="sub-count-text">{{ owner.get('subscribers', [])|length }}</span> {{ t.subs_count }} • <span id="watch-view-count">{{ video.get('views', 0) }}</span> {{ t.views }}</div>
                </div>
            </div>

            <div style="display:flex; gap:10px; flex-wrap:wrap;">
                {% set liked = current_user in video.get('likes', []) %}
                <button type="button" id="like-main-btn" onclick="asyncAction('{{ url_for('like_video', vid_id=video.id) }}', handleLikeRes)" class="btn {{ 'btn-accent' if liked else '' }}">
                    👍 {{ t.like }} (<span id="like-main-count">{{ video.get('likes', [])|length }}</span>)
                </button>

                {% set saved = current_user in video.get('saves', []) %}
                <button type="button" id="save-main-btn" onclick="asyncAction('{{ url_for('save_video', vid_id=video.id) }}', handleSaveRes)" class="btn {{ 'btn-accent' if saved else '' }}">
                    💾 {{ t.save }} (<span id="save-main-count">{{ video.get('saves', [])|length }}</span>)
                </button>

                {% set is_sub = current_user in owner.get('subscribers', []) %}
                <button type="button" id="sub-main-btn" onclick="asyncAction('{{ url_for('subscribe_channel', owner_name=video.owner, vid_id=video.id) }}', handleSubRes)" class="btn" style="background: {{ '#333' if is_sub else '#f1f1f1' }}; color: {{ '#fff' if is_sub else '#0f0f0f' }};">
                    <span id="sub-btn-text">{{ t.subscribed if is_sub else t.subscribe }}</span> (<span id="sub-main-count">{{ owner.get('subscribers', [])|length }}</span>)
                </button>
            </div>
        </div>

        <div class="desc-box">{{ video.description or 'אין תיאור לסרטון זה.' }}</div>

        <h3 style="margin-top:20px;">{{ t.comments }} ({{ video.get('comments', [])|length }})</h3>
        <form class="comment-form" action="{{ url_for('comment_video', vid_id=video.id) }}" method="post">
            <input type="text" name="text" placeholder="{{ t.add_comment }}" required>
            <button type="submit" class="btn btn-accent">{{ t.send }}</button>
        </form>

        {% for c in video.get('comments', [])|reverse %}
            {% set c_author = data.users.get(c.user, {}).get('channel_name', c.user) %}
            {% set c_liked = current_user in c.get('likes', []) %}
            <div class="comment-item">
                <div class="comment-author" onclick="openChannelModal('{{ c.user }}')">
                    <span>@{{ c_author }}</span>
                    {% if c.user == video.owner %}<span class="creator-badge">יוצר הערוץ</span>{% endif %}
                </div>
                <div>{{ c.text }}</div>

                <div class="comment-actions">
                    <form action="{{ url_for('like_comment', vid_id=video.id, comment_id=c.id) }}" method="post" style="display:inline;">
                        <button type="submit" class="btn btn-sm {{ 'btn-accent' if c_liked else '' }}">
                            👍 {{ c.get('likes', [])|length }}
                        </button>
                    </form>
                    <button type="button" class="btn btn-sm" onclick="toggleReply('{{ c.id }}')">💬 להגיב</button>
                </div>

                <form id="reply-box-{{ c.id }}" class="reply-box" action="{{ url_for('reply_comment', vid_id=video.id, comment_id=c.id) }}" method="post">
                    <input type="text" name="text" placeholder="כתוב תגובה ל-@{{ c_author }}..." required>
                    <button type="submit" class="btn btn-sm btn-accent">{{ t.send }}</button>
                </form>

                {% if c.get('replies') %}
                    <div class="replies-list">
                        {% for r in c.get('replies', []) %}
                            {% set r_author = data.users.get(r.user, {}).get('channel_name', r.user) %}
                            <div class="reply-item">
                                <div class="comment-author" onclick="openChannelModal('{{ r.user }}')">
                                    <span>@{{ r_author }}</span>
                                    {% if r.user == video.owner %}<span class="creator-badge">יוצר הערוץ</span>{% endif %}
                                </div>
                                <div>{{ r.text }}</div>
                            </div>
                        {% endfor %}
                    </div>
                {% endif %}
            </div>
        {% endfor %}
    </div>

    <script>
        async function asyncAction(url, callback) {
            try {
                const res = await fetch(url, {
                    method: 'POST',
                    headers: { 'X-Requested-With': 'XMLHttpRequest' }
                });
                const data = await res.json();
                if (data.redirect) {
                    window.location.href = data.redirect;
                    return;
                }
                if (data.ok) {
                    callback(data);
                }
            } catch (e) {
                console.error(e);
            }
        }

        function handleLikeRes(data) {
            const btn = document.getElementById('like-main-btn');
            const cnt = document.getElementById('like-main-count');
            if (btn) btn.classList.toggle('btn-accent', data.liked);
            if (cnt) cnt.textContent = data.count;
        }

        function handleSaveRes(data) {
            const btn = document.getElementById('save-main-btn');
            const cnt = document.getElementById('save-main-count');
            if (btn) btn.classList.toggle('btn-accent', data.saved);
            if (cnt) cnt.textContent = data.count;
        }

        function handleSubRes(data) {
            const btn = document.getElementById('sub-main-btn');
            const txt = document.getElementById('sub-btn-text');
            const cnt = document.getElementById('sub-main-count');
            const cntTxt = document.getElementById('sub-count-text');
            if (btn) {
                btn.style.background = data.subscribed ? '#333' : '#f1f1f1';
                btn.style.color = data.subscribed ? '#fff' : '#0f0f0f';
            }
            if (txt) txt.textContent = data.subscribed ? '{{ t.subscribed }}' : '{{ t.subscribe }}';
            if (cnt) cnt.textContent = data.count;
            if (cntTxt) cntTxt.textContent = data.count;
        }

        const watchPlayer = document.getElementById('watch-video-player');
        if (watchPlayer) {
            let viewTimer = null;
            let viewSent = false;
            const cancelViewTimer = () => {
                if (viewTimer) clearTimeout(viewTimer);
                viewTimer = null;
            };
            watchPlayer.addEventListener('playing', () => {
                if (viewSent || viewTimer) return;
                viewTimer = setTimeout(async () => {
                    viewTimer = null;
                    if (watchPlayer.paused || watchPlayer.ended || viewSent) return;
                    viewSent = true;
                    try {
                        const response = await fetch(`/view/${watchPlayer.dataset.vidId}`, {
                            method: 'POST',
                            headers: { 'X-Requested-With': 'XMLHttpRequest' }
                        });
                        const result = await response.json();
                        const count = document.getElementById('watch-view-count');
                        if (result.ok && count) count.textContent = result.views;
                    } catch (err) { console.error(err); }
                }, 2000);
            });
            watchPlayer.addEventListener('pause', cancelViewTimer);
            watchPlayer.addEventListener('waiting', cancelViewTimer);
            watchPlayer.addEventListener('ended', cancelViewTimer);
        }
    </script>
    """
    return render_page(html, video=video, filename=filename)

@app.route("/view/<vid_id>", methods=["POST"])
def register_video_view(vid_id):
    viewed = session.get("viewed_video_ids", [])
    if vid_id in viewed:
        data = load_data()
        video = next((v for v in data["videos"] if v["id"] == vid_id), None)
        if not video:
            return jsonify({"ok": False}), 404
        return jsonify({"ok": True, "counted": False, "views": int(video.get("views", 0))})

    data = load_data()
    video = next((v for v in data["videos"] if v["id"] == vid_id), None)
    if not video:
        return jsonify({"ok": False}), 404

    video["views"] = int(video.get("views", 0)) + 1
    save_data(data)
    viewed.append(vid_id)
    session["viewed_video_ids"] = viewed[-200:]
    return jsonify({"ok": True, "counted": True, "views": video["views"]})

@app.route("/save/<vid_id>", methods=["POST"])
def save_video(vid_id):
    is_ajax = request.headers.get("X-Requested-With") == "XMLHttpRequest" or request.is_json
    if not session.get("user"):
        if is_ajax:
            return jsonify({"ok": False, "redirect": url_for("auth")}), 401
        return redirect(url_for("auth"))
    data = load_data()
    video = next((v for v in data["videos"] if v["id"] == vid_id), None)
    saved = False
    count = 0
    if video:
        saves = video.setdefault("saves", [])
        u = session["user"]
        if u in saves:
            saves.remove(u)
            saved = False
        else:
            saves.append(u)
            saved = True
        count = len(saves)
        save_data(data)
    if is_ajax:
        return jsonify({"ok": True, "saved": saved, "count": count})
    return redirect(url_for("watch", vid_id=vid_id))

@app.route("/like/<vid_id>", methods=["POST"])
def like_video(vid_id):
    is_ajax = request.headers.get("X-Requested-With") == "XMLHttpRequest" or request.is_json
    if not session.get("user"):
        if is_ajax:
            return jsonify({"ok": False, "redirect": url_for("auth")}), 401
        return redirect(url_for("auth"))
    data = load_data()
    video = next((v for v in data["videos"] if v["id"] == vid_id), None)
    liked = False
    count = 0
    if video:
        likes = video.setdefault("likes", [])
        u = session["user"]
        if u in likes:
            likes.remove(u)
            liked = False
        else:
            likes.append(u)
            liked = True
        count = len(likes)
        save_data(data)
    if is_ajax:
        return jsonify({"ok": True, "liked": liked, "count": count})
    if request.form.get("from_short"):
        return redirect(url_for("yobshort", v=vid_id))
    return redirect(url_for("watch", vid_id=vid_id))

@app.route("/subscribe/<owner_name>/<vid_id>", methods=["POST"])
def subscribe_channel(owner_name, vid_id):
    is_ajax = request.headers.get("X-Requested-With") == "XMLHttpRequest" or request.is_json
    if not session.get("user"):
        if is_ajax:
            return jsonify({"ok": False, "redirect": url_for("auth")}), 401
        return redirect(url_for("auth"))
    u = session["user"]
    subscribed = False
    count = 0
    if u != owner_name:
        data = load_data()
        owner = data["users"].get(owner_name)
        if owner:
            subs = owner.setdefault("subscribers", [])
            if u in subs:
                subs.remove(u)
                subscribed = False
            else:
                subs.append(u)
                subscribed = True
            count = len(subs)
            save_data(data)
    if is_ajax:
        return jsonify({"ok": True, "subscribed": subscribed, "count": count})
    return redirect(url_for("watch", vid_id=vid_id))

@app.route("/comment/<vid_id>", methods=["POST"])
def comment_video(vid_id):
    is_ajax = request.headers.get("X-Requested-With") == "XMLHttpRequest" or request.is_json
    if not session.get("user"):
        if is_ajax:
            return jsonify({"ok": False, "redirect": url_for("auth")}), 401
        return redirect(url_for("auth"))
    txt = (request.get_json(silent=True) or {}).get("text", "").strip() if request.is_json else request.form.get("text", "").strip()
    if txt:
        data = load_data()
        video = next((v for v in data["videos"] if v["id"] == vid_id), None)
        if video:
            u = session["user"]
            new_c = {
                "id": str(uuid.uuid4()),
                "user": u,
                "text": txt,
                "likes": [],
                "replies": []
            }
            video.setdefault("comments", []).append(new_c)
            save_data(data)
            if is_ajax:
                author = data["users"].get(u, {}).get("channel_name", u)
                return jsonify({
                    "ok": True,
                    "comment": {
                        "id": new_c["id"],
                        "user": u,
                        "author": author,
                        "is_creator": (u == video["owner"]),
                        "text": txt,
                        "likes_count": 0,
                        "liked": False,
                        "replies": []
                    },
                    "total_comments": len(video["comments"])
                })
    if is_ajax:
        return jsonify({"ok": False}), 400
    return redirect(url_for("watch", vid_id=vid_id))

@app.route("/like_comment/<vid_id>/<comment_id>", methods=["POST"])
def like_comment(vid_id, comment_id):
    is_ajax = request.headers.get("X-Requested-With") == "XMLHttpRequest" or request.is_json
    if not session.get("user"):
        if is_ajax:
            return jsonify({"ok": False, "redirect": url_for("auth")}), 401
        return redirect(url_for("auth"))
    data = load_data()
    video = next((v for v in data["videos"] if v["id"] == vid_id), None)
    liked = False
    count = 0
    if video:
        comment = next((c for c in video.get("comments", []) if c.get("id") == comment_id), None)
        if comment:
            likes = comment.setdefault("likes", [])
            u = session["user"]
            if u in likes:
                likes.remove(u)
                liked = False
            else:
                likes.append(u)
                liked = True
            count = len(likes)
            save_data(data)
    if is_ajax:
        return jsonify({"ok": True, "liked": liked, "count": count})
    if request.form.get("from_studio"):
        return redirect(url_for("studio_comments", vid_id=vid_id))
    return redirect(url_for("watch", vid_id=vid_id))

@app.route("/reply_comment/<vid_id>/<comment_id>", methods=["POST"])
def reply_comment(vid_id, comment_id):
    is_ajax = request.headers.get("X-Requested-With") == "XMLHttpRequest" or request.is_json
    if not session.get("user"):
        if is_ajax:
            return jsonify({"ok": False, "redirect": url_for("auth")}), 401
        return redirect(url_for("auth"))
    txt = (request.get_json(silent=True) or {}).get("text", "").strip() if request.is_json else request.form.get("text", "").strip()
    if txt:
        data = load_data()
        video = next((v for v in data["videos"] if v["id"] == vid_id), None)
        if video:
            comment = next((c for c in video.get("comments", []) if c.get("id") == comment_id), None)
            if comment:
                u = session["user"]
                new_r = {
                    "id": str(uuid.uuid4()),
                    "user": u,
                    "text": txt
                }
                comment.setdefault("replies", []).append(new_r)
                save_data(data)
                if is_ajax:
                    author = data["users"].get(u, {}).get("channel_name", u)
                    return jsonify({
                        "ok": True,
                        "reply": {
                            "id": new_r["id"],
                            "user": u,
                            "author": author,
                            "is_creator": (u == video["owner"]),
                            "text": txt
                        }
                    })
    if is_ajax:
        return jsonify({"ok": False}), 400
    if request.form.get("from_studio"):
        return redirect(url_for("studio_comments", vid_id=vid_id))
    return redirect(url_for("watch", vid_id=vid_id))

@app.route("/upload", methods=["GET", "POST"])
def upload():
    if not session.get("user"):
        return redirect(url_for("auth"))
    data = load_data()
    _, t = get_lang()
    error = ""

    if request.method == "POST":
        video_url = request.form.get("video_url", "").strip()
        thumb_url = request.form.get("thumb_url", "").strip()
        title = request.form.get("title", "").strip()
        desc = request.form.get("description", "").strip()
        cat_name = request.form.get("category", "")
        is_short = request.form.get("is_short") == "1"

        if not video_url or not title:
            error = "חובה להעלות סרטון ולהזין כותרת."
        else:
            if not thumb_url and "/upload/" in video_url:
                thumb_url = video_url.rsplit(".", 1)[0] + ".jpg"

            import time
            cat_idx = t["cats"].index(cat_name) if cat_name in t["cats"] else 1
            new_vid = {
                "id": str(uuid.uuid4()),
                "owner": session["user"],
                "title": title,
                "description": desc,
                "web_file": video_url,
                "file_path": video_url,
                "thumb_file": thumb_url,
                "category": cat_name,
                "cat_idx": cat_idx,
                "is_short": is_short,
                "views": 0,
                "likes": [],
                "saves": [],
                "comments": [],
                "created_at": time.time(),
                "thumb_color": data["users"][session["user"]].get("avatar_color", "#1f3a52")
            }
            data["videos"].append(new_vid)
            save_data(data)
            return redirect(url_for("index"))

    html = """
    <div class="box" style="max-width: 600px;">
        <h2>{{ t.create }}</h2>
        {% if error %}<div class="alert">{{ error }}</div>{% endif %}
        <form id="uploadForm" method="post">
            <input type="hidden" name="video_url" id="video_url">
            <input type="hidden" name="thumb_url" id="thumb_url">

            <div class="form-group">
                <label>קובץ סרטון (MP4 / WebM / MOV):</label>
                <input type="file" id="video_file" accept="video/*" required>
            </div>
            <div class="form-group">
                <label>תמונה ממוזערת / טמנייל (אופציונלי - ייווצר אוטומטית אם ריק):</label>
                <input type="file" id="thumb_file" accept="image/*">
            </div>
            <div class="form-group">
                <label>כותרת הסרטון:</label>
                <input type="text" name="title" required>
            </div>
            <div class="form-group">
                <label>תיאור הסרטון:</label>
                <textarea name="description" rows="4"></textarea>
            </div>
            <div class="form-group">
                <label>סוג סרטון:</label>
                <select name="is_short">
                    <option value="0">סרטון רגיל (16:9)</option>
                    <option value="1">📱 Yobshort — סרטון קצר אנכי (9:16)</option>
                </select>
            </div>
            <div class="form-group">
                <label>קטגוריה:</label>
                <select name="category">
                    {% for c in t.cats[1:] %}
                        <option value="{{ c }}">{{ c }}</option>
                    {% endfor %}
                </select>
            </div>
            <div id="uploadProgressWrap" style="display:none; margin-bottom:16px; background:#101010; padding:12px; border-radius:10px; border:1px solid #303030;">
                <div style="display:flex; justify-content:space-between; margin-bottom:6px; font-size:13px; font-weight:bold;">
                    <span id="uploadStatus" style="color:#3ea6ff;">⏳ מעלה סרטון לענן...</span>
                    <span id="uploadPercent" style="color:#f1f1f1;">0%</span>
                </div>
                <div style="width:100%; height:10px; background:#272727; border-radius:6px; overflow:hidden;">
                    <div id="uploadBar" style="width:0%; height:100%; background:#3ea6ff; transition: width 0.2s ease;"></div>
                </div>
                <div id="uploadEta" style="margin-top:6px; font-size:12px; color:#aaa; text-align:left;">מחשב זמן נותר...</div>
            </div>

            <button type="submit" id="submitBtn" class="btn btn-accent" style="width:100%; justify-content:center; padding:12px;">🚀 פרסם סרטון</button>
        </form>
    </div>

    <script>
        const CLOUD_NAME = "{{ cloud_name }}";
        const UPLOAD_PRESET = "{{ upload_preset }}";

        function formatTime(seconds) {
            if (!isFinite(seconds) || seconds < 0) return "מחשב...";
            seconds = Math.round(seconds);
            if (seconds < 60) return `כ-${seconds} שניות נותרו`;
            const mins = Math.floor(seconds / 60);
            const secs = seconds % 60;
            return `כ-${mins} דקות ו-${secs} שניות נותרו`;
        }

        function uploadToCloudinary(file, resourceType, onProgress) {
            return new Promise((resolve, reject) => {
                const xhr = new XMLHttpRequest();
                const formData = new FormData();
                formData.append("file", file);
                formData.append("upload_preset", UPLOAD_PRESET);

                const startTime = Date.now();

                xhr.upload.addEventListener("progress", (e) => {
                    if (e.lengthComputable && onProgress) {
                        const percent = Math.round((e.loaded / e.total) * 100);
                        const elapsedSec = (Date.now() - startTime) / 1000;
                        const speed = elapsedSec > 0 ? e.loaded / elapsedSec : 0;
                        const remainingBytes = e.total - e.loaded;
                        const etaSec = speed > 0 ? remainingBytes / speed : 0;
                        onProgress(percent, etaSec);
                    }
                });

                xhr.onreadystatechange = function () {
                    if (xhr.readyState === 4) {
                        try {
                            const data = JSON.parse(xhr.responseText);
                            if (xhr.status >= 200 && xhr.status < 300) {
                                resolve(data.secure_url);
                            } else {
                                reject(new Error(data.error?.message || "Upload failed"));
                            }
                        } catch (err) {
                            reject(new Error("שגיאה בתגובת השרת"));
                        }
                    }
                };

                xhr.onerror = () => reject(new Error("שגיאת רשת בהעלאה"));
                xhr.open("POST", "https://api.cloudinary.com/v1_1/" + CLOUD_NAME + "/" + resourceType + "/upload");
                xhr.send(formData);
            });
        }

        document.getElementById("uploadForm").addEventListener("submit", async function(e) {
            e.preventDefault();
            const videoFile = document.getElementById("video_file").files[0];
            const thumbFile = document.getElementById("thumb_file").files[0];

            const wrapEl = document.getElementById("uploadProgressWrap");
            const statusEl = document.getElementById("uploadStatus");
            const percentEl = document.getElementById("uploadPercent");
            const barEl = document.getElementById("uploadBar");
            const etaEl = document.getElementById("uploadEta");
            const btn = document.getElementById("submitBtn");

            if (!videoFile) return;
            btn.disabled = true;
            wrapEl.style.display = "block";
            statusEl.textContent = "⏳ מעלה סרטון לענן...";

            try {
                const vidUrl = await uploadToCloudinary(videoFile, "video", (pct, eta) => {
                    percentEl.textContent = pct + "%";
                    barEl.style.width = pct + "%";
                    etaEl.textContent = pct < 100 ? formatTime(eta) : "מעבד סרטון בענן...";
                });
                document.getElementById("video_url").value = vidUrl;

                if (thumbFile) {
                    statusEl.textContent = "⏳ מעלה תמונה ממוזערת...";
                    percentEl.textContent = "0%";
                    barEl.style.width = "0%";
                    const thUrl = await uploadToCloudinary(thumbFile, "image", (pct, eta) => {
                        percentEl.textContent = pct + "%";
                        barEl.style.width = pct + "%";
                        etaEl.textContent = formatTime(eta);
                    });
                    document.getElementById("thumb_url").value = thUrl;
                }

                statusEl.textContent = "✅ ההעלאה הושלמה! מפרסם...";
                percentEl.textContent = "100%";
                barEl.style.width = "100%";
                barEl.style.background = "#2ecc71";
                etaEl.textContent = "מוכן!";
                this.submit();
            } catch (err) {
                alert("שגיאה בהעלאה: " + err.message);
                btn.disabled = false;
                wrapEl.style.display = "none";
            }
        });
    </script>
    """
    return render_page(html, error=error, cloud_name=CLOUDINARY_CLOUD_NAME, upload_preset=CLOUDINARY_UPLOAD_PRESET)

@app.route("/studio", methods=["GET", "POST"])
def studio():
    if not session.get("user"):
        return redirect(url_for("auth"))
    data = load_data()
    u = session["user"]
    user_info = data["users"][u]

    if request.method == "POST":
        new_name = request.form.get("channel_name", "").strip()
        if new_name:
            user_info["channel_name"] = new_name
        user_info["bio"] = request.form.get("bio", "").strip()
        user_info["avatar_color"] = request.form.get("avatar_color", user_info.get("avatar_color", "#16a085"))

        av_file = request.files.get("avatar_file")
        if av_file and av_file.filename:
            ext = os.path.splitext(secure_filename(av_file.filename))[1] or ".png"
            av_name = f"av_{uuid.uuid4().hex}{ext}"
            av_file.save(os.path.join(app.config["UPLOAD_FOLDER"], av_name))
            user_info["avatar_file"] = av_name

        save_data(data)
        return redirect(url_for("studio"))

    my_videos = [v for v in data["videos"] if v["owner"] == u]
    total_views = sum(v.get("views", 0) for v in my_videos)
    total_subs = len(user_info.get("subscribers", []))

    html = """
    <div style="max-width:850px; margin:0 auto;">
        <h2>🎬 Yoyob Studio — ניהול הערוץ שלך</h2>

        <div class="stats-grid">
            <div class="stat-card"><div class="stat-val">{{ my_videos|length }}</div><div>סרטונים שהועלו</div></div>
            <div class="stat-card"><div class="stat-val">{{ total_views }}</div><div>סה״כ צפיות</div></div>
            <div class="stat-card"><div class="stat-val">{{ total_subs }}</div><div>מנויים בערוץ</div></div>
        </div>

        <div style="margin: 20px 0; display: flex; gap: 12px; flex-wrap: wrap;">
            <a href="{{ url_for('studio_content') }}" class="btn btn-accent" style="padding: 12px 20px; font-size: 15px;">📁 מעבר לניהול תוכן הסרטונים</a>
            <button type="button" onclick="openChannelModal('{{ current_user }}')" class="btn" style="padding: 12px 20px; font-size: 15px;">👁️ צפה בערוץ שלי כצופה (בחלונית)</button>
        </div>

        <div class="box" style="max-width:100%; margin:20px 0;">
            <h3>🎨 התאמה אישית לערוץ</h3><br>
            <form method="post" enctype="multipart/form-data">
                <div class="form-group">
                    <label>שם הערוץ:</label>
                    <input type="text" name="channel_name" value="{{ user_info.channel_name }}" required>
                </div>
                <div class="form-group">
                    <label>תיאור הערוץ:</label>
                    <input type="text" name="bio" value="{{ user_info.get('bio', '') }}">
                </div>
                <div class="form-group">
                    <label>צבע פרופיל:</label>
                    <input type="color" name="avatar_color" value="{{ user_info.get('avatar_color', '#16a085') }}" style="height:42px; padding:2px;">
                </div>
                <div class="form-group">
                    <label>תמונת פרופיל חדשה (אופציונלי):</label>
                    <input type="file" name="avatar_file" accept="image/*">
                </div>
                <button type="submit" class="btn btn-accent">💾 שמור שינויים בערוץ</button>
            </form>
        </div>
    </div>
    """
    return render_page(html, active_nav="studio", user_info=user_info, my_videos=my_videos, total_views=total_views, total_subs=total_subs)

@app.route("/studio/content")
def studio_content():
    if not session.get("user"):
        return redirect(url_for("auth"))
    data = load_data()
    u = session["user"]
    my_videos = [v for v in data["videos"] if v["owner"] == u]

    html = """
    <div style="max-width:950px; margin:0 auto;">
        <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:20px; flex-wrap:wrap; gap:10px;">
            <h2>📁 תוכן הערוץ — ניהול סרטונים</h2>
            <a href="{{ url_for('upload') }}" class="btn btn-accent">＋ העלה סרטון חדש</a>
        </div>

        {% for v in my_videos|reverse %}
            <div class="studio-row">
                <div class="studio-vid-info">
                    <div class="studio-thumb">
                        {% if v.get('thumb_file') %}
                            <img src="{{ url_for('uploaded_file', filename=v.thumb_file) }}" alt="{{ v.title }}">
                        {% else %}
                            ▶
                        {% endif %}
                    </div>
                    <div>
                        <strong>{{ v.title }}</strong>
                        <div class="card-meta">{{ v.get('views', 0) }} צפיות • {{ v.get('likes', [])|length }} לייקים • {{ v.get('comments', [])|length }} תגובות</div>
                    </div>
                </div>
                <div style="display:flex; gap:8px; align-items:center; flex-wrap:wrap;">
                    <a href="{{ url_for('edit_video', vid_id=v.id) }}" class="btn" title="עריכת טמנייל, כותרת ותיאור">✏️ עריכה</a>
                    <a href="{{ url_for('studio_comments', vid_id=v.id) }}" class="btn" title="צפייה ותגובה לתגובות">💬 תגובות ({{ v.get('comments', [])|length }})</a>
                    <a href="{{ url_for('studio_analytics', vid_id=v.id) }}" class="btn btn-accent" title="נתונים ואנליטיקה">📊 אנליטיקה</a>
                    <form action="{{ url_for('delete_video', vid_id=v.id) }}" method="post" onsubmit="return confirm('האם אתה בטוח שברצונך למחוק סרטון זה?');">
                        <button type="submit" class="btn btn-red" title="מחיקת הסרטון">🗑️ מחיקה</button>
                    </form>
                </div>
            </div>
        {% else %}
            <div class="empty">
                <p>עדיין לא העלית סרטונים לערוץ. לחץ על העלה סרטון חדש כדי להתחיל!</p>
            </div>
        {% endfor %}
    </div>
    """
    return render_page(html, active_nav="studio_content", my_videos=my_videos)

@app.route("/studio/analytics/<vid_id>")
def studio_analytics(vid_id):
    if not session.get("user"):
        return redirect(url_for("auth"))
    data = load_data()
    u = session["user"]
    video = next((v for v in data["videos"] if v["id"] == vid_id and v["owner"] == u), None)
    if not video:
        return redirect(url_for("studio_content"))

    views = video.get("views", 0)
    avg_watch_secs = min(views * 14, 180)
    subscribers_gained = len([uname for uname, uinf in data["users"].items() if u in uinf.get("subscribers", [])])
    
    html = """
    <div style="max-width:850px; margin:0 auto;">
        <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:20px; flex-wrap:wrap; gap:10px;">
            <h2>📊 אנליטיקה ונתוני סרטון: {{ video.title }}</h2>
            <a href="{{ url_for('studio_content') }}" class="btn">חזרה לתוכן</a>
        </div>

        <div class="stats-grid">
            <div class="stat-card">
                <div class="stat-val">{{ views }}</div>
                <div>סה״כ צפיות בסרטון</div>
            </div>
            <div class="stat-card">
                <div class="stat-val">{{ avg_watch_secs }} שניות</div>
                <div>ממוצע זמן צפייה (משוער)</div>
            </div>
            <div class="stat-card">
                <div class="stat-val">{{ video.get('likes', [])|length }}</div>
                <div>כמות לייקים</div>
            </div>
            <div class="stat-card">
                <div class="stat-val">{{ video.get('comments', [])|length }}</div>
                <div>כמות תגובות</div>
            </div>
            <div class="stat-card">
                <div class="stat-val">{{ subscribers_gained }}</div>
                <div>מנויים כוללים בערוץ</div>
            </div>
            <div class="stat-card">
                <div class="stat-val">{{ video.get('saves', [])|length }}</div>
                <div>שמירות לסרטונים שמורים</div>
            </div>
        </div>
    </div>
    """
    return render_page(html, active_nav="studio_content", video=video, views=views, avg_watch_secs=avg_watch_secs, subscribers_gained=subscribers_gained)

@app.route("/studio/comments/<vid_id>")
def studio_comments(vid_id):
    if not session.get("user"):
        return redirect(url_for("auth"))
    data = load_data()
    u = session["user"]
    video = next((v for v in data["videos"] if v["id"] == vid_id and v["owner"] == u), None)
    if not video:
        return redirect(url_for("studio_content"))

    html = """
    <div style="max-width:850px; margin:0 auto;">
        <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:20px; flex-wrap:wrap; gap:10px;">
            <h2>💬 תגובות על הסרטון: {{ video.title }}</h2>
            <a href="{{ url_for('studio_content') }}" class="btn">חזרה לתוכן</a>
        </div>

        <form class="comment-form" action="{{ url_for('comment_video', vid_id=video.id) }}" method="post">
            <input type="text" name="text" placeholder="הוסף תגובה חדשה כבעל הערוץ..." required>
            <button type="submit" class="btn btn-accent">פרסם תגובה</button>
        </form>

        {% if not video.get('comments') %}
            <div class="empty" style="padding:40px 20px;">
                <p>עדיין אין תגובות לסרטון זה.</p>
            </div>
        {% else %}
            {% for c in video.get('comments', [])|reverse %}
                {% set c_author = data.users.get(c.user, {}).get('channel_name', c.user) %}
                {% set c_liked = current_user in c.get('likes', []) %}
                <div class="comment-item">
                    <div class="comment-author">
                        <span>@{{ c_author }}</span>
                        {% if c.user == video.owner %}<span class="creator-badge">יוצר הערוץ</span>{% endif %}
                    </div>
                    <div style="margin:6px 0;">{{ c.text }}</div>

                    <div class="comment-actions">
                        <form action="{{ url_for('like_comment', vid_id=video.id, comment_id=c.id) }}" method="post" style="display:inline;">
                            <input type="hidden" name="from_studio" value="1">
                            <button type="submit" class="btn btn-sm {{ 'btn-accent' if c_liked else '' }}">
                                👍 {{ c.get('likes', [])|length }}
                            </button>
                        </form>
                        <button type="button" class="btn btn-sm" onclick="toggleReply('{{ c.id }}')">💬 להגיב</button>
                    </div>

                    <form id="reply-box-{{ c.id }}" class="reply-box" action="{{ url_for('reply_comment', vid_id=video.id, comment_id=c.id) }}" method="post">
                        <input type="hidden" name="from_studio" value="1">
                        <input type="text" name="text" placeholder="הגב ל-@{{ c_author }} מתוך הסטודיו..." required>
                        <button type="submit" class="btn btn-sm btn-accent">שלח תגובה</button>
                    </form>

                    {% if c.get('replies') %}
                        <div class="replies-list">
                            {% for r in c.get('replies', []) %}
                                {% set r_author = data.users.get(r.user, {}).get('channel_name', r.user) %}
                                <div class="reply-item">
                                    <div class="comment-author">
                                        <span>@{{ r_author }}</span>
                                        {% if r.user == video.owner %}<span class="creator-badge">יוצר הערוץ</span>{% endif %}
                                    </div>
                                    <div>{{ r.text }}</div>
                                </div>
                            {% endfor %}
                        </div>
                    {% endif %}
                </div>
            {% endfor %}
        {% endif %}
    </div>
    """
    return render_page(html, active_nav="studio_content", video=video)

@app.route("/edit_video/<vid_id>", methods=["GET", "POST"])
def edit_video(vid_id):
    if not session.get("user"):
        return redirect(url_for("auth"))
    data = load_data()
    u = session["user"]
    video = next((v for v in data["videos"] if v["id"] == vid_id and v["owner"] == u), None)
    if not video:
        return redirect(url_for("studio_content"))

    error = ""
    if request.method == "POST":
        title = request.form.get("title", "").strip()
        desc = request.form.get("description", "").strip()
        thumb_file = request.files.get("thumb_file")

        if not title:
            error = "חובה להזין כותרת לסרטון."
        else:
            video["title"] = title
            video["description"] = desc

            if thumb_file and thumb_file.filename:
                t_ext = os.path.splitext(secure_filename(thumb_file.filename))[1] or ".jpg"
                thumb_name = f"thumb_{uuid.uuid4().hex}{t_ext}"
                thumb_file.save(os.path.join(app.config["UPLOAD_FOLDER"], thumb_name))
                video["thumb_file"] = thumb_name

            save_data(data)
            return redirect(url_for("studio_content"))

    html = """
    <div class="box">
        <h2>✏️ עריכת סרטון</h2>
        {% if error %}<div class="alert">{{ error }}</div>{% endif %}
        <form method="post" enctype="multipart/form-data">
            <div class="form-group">
                <label>שם הסרטון:</label>
                <input type="text" name="title" value="{{ video.title }}" required>
            </div>
            <div class="form-group">
                <label>תיאור הסרטון:</label>
                <textarea name="description" rows="4">{{ video.get('description', '') }}</textarea>
            </div>
            {% if video.get('thumb_file') %}
            <div class="form-group">
                <label>תמונה נוכחית:</label>
                <img src="{{ url_for('uploaded_file', filename=video.thumb_file) }}" style="width:100%; max-height:180px; object-fit:cover; border-radius:10px; border:1px solid #303030;">
            </div>
            {% endif %}
            <div class="form-group">
                <label>החלף תמונה ממוזערת / טמנייל (אופציונלי):</label>
                <input type="file" name="thumb_file" accept="image/*">
            </div>
            <div style="display:flex; gap:10px; margin-top:16px;">
                <button type="submit" class="btn btn-accent" style="flex:1; justify-content:center; padding:12px;">💾 שמור שינויים</button>
                <a href="{{ url_for('studio_content') }}" class="btn" style="justify-content:center; padding:12px;">ביטול</a>
            </div>
        </form>
    </div>
    """
    return render_page(html, active_nav="studio_content", video=video, error=error)

@app.route("/delete_video/<vid_id>", methods=["POST"])
def delete_video(vid_id):
    if session.get("user"):
        data = load_data()
        user = session["user"]
        video_to_delete = next((v for v in data["videos"] if v["id"] == vid_id and v["owner"] == user), None)
        if video_to_delete:
            fname = video_to_delete.get("web_file")
            if fname and not fname.startswith("http"):
                p = os.path.join(app.config["UPLOAD_FOLDER"], os.path.basename(fname))
                if os.path.exists(p):
                    try:
                        os.remove(p)
                    except Exception as e:
                        print("Error deleting video file:", e)
            
            thumb = video_to_delete.get("thumb_file")
            if thumb and not thumb.startswith("http"):
                tp = os.path.join(app.config["UPLOAD_FOLDER"], os.path.basename(thumb))
                if os.path.exists(tp):
                    try:
                        os.remove(tp)
                    except Exception as e:
                        print("Error deleting thumbnail file:", e)

            data["videos"] = [v for v in data["videos"] if v["id"] != vid_id]
            save_data(data)
    return redirect(url_for("studio_content"))

@app.route("/subscriptions")
def subscriptions():
    if not session.get("user"):
        return redirect(url_for("auth"))
    data = load_data()
    u = session["user"]
    subscribed_channels = [
        {
            "username": uname,
            "channel_name": info.get("channel_name", uname),
            "avatar_color": info.get("avatar_color", "#16a085"),
            "avatar_file": info.get("avatar_file", ""),
            "bio": info.get("bio", ""),
            "subs_count": len(info.get("subscribers", []))
        }
        for uname, info in data["users"].items()
        if u in info.get("subscribers", [])
    ]

    html = """
    <h2 style="margin-bottom:16px;">{{ t.subscriptions }}</h2>
    {% if not subscribed_channels %}
        <div class="empty"><p>{{ t.no_subs }}</p></div>
    {% else %}
        <div class="grid" style="grid-template-columns: repeat(auto-fill, minmax(160px, 1fr)); gap: 24px;">
            {% for ch in subscribed_channels %}
                <div class="card" onclick="openChannelModal('{{ ch.username }}')" style="display:flex; flex-direction:column; align-items:center; text-align:center; padding: 8px; cursor: pointer;">
                    <div class="avatar" style="width:96px; height:96px; font-size:34px; margin-bottom:10px; background: {{ ch.avatar_color }};">
                        {% if ch.avatar_file %}
                            <img src="{{ url_for('uploaded_file', filename=ch.avatar_file) }}" alt="{{ ch.channel_name }}">
                        {% else %}
                            {{ ch.channel_name[0]|upper }}
                        {% endif %}
                    </div>
                    <div class="card-title" style="font-size:16px;">{{ ch.channel_name }}</div>
                    <div class="card-meta" style="margin-top:3px; font-size:13px;">{{ ch.subs_count }} {{ t.subs_count }}</div>
                </div>
            {% endfor %}
        </div>
    {% endif %}
    """
    return render_page(html, active_nav="subs", subscribed_channels=subscribed_channels)

@app.route("/subscriptions_feed")
def subscriptions_feed():
    if not session.get("user"):
        return redirect(url_for("auth"))
    data = load_data()
    u = session["user"]
    subs = [uname for uname, info in data["users"].items() if u in info.get("subscribers", [])]
    sub_vids = [v for v in reversed(data["videos"]) if v["owner"] in subs]

    regular_videos = [v for v in sub_vids if not v.get("is_short")]
    short_videos = [v for v in sub_vids if v.get("is_short")]
    feed_sections = build_mixed_feed(regular_videos, short_videos)

    html = """
    <h2 style="margin-bottom:16px;">{{ t.subs_feed }}</h2>
    
    {% if not feed_sections %}
        <div class="empty">
            <div style="font-size: 48px; margin-bottom: 12px;">🎬</div>
            <p style="margin-bottom: 18px;">{{ t.no_videos }}</p>
            <a href="{{ url_for('upload') }}" class="btn btn-accent">{{ t.create }}</a>
        </div>
    {% else %}
        {% for sec in feed_sections %}
            {% if sec.type == 'regular' %}
                <div class="grid" style="margin-bottom: 20px;">
                    {% for v in sec['items'] %}
                        {% set owner = data.users.get(v.owner, {}) %}
                        {% set ch_name = owner.get('channel_name', v.owner) %}
                        <div class="card">
                            <a href="{{ url_for('watch', vid_id=v.id) }}">
                                <div class="thumb" style="border-color: {{ v.get('thumb_color', '#333') }};">
                                    {% if v.category %}<span class="thumb-cat">{{ v.category }}</span>{% endif %}
                                    {% if v.get('thumb_file') %}
                                        <img class="thumb-img" src="{{ url_for('uploaded_file', filename=v.thumb_file) }}" alt="{{ v.title }}">
                                        <div class="thumb-overlay"><div class="thumb-play">▶</div></div>
                                    {% else %}
                                        <video class="thumb-img" preload="metadata" muted playsinline style="object-fit:cover;"><source src="{{ url_for('uploaded_file', filename=v.get('web_file') or '') }}#t=0.5"></video>
                                        <div class="thumb-overlay"><div class="thumb-play">▶</div></div>
                                    {% endif %}
                                </div>
                            </a>
                            <div class="card-info">
                                <div class="avatar" onclick="openChannelModal('{{ v.owner }}')" style="background: {{ owner.get('avatar_color', '#16a085') }};">
                                    {% if owner.get('avatar_file') %}
                                        <img src="{{ url_for('uploaded_file', filename=owner.avatar_file) }}">
                                    {% else %}
                                        {{ ch_name[0]|upper }}
                                    {% endif %}
                                </div>
                                <div>
                                    <a href="{{ url_for('watch', vid_id=v.id) }}"><div class="card-title">{{ v.title }}</div></a>
                                    <div class="card-meta">
                                        <span onclick="openChannelModal('{{ v.owner }}')" style="cursor: pointer; color: #aaa;">{{ ch_name }}</span> • {{ v.get('views', 0) }} {{ t.views }}
                                    </div>
                                </div>
                            </div>
                        </div>
                    {% endfor %}
                </div>
            {% elif sec.type == 'shorts' %}
                <div class="shorts-shelf">
                    <div class="shorts-shelf-header">
                        <a href="{{ url_for('yobshort') }}" class="shorts-shelf-title">
                            <span class="shorts-shelf-badge">▶</span>
                            <span>{{ t.yobshort }}</span>
                        </a>
                        <a href="{{ url_for('yobshort') }}" class="btn btn-sm">{{ t.yobshort }} ←</a>
                    </div>
                    <div class="shorts-shelf-grid">
                        {% for sv in sec['items'] %}
                            {% set s_owner = data.users.get(sv.owner, {}) %}
                            {% set s_ch = s_owner.get('channel_name', sv.owner) %}
                            <a href="{{ url_for('yobshort', v=sv.id) }}" class="short-shelf-card">
                                <div class="short-shelf-thumb" style="border-color: {{ sv.get('thumb_color', '#333') }};">
                                    {% if sv.get('thumb_file') %}
                                        <img src="{{ url_for('uploaded_file', filename=sv.thumb_file) }}" alt="{{ sv.title }}">
                                    {% else %}
                                        <video style="width:100%; height:100%; object-fit:cover; position:absolute; inset:0;" preload="auto" muted playsinline><source src="{{ url_for('uploaded_file', filename=sv.get('web_file') or '') }}#t=0.5"></video>
                                        <div class="thumb-play" style="position:relative; z-index:2; margin-bottom: 24px;">▶</div>
                                    {% endif %}
                                    <div class="short-shelf-gradient">
                                        <div class="short-shelf-card-title">{{ sv.title }}</div>
                                        <div class="short-shelf-card-meta">{{ s_ch }} • {{ sv.get('views', 0) }} {{ t.views }}</div>
                                    </div>
                                </div>
                            </a>
                        {% endfor %}
                    </div>
                </div>
            {% endif %}
        {% endfor %}
    {% endif %}
    """
    return render_page(html, active_nav="subs_feed", feed_sections=feed_sections)

@app.route("/saved")
def saved_videos():
    if not session.get("user"):
        return redirect(url_for("auth"))
    data = load_data()
    u = session["user"]
    videos = [v for v in reversed(data["videos"]) if u in v.get("saves", [])]

    html = """
    <h2 style="margin-bottom:16px;">{{ t.saved }}</h2>
    {% if not videos %}
        <div class="empty"><p>אין עדיין סרטונים שמורים.</p></div>
    {% else %}
        <div class="grid">
            {% for v in videos %}
                {% set owner = data.users.get(v.owner, {}) %}
                <a href="{{ url_for('watch', vid_id=v.id) }}" class="card">
                    <div class="thumb">
                        {% if v.get('thumb_file') %}
                            <img class="thumb-img" src="{{ url_for('uploaded_file', filename=v.thumb_file) }}" alt="{{ v.title }}">
                            <div class="thumb-overlay"><div class="thumb-play">▶</div></div>
                        {% else %}
                            <div class="thumb-play">▶</div>
                            <div class="thumb-title">{{ v.title }}</div>
                        {% endif %}
                    </div>
                    <div class="card-info"><div><div class="card-title">{{ v.title }}</div><div class="card-meta">{{ owner.get('channel_name', v.owner) }}</div></div></div>
                </a>
            {% endfor %}
        </div>
    {% endif %}
    """
    return render_page(html, active_nav="saved", videos=videos)

@app.route("/liked")
def liked():
    if not session.get("user"):
        return redirect(url_for("auth"))
    data = load_data()
    u = session["user"]
    videos = [v for v in reversed(data["videos"]) if u in v.get("likes", [])]

    html = """
    <h2 style="margin-bottom:16px;">{{ t.liked }}</h2>
    {% if not videos %}
        <div class="empty"><p>{{ t.no_videos }}</p></div>
    {% else %}
        <div class="grid">
            {% for v in videos %}
                {% set owner = data.users.get(v.owner, {}) %}
                <a href="{{ url_for('watch', vid_id=v.id) }}" class="card">
                    <div class="thumb">
                        {% if v.get('thumb_file') %}
                            <img class="thumb-img" src="{{ url_for('uploaded_file', filename=v.thumb_file) }}" alt="{{ v.title }}">
                            <div class="thumb-overlay"><div class="thumb-play">▶</div></div>
                        {% else %}
                            <div class="thumb-play">▶</div>
                            <div class="thumb-title">{{ v.title }}</div>
                        {% endif %}
                    </div>
                    <div class="card-info"><div><div class="card-title">{{ v.title }}</div><div class="card-meta">{{ owner.get('channel_name', v.owner) }}</div></div></div>
                </a>
            {% endfor %}
        </div>
    {% endif %}
    """
    return render_page(html, active_nav="liked", videos=videos)

@app.route("/settings", methods=["GET", "POST"])
def settings():
    if request.method == "POST":
        chosen = request.form.get("lang")
        if chosen in LANGUAGES:
            session["language"] = chosen
            data = load_data()
            data["language"] = chosen
            save_data(data)
        return redirect(url_for("index"))

    html = """
    <div class="box">
        <h2>⚙️ {{ t.settings }}</h2>
        <form method="post">
            {% for lname, ldata in languages.items() %}
                <button type="submit" name="lang" value="{{ lname }}" class="btn {{ 'btn-accent' if lname == lang_name else '' }}" style="width:100%; justify-content:center; margin-bottom:8px; padding:12px;">
                    {{ lname }} ({{ ldata.country }})
                </button>
            {% endfor %}
        </form>
    </div>
    """
    return render_page(html, languages=LANGUAGES)

@app.route("/auth", methods=["GET", "POST"])
def auth():
    error = ""
    if request.method == "POST":
        action = request.form.get("action")
        u = request.form.get("username", "").strip()
        p = request.form.get("password", "").strip()
        data = load_data()

        if not u or not p:
            error = "נא למלא שם משתמש וסיסמה."
        elif action == "login":
            if u in data["users"] and data["users"][u]["password"] == p:
                session["user"] = u
                return redirect(url_for("index"))
            error = "שם משתמש או סיסמה שגויים."
        elif action == "register":
            if u in data["users"]:
                error = "שם המשתמש כבר תפוס."
            else:
                data["users"][u] = {
                    "password": p,
                    "channel_name": u,
                    "bio": "",
                    "avatar_color": "#16a085",
                    "subscribers": []
                }
                save_data(data)
                session["user"] = u
                return redirect(url_for("index"))

    html = """
    <div class="box">
        <h2>{{ t.login }} / {{ t.register }}</h2>
        {% if error %}<div class="alert">{{ error }}</div>{% endif %}
        <form method="post">
            <div class="form-group">
                <label>שם משתמש:</label>
                <input type="text" name="username" required>
            </div>
            <div class="form-group">
                <label>סיסמה:</label>
                <input type="password" name="password" required>
            </div>
            <div style="display:flex; gap:10px; margin-top:16px;">
                <button type="submit" name="action" value="login" class="btn btn-accent" style="flex:1; justify-content:center; padding:11px;">{{ t.login }}</button>
                <button type="submit" name="action" value="register" class="btn" style="flex:1; justify-content:center; padding:11px;">{{ t.register }}</button>
            </div>
        </form>
    </div>
    """
    return render_page(html, error=error)

@app.route("/logout")
def logout():
    session.pop("user", None)
    return redirect(url_for("index"))

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
