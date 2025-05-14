from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_cors import CORS # 引入 CORS
from config import Config

# 初始化扩展，但先不传入 app 对象
db = SQLAlchemy()
migrate = Migrate()
cors = CORS() # 初始化 CORS

def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    # 初始化 Flask 扩展
    db.init_app(app)
    migrate.init_app(app, db)
    cors.init_app(app, resources={r"/api/*": {"origins": "*"}}) # 配置CORS，允许所有来源访问/api/下的所有路由，生产环境需要更严格的配置

    # 注册蓝图 (Blueprint)
    # 我们后面会在这里注册用户认证、竞赛等模块的蓝图
    from app.routes.auth import bp as auth_bp # 示例，auth.py 文件和 bp 变量需要后续创建
    app.register_blueprint(auth_bp, url_prefix='/api/auth')

    # 可以有一个简单的测试路由
    @app.route('/hello')
    def hello():
        return "Hello, Teammate Finder API is running!"

    return app