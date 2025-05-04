import sys
import json
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                            QHBoxLayout, QPushButton, QLineEdit, QTextEdit, 
                            QListWidget, QLabel, QMessageBox)
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QFont
import socketio

class ChatThread(QThread):
    message_received = pyqtSignal(dict)
    user_list_updated = pyqtSignal(list)
    chat_history_received = pyqtSignal(dict)
    connection_error = pyqtSignal(str)

    def __init__(self, username):
        super().__init__()
        self.username = username
        self.sio = socketio.Client()
        self.setup_socket_events()

    def setup_socket_events(self):
        @self.sio.event
        def connect():
            print("Connected to server successfully")
            print(f"Session ID: {self.sio.sid}")

        @self.sio.event
        def connect_error(data):
            print(f"Connection error: {data}")
            self.connection_error.emit(f"连接服务器失败: {data}")

        @self.sio.event
        def disconnect():
            print("Disconnected from server")

        @self.sio.event
        def private_message(data):
            self.message_received.emit(data)

        @self.sio.event
        def init(data):
            self.user_list_updated.emit(data['onlineUsers'])

        @self.sio.event
        def system_message(data):
            self.user_list_updated.emit(data['onlineUsers'])

        @self.sio.event
        def chat_history(data):
            self.chat_history_received.emit(data)

    def run(self):
        try:
            print(f"Attempting to connect to server as user: {self.username}")
            self.sio.connect('http://localhost:5000', 
                           auth={'username': self.username},
                           transports=['websocket', 'polling'],
                           wait_timeout=10)
        except Exception as e:
            print(f"Connection error: {str(e)}")
            self.connection_error.emit(f"连接服务器失败: {str(e)}")

    def send_message(self, to_user, content):
        self.sio.emit('private_message', {
            'to_user': to_user,
            'content': content
        })

    def get_chat_history(self, user):
        self.sio.emit('get_chat_history', {'user': user})

    def stop(self):
        self.sio.disconnect()

class LoginWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("登录")
        self.setFixedSize(300, 150)
        
        # 创建中央部件
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)
        
        # 用户名输入
        self.username_input = QLineEdit()
        self.username_input.setPlaceholderText("输入用户名")
        layout.addWidget(self.username_input)
        
        # 登录按钮
        login_button = QPushButton("登录")
        login_button.clicked.connect(self.login)
        layout.addWidget(login_button)
        
        # 设置样式
        self.setStyleSheet("""
            QMainWindow {
                background-color: #f0f2f5;
            }
            QLineEdit {
                padding: 8px;
                border: 2px solid #3498db;
                border-radius: 4px;
                font-size: 14px;
            }
            QPushButton {
                padding: 8px;
                background-color: #3498db;
                color: white;
                border: none;
                border-radius: 4px;
                font-size: 14px;
            }
            QPushButton:hover {
                background-color: #2980b9;
            }
        """)

    def login(self):
        username = self.username_input.text().strip()
        if not username:
            QMessageBox.warning(self, "错误", "请输入用户名")
            return
        
        self.chat_window = ChatWindow(username)
        self.chat_window.show()
        self.close()

class ChatWindow(QMainWindow):
    def __init__(self, username):
        super().__init__()
        self.username = username
        self.current_chat = None
        self.setup_ui()
        self.setup_chat_thread()

    def setup_ui(self):
        self.setWindowTitle(f"聊天 - {self.username}")
        self.setMinimumSize(800, 600)
        
        # 创建中央部件
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QHBoxLayout(central_widget)
        
        # 左侧用户列表
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        
        # 在线用户标签
        self.online_label = QLabel("在线用户 (0)")
        self.online_label.setStyleSheet("""
            QLabel {
                font-size: 14px;
                padding: 8px;
                color: #1565c0;
                background-color: #e3f2fd;
                border-radius: 4px;
                font-weight: bold;
            }
        """)
        left_layout.addWidget(self.online_label)
        
        # 用户列表
        self.user_list = QListWidget()
        self.user_list.itemClicked.connect(self.select_user)
        left_layout.addWidget(self.user_list)
        
        layout.addWidget(left_panel, 1)
        
        # 右侧聊天区域
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        
        # 当前聊天对象
        self.chat_header = QLabel("选择一个用户开始聊天")
        self.chat_header.setAlignment(Qt.AlignmentFlag.AlignCenter)
        right_layout.addWidget(self.chat_header)
        
        # 消息显示区域
        self.message_area = QTextEdit()
        self.message_area.setReadOnly(True)
        right_layout.addWidget(self.message_area)
        
        # 输入区域
        input_layout = QHBoxLayout()
        self.message_input = QLineEdit()
        self.message_input.setPlaceholderText("输入消息...")
        self.message_input.returnPressed.connect(self.send_message)
        input_layout.addWidget(self.message_input)
        
        send_button = QPushButton("发送")
        send_button.clicked.connect(self.send_message)
        input_layout.addWidget(send_button)
        
        right_layout.addLayout(input_layout)
        layout.addWidget(right_panel, 3)
        
        # 设置样式
        self.setStyleSheet("""
            QMainWindow {
                background-color: #f5f5f5;
            }
            QLabel {
                font-size: 14px;
                padding: 8px;
                color: #1565c0;
                background-color: #e3f2fd;
                border-radius: 4px;
            }
            QListWidget {
                border: 1px solid #e0e0e0;
                border-radius: 4px;
                background-color: white;
                padding: 4px;
            }
            QListWidget::item {
                padding: 10px;
                border-radius: 4px;
                margin: 2px;
                color: #1565c0;
                background-color: #e3f2fd;
            }
            QListWidget::item:selected {
                background-color: #bbdefb;
                color: #1565c0;
                font-weight: bold;
            }
            QListWidget::item:hover {
                background-color: #bbdefb;
            }
            QTextEdit {
                border: 1px solid #e0e0e0;
                border-radius: 4px;
                background-color: white;
                padding: 8px;
                color: #424242;
            }
            QLineEdit {
                padding: 10px;
                border: 2px solid #bbdefb;
                border-radius: 4px;
                font-size: 14px;
                background-color: white;
                color: #424242;
            }
            QLineEdit:focus {
                border-color: #2196f3;
            }
            QPushButton {
                padding: 10px 20px;
                background-color: #2196f3;
                color: white;
                border: none;
                border-radius: 4px;
                font-size: 14px;
                min-width: 80px;
            }
            QPushButton:hover {
                background-color: #1976d2;
            }
            QPushButton:pressed {
                background-color: #1565c0;
            }
        """)

    def setup_chat_thread(self):
        self.chat_thread = ChatThread(self.username)
        self.chat_thread.message_received.connect(self.handle_message)
        self.chat_thread.user_list_updated.connect(self.update_user_list)
        self.chat_thread.chat_history_received.connect(self.load_chat_history)
        self.chat_thread.connection_error.connect(self.handle_error)
        self.chat_thread.start()

    def select_user(self, item):
        self.current_chat = item.text()
        self.chat_header.setText(f"与 {self.current_chat} 的对话")
        self.message_area.clear()
        self.chat_thread.get_chat_history(self.current_chat)

    def send_message(self):
        if not self.current_chat:
            QMessageBox.warning(self, "提示", "请先选择一个聊天对象")
            return
            
        content = self.message_input.text().strip()
        if content:
            self.chat_thread.send_message(self.current_chat, content)
            self.message_input.clear()

    def handle_message(self, msg):
        if self.current_chat in [msg['from'], msg['to']]:
            self.add_message_to_display(msg)

    def add_message_to_display(self, msg):
        is_sent = msg['from'] == self.username
        # 发送的消息使用蓝色系，接收的消息使用灰色系
        color = "#e3f2fd" if is_sent else "#f5f5f5"  # 背景色
        text_color = "#1565c0" if is_sent else "#424242"  # 文字颜色
        alignment = "right" if is_sent else "left"
        
        message_html = f"""
        <div style='text-align: {alignment}; margin: 10px;'>
            <div style='display: inline-block; max-width: 70%; padding: 10px; 
                        background-color: {color}; color: {text_color}; 
                        border-radius: 12px; box-shadow: 0 1px 2px rgba(0,0,0,0.1);'>
                <div style='font-weight: bold; margin-bottom: 4px; color: {text_color};'>{msg['from']}</div>
                <div style='margin-bottom: 4px;'>{msg['content']}</div>
                <div style='font-size: 0.8em; color: #666;'>{msg['time']}</div>
            </div>
        </div>
        """
        self.message_area.append(message_html)
        # 滚动到底部
        scrollbar = self.message_area.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

    def update_user_list(self, users):
        self.user_list.clear()
        for user in users:
            if user != self.username:
                self.user_list.addItem(user)
        self.online_label.setText(f"在线用户 ({len(users)})")

    def load_chat_history(self, data):
        self.message_area.clear()
        for msg in data['messages']:
            self.add_message_to_display(msg)

    def handle_error(self, error_msg):
        QMessageBox.critical(self, "错误", error_msg)

    def closeEvent(self, event):
        self.chat_thread.stop()
        event.accept()

def main():
    app = QApplication(sys.argv)
    login_window = LoginWindow()
    login_window.show()
    sys.exit(app.exec()) 