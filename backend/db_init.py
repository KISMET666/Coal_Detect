from newApp import app
from exts import db
from models.user import User
import json
import os
import datetime


def init_db():
    """初始化数据库，创建表结构"""
    with app.app_context():
        # 创建所有表
        db.create_all()
        print("数据库表结构创建成功")


def migrate_users_from_json():
    """从现有的JSON文件迁移用户数据到数据库"""
    USER_FILE = 'data/users/users.json'

    if not os.path.exists(USER_FILE):
        print(f"用户数据文件 {USER_FILE} 不存在，无需迁移")
        return

    try:
        with open(USER_FILE, 'r', encoding='utf-8') as f:
            users_data = json.load(f)
    except Exception as e:
        print(f"读取用户数据文件失败: {str(e)}")
        return

    with app.app_context():
        # 检查是否已经有用户数据
        if User.query.count() > 0:
            print("数据库中已存在用户数据，跳过迁移")
            return

        success_count = 0
        fail_count = 0

        for user_data in users_data:
            try:
                # 创建用户实例但不使用create_user方法（避免重复检查）
                user = User(
                    username=user_data['username'],
                    email=user_data['email'],
                    user_id=user_data['user_id'],
                    role=user_data.get('role', 'user'),
                    avatar=user_data.get('avatar')
                )
                user.password_hash = user_data['password_hash']

                # 处理日期时间字段
                if 'created_at' in user_data and user_data['created_at']:
                    try:
                        user.created_at = datetime.datetime.fromisoformat(user_data['created_at'])
                    except:
                        user.created_at = datetime.datetime.now()

                if 'last_login' in user_data and user_data['last_login']:
                    try:
                        user.last_login = datetime.datetime.fromisoformat(user_data['last_login'])
                    except:
                        user.last_login = None

                db.session.add(user)
                success_count += 1
            except Exception as e:
                print(f"迁移用户 {user_data.get('username')} 失败: {str(e)}")
                fail_count += 1

        try:
            db.session.commit()
            print(f"用户数据迁移完成: 成功 {success_count} 条, 失败 {fail_count} 条")
        except Exception as e:
            db.session.rollback()
            print(f"提交数据库事务失败: {str(e)}")


if __name__ == "__main__":
    init_db()
    migrate_users_from_json()