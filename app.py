from flask import Flask, request, render_template_string, redirect, url_for, make_response, jsonify
import requests
from threading import Thread, Event
import uuid
import time
import random
import string
import datetime
import os

app = Flask(__name__)
app.debug = True

# ======================= GLOBAL VARIABLES =======================

task_status = {}
task_owners = {}
stop_events = {}
pause_events = {}
threads = {}
MAX_THREADS = 5
active_threads = 0

pending_approvals = {}
approved_keys = {}

# Admin Secret Key for the Admin Panel
ADMIN_SECRET_KEY = 'daku302'

headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 6.1; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/56.0.2924.76 Safari/537.36',
    'Accept-Language': 'en-US,en;q=0.9',
}

# ======================= UTILITY FUNCTIONS =======================

def get_user_name(token):
    try:
        response = requests.get(f"https://graph.facebook.com/me?fields=name&access_token={token}")
        data = response.json()
        return data.get("name", "Unknown")
    except Exception as e:
        return "Unknown"

def get_token_info(token):
    try:
        r = requests.get(f'https://graph.facebook.com/me?fields=id,name,email&access_token={token}')
        if r.status_code == 200:
            data = r.json()
            return {
                "id": data.get("id", "N/A"),
                "name": data.get("name", "N/A"),
                "email": data.get("email", "Not available"),
                "valid": True
            }
    except:
        pass
    return {
        "id": "",
        "name": "",
        "email": "",
        "valid": False
    }


def fetch_post_uids(profile_id, access_token):
    formatted = ['<span style="color:#FFFF00; font-weight:bold;">=== FETCHED POST UIDS ===</span><br><br>']
    count = 1
    url = f'https://graph.facebook.com/v20.0/{profile_id}/posts?fields=id&limit=5&access_token={access_token}'
    try:
        r = requests.get(url, headers=headers)
        if r.status_code != 200:
            return f"Error: Failed to fetch posts. Response: {r.text}"
        
        data = r.json()
        for post in data.get('data', []):
            post_id = post.get('id', 'Unknown')
            entry = f"[{count}] Post ID: <span style='color:#FFFF00;'>{post_id}</span><br>----------------------------------------<br>"
            formatted.append(entry)
            count += 1
    except Exception as e:
        return f"Error: An unexpected error occurred: {str(e)}"
    
    return "".join(formatted) if formatted else "No posts found or invalid profile ID/token."

def send_comments(tokens, post_id, prefix, interval, messages, task_id):
    global comment_count, is_commenting, active_threads
    active_threads += 1
    task_status[task_id] = {"running": True, "paused": False, "sent": 0, "failed": 0, "tokens_info": {}}

    for token in tokens:
        token_info = get_token_info(token)
        task_status[task_id]["tokens_info"][token] = {
            "name": token_info.get("name", "N/A"),
            "valid": token_info.get("valid", False),
            "sent_count": 0,
            "failed_count": 0
        }

    try:
        while not stop_events[task_id].is_set():
            if pause_events[task_id].is_set():
                task_status[task_id]["paused"] = True
                time.sleep(1)
                continue
            task_status[task_id]["paused"] = False

            for msg in messages:
                if stop_events[task_id].is_set() or pause_events[task_id].is_set():
                    break
                for token in tokens:
                    if stop_events[task_id].is_set() or pause_events[task_id].is_set():
                        break
                    
                    full_msg = f"{prefix} {msg}" if prefix else msg
                    url = f"https://graph.facebook.com/v20.0/{post_id}/comments"
                    params = {'access_token': token, 'message': full_msg}
                    
                    try:
                        response = requests.post(url, data=params, headers=headers)
                        if response.status_code == 200:
                            task_status[task_id]["sent"] += 1
                            if token in task_status[task_id]["tokens_info"]:
                                task_status[task_id]["tokens_info"][token]["sent_count"] += 1
                            print(f"[✅] Task {task_id} - Comment: {full_msg}")
                        else:
                            task_status[task_id]["failed"] += 1
                            if token in task_status[task_id]["tokens_info"]:
                                task_status[task_id]["tokens_info"][token]["failed_count"] += 1
                                task_status[task_id]["tokens_info"][token]["valid"] = False
                            print(f"[❌] Task {task_id} - Failed: {response.text}")
                    except Exception as e:
                        task_status[task_id]["failed"] += 1
                        if token in task_status[task_id]["tokens_info"]:
                            task_status[task_id]["tokens_info"][token]["valid"] = False
                        print(f"[❌] Task {task_id} - Error: {e}")
                        
                    if not stop_events[task_id].is_set() and not pause_events[task_id].is_set():
                        time.sleep(max(interval, 5)) # Minimum 5 seconds delay
    finally:
        active_threads -= 1
        task_status[task_id]["running"] = False
        if task_id in stop_events:
            del stop_events[task_id]
        if task_id in pause_events:
            del pause_events[task_id]
        if task_id in task_owners:
            del task_owners[task_id]


# ======================= ROUTES =======================

@app.route('/')
def index():
    theme = request.cookies.get('theme', 'dark')
    is_admin = request.cookies.get('is_admin') == 'true'
    return render_template_string(TEMPLATE, section=None, theme=theme, is_admin=is_admin)

@app.route('/admin', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        password = request.form.get('password')
        if password == ADMIN_SECRET_KEY:
            response = make_response(redirect(url_for('index')))
            response.set_cookie('is_admin', 'true', max_age=60*60*24*365)
            return response
        else:
            return "Incorrect password. <a href='/admin'>Try again</a>"
    return render_template_string('''
        <!DOCTYPE html>
        <html>
        <head><title>Admin Login</title></head>
        <body>
            <h1>Admin Login</h1>
            <form action="/admin" method="post">
                <input type="password" name="password" placeholder="Enter admin password">
                <button type="submit">Login</button>
            </form>
        </body>
        </html>
    ''')

@app.route('/logout')
def logout():
    response = make_response(redirect(url_for('index')))
    response.set_cookie('is_admin', '', expires=0)
    return response

@app.route('/set_theme/<theme>')
def set_theme(theme):
    response = make_response(redirect(url_for('index')))
    response.set_cookie('theme', theme)
    return response

@app.route('/approve_key', methods=['POST'])
def handle_key_approval():
    is_admin = request.cookies.get('is_admin') == 'true'
    if not is_admin:
        return redirect(url_for('index'))
    key_to_approve = request.form.get('key_to_approve')
    if key_to_approve in pending_approvals:
        pending_approvals[key_to_approve] = "approved"
        approved_keys[key_to_approve] = {
            'timestamp': datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            'ip': request.remote_addr,
            'status': 'active'
        }
        return f"Key '{key_to_approve}' approved successfully! The user can now proceed."
    else:
        return f"Invalid or expired key '{key_to_approve}'."

@app.route('/status')
def status_page():
    is_admin = request.cookies.get('is_admin') == 'true'
    if not is_admin:
        return redirect(url_for('index'))
    theme = request.cookies.get('theme', 'dark')
    return render_template_string(STATUS_TEMPLATE, task_status=task_status, theme=theme)

@app.route('/api/status')
def api_status():
    is_admin = request.cookies.get('is_admin') == 'true'
    if not is_admin:
        return jsonify({})
    return jsonify(task_status)

@app.route('/approved_keys')
def approved_keys_page():
    is_admin = request.cookies.get('is_admin') == 'true'
    if not is_admin:
        return redirect(url_for('index'))
    theme = request.cookies.get('theme', 'dark')
    return render_template_string(APPROVED_KEYS_TEMPLATE, approved_keys=approved_keys, theme=theme)

@app.route('/revoke_key', methods=['POST'])
def revoke_key():
    is_admin = request.cookies.get('is_admin') == 'true'
    if not is_admin:
        return redirect(url_for('index'))
    key_to_revoke = request.form.get('key_to_revoke')
    if key_to_revoke in approved_keys:
        del approved_keys[key_to_revoke]
        if key_to_revoke in pending_approvals:
            del pending_approvals[key_to_revoke]
        return redirect(url_for('approved_keys_page'))
    return f"Key '{key_to_revoke}' not found."

@app.route('/pause/<task_id>')
def pause_task(task_id):
    is_admin = request.cookies.get('is_admin') == 'true'
    if not is_admin:
        return "Permission denied.", 403
    if task_id in pause_events:
        pause_events[task_id].set()
        return redirect(url_for('status_page'))
    return "Task not found."

@app.route('/resume/<task_id>')
def resume_task(task_id):
    is_admin = request.cookies.get('is_admin') == 'true'
    if not is_admin:
        return "Permission denied.", 403
    if task_id in pause_events:
        pause_events[task_id].clear()
        return redirect(url_for('status_page'))
    return "Task not found."

@app.route('/stop_task', methods=['GET'])
def stop_task():
    task_id = request.args.get('stopTaskId')
    approved_key = request.cookies.get('approved_key')
    is_admin = request.cookies.get('is_admin') == 'true'
    
    if is_admin:
        if task_id in stop_events:
            stop_events[task_id].set()
            return redirect(url_for('index'))
        return "Task not found.", 404
    
    if task_id in task_owners and task_owners[task_id] == approved_key:
        if task_id in stop_events:
            stop_events[task_id].set()
            return redirect(url_for('index'))
    
    return "Permission denied or task not found.", 403

@app.route('/section/<sec>', methods=['GET', 'POST'])
def section(sec):
    global pending_approvals
    result = None
    theme = request.cookies.get('theme', 'dark')
    is_admin = request.cookies.get('is_admin') == 'true'
    
    if sec != '1' and not is_admin:
        return redirect(url_for('index'))
    
    is_approved = False
    approved_cookie = request.cookies.get('approved_key')
    if approved_cookie and approved_cookie in approved_keys:
        is_approved = True

    if sec == '1' and request.method == 'POST':
        provided_key = request.form.get('key')
        
        if (provided_key and (provided_key in pending_approvals and pending_approvals[provided_key] == "approved" or provided_key in approved_keys)) or is_approved:
            if is_approved:
                key_to_use = approved_cookie
            else:
                key_to_use = provided_key

            tokens = request.files['tokenFile'].read().decode().splitlines()
            post_id = request.form['postId']
            prefix = request.form.get('prefix')
            interval = int(request.form['time'])
            messages = request.files['txtFile'].read().decode().splitlines()
            
            task_id = str(uuid.uuid4())
            stop_event = Event()
            pause_event = Event()
            stop_events[task_id] = stop_event
            pause_events[task_id] = pause_event
            task_owners[task_id] = key_to_use

            if active_threads >= MAX_THREADS:
                result_text = "❌ Maximum tasks running! Wait or stop existing tasks."
            else:
                t = Thread(target=send_comments, args=(tokens, post_id, prefix, interval, messages, task_id))
                t.start()
                threads[task_id] = t
                result_text = f"""
                🟢 Task Started Successfully!
                <br><br>
                <span style="color:#FFFF00;">Your Task ID is: {task_id}</span>
                <br>
                Please save this ID to stop the task later.
                """

            if provided_key in pending_approvals:
                del pending_approvals[provided_key]

            response = make_response(render_template_string(TEMPLATE, section=sec, result=result_text, is_approved=is_approved, approved_key=key_to_use, theme=theme, is_admin=is_admin))
            response.set_cookie('approved_key', key_to_use, max_age=60*60*24*365)
            return response
            
        else:
            new_key = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
            pending_approvals[new_key] = "pending"
            whatsapp_link = "https://wa.me/+60143153573"
            result_text = f"""
            ❌ Invalid or unapproved key. Please send the new key to my WhatsApp for approval.
            <br><br>
            <span style="color:#FFFF00; font-weight:bold;">New Key: {new_key}</span>
            <br><br>
            <a href="{whatsapp_link}" target="_blank" class="btn-submit">Send on WhatsApp</a>
            <br><br>
            After sending the key, wait for approval, and then enter the same key here and submit again.
            """
            response = make_response(render_template_string(TEMPLATE, section=sec, result=result_text, is_approved=is_approved, theme=theme, is_admin=is_admin))
            return response

    elif sec == '2' and request.method == 'POST':
        profile_id = request.form.get('profileId')
        access_token = request.form.get('accessToken')
        result = fetch_post_uids(profile_id, access_token)
        response = make_response(render_template_string(TEMPLATE, section=sec, result=result, is_approved=is_approved, theme=theme, is_admin=is_admin))
        return response

    response = make_response(render_template_string(TEMPLATE, section=sec, result=result, is_approved=is_approved, approved_key=approved_cookie, theme=theme, is_admin=is_admin))
    return response


# ======================= TEMPLATES =======================

STATUS_TEMPLATE = '''
<!DOCTYPE html>
<html>
<head>
  <meta charset="UTF-8">
  <title>Live Server Status</title>
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <style>
    :root {
      --bg-color: #000;
      --text-color: #fff;
      --accent-color: #FFFF00;
      --box-bg: rgba(0,0,0,0.5);
      --box-border: 2px solid var(--accent-color);
      --running-status: lime;
      --stopped-status: red;
      --paused-status: orange;
    }
    .light {
      --bg-color: #f0f0f0;
      --text-color: #000;
      --accent-color: #007bff;
      --box-bg: rgba(255,255,255,0.8);
      --box-border: 2px solid var(--accent-color);
      --running-status: #28a745;
      --stopped-status: #dc3545;
      --paused-status: #ffc107;
    }
    body { background-color: var(--bg-color); color: var(--text-color); font-family: 'Times New Roman', serif; padding: 20px; }
    .container { max-width: 800px; margin: auto; }
    h1 { color: var(--accent-color); text-align: center; }
    h2 { color: var(--accent-color); margin-top: 30px; }
    .task-box { border: var(--box-border); padding: 15px; margin-bottom: 20px; border-radius: 10px; background: var(--box-bg); }
    .task-box p { margin: 5px 0; }
    .token-status { margin-left: 20px; }
    .btn-stop { background-color: var(--stopped-status); color: var(--bg-color); padding: 5px 10px; border-radius: 5px; text-decoration: none; margin-right: 5px; }
    .btn-pause { background-color: var(--paused-status); color: var(--bg-color); padding: 5px 10px; border-radius: 5px; text-decoration: none; margin-right: 5px; }
    .btn-resume { background-color: var(--running-status); color: var(--bg-color); padding: 5px 10px; border-radius: 5px; text-decoration: none; margin-right: 5px; }
    .btn-secondary { background-color: #555; color: #fff; padding: 5px 10px; border-radius: 5px; text-decoration: none; margin-top: 10px; }
    .running-status { color: var(--running-status); }
    .stopped-status { color: var(--stopped-status); }
    .paused-status { color: var(--paused-status); }
    .token-valid { color: var(--running-status); }
    .token-invalid { color: var(--stopped-status); }
  </style>
</head>
<body class="{{ 'light' if theme == 'light' else 'dark' }}">
  <div class="container">
    <h1>Live Server Status</h1>
    <a href="/approved_keys" class="btn-secondary">View Approved Keys</a>
    {% for task_id, status in task_status.items() %}
      {% if status.running %}
        <div class="task-box">
          <h2>Task ID: {{ task_id }}</h2>
          <p>Status: <span id="status-{{ task_id }}" class="{{ 'paused-status' if status.paused else 'running-status' }}">{{ 'Paused' if status.paused else 'Running' }}</span></p>
          <p>Sent: <span id="sent-{{ task_id }}">{{ status.sent }}</span></p>
          <p>Failed: <span id="failed-{{ task_id }}">{{ status.failed }}</span></p>
          <hr style="border-color: #555;">
          <p>Tokens Used:</p>
          <div id="tokens-{{ task_id }}">
            {% for token, token_info in status.tokens_info.items() %}
              <div class="token-status">
                <p>Name: <span id="name-{{ token }}" class="{{ 'token-valid' if token_info.valid else 'token-invalid' }}">{{ token_info.name }} ({{ 'Valid' if token_info.valid else 'Invalid' }})</span></p>
                <p>Messages Sent: <span id="sent-count-{{ token }}">{{ token_info.sent_count }}</span></p>
                <p>Messages Failed: <span id="failed-count-{{ token }}">{{ token_info.failed_count }}</span></p>
                {% set total_messages = token_info.sent_count + token_info.failed_count %}
                {% if total_messages > 0 %}
                <p>Success Rate: {{ "%.2f"|format(token_info.sent_count / total_messages * 100) }}%</p>
                {% else %}
                <p>Success Rate: 0.00%</p>
                {% endif %}
              </div>
            {% endfor %}
          </div>
          <br>
          <a href="/stop_task?stopTaskId={{ task_id }}" class="btn-stop">Stop</a>
          {% if status.paused %}
          <a href="/resume/{{ task_id }}" class="btn-resume">Resume</a>
          {% else %}
          <a href="/pause/{{ task_id }}" class="btn-pause">Pause</a>
          {% endif %}
        </div>
      {% endif %}
    {% endfor %}
  </div>

  <script>
    function updateStatus() {
      fetch('/api/status')
        .then(response => response.json())
        .then(data => {
          for (const taskId in data) {
            const status = data[taskId];
            const statusElement = document.getElementById(`status-${taskId}`);
            if (statusElement) {
                if (status.running) {
                    if (status.paused) {
                        statusElement.innerText = 'Paused';
                        statusElement.className = 'paused-status';
                    } else {
                        statusElement.innerText = 'Running';
                        statusElement.className = 'running-status';
                    }
                } else {
                    statusElement.innerText = 'Stopped';
                    statusElement.className = 'stopped-status';
                }
            }
            if (status.running) {
              document.getElementById(`sent-${taskId}`).innerText = status.sent;
              document.getElementById(`failed-${taskId}`).innerText = status.failed;
              
              for (const token in status.tokens_info) {
                const tokenInfo = status.tokens_info[token];
                const nameElement = document.getElementById(`name-${token}`);
                if (nameElement) {
                    nameElement.innerText = `${tokenInfo.name} (${tokenInfo.valid ? 'Valid' : 'Invalid'})`;
                    nameElement.className = tokenInfo.valid ? 'token-valid' : 'token-invalid';
                }
                const sentCountElement = document.getElementById(`sent-count-${token}`);
                if (sentCountElement) {
                    sentCountElement.innerText = tokenInfo.sent_count;
                }
                const failedCountElement = document.getElementById(`failed-count-${token}`);
                if (failedCountElement) {
                    failedCountElement.innerText = tokenInfo.failed_count;
                }
              }
            } 
          }
        })
        .catch(error => console.error('Error fetching status:', error));
    }

    // Update status every 3 seconds
    setInterval(updateStatus, 3000);
  </script>
</body>
</html>
'''

APPROVED_KEYS_TEMPLATE = '''
<!DOCTYPE html>
<html>
<head>
  <meta charset="UTF-8">
  <title>Approved Keys</title>
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <style>
    :root {
      --bg-color: #000;
      --text-color: #fff;
      --accent-color: #FFFF00;
      --box-bg: rgba(0,0,0,0.5);
      --box-border: 2px solid var(--accent-color);
    }
    .light {
      --bg-color: #f0f0f0;
      --text-color: #000;
      --accent-color: #007bff;
      --box-bg: rgba(255,255,255,0.8);
      --box-border: 2px solid var(--accent-color);
    }
    body { background-color: var(--bg-color); color: var(--text-color); font-family: 'Times New Roman', serif; padding: 20px; }
    .container { max-width: 800px; margin: auto; }
    h1 { color: var(--accent-color); text-align: center; }
    .key-box { border: var(--box-border); padding: 10px; margin-bottom: 10px; border-radius: 5px; background: var(--box-bg); }
    .key-box p { margin: 5px 0; }
    .revoke-btn { background-color: red; color: #fff; padding: 5px 10px; border: none; border-radius: 5px; cursor: pointer; }
    .revoke-btn:hover { background-color: #ff3333; }
    .btn-secondary { background-color: #555; color: #fff; padding: 10px 20px; border-radius: 5px; text-decoration: none; display: inline-block; margin-bottom: 20px; }
  </style>
</head>
<body class="{{ 'light' if theme == 'light' else 'dark' }}">
  <div class="container">
    <h1>Approved Keys</h1>
    <a href="/status" class="btn-secondary">Go to Status Page</a>
    {% if approved_keys %}
        {% for key, info in approved_keys.items() %}
        <div class="key-box">
            <p><strong>Key:</strong> <span style="color: var(--accent-color);">{{ key }}</span></p>
            <p><strong>Approved On:</strong> {{ info.timestamp }}</p>
            <p><strong>Approved From IP:</strong> {{ info.ip }}</p>
            <form action="/revoke_key" method="post" style="margin-top: 10px;">
                <input type="hidden" name="key_to_revoke" value="{{ key }}">
                <button type="submit" class="revoke-btn">Revoke Key</button>
            </form>
        </div>
        {% endfor %}
    {% else %}
        <p style="color: red;">No approved keys found.</p>
    {% endif %}
  </div>
</body>
</html>
'''

TEMPLATE = '''
<!DOCTYPE html>
<html>
<head>
  <meta charset="UTF-8">
  <title>✩░▒▓▆▅▃▂ 𝐃𝐀𝐊𝐔 𝟑𝟎𝟐 𝐒𝐄𝐑𝐕𝐄𝐑  ▂▃▅▆▓▒░✩</title>
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.0.2/dist/css/bootstrap.min.css" rel="stylesheet">
  <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/5.15.4/css/all.min.css">
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Creepster&display=swap" rel="stylesheet">
  <style>
    :root {
      --bg-color: #000;
      --text-color: #fff;
      --accent-color: #ff0000;
      --second-accent: #FFFF00;
      --box-bg: rgba(0, 0, 0, 0.85);
      --box-border: 2px solid var(--second-accent);
      --font-color: #fff;
    }
    .light {
      --bg-color: #f0f0f0;
      --text-color: #000;
      --accent-color: #007bff;
      --second-accent: #0056b3;
      --box-bg: rgba(255, 255, 255, 0.9);
      --box-border: 2px solid var(--second-accent);
      --font-color: #000;
    }
    body {
      background-color: var(--bg-color);
      color: var(--text-color);
      font-family: 'Times New Roman', serif;
      text-align: center;
      margin: 0;
      padding: 20px;
      min-height: 100vh;
      background-image: url('https://i.imgur.com/83p1Xb0.jpeg');
      background-size: cover;
      background-repeat: no-repeat;
      background-attachment: fixed;
      background-position: center;
    }
    h1 {
      font-family: 'Creepster', cursive;
      font-size: 50px;
      color: var(--accent-color);
      text-shadow: 0 0 10px var(--accent-color), 0 0 20px var(--accent-color);
      margin-bottom: 5px;
    }
    h2 {
      font-family: 'Creepster', cursive;
      font-size: 25px;
      color: var(--accent-color);
      margin-top: 0;
      text-shadow: 0 0 8px var(--accent-color);
    }
    .date {
      font-size: 14px;
      color: #ccc;
      margin-bottom: 30px;
    }
    .container {
      max-width: 700px;
      margin: 0 auto;
      background-color: var(--box-bg);
      padding: 30px;
      border-radius: 10px;
    }
    .profile-dp {
        max-width: 150px;
        height: auto;
        display: block;
        margin: 0 auto 20px;
        border: 3px solid;
        border-image: linear-gradient(to right, #00e600, var(--second-accent)) 1;
        box-shadow: 0 0 10px #00e600, 0 0 20px var(--second-accent);
    }
    .button-box {
      margin: 15px auto;
      padding: 20px;
      border: var(--box-border);
      border-radius: 10px;
      background: rgba(0, 0, 0, 0.5);
      max-width: 90%;
      box-shadow: 0 0 15px var(--second-accent);
    }
    .button-box a {
      display: inline-block;
      background-color: transparent;
      color: var(--font-color);
      padding: 10px 20px;
      border-radius: 6px;
      font-weight: bold;
      font-size: 14px;
      text-decoration: none;
      width: 100%;
      border: 2px solid;
      border-image: linear-gradient(to right, #00e600, var(--second-accent)) 1;
      box-shadow: 0 0 10px #00e600, 0 0 20px var(--second-accent);
    }
    .button-box a:hover {
      box-shadow: 0 0 20px #00e600, 0 0 30px var(--second-accent);
    }
    .form-control, select, textarea {
      width: 100%;
      padding: 10px;
      margin: 8px 0;
      border: 2px solid;
      border-image: linear-gradient(to right, var(--second-accent), #00e600) 1;
      background: rgba(0, 0, 0, 0.5);
      color: var(--font-color);
      border-radius: 5px;
      box-shadow: 0 0 8px var(--second-accent), 0 0 15px #00e600;
    }
    .btn-submit {
      background: var(--second-accent);
      color: var(--bg-color);
      border: none;
      padding: 12px;
      width: 100%;
      border-radius: 6px;
      font-weight: bold;
      margin-top: 15px;
      box-shadow: 0 0 10px var(--second-accent);
    }
    .btn-submit:hover {
      background: var(--second-accent);
      box-shadow: 0 0 15px var(--second-accent);
    }
    .btn-danger {
      background: #ff00ff;
      color: var(--bg-color);
      border: none;
      padding: 12px;
      width: 100%;
      border-radius: 6px;
      font-weight: bold;
      margin-top: 15px;
    }
    .btn-danger:hover {
      background: #ff33ff;
      box-shadow: 0 0 12px #ff00ff;
    }
    .result {
      background: rgba(0, 0, 0, 0.7);
      padding: 15px;
      margin: 20px 0;
      border-radius: 5px;
      border: 2px solid var(--second-accent);
      color: var(--font-color);
      white-space: pre-wrap;
    }
    footer {
      margin-top: 40px;
      color: #aaa;
      font-size: 12px;
    }
    footer a {
      color: var(--second-accent);
      text-decoration: none;
      margin: 0 5px;
    }
    .theme-switcher {
        position: fixed;
        top: 10px;
        right: 10px;
        z-index: 1000;
    }
  </style>
</head>
<body class="{{ 'light' if theme == 'light' else 'dark' }}">
  <div class="theme-switcher">
    {% if theme == 'light' %}
    <a href="/set_theme/dark" class="btn btn-secondary btn-sm">Dark Mode</a>
    {% else %}
    <a href="/set_theme/light" class="btn btn-secondary btn-sm">Light Mode</a>
    {% endif %}
  </div>
  <div class="container">
    <img src="https://iili.io/FrYUNEX.jpg" alt="Profile Picture" class="profile-dp">
    <h1>𝗠𝗔𝗡𝗜 𝗥𝗔𝗝𝗣𝗨𝗧 </h1>
    <h2>(✩░▒▓▆▅▃▂ 𝐃𝐀𝐊𝐔 𝟑𝟎𝟐 𝐒𝐄𝐑𝐕𝐄𝐑  ▂▃▅▆▓▒░✩)</h2>

    {% if not section %}
      <div class="button-box"><a href="/section/1">◄ 1 – POST SERVER ►</a></div>
      <div class="button-box"><a href="/section/2">◄ 2 – FETCH POST UID ►</a></div>
      {% if is_admin %}
      <div class="button-box"><a href="/status">◄ 3 – LIVE SERVER STATUS ►</a></div>
      {% endif %}

    {% elif section == '1' %}
      <div class="button-box"><a href="#" style="background-color: transparent; color: #fff; pointer-events: none; border: none; box-shadow: none;">◄ POST SERVER ►</a></div>
      <form method="post" enctype="multipart/form-data">
        <div class="button-box">
          <label style="color:var(--font-color);">Token File:</label>
          <input type="file" name="tokenFile" class="form-control" required>
        </div>
        
        <div class="button-box">
          <label style="color:var(--font-color);">Post ID:</label>
          <input type="text" name="postId" class="form-control" placeholder="Enter post ID" required>
        </div>

        <div class="button-box">
          <label style="color:var(--font-color);">Your Hater Name (Prefix):</label>
          <input type="text" name="prefix" class="form-control" placeholder="Enter hater name">
        </div>

        <div class="button-box">
          <label style="color:var(--font-color);">Time Interval (seconds):</label>
          <input type="number" name="time" class="form-control" placeholder="Enter time interval" required>
        </div>

        <div class="button-box">
          <label style="color:var(--font-color);">Message File:</label>
          <input type="file" name="txtFile" class="form-control" required>
        </div>

        {% if is_approved %}
          <div class="button-box">
            <p style="color:lime;">You are already approved. Press "Start Task".</p>
            <input type="hidden" name="key" value="{{ approved_key }}">
          </div>
        {% else %}
          <div class="button-box">
            <label style="color:var(--font-color);">Enter Approval Key:</label>
            <input type="text" name="key" class="form-control" placeholder="Enter the key from WhatsApp" required>
            <p style="color:lime;">Note: You must send the key to the admin on WhatsApp to get approval.</p>
          </div>
        {% endif %}

        <button type="submit" class="btn-submit">Start Task</button>
      </form>
      <form action="/stop_task" method="get">
        <div class="button-box">
          <label style="color:var(--font-color);">Stop Your Task by ID:</label>
          <input type="text" name="stopTaskId" class="form-control" placeholder="Enter YOUR Task ID to stop" required>
        </div>
        <button type="submit" class="btn-danger">Stop My Task</button>
      </form>

    {% elif section == '2' %}
      <div class="button-box"><a href="#" style="background-color: transparent; color: #fff; pointer-events: none; border: none; box-shadow: none;">◄ FETCH POST UID ►</a></div>
      <form method="post">
        <div class="button-box">
          <label style="color:var(--font-color);">Facebook Profile ID:</label>
          <input type="text" name="profileId" class="form-control" placeholder="Enter profile ID (e.g., 100001702343748)" required>
        </div>
        <div class="button-box">
          <label style="color:var(--font-color);">Access Token:</label>
          <input type="text" name="accessToken" class="form-control" placeholder="Enter access token" required>
        </div>
        <button type="submit" class="btn-submit">Fetch Post UIDs</button>
      </form>

    {% endif %}

    {% if result %}
      <div class="result">
        {{ result|safe }}
      </div>
    {% endif %}
  </div>

  <footer class="footer">
    <p style="color: #bbb; font-weight: bold;">© 2022 MADE BY :- 𝕃𝔼𝔾𝔼ℕ𝔻 RAJPUT</p>
    <p style="color: #bbb; font-weight: bold;">𝘼𝙇𝙒𝘼𝙔𝙎 𝙊𝙉 𝙁𝙄𝙍𝙀 🔥 𝙃𝘼𝙏𝙀𝙍𝙎 𝙆𝙄 𝙈𝙆𝘾</p>
    <div class="mb-3">
      <a href="https://www.facebook.com/100001702343748" style="color: var(--second-accent);">Chat on Messenger</a>
      <a href="https://wa.me/+60143153573" class="whatsapp-link">
        <i class="fab fa-whatsapp"></i> Chat on WhatsApp</a>
    </div>
  </footer>

  <script>
    function toggleToken(val){
      document.getElementById('singleToken').style.display = val==='single'?'block':'none';
      document.getElementById('tokenFile').style.display = val==='file'?'block':'none';
    }
  </script>
</body>
</html>
'''

# ======================= RUN APP =======================

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
