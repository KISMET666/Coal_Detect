from werkzeug.security import generate_password_hash, check_password_hash
import datetime
import uuid
from exts import db


class User(db.Model):
    """用户模型"""
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.String(36), unique=True, nullable=False, default=lambda: str(uuid.uuid4()))
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), nullable=False, default='user')
    avatar = db.Column(db.String(255), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.datetime.now)
    last_login = db.Column(db.DateTime, nullable=True)

    def __init__(self, username, email, password=None, user_id=None, role='user', avatar=None):
        self.username = username
        self.email = email
        if password:
            self.password_hash = generate_password_hash(password)
        self.user_id = user_id or str(uuid.uuid4())
        self.role = role
        self.avatar = avatar

    def check_password(self, password):
        """验证密码"""
        return check_password_hash(self.password_hash, password)

    @classmethod
    def create_user(cls, username, email, password, role='user'):
        """创建新用户"""
        # 检查用户名是否已存在
        if cls.find_by_username(username):
            return None, "用户名已存在"

        # 检查邮箱是否已存在
        if cls.find_by_email(email):
            return None, "邮箱已被注册"

        # 创建新用户
        user = cls(username=username, email=email, password=password, role=role)

        try:
            # 保存用户数据
            db.session.add(user)
            db.session.commit()
            return user, None
        except Exception as e:
            db.session.rollback()
            return None, f"创建用户失败: {str(e)}"

    @classmethod
    def find_by_username(cls, username):
        """通过用户名查找用户"""
        return cls.query.filter(db.func.lower(cls.username) == username.lower()).first()

    @classmethod
    def find_by_email(cls, email):
        """通过邮箱查找用户"""
        return cls.query.filter(db.func.lower(cls.email) == email.lower()).first()

    @classmethod
    def find_by_id(cls, user_id):
        """通过ID查找用户"""
        return cls.query.filter_by(user_id=user_id).first()

    @classmethod
    def update_last_login(cls, user_id):
        """更新最后登录时间"""
        user = cls.find_by_id(user_id)
        if user:
            user.last_login = datetime.datetime.now()
            try:
                db.session.commit()
                return True
            except:
                db.session.rollback()
                return False
        return False