from flask import request
from flask_restx import Namespace, Resource, fields  # 导入 Namespace, Resource, fields
from app import db
from app.models import User
from flask_jwt_extended import create_access_token, create_refresh_token, jwt_required, get_jwt_identity
import datetime

# 创建一个 Namespace 实例，可以把它看作是 Blueprint 的 RESTX 版本
# name 是 Namespace 的名称，description 是在 Swagger UI 中显示的描述
ns = Namespace('auth', description='User authentication operations')

# --- 定义数据模型 (用于 Swagger 文档和请求/响应校验) ---
# Flask-RESTX 使用 fields 来定义数据的结构和类型，这会被用于生成 Swagger 文档中的模型，
# 并且可以用于请求体的校验和响应体的格式化。

# 用户注册请求模型
register_parser = ns.parser()
register_parser.add_argument('username', type=str, required=True, help='Unique username', location='json')
register_parser.add_argument('email', type=str, required=True, help='Unique email address', location='json')
register_parser.add_argument('password', type=str, required=True, help='User password', location='json')
register_parser.add_argument('nickname', type=str, help='Optional nickname', location='json')

# 也可以用 ns.model 来定义更复杂的模型结构 (通常用于响应)
user_model_fields = {
    'id': fields.Integer(readonly=True, description='The user unique identifier'),
    'username': fields.String(required=True, description='The username'),
    'email': fields.String(required=True, description='The user email address (returned on register/profile)'),
    'nickname': fields.String(description='The user nickname'),
    'avatar_url': fields.String(description='URL of the user avatar'),
    'major': fields.String(description='User major'),
    'grade': fields.String(description='User grade'),
    'bio': fields.String(description='User biography'),
    'skills': fields.String(description='User skills (comma-separated)'),
    'created_at': fields.DateTime(description='Timestamp of user creation')
}
# 这个是基础用户模型，不包含敏感信息如 password_hash
user_public_model = ns.model('UserPublic',
                             {k: v for k, v in user_model_fields.items() if k not in ['email']})  # 公开信息，不含 email
user_private_model = ns.model('UserPrivate', user_model_fields)  # 私有信息，含 email

# 登录请求模型
login_parser = ns.parser()
login_parser.add_argument('identifier', type=str, required=True, help='Username or email', location='json')
login_parser.add_argument('password', type=str, required=True, help='Password', location='json')

# Token 响应模型
token_model = ns.model('Token', {
    'access_token': fields.String(required=True, description='Access Token for API access'),
    'refresh_token': fields.String(required=True, description='Refresh Token to get new access token')
})

login_success_model = ns.model('LoginSuccess', {
    'msg': fields.String(description='Success message'),
    'tokens': fields.Nested(token_model),  # 嵌套 Token 模型
    'user': fields.Nested(user_public_model)  # 返回用户信息
})

# 通用消息响应模型
message_model = ns.model('Message', {
    'msg': fields.String(description='A message describing the result of the operation')
})


# --- 定义资源类 (Resource) ---
# 每个类通常对应一个 URL 路径，类中的方法 (get, post, put, delete) 对应 HTTP 方法

@ns.route('/register')  # 路由是相对于 Namespace 的 path 前缀 (/api/auth)
class Register(Resource):
    @ns.expect(register_parser)  # 声明期望的请求体格式 (使用我们定义的 parser)
    @ns.response(201, 'User registered successfully', model=message_model)  # 声明成功响应 (状态码，描述，可选的响应模型)
    @ns.response(400, 'Validation error / Missing data', model=message_model)
    @ns.response(409, 'Username or email already exists', model=message_model)
    @ns.response(500, 'Failed to register user', model=message_model)
    def post(self):
        """Registers a new user."""  # 这个 docstring 会显示在 Swagger UI 中作为接口描述
        args = register_parser.parse_args()  # 解析并校验请求参数
        username = args['username']
        email = args['email']
        password = args['password']
        nickname = args.get('nickname')  # .get() 因为它是可选的

        if User.query.filter_by(username=username).first():
            return {'msg': 'Username already exists'}, 409
        if User.query.filter_by(email=email).first():
            return {'msg': 'Email already exists'}, 409

        new_user = User(username=username, email=email, nickname=nickname)
        new_user.set_password(password)
        try:
            db.session.add(new_user)
            db.session.commit()
        except Exception:
            db.session.rollback()
            return {'msg': 'Failed to register user'}, 500

        # 如果也想返回创建的用户信息，可以调整 model
        # return {'msg': 'User registered successfully', 'user': marshal(new_user, user_private_model)}, 201
        return {'msg': 'User registered successfully'}, 201


@ns.route('/login')
class Login(Resource):
    @ns.expect(login_parser)
    @ns.response(200, 'Login successful', model=login_success_model)  # 使用我们定义的 login_success_model
    @ns.response(400, 'Validation error / Missing data', model=message_model)
    @ns.response(401, 'Bad username or password', model=message_model)
    def post(self):
        """Logs in a user and returns access and refresh tokens."""
        args = login_parser.parse_args()
        identifier = args['identifier']
        password = args['password']

        user = User.query.filter((User.email == identifier) | (User.username == identifier)).first()

        if user and user.check_password(password):
            access_token = create_access_token(identity=str(user.id), expires_delta=datetime.timedelta(hours=1))
            refresh_token = create_refresh_token(identity=str(user.id), expires_delta=datetime.timedelta(days=30))

            # 使用 marshal 来格式化响应 (如果响应模型复杂)
            # from flask_restx import marshal
            # user_data_for_response = marshal(user, user_public_model)
            # return {'msg': 'Login successful', 'tokens': {'access_token': access_token, 'refresh_token': refresh_token}, 'user': user_data_for_response}, 200
            return {
                'msg': 'Login successful',
                'tokens': {
                    'access_token': access_token,
                    'refresh_token': refresh_token
                },
                'user': user.to_dict()  # 也可以继续用我们模型里的 to_dict，或者用 marshal
            }, 200
        else:
            return {'msg': 'Bad username or password'}, 401


# --- 个人资料接口 ---
profile_update_parser = ns.parser()  # 用于更新的 parser
profile_update_parser.add_argument('nickname', type=str, help='New nickname', location='json')
profile_update_parser.add_argument('avatar_url', type=str, help='New avatar URL', location='json')
profile_update_parser.add_argument('major', type=str, help='New major', location='json')
profile_update_parser.add_argument('grade', type=str, help='New grade', location='json')
profile_update_parser.add_argument('bio', type=str, help='New biography', location='json')
profile_update_parser.add_argument('skills', type=str, help='New skills (comma-separated)', location='json')


@ns.route('/profile')
class UserProfile(Resource):
    @jwt_required()  # 保护接口
    @ns.doc(security='jsonWebToken')  # 告诉 Swagger UI 这个接口需要 JWT 认证
    @ns.response(200, 'User profile data', model=user_private_model)  # 获取时返回私有模型 (含 email)
    @ns.response(401, 'Unauthorized / Invalid Token', model=message_model)
    @ns.response(404, 'User not found', model=message_model)
    def get(self):
        """Fetches the current logged-in user's profile."""
        current_user_id_str = get_jwt_identity()
        # ... (获取 user 对象的逻辑和之前一样) ...
        # user = User.query.get(int(current_user_id_str))
        user = db.session.get(User, int(current_user_id_str))  # <--- 修
        if not user:
            return {'msg': 'User not found'}, 404
        # from flask_restx import marshal # 如果用 marshal
        # return marshal(user, user_private_model), 200
        return user.to_dict(include_email=True), 200

    @jwt_required()
    @ns.doc(security='jsonWebToken')
    @ns.expect(profile_update_parser)  # 更新时期望的请求体
    @ns.response(200, 'Profile updated successfully', model=user_private_model)
    @ns.response(400, 'Validation error / Missing data', model=message_model)
    @ns.response(401, 'Unauthorized / Invalid Token', model=message_model)
    @ns.response(404, 'User not found', model=message_model)
    @ns.response(500, 'Failed to update profile', model=message_model)
    def put(self):
        """Updates the current logged-in user's profile."""
        current_user_id_str = get_jwt_identity()
        # ... (获取 user 对象的逻辑和之前一样) ...
        # user = User.query.get(int(current_user_id_str))
        user = db.session.get(User, int(current_user_id_str))  # <--- 修
        if not user:
            return {'msg': 'User not found'}, 404

        args = profile_update_parser.parse_args()  # 解析更新的参数

        # 只有当参数在请求中提供了才更新 (args 会包含所有定义的参数，值为 None 如果没提供)
        if args.get('nickname') is not None: user.nickname = args['nickname']
        if args.get('avatar_url') is not None: user.avatar_url = args['avatar_url']
        if args.get('major') is not None: user.major = args['major']
        if args.get('grade') is not None: user.grade = args['grade']
        if args.get('bio') is not None: user.bio = args['bio']
        if args.get('skills') is not None: user.skills = args['skills']

        try:
            db.session.commit()
        except Exception:
            db.session.rollback()
            return {'msg': 'Failed to update profile'}, 500

        # from flask_restx import marshal
        # return marshal(user, user_private_model), 200
        return {'msg': 'Profile updated successfully', 'user': user.to_dict(include_email=True)}, 200


# --- Token 刷新接口 ---
@ns.route('/refresh')
class TokenRefresh(Resource):
    @jwt_required(refresh=True)  # 需要 refresh_token
    @ns.doc(security='jsonWebTokenRefresh')  # 可以定义不同的 security scheme
    @ns.response(200, 'Access token refreshed successfully',
                 model=ns.model('NewAccessToken', {'access_token': fields.String}))
    @ns.response(401, 'Invalid refresh token', model=message_model)
    def post(self):
        """Refreshes an access token using a refresh token."""
        current_user_id_str = get_jwt_identity()
        new_access_token = create_access_token(identity=current_user_id_str, expires_delta=datetime.timedelta(hours=1))
        return {'access_token': new_access_token}, 200

# 我们还需要在 app/__init__.py 的 Api 对象中配置 authorizations，以便 Swagger UI 显示 Authorize 按钮
# 在 app/__init__.py 中：
# authorizations = {
#     'jsonWebToken': {
#         'type': 'apiKey',
#         'in': 'header',
#         'name': 'Authorization',
#         'description': "JWT Authorization header using the Bearer scheme. Example: \"Authorization: Bearer {token}\""
#     },
#     'jsonWebTokenRefresh': { # 用于刷新 token 的接口
#         'type': 'apiKey',
#         'in': 'header',
#         'name': 'Authorization',
#         'description': "JWT Authorization header using the Bearer scheme with REFRESH token. Example: \"Authorization: Bearer {refresh_token}\""
#     }
# }
# api = Api(..., authorizations=authorizations)