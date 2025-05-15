# app/__init__.py (确保 JWT 初始化和 Namespace 注册是这样的)

from flask import Flask, jsonify  # 确保 jsonify 被导入
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_cors import CORS
from config import Config
from flask_jwt_extended import JWTManager, jwt_required, get_jwt_identity # <--- 在这里添加 get_jwt_identity
from flask_restx import Api

db = SQLAlchemy()
migrate = Migrate()
cors = CORS()
jwt = JWTManager()  # 初始化 JWTManager

authorizations = {
    'jsonWebToken': {
        'type': 'apiKey',
        'in': 'header',
        'name': 'Authorization',
        'description': "JWT Authorization header using the Bearer scheme. Example: \"Authorization: Bearer {token}\""
    }
}

api = Api(
    version='1.0',
    title='Teammate Finder API',
    description='A RESTful API for the Teammate Finder application...',
    doc='/api/docs',
    authorizations=authorizations,
)


def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    db.init_app(app)
    migrate.init_app(app, db)
    cors.init_app(app, resources={r"/api/*": {"origins": "*"}})
    jwt.init_app(app)  # <--- JWT 初始化
    api.init_app(app)  # <--- API 初始化

    # --- 自定义 JWT 错误处理器 ---
    @jwt.unauthorized_loader
    def unauthorized_callback(error_string):
        # app.logger.error(f"JWT UNAUTHORIZED LOADER CALLED: {error_string}") # 日志很好
        return jsonify(msg=error_string), 401

    @jwt.invalid_token_loader
    def invalid_token_callback(error_string):
        # app.logger.error(f"JWT INVALID TOKEN LOADER CALLED: {error_string}")
        return jsonify(msg=error_string), 422  # 通常是422，表示token格式不对或类型不对

    @jwt.expired_token_loader
    def expired_token_callback(jwt_header, jwt_payload):
        # app.logger.error("JWT EXPIRED TOKEN LOADER CALLED")
        return jsonify(msg="Token has expired"), 401

    # --- 缺少 token 但 @jwt_required 装饰的路由，通常会触发 unauthorized_loader ---
    # Flask-JWT-Extended 内部会抛出 NoAuthorizationError，然后被 unauthorized_loader 处理

    from .models import User, Competition, Team, team_members_association

    # --- 注册 Namespaces ---
    from app.routes.auth_restx import ns as auth_ns
    api.add_namespace(auth_ns, path='/api/auth')

    from app.routes.competitions_restx import ns as competitions_ns
    api.add_namespace(competitions_ns, path='/api/competitions')

    from app.routes.teams_restx import ns as teams_ns
    api.add_namespace(teams_ns, path='/api/teams')  # 确保前缀正确

    # --- 确保旧的 Blueprint 注册已移除或注释 ---

    @app.route('/hello')
    def hello():
        return "Hello, Teammate Finder API is running! Swagger UI at /api/docs"

    # --- 添加一个简单的受JWT保护的普通Flask路由用于测试 ---
    @app.route('/api/test_jwt_protection', methods=['POST'])
    @jwt_required()
    def test_jwt_route():
        current_user = get_jwt_identity()
        return jsonify(msg=f"You are authorized for plain Flask route! User: {current_user}"), 200

    return app