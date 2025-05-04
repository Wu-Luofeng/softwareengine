from flask import Flask, render_template, request, session, redirect
from flask_socketio import SocketIO, emit
from datetime import datetime
import os
import time
import json

# 初始化Flask应用
app = Flask(__name__)
app.secret_key = os.urandom(24)
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SECURE'] = False  # 开发环境设置为False
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'

# 配置Socket.IO
socketio = SocketIO(app,
                    cors_allowed_origins="*",
                    logger=True,
                    engineio_logger=True,
                    async_mode='threading')


# 安全头中间件
@app.after_request
def add_security_headers(response):
    headers = {
        'X-Content-Type-Options': 'nosniff',
        'X-Frame-Options': 'DENY',
        'Content-Security-Policy': "default-src 'self' 'unsafe-inline' https://cdnjs.cloudflare.com; connect-src 'self' ws: wss:",
        'Strict-Transport-Security': 'max-age=31536000; includeSubDomains'
    }
    for key, value in headers.items():
        response.headers[key] = value
    return response


# 数据存储
messages = {}  # {user_pair: [messages]}  user_pair 是排序后的用户名组合
online_users = {}  # {username: sid}


@app.route('/')
def index():
    if 'username' in session and session['username'] in online_users:
        return redirect('/chat')
    return render_template('login.html')


@app.route('/login', methods=['POST'])
def login():
    username = request.form.get('username', '').strip()[:20]
    if not username:
        return render_template('login.html', error="用户名不能为空")

    if username in online_users:
        return render_template('login.html', error="用户名已被使用")

    session['username'] = username
    return redirect('/chat')


@app.route('/chat')
def chat():
    if 'username' not in session:
        return redirect('/')
    return render_template('chat.html')


# WebSocket事件处理
@socketio.on('connect')
def handle_connect(auth):
    print(f"\n=== 新连接 ===")
    print(f"Session ID: {request.sid}")
    print(f"Auth数据: {auth}")

    username = auth.get('username') if auth else None
    if not username:
        print("未提供用户名")
        return False

    if username in online_users:
        print(f"用户名冲突: {username}")
        emit('duplicate_login')
        time.sleep(1)
        return False

    print(f"用户 {username} 连接成功")
    online_users[username] = request.sid
    session['username'] = username

    # 发送初始化数据
    emit('init', {
        'user': username,
        'onlineUsers': list(online_users.keys()),
        'onlineCount': len(online_users)
    })

    # 广播用户加入（包括发送者）
    emit('system_message', {
        'type': 'join',
        'user': username,
        'time': datetime.now().strftime("%H:%M:%S"),
        'onlineCount': len(online_users),
        'onlineUsers': list(online_users.keys())
    }, broadcast=True)

    print(f"当前在线用户: {online_users.keys()}\n")


@socketio.on('disconnect')
def handle_disconnect():
    username = session.get('username')
    if username in online_users:
        print(f"\n=== 用户断开 ===")
        print(f"用户 {username} 断开连接")
        del online_users[username]

        emit('system_message', {
            'type': 'leave',
            'user': username,
            'time': datetime.now().strftime("%H:%M:%S"),
            'onlineCount': len(online_users),
            'onlineUsers': list(online_users.keys())
        }, broadcast=True)

        print(f"剩余在线用户: {online_users.keys()}\n")


@socketio.on('private_message')
def handle_private_message(data):
    print("\n=== 收到私聊消息 ===")
    username = session.get('username')
    print(f"发送用户: {username}")
    print(f"消息内容: {data}")

    if not username or username not in online_users:
        print("非法用户发送消息")
        return

    content = data.get('content', '').strip()
    to_user = data.get('to_user', '').strip()
    
    if not content or len(content) > 500 or not to_user:
        print("消息内容无效")
        return

    if to_user not in online_users:
        print("目标用户不在线")
        return

    # 创建用户对（确保顺序一致）
    user_pair = tuple(sorted([username, to_user]))
    if user_pair not in messages:
        messages[user_pair] = []

    message = {
        'from': username,
        'to': to_user,
        'content': content,
        'time': datetime.now().strftime("%H:%M:%S"),
        'timestamp': time.time()
    }

    messages[user_pair].append(message)

    # 发送给发送者
    emit('private_message', message)
    
    # 发送给接收者
    emit('private_message', message, room=online_users[to_user])


@socketio.on('get_chat_history')
def handle_get_chat_history(data):
    username = session.get('username')
    other_user = data.get('user', '').strip()
    
    if not username or not other_user:
        return
        
    user_pair = tuple(sorted([username, other_user]))
    history = messages.get(user_pair, [])
    
    emit('chat_history', {
        'user': other_user,
        'messages': history
    })


if __name__ == '__main__':
    print("=== 启动服务器 ===")
    socketio.run(app,
                 host='0.0.0.0',
                 port=5000,
                 debug=True,
                 allow_unsafe_werkzeug=True)