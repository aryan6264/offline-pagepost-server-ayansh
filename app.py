from flask import Flask, request, render_template_string
import requests
from threading import Thread, Event
import uuid
import time

app = Flask(__name__)
sessions = {}

HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head><title>Mani RuLex Comment Bot</title></head>
<body>
  <h2>👑 MANI RULEX COMMENT PANEL 👑</h2>
  <form method="POST" enctype="multipart/form-data">
    <label>🔑 Token File:</label><br>
    <input type="file" name="token_file"><br><br>

    <label>📌 Post ID:</label><br>
    <input type="text" name="post_id"><br><br>

    <label>✍️ Comment Prefix (Optional):</label><br>
    <input type="text" name="prefix"><br><br>

    <label>⏱️ Delay (seconds):</label><br>
    <input type="text" name="delay" value="10"><br><br>

    <label>🗒️ Comments File (.txt):</label><br>
    <input type="file" name="comments_file"><br><br>

    <input type="submit" value="🚀 Start Commenting">
  </form>
  <hr>
  {% if status %}
    <h3>📡 Status</h3>
    <p><b>Token Valid:</b> {{ status.token_valid }}</p>
    <p><b>Session ID:</b> {{ status.session_id }}</p>
    <p><b>Comments Sent:</b> {{ status.sent_count }}</p>
    <p><b>🛑 Stop URL:</b> /stop/{{ status.session_id }}</p>
  {% endif %}
</body>
</html>
"""

def validate_token(token):
    try:
        r = requests.get(f'https://graph.facebook.com/me?access_token={token}')
        return 'id' in r.json()
    except:
        return False

def comment_worker(token, post_id, comments, delay, prefix, stop_event, session_id):
    count = 0
    for comment in comments:
        if stop_event.is_set():
            break
        message = f"{prefix} {comment.strip()}" if prefix else comment.strip()
        url = f"https://graph.facebook.com/{post_id}/comments"
        r = requests.post(url, data={'message': message, 'access_token': token})
        if r.status_code == 200:
            count += 1
        sessions[session_id]['sent_count'] = count
        time.sleep(delay)

@app.route("/", methods=["GET", "POST"])
def index():
    status = None
    if request.method == "POST":
        token_file = request.files["token_file"]
        token = token_file.read().decode().strip()

        comments_file = request.files["comments_file"]
        comments = comments_file.read().decode().splitlines()

        post_id = request.form["post_id"]
        delay = int(request.form.get("delay", 10))
        prefix = request.form.get("prefix", "")

        session_id = str(uuid.uuid4())[:8]
        stop_event = Event()
        sessions[session_id] = {"stop_event": stop_event, "sent_count": 0}

        is_valid = validate_token(token)
        if is_valid:
            t = Thread(target=comment_worker, args=(token, post_id, comments, delay, prefix, stop_event, session_id))
            t.start()

        status = {
            "token_valid": is_valid,
            "session_id": session_id,
            "sent_count": 0
        }

    return render_template_string(HTML_TEMPLATE, status=status)

@app.route("/stop/<session_id>")
def stop_session(session_id):
    if session_id in sessions:
        sessions[session_id]["stop_event"].set()
        return f"🛑 Session {session_id} stopped."
    return "❌ Invalid session ID"
