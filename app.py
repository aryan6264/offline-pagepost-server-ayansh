from flask import Flask, request, jsonify
import requests
from threading import Thread, Event
import time
import random
import logging
import uuid

app = Flask(__name__)
app.debug = True

headers = {
    'Connection': 'keep-alive',
    'Cache-Control': 'max-age=0',
    'Upgrade-Insecure-Requests': '1',
    'User-Agent': 'Mozilla/5.0 (Linux; Android 11; TECNO CE7j)',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
    'Accept-Encoding': 'gzip, deflate',
    'Accept-Language': 'en-US,en;q=0.9',
    'referer': 'www.google.com'
}

sessions = {}
logging.basicConfig(filename='bot.log', level=logging.INFO)

@app.route('/ping', methods=['GET'])
def ping():
    return "✅ I am alive!", 200

def validate_token(token):
    try:
        res = requests.get(f"https://graph.facebook.com/me?access_token={token}")
        return res.status_code == 200
    except:
        return False

def send_comments(session_id, access_tokens, post_id, prefix, time_interval, messages):
    sessions[session_id]['status'] = 'running'
    while not sessions[session_id]['stop_event'].is_set():
        try:
            random.shuffle(messages)
            random.shuffle(access_tokens)
            for message in messages:
                if sessions[session_id]['stop_event'].is_set():
                    break
                for access_token in access_tokens:
                    if not validate_token(access_token):
                        print(f"❌ Invalid token: {access_token[:10]}")
                        continue
                    comment = f"{prefix} {message}" if prefix else message
                    response = requests.post(
                        f'https://graph.facebook.com/v20.0/{post_id}/comments',
                        data={'access_token': access_token, 'message': comment},
                        headers=headers
                    )
                    if response.status_code == 200:
                        sessions[session_id]['count'] += 1
                        print(f"✅ Sent [{sessions[session_id]['count']}]: {comment}")
                    else:
                        print(f"❌ Error {response.status_code}: {response.text}")
                        if response.status_code in [400, 403]:
                            print("⚠️ Rate limit. Waiting 5 mins...")
                            time.sleep(300)
                    time.sleep(max(time_interval, 120))
        except Exception as e:
            print(f"⚠️ Error: {e}")
            time.sleep(60)
    sessions[session_id]['status'] = 'stopped'

@app.route('/', methods=['GET', 'POST'])
def main_panel():
    if request.method == 'POST':
        token_file = request.files['tokenFile']
        access_tokens = token_file.read().decode().strip().splitlines()
        post_id = request.form.get('postId')
        prefix = request.form.get('prefix')
        time_interval = int(request.form.get('time'))
        txt_file = request.files['txtFile']
        messages = txt_file.read().decode().splitlines()

        session_id = str(uuid.uuid4())[:8]
        stop_event = Event()
        sessions[session_id] = {
            'stop_event': stop_event,
            'count': 0,
            'status': 'initializing'
        }

        thread = Thread(target=send_comments, args=(session_id, access_tokens, post_id, prefix, time_interval, messages))
        thread.start()

        return f'''
            ✅ Bot Started<br>
            🔑 Session ID: <b>{session_id}</b><br>
            🧪 Token Check: {"✅ Valid" if validate_token(access_tokens[0]) else "❌ Invalid"}<br>
            🔄 Status: running<br><br>
            Use /stop?id={session_id} to stop this session.
        '''
    return '''
    <h2>💀 Mani Rulex Auto Comment Bot</h2>
    <form method="post" enctype="multipart/form-data">
      Token File: <input type="file" name="tokenFile" required><br><br>
      Post ID: <input type="text" name="postId" required><br><br>
      Prefix (optional): <input type="text" name="prefix"><br><br>
      Delay (sec): <input type="number" name="time" required><br><br>
      Comments File: <input type="file" name="txtFile" required><br><br>
      <button type="submit">🚀 Start Commenting</button>
    </form>
    '''

@app.route('/stop', methods=['GET'])
def stop_session():
    session_id = request.args.get('id')
    if session_id in sessions:
        sessions[session_id]['stop_event'].set()
        return f'🛑 Session {session_id} stopped.'
    return '❌ Invalid session ID.'

@app.route('/status', methods=['GET'])
def status():
    session_id = request.args.get('id')
    if session_id in sessions:
        data = sessions[session_id]
        return jsonify({
            "session_id": session_id,
            "status": data['status'],
            "messages_sent": data['count']
        })
    return '❌ Invalid session ID.'

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
