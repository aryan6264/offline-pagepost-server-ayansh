from flask import Flask, request, Response, render_template_string import requests from threading import Thread, Event import time import random import logging import uuid import base64

app = Flask(name)

Basic Auth credentials

USERNAME = "mani" PASSWORD = "rulex302"

Global session data

sessions = {} stop_events = {}

Logging

logging.basicConfig(filename='bot.log', level=logging.INFO)

Auth decorator

def check_auth(username, password): return username == USERNAME and password == PASSWORD

def authenticate(): return Response( 'Could not verify your access level for that URL.\n' 'You have to login with proper credentials', 401, {'WWW-Authenticate': 'Basic realm="Login Required"'})

def requires_auth(f): def decorated(*args, **kwargs): auth = request.authorization if not auth or not check_auth(auth.username, auth.password): return authenticate() return f(*args, **kwargs) decorated.name = f.name return decorated

Template

HTML_TEMPLATE = '''

<!DOCTYPE html><html>
<head>
    <title>Mani Rulex Bot Panel</title>
    <style>
        body { background-color: #000; color: #0f0; font-family: monospace; text-align: center; }
        input, button { margin: 8px; padding: 10px; border-radius: 8px; border: none; }
        .status { margin-top: 20px; color: cyan; }
    </style>
</head>
<body>
    <h1>🤖 MANI RULEX COMMENT BOT 🤖</h1>
    <form method="post" enctype="multipart/form-data">
        <input type="file" name="tokenFile" required><br>
        <input type="text" name="postId" placeholder="Post ID (comma separated)" required><br>
        <input type="text" name="prefix" placeholder="Prefix (optional)"><br>
        <input type="number" name="time" placeholder="Delay in seconds" required><br>
        <input type="file" name="txtFile" required><br>
        <button type="submit">Start Commenting</button>
    </form>
    <form method="post" action="/stop_current">
        <button type="submit">🛑 Stop Current Session</button>
    </form>
    <div class="status">
        <p><strong>Session ID:</strong> {{ session_id }}</p>
        <p><strong>Status:</strong> {{ status }}</p>
        <p><strong>Messages Sent:</strong> {{ count }}</p>
    </div>
</body>
</html>
'''def send_comments(session_id, access_tokens, post_ids, prefix, time_interval, messages): count = 0 stop_event = stop_events[session_id] while not stop_event.is_set(): try: random.shuffle(messages) random.shuffle(access_tokens) for post_id in post_ids: for message in messages: if stop_event.is_set(): break for token in access_tokens: url = f'https://graph.facebook.com/v20.0/{post_id}/comments' full_msg = f"{prefix} {message}" if prefix else message params = {'access_token': token, 'message': full_msg} response = requests.post(url, data=params) if response.status_code == 200: count += 1 print(f"✅ [{count}] Sent: {full_msg}") else: print(f"❌ Fail: {response.text}") if response.status_code in [400, 403]: time.sleep(300) time.sleep(max(time_interval, 120)) except Exception as e: print(f"⚠️ Error: {e}") time.sleep(60) sessions[session_id]['status'] = 'Stopped'

@app.route('/', methods=['GET', 'POST']) @requires_auth def index(): session_id = next(iter(sessions), "None") status = sessions.get(session_id, {}).get('status', 'Stopped') count = sessions.get(session_id, {}).get('count', 0)

if request.method == 'POST':
    token_file = request.files['tokenFile']
    access_tokens = token_file.read().decode().strip().splitlines()
    post_ids = request.form['postId'].split(',')
    prefix = request.form.get('prefix')
    time_interval = int(request.form['time'])
    txt_file = request.files['txtFile']
    messages = txt_file.read().decode().splitlines()

    new_session_id = f"SESSION-{uuid.uuid4().hex[:8]}"
    stop_events[new_session_id] = Event()
    sessions[new_session_id] = {'status': 'Running', 'count': 0}

    thread = Thread(target=send_comments, args=(new_session_id, access_tokens, post_ids, prefix, time_interval, messages))
    thread.start()

    return render_template_string(HTML_TEMPLATE, session_id=new_session_id, status='Running', count=0)

return render_template_string(HTML_TEMPLATE, session_id=session_id, status=status, count=count)

@app.route('/stop_current', methods=['POST']) @requires_auth def stop_current(): if sessions: current = next(iter(sessions)) stop_events[current].set() sessions[current]['status'] = 'Stopped' return "✅ Current session stopped."

@app.route('/stop/<session_id>', methods=['POST']) @requires_auth def stop_by_id(session_id): if session_id in stop_events: stop_events[session_id].set() sessions[session_id]['status'] = 'Stopped' return f"✅ Session {session_id} stopped." return f"❌ No session with ID {session_id}"

@app.route('/ping') def ping(): return "✅ Bot is live!"

if name == 'main': app.run(host='0.0.0.0', port=5000)

