import os

class Config:
    #数据库配置
    # 数据库配置
    HOSTNAME = "127.0.0.1"
    PORT = 3306
    USERNAME = "root"
    PASSWORD = "1234"
    DATABASE = "coal_detection_system"
    DB_URI = f"mysql+pymysql://{USERNAME}:{PASSWORD}@{HOSTNAME}:{PORT}/{DATABASE}?charset=utf8mb4"
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URI', DB_URI)
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # JWT配置
    JWT_SECRET_KEY = os.environ.get('JWT_SECRET_KEY', 'your_jwt_secret_key_here')

    # 应用程序密钥
    SECRET_KEY = os.environ.get('SECRET_KEY', 'your_app_secret_key_here')
    # 应用配置
    PROPAGATE_EXCEPTIONS = True # 确保异常正常传播# 确保异常正常传播
    PRESERVE_CONTEXT_ON_EXCEPTION = False # 不保留异常上下文
    MAX_CONTENT_LENGTH = 1024 * 1024 * 500  # 允许500MB的上传

    # 目录配置
    UPLOAD_FOLDER = 'uploads'
    DEFAULT_SAVE_PATH = 'D:\\SurveillanceVideo'

    # 摄像头配置
    CAMERA_INDICES = [0, -1, -1, -1, -1, -1, -1, -1, -1]  # 9个摄像头，只有第一个连接

    # 视频分段配置
    SEGMENT_DURATION = 15 * 60  # 15分钟视频片段

    # 模型配置
    MODEL_PATH = 'best.pt'

    # 确保目录存在
    @classmethod
    def init(cls):
        os.makedirs(cls.UPLOAD_FOLDER, exist_ok=True)
        os.makedirs(cls.DEFAULT_SAVE_PATH, exist_ok=True)