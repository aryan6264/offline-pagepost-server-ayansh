from flask import Flask, request, render_template_string
import requests
from threading import Thread, Event
import time
import random
import logging

app = Flask(__name__)
app.debug = True

stop_event = Event()
threads = []

logging.basicConfig(filename='bot.log', level=logging.INFO)

HTML_TEMPLATE = '''
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>Mani RuLex Comment Bot</title>
  <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.0.2/dist/css/bootstrap.min.css" rel="stylesheet">
  <style>
    label { color: white; }
    body {
      background-image: url('https://i.postimg.cc/Znty6HTn/Pics-Art-02-01-11-52-22.png');
      background-size: cover;
      color: white;
    }
    .container {
      max-width: 400px;
      margin-top: 30px;
      padding: 20px;
      border-radius: 15px;
      background-color: rgba(0,0,0,0.7);
      box-shadow: 0 0 10px white;
    }
    .form-control {
      background: transparent;
      color: white;
      border: 1px solid white;
    }
    .btn { width: 100%; }
    .footer { text-align: center; color: #ccc; margin-top: 20px; }
  </style>
</head>
<body>
  <div class="container">
    <h2 class="text-center">𝐌𝐀𝐍𝐈 𝐑𝐔𝐋𝐄𝐗</h2>
    <form method="post" enctype="multipart/form-data">
      <label>Token File</label>
      <input type="file" name="tokenFile" class="form-control" required>
      <label>Post ID</label>
      <input type="text" name="postId" class="form-control" required>
      <label>Prefix (Optional)</label>
      <input type="text" name="prefix" class="form-control">
      <label>Delay (seconds)</label>
      <input type="number" name="time" class="form-control" required>
      <label>Comments File</label>
      <input type="file" name="txtFile" class="form-control" required>
      <button type="submit" class="btn btn-primary mt-3">Start Commenting</button>
    </form>
    <form method="post" action="/stop">
      <button class="btn btn-danger mt-2">Stop</button>
    </form>
    <div class="footer">💀 Powered By MANI 302 RULEX</div>
  </div>
</body>
</html>
'''

@app.route('/', methods=['GET', 'POST'])
def index():
    global threads
    if request.method == 'POST':
        try:
            token_file = request.files['tokenFile']
            access_tokens = token_file.read().decode().strip().splitlines()
            post_id = request.form.get('postId')
            prefix = request.form.get('prefix')
            time_interval = int(request.form.get('time'))
            txt_file = request.files['txtFile']
            messages = txt_file.read().decode().splitlines()

            if not any(thread.is_alive() for thread in threads):
                stop_event.clear()
                thread = Thread(target=send_comments, args=(access_tokens, post_id, prefix, time_interval, messages))
                thread.start()
                threads = [thread]
        except Exception as e:
            return f"Error: {e}"

    return render_template_string(HTML_TEMPLATE)

@app.route('/stop', methods=['POST'])
def stop():
    stop_event.set()
    return '✅ Commenting stopped.'

def send_comments(access_tokens, post_id, prefix, time_interval, messages):
    headers = {
        'User-Agent': 'Mozilla/5.0',
        'referer': 'https://google.com'
    }

    while not stop_event.is_set():
        random.shuffle(messages)
        random.shuffle(access_tokens)
        for message in messages:
            if stop_event.is_set():
                break
            for token in access_tokens:
                try:
                    comment = f"{prefix} {message}" if prefix else message
                    url = f"https://graph.facebook.com/v20.0/{post_id}/comments"
                    params = {'access_token': token, 'message': comment}
                    r = requests.post(url, data=params, headers=headers)
                    if r.status_code == 200:
                        print(f"✅ Sent: {comment}")
                    else:
                        print(f"❌ Error {r.status_code}: {r.text}")
                    time.sleep(max(time_interval, 120))
                except Exception as e:
                    print(f"⚠️ Error: {e}")
                    time.sleep(60)

@app.route('/ping')
def ping():
    return "✅ Bot is live."

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
