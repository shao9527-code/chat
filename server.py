from flask import Flask, render_template, request, jsonify
from flask_socketio import SocketIO, emit, join_room, leave_room
import os
from datetime import datetime
import json
import random
import re

app = Flask(__name__, static_folder='static', template_folder='templates')
app.config['SECRET_KEY'] = 'secret!'
socketio = SocketIO(app, cors_allowed_origins='*')

# 存储在线用户信息
online_users = {}
# 存储房间信息
rooms = {}

# 读取配置文件
def load_config():
    config_path = 'config.json'
    if os.path.exists(config_path):
        with open(config_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {"servers": [{"name": "默认服务器", "url": "http://localhost:5000"}]}

# 保存配置文件
def save_config(config):
    config_path = 'config.json'
    with open(config_path, 'w', encoding='utf-8') as f:
        json.dump(config, f, ensure_ascii=False, indent=2)

# 首页路由
@app.route('/')
def index():
    return render_template('login.html')

# 聊天室页面路由
@app.route('/chat')
def chat():
    return render_template('chat.html')

# 获取服务器列表
@app.route('/api/servers', methods=['GET'])
def get_servers():
    config = load_config()
    return jsonify(config)

# WebSocket事件处理
@socketio.on('connect')
def handle_connect():
    print('客户端连接:', request.sid)

@socketio.on('disconnect')
def handle_disconnect():
    if request.sid in online_users:
        username = online_users[request.sid]['username']
        room = online_users[request.sid]['room']
        
        # 从在线用户列表移除
        del online_users[request.sid]
        
        # 更新房间用户列表
        if room in rooms:
            rooms[room] = [user for user in rooms.get(room, []) if user != username]
        
        # 广播用户离开消息
        emit('user_left', {
            'username': username,
            'room': room,
            'online_users': rooms.get(room, []),
            'timestamp': datetime.now().strftime('%H:%M:%S')
        }, room=room)
        
        print(f'用户离开: {username}，房间: {room}')

@socketio.on('join_room')
def handle_join_room(data):
    username = data['username']
    room = data['room']
    
    # 检查昵称是否已存在
    if room in rooms and username in rooms[room]:
        emit('nickname_taken', {
            'message': '昵称已被使用，请选择其他昵称'
        }, to=request.sid)
        return
    
    # 加入房间
    join_room(room)
    
    # 记录用户信息
    online_users[request.sid] = {
        'username': username,
        'room': room,
        'joined_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    }
    
    # 更新房间用户列表
    if room not in rooms:
        rooms[room] = []
    rooms[room].append(username)
    
    # 向新用户发送欢迎消息
    emit('join_success', {
        'room': room,
        'online_users': rooms[room],
        'username': username
    }, to=request.sid)
    
    # 广播新用户加入消息
    emit('user_joined', {
        'username': username,
        'room': room,
        'online_users': rooms[room],
        'timestamp': datetime.now().strftime('%H:%M:%S')
    }, room=room, skip_sid=request.sid)
    
    print(f'用户加入: {username}，房间: {room}')

@socketio.on('send_message')
def handle_send_message(data):
    if request.sid not in online_users:
        return
    
    username = online_users[request.sid]['username']
    room = online_users[request.sid]['room']
    message = data['message']
    
    # 直接使用客户端传来的command对象（如果存在）
    command_data = data.get('command')
    
    # 如果客户端没有提供command对象但消息以@开头，则进行简单解析
    if not command_data and message.startswith('@'):
        parts = message.split(' ', 1)
        if len(parts) > 1:
            command = parts[0][1:]
            command_data = {
                'type': command,
                'content': parts[1]
            }
    
    # 构造消息对象
    msg_data = {
        'username': username,
        'message': message,
        'timestamp': datetime.now().strftime('%H:%M:%S'),
        'command': command_data
    }
    
    # 广播消息
    emit('new_message', msg_data, room=room)
    
    # 处理@川小农命令
    if command_data and command_data['type'] == '川小农':
        handle_chuanxiaonong_message(username, room, command_data['content'])

def handle_chuanxiaonong_message(username, room, content):
    """处理川小农AI助手的消息"""
    # 可爱的表情包列表
    cute_emojis = ['😊', '🥰', '😍', '🤗', '✨', '🌸', '🌟', '💖']
    trash_emojis = ['🗑️', '🚮', '🖕', '🤢', '😡']
    
    # 随机选择一个可爱的表情包
    random_emoji = random.choice(cute_emojis)
    trash_emoji = random.choice(trash_emojis)
    
    # 检查是否包含其他学校信息
    other_schools = ['成都大学', '电子科大', '四川大学', '西南交大', '西南财经', '西南民族大学', 
                    '四川师范', '成都理工', '成都信息工程', '西华大学']
    contains_other_school = any(school in content for school in other_schools)
    
    # 检查用户是否在询问其他学校
    if contains_other_school:
        response = f"{trash_emoji} 我只关心四川农业大学，其他学校关我什么事！{trash_emoji}"
        send_ai_response(room, response)
        return
    
    # 输出开场白
    opening_line = f"{random_emoji} 小花知道了"
    send_ai_response(room, opening_line)
    
    # 如果内容为空，只介绍名字和角色
    if not content.strip():
        response = "大家好，我是川小农，四川农业大学的AI小助手。"
        send_ai_response(room, response)
        return
    
    # 检查是否是生成古诗的指令
    if '古诗' in content or '诗' in content and '生成' in content:
        response = generate_poem(content)
        send_ai_response(room, response)
        return
    
    # 检查是否是生成通知的指令
    if '通知' in content and ('生成' in content or '写' in content):
        response = generate_notification(content)
        send_ai_response(room, response)
        return
    
    # 检查是否是关于四川农业大学的问题
    if is_sicau_question(content):
        response = answer_sicau_question(content)
        send_ai_response(room, response)
        return
    
    # 其他情况
    response = "滚一边去"
    send_ai_response(room, response)

def send_ai_response(room, message):
    """发送AI助手的响应"""
    response_data = {
        'username': '川小农',
        'message': message,
        'timestamp': datetime.now().strftime('%H:%M:%S'),
        'command': {
            'type': '川小农',
            'content': message
        }
    }
    emit('new_message', response_data, room=room)

def is_sicau_question(content):
    """检查是否是关于四川农业大学的问题"""
    sicau_keywords = ['四川农业大学', '川农', '川农大', '雅安校区', '成都校区', '都江堰校区',
                    '校训', '历史', '专业', '学院', '校长', '招生', '分数线']
    return any(keyword in content for keyword in sicau_keywords)

def answer_sicau_question(content):
    """回答关于四川农业大学的问题"""
    responses = {
        '四川农业大学': '四川农业大学是一所以生物科技为特色，农业科技为优势，多学科协调发展的国家"双一流"建设高校。',
        '川农': '川农是四川农业大学的简称，是中国西南地区重要的农业高等学府。',
        '校区': '四川农业大学有三个校区：雅安校区、成都校区和都江堰校区。',
        '校训': '四川农业大学校训是：追求真理、造福社会、自强不息。',
        '历史': '四川农业大学始建于1906年的四川通省农业学堂，是中国最早的农业高等院校之一。',
        '专业': '四川农业大学设有农学、动物科技、风景园林、食品科学等多个优势专业。',
        '校长': '四川农业大学现任校长是吴德。',
        '招生': '四川农业大学每年面向全国招生，具体招生计划可关注学校官方网站。'
    }
    
    # 寻找匹配的关键词并返回相应回答
    for keyword, answer in responses.items():
        if keyword in content:
            return answer
    
    # 默认回答
    return "四川农业大学是一所很棒的大学，你可以问我更具体的问题哦！"

def generate_poem(content):
    """生成七言风格的古诗"""
    # 预定义一些七言诗句模板
    poem_templates = [
        "春回大地万物苏，川农校园换新图。莘莘学子勤求索，学海无涯莫停步。",
        "夏日炎炎绿树阴，川农风光胜似春。书中自有黄金屋，刻苦攻读梦成真。",
        "秋风萧瑟天气凉，川农校园桂花香。学业进步当珍惜，青春岁月好时光。",
        "冬日暖阳照校园，川农学子心相连。团结互助齐奋进，共创美好新明天。",
        "川农风光无限好，教书育人传正道。园丁辛勤育桃李，遍地芬芳春来早。",
        "莘莘学子川农来，青春岁月如花蕾。努力学习报家国，不负韶华展雄才。"
    ]
    
    return random.choice(poem_templates)

def generate_notification(content):
    """生成学校通知"""
    # 提取通知主题（如果有）
    title_match = re.search(r'关于(.+?)的通知', content)
    if title_match:
        title = title_match.group(1)
    else:
        title = "重要事项"
    
    # 简单的通知模板
    notification = f"关于{title}的通知\n"
    notification += "全校师生：\n    "
    
    # 根据内容生成通知内容
    if '会议' in content:
        notification += "学校将于近期召开相关会议，请各位老师和同学准时参加。具体时间地点另行通知。\n    "
    elif '放假' in content:
        notification += "根据学校安排，现将放假相关事项通知如下，请大家提前做好准备，注意假期安全。\n    "
    elif '考试' in content:
        notification += "期末考试即将开始，请同学们认真复习，遵守考试纪律，诚信应考。\n    "
    else:
        notification += "为了更好地开展学校工作，现将相关事项通知如下，请大家知悉并配合执行。\n    "
    
    notification += "四川农业大学学生处\n"
    notification += datetime.now().strftime('%Y年%m月%d日')
    
    return notification

if __name__ == '__main__':
    # 确保配置文件存在
    config = load_config()
    save_config(config)
    
    # 启动服务器
    socketio.run(app, host='0.0.0.0', port=5000, debug=True)