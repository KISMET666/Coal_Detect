import jwt
import datetime
import os
from functools import wraps
from flask import request, jsonify

# 从环境变量中获取密钥，如果没有则使用默认值
SECRET_KEY = os.environ.get('JWT_SECRET_KEY', 'your_jwt_secret_key_here')


def generate_token(user_id, username, role='user', expiration=24):
    """
    生成JWT token
    :param user_id: 用户ID
    :param username: 用户名
    :param role: 用户角色
    :param expiration: 过期时间（小时）
    :return: JWT token
    """
    payload = {
        'exp': datetime.datetime.utcnow() + datetime.timedelta(hours=expiration),
        'iat': datetime.datetime.utcnow(),
        'sub': user_id,
        'username': username,
        'role': role
    }
    return jwt.encode(payload, SECRET_KEY, algorithm='HS256')


def decode_token(token):
    """
    解码JWT token
    :param token: JWT token
    :return: 解码后的payload
    """
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=['HS256'])
        return payload
    except jwt.ExpiredSignatureError:
        return None  # Token已过期
    except jwt.InvalidTokenError:
        return None  # 无效的Token


def token_required(f):
    """
    验证JWT token的装饰器
    """

    @wraps(f)
    def decorated(*args, **kwargs):
        token = None
        # 从请求头中获取token
        if 'Authorization' in request.headers:
            auth_header = request.headers['Authorization']
            if auth_header.startswith('Bearer '):
                token = auth_header.split(' ')[1]

        if not token:
            return jsonify({'message': '未提供有效的认证令牌'}), 401

        # 解码token
        payload = decode_token(token)
        if not payload:
            return jsonify({'message': '无效的认证令牌或已过期'}), 401

        # 将用户信息传递给被装饰的函数
        return f(payload, *args, **kwargs)

    return decorated


def admin_required(f):
    """
    验证管理员权限的装饰器
    """

    @wraps(f)
    def decorated(*args, **kwargs):
        token = None
        # 从请求头中获取token
        if 'Authorization' in request.headers:
            auth_header = request.headers['Authorization']
            if auth_header.startswith('Bearer '):
                token = auth_header.split(' ')[1]

        if not token:
            return jsonify({'message': '未提供有效的认证令牌'}), 401

        # 解码token
        payload = decode_token(token)
        if not payload:
            return jsonify({'message': '无效的认证令牌或已过期'}), 401

        # 检查用户角色
        if payload.get('role') != 'admin':
            return jsonify({'message': '权限不足，需要管理员权限'}), 403

        # 将用户信息传递给被装饰的函数
        return f(payload, *args, **kwargs)

    return decorated