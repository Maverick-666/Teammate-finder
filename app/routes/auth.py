from flask import request, jsonify, Blueprint
from app import db # 从 app 包的 __init__.py 导入 db
from app.models import User # 导入 User 模型
from flask_jwt_extended import create_access_token, create_refresh_token, jwt_required, get_jwt_identity # JWT 相关
import datetime # 用于设置 token 过期时间

bp = Blueprint('auth', __name__)

@bp.route('/register', methods=['POST'])
def register():
    data = request.get_json() # 获取前端通过 JSON 格式发来的数据

    if not data:
        return jsonify({"msg": "Missing JSON in request"}), 400

    username = data.get('username')
    email = data.get('email')
    password = data.get('password')
    nickname = data.get('nickname') # 昵称是可选的

    if not username or not email or not password:
        return jsonify({"msg": "Username, email, and password are required"}), 400

    # 检查用户名或邮箱是否已存在
    if User.query.filter_by(username=username).first():
        return jsonify({"msg": "Username already exists"}), 409 # 409 Conflict
    if User.query.filter_by(email=email).first():
        return jsonify({"msg": "Email already exists"}), 409

    # 创建新用户
    new_user = User(username=username, email=email, nickname=nickname)
    new_user.set_password(password) # 使用我们之前在 User模型中定义的 set_password 方法来哈希密码

    try:
        db.session.add(new_user)
        db.session.commit()
    except Exception as e:
        db.session.rollback() # 如果出错，回滚事务
        return jsonify({"msg": "Failed to register user", "error": str(e)}), 500

    # （可选）注册成功后直接返回 token，让用户自动登录
    access_token = create_access_token(identity=new_user.id, expires_delta=datetime.timedelta(hours=1))
    refresh_token = create_refresh_token(identity=new_user.id)

    return jsonify({
        "msg": "User registered successfully",
        "user": new_user.to_dict(include_email=True) # 返回用户信息，可以选择是否包含敏感信息
        # "access_token": access_token, # 如果需要注册后自动登录
        # "refresh_token": refresh_token
    }), 201 # 201 Created

@bp.route('/login', methods=['POST'])
def login():
    data = request.get_json()

    if not data:
        return jsonify({"msg": "Missing JSON in request"}), 400

    identifier = data.get('identifier') # 用户可以用用户名或邮箱登录
    password = data.get('password')

    if not identifier or not password:
        return jsonify({"msg": "Identifier (username or email) and password are required"}), 400

    # 尝试通过邮箱或用户名查找用户
    user = User.query.filter((User.email == identifier) | (User.username == identifier)).first()

    if user and user.check_password(password):
        # 密码正确，生成 JWT
        # identity 可以是任何能唯一标识用户的东西，通常用 user.id
        # expires_delta 设置 token 的有效时间
        access_token = create_access_token(identity=str(user.id),expires_delta=datetime.timedelta(hours=1))  # <--- 这里修改
        refresh_token = create_refresh_token(identity=str(user.id),expires_delta=datetime.timedelta(days=30))  # <--- 这里修改

        return jsonify({
            "msg": "Login successful",
            "access_token": access_token,
            "refresh_token": refresh_token,
            "user": user.to_dict() # 可以返回一些用户信息
        }), 200
    else:
        return jsonify({"msg": "Bad username or password"}), 401 # 401 Unauthorized





@bp.route('/protected', methods=['GET'])
@jwt_required()  # 这个装饰器表示这个接口需要有效的 JWT 才能访问
def protected():
    # 如果 JWT 无效或没有提供，Flask-JWT-Extended 会自动返回 401 或 422 错误
    current_user_id = get_jwt_identity()  # 获取 JWT 中的 identity (我们存的是 user_id)
    user = User.query.get(current_user_id)  # 根据 ID 查找用户

    if not user:
        return jsonify({"msg": "User not found"}), 404

    return jsonify({
        "msg": f"Hello {user.username}! You are accessing a protected route.",
        "user_id": current_user_id,
        "user_email": user.email
    }), 200


@bp.route('/refresh', methods=['POST'])
@jwt_required(refresh=True)  # 这个装饰器表示这个接口需要有效的 refresh_token
def refresh():
    current_user_id_from_token = get_jwt_identity()  # get_jwt_identity() 返回的已经是解码后的 identity
    # 如果我们之前存的是字符串，这里 current_user_id_from_token 也会是字符串
    # 如果我们想在应用逻辑中把它当整数用，可以转一下：
    # current_user_id_int = int(current_user_id_from_token)

    # 创建新的 access_token 时，确保 identity 是字符串
    new_access_token = create_access_token(identity=str(current_user_id_from_token),expires_delta=datetime.timedelta(hours=1))  # <--- 这里确保是字符串
    return jsonify(access_token=new_access_token), 200



# --- 获取当前登录用户的个人资料 ---
@bp.route('/profile', methods=['GET'])
@jwt_required()
def get_current_user_profile():
    current_user_id_str = get_jwt_identity()
    try:
        current_user_id = int(current_user_id_str)
    except ValueError:
        return jsonify({"msg": "Invalid user ID in token"}), 400  # 理论上不应发生，因为存入的是str

    user = User.query.get(current_user_id)

    if not user:
        return jsonify({"msg": "User not found"}), 404  # 理论上，如果token有效，用户应该存在

    # 使用 User 模型的 to_dict 方法，可以考虑是否包含 email
    return jsonify(user.to_dict(include_email=True)), 200


# --- 更新当前登录用户的个人资料 ---
@bp.route('/profile', methods=['PUT'])
@jwt_required()
def update_current_user_profile():
    current_user_id_str = get_jwt_identity()
    try:
        current_user_id = int(current_user_id_str)
    except ValueError:
        return jsonify({"msg": "Invalid user ID in token"}), 400

    user = User.query.get(current_user_id)

    if not user:
        return jsonify({"msg": "User not found"}), 404

    data = request.get_json()
    if not data:
        return jsonify({"msg": "Missing JSON in request"}), 400

    # 允许用户更新的字段
    # 用户名(username)和邮箱(email)通常不建议在这里直接修改，它们是唯一标识符，修改可能需要额外验证
    # 密码修改应该有单独的接口

    if 'nickname' in data:
        user.nickname = data['nickname']
    if 'avatar_url' in data:  # 前端可以先实现上传图片到图床，然后后端只保存URL
        user.avatar_url = data['avatar_url']
    if 'major' in data:
        user.major = data['major']
    if 'grade' in data:
        user.grade = data['grade']
    if 'bio' in data:
        user.bio = data['bio']
    if 'skills' in data:  # 技能标签，前端可以传一个逗号分隔的字符串
        user.skills = data['skills']

    # user.updated_at 字段在模型中配置了 onupdate=func.now()，数据库层面会自动更新
    # 如果没有，可以在这里手动更新：
    user.updated_at = datetime.datetime.now(datetime.timezone.utc)

    try:
        db.session.commit()  # SQLAlchemy 会检测到对象的更改并提交
    except Exception as e:
        db.session.rollback()
        # 检查是否有唯一性约束冲突，比如如果允许修改 email 或 username 但没做唯一性检查
        # if "UNIQUE constraint failed" in str(e) or "Duplicate entry" in str(e):
        #     return jsonify({"msg": "Update failed due to unique constraint (e.g., email or username already exists)"}), 409
        return jsonify({"msg": "Failed to update profile", "error": str(e)}), 500

    return jsonify({
        "msg": "Profile updated successfully",
        "user": user.to_dict(include_email=True)
    }), 200