from api.auth_routes import auth_bp
from api.detection_routes import detection_bp
from api.surveillance_routes import surveillance_bp


def register_blueprints(app):
    """注册所有蓝图到应用"""
    app.register_blueprint(auth_bp, url_prefix='/api/auth')
    app.register_blueprint(detection_bp, url_prefix='/api')
    app.register_blueprint(surveillance_bp, url_prefix='/api/surveillance')

    # 注册全局错误处理
    from api.error_handlers import register_error_handlers
    register_error_handlers(app)