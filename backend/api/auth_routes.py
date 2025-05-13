from flask import Blueprint, request, jsonify
from models.user import User
from utils.jwt_utils import generate_token, token_required
import datetime
from exts import db

# 创建Blueprint
auth_bp = Blueprint('auth', __name__)


@auth_bp.route('/register', methods=['POST'])
def register():
    """用户注册"""
    # 获取请求数据
    data = request.get_json()

    # 验证必要的字段
    if not data or not all(k in data for k in ['username', 'email', 'password']):
        return jsonify({
            'success': False,
            'message': '请提供有效的用户名、邮箱和密码'
        }), 400

    # 检查密码长度
    if len(data['password']) < 6:
        return jsonify({
            'success': False,
            'message': '密码长度不能少于6个字符'
        }), 400

    # 创建用户
    user, error = User.create_user(
        username=data['username'],
        email=data['email'],
        password=data['password']
    )

    if error:
        return jsonify({
            'success': False,
            'message': error
        }), 400

    # 注册成功
    return jsonify({
        'success': True,
        'message': '注册成功',
        'user': {
            'username': user.username,
            'email': user.email,
            'user_id': user.user_id
        }
    }), 201


@auth_bp.route('/login', methods=['POST'])
def login():
    """用户登录"""
    # 获取请求数据
    data = request.get_json()

    # 验证必要的字段
    if not data or not all(k in data for k in ['username', 'password']):
        return jsonify({
            'success': False,
            'message': '请提供有效的用户名和密码'
        }), 400

    # 查找用户
    user = User.find_by_username(data['username'])

    # 检查用户是否存在以及密码是否正确
    if not user or not user.check_password(data['password']):
        return jsonify({
            'success': False,
            'message': '用户名或密码错误'
        }), 401

    # 更新最后登录时间
    User.update_last_login(user.user_id)

    # 生成Token
    token = generate_token(user.user_id, user.username, user.role)

    # 登录成功
    return jsonify({
        'success': True,
        'message': '登录成功',
        'token': token,
        'user': {
            'username': user.username,
            'email': user.email,
            'user_id': user.user_id,
            'role': user.role
        }
    })


@auth_bp.route('/profile', methods=['GET'])
@token_required
def get_profile(current_user):
    """获取当前用户信息"""
    # 从token信息中获取用户ID
    user_id = current_user['sub']

    # 查找用户
    user = User.find_by_id(user_id)

    if not user:
        return jsonify({
            'success': False,
            'message': '用户不存在'
        }), 404

    # 返回用户信息
    return jsonify({
        'success': True,
        'user': {
            'username': user.username,
            'email': user.email,
            'user_id': user.user_id,
            'role': user.role,
            'avatar': user.avatar,
            'created_at': user.created_at.isoformat() if user.created_at else None,
            'last_login': user.last_login.isoformat() if user.last_login else None
        }
    })


@auth_bp.route('/check-token', methods=['GET'])
@token_required
def check_token(current_user):
    """验证token是否有效"""
    return jsonify({
        'success': True,
        'message': 'Token有效',
        'user': {
            'user_id': current_user['sub'],
            'username': current_user['username'],
            'role': current_user['role']
        }
    })


# 可添加更多用户管理功能，如修改密码、更新个人资料等
@auth_bp.route('/update-profile', methods=['PUT'])
@token_required
def update_profile(current_user):
    """更新用户资料"""
    user_id = current_user['sub']
    data = request.get_json()

    user = User.find_by_id(user_id)
    if not user:
        return jsonify({
            'success': False,
            'message': '用户不存在'
        }), 404

    # 更新可修改的字段
    if 'avatar' in data:
        user.avatar = data['avatar']

    try:
        db.session.commit()
        return jsonify({
            'success': True,
            'message': '资料更新成功'
        })
    except:
        db.session.rollback()
        return jsonify({
            'success': False,
            'message': '资料更新失败'
        }), 500