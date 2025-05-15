from flask import request, jsonify, Blueprint
from app import db
from app.models import User, Competition  # 导入 Competition 模型
from flask_jwt_extended import jwt_required, get_jwt_identity
import datetime

bp = Blueprint('competitions', __name__)


# --- 创建新竞赛 ---
@bp.route('', methods=['POST'])  # 路径是 /api/competitions (因为蓝图前缀)
@jwt_required()  # 需要登录才能创建
def create_competition():
    current_user_id_str = get_jwt_identity()  # JWT identity 是字符串
    try:
        current_user_id = int(current_user_id_str)  # 转换为整数以匹配 User ID 类型
    except ValueError:
        return jsonify({"msg": "Invalid user ID in token"}), 400

    data = request.get_json()
    if not data:
        return jsonify({"msg": "Missing JSON in request"}), 400

    name = data.get('name')
    category = data.get('category')
    description = data.get('description')
    start_time_str = data.get('start_time')  # 前端可能传来 ISO 格式的日期时间字符串
    end_time_str = data.get('end_time')
    organizer = data.get('organizer')
    # status 默认为 'recruiting'，也可以让用户指定

    if not name or not description:
        return jsonify({"msg": "Name and description are required"}), 400

    # 日期时间字符串转换为 datetime 对象 (如果提供了的话)
    start_time = None
    if start_time_str:
        try:
            start_time = datetime.datetime.fromisoformat(start_time_str.replace('Z', '+00:00'))  # 处理 'Z' (UTC)
        except ValueError:
            return jsonify({"msg": "Invalid start_time format. Use ISO format."}), 400

    end_time = None
    if end_time_str:
        try:
            end_time = datetime.datetime.fromisoformat(end_time_str.replace('Z', '+00:00'))
        except ValueError:
            return jsonify({"msg": "Invalid end_time format. Use ISO format."}), 400

    new_competition = Competition(
        name=name,
        category=category,
        description=description,
        start_time=start_time,
        end_time=end_time,
        organizer=organizer,
        created_by_user_id=current_user_id  # 关联创建者
        # status 字段会使用模型中定义的默认值 'recruiting'
    )

    try:
        db.session.add(new_competition)
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        return jsonify({"msg": "Failed to create competition", "error": str(e)}), 500

    return jsonify({
        "msg": "Competition created successfully",
        "competition": new_competition.to_dict()  # 使用模型中的 to_dict 方法
    }), 201


# --- 获取所有竞赛列表 ---
@bp.route('', methods=['GET'])  # 路径是 /api/competitions
def get_all_competitions():
    # 后续可以添加分页、过滤等参数
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 10, type=int)
    category_filter = request.args.get('category', None, type=str)
    status_filter = request.args.get('status', None, type=str)
    search_term = request.args.get('search', None, type=str)

    query = Competition.query.order_by(Competition.created_at.desc())  # 按创建时间降序排列

    if category_filter:
        query = query.filter(Competition.category.ilike(f"%{category_filter}%"))  # 不区分大小写模糊匹配
    if status_filter:
        query = query.filter_by(status=status_filter)
    if search_term:
        # 简单搜索竞赛名称和描述
        query = query.filter(
            db.or_(
                Competition.name.ilike(f"%{search_term}%"),
                Competition.description.ilike(f"%{search_term}%")
            )
        )

    paginated_competitions = query.paginate(page=page, per_page=per_page, error_out=False)

    competitions_list = [comp.to_dict() for comp in paginated_competitions.items]

    return jsonify({
        "competitions": competitions_list,
        "total": paginated_competitions.total,
        "pages": paginated_competitions.pages,
        "current_page": paginated_competitions.page
    }), 200


# --- 获取单个竞赛详情 ---
@bp.route('/<int:competition_id>', methods=['GET'])  # 路径如 /api/competitions/1
def get_competition_detail(competition_id):
    competition = Competition.query.get_or_404(competition_id)
    # get_or_404: 如果找不到对应 ID 的记录，会自动返回 404 Not Found 错误

    return jsonify(competition.to_dict()), 200


# --- 更新竞赛信息 ---
@bp.route('/<int:competition_id>', methods=['PUT'])
@jwt_required()  # 需要登录
def update_competition(competition_id):
    current_user_id_str = get_jwt_identity()
    try:
        current_user_id = int(current_user_id_str)
    except ValueError:
        return jsonify({"msg": "Invalid user ID in token"}), 400

    competition = Competition.query.get_or_404(competition_id)  # 获取要更新的竞赛

    # 权限检查：只有创建者才能修改
    if competition.created_by_user_id != current_user_id:
        return jsonify({"msg": "Forbidden: You are not the creator of this competition"}), 403  # 403 Forbidden

    data = request.get_json()
    if not data:
        return jsonify({"msg": "Missing JSON in request"}), 400

    # 更新允许修改的字段
    # 用户不能修改 created_by_user_id 和 created_at
    if 'name' in data:
        competition.name = data['name']
    if 'category' in data:
        competition.category = data['category']
    if 'description' in data:
        competition.description = data['description']
    if 'start_time' in data:
        try:
            competition.start_time = datetime.datetime.fromisoformat(data['start_time'].replace('Z', '+00:00')) if data[
                'start_time'] else None
        except ValueError:
            return jsonify({"msg": "Invalid start_time format. Use ISO format."}), 400
    if 'end_time' in data:
        try:
            competition.end_time = datetime.datetime.fromisoformat(data['end_time'].replace('Z', '+00:00')) if data[
                'end_time'] else None
        except ValueError:
            return jsonify({"msg": "Invalid end_time format. Use ISO format."}), 400
    if 'organizer' in data:
        competition.organizer = data['organizer']
    if 'status' in data:  # 允许创建者修改竞赛状态
        competition.status = data['status']

    # updated_at 字段会在模型层面通过 onupdate=func.now() 自动更新 (如果数据库层面支持)
    # 或者我们可以在这里手动更新 SQLAlchemy 对象的 updated_at 字段，如果模型定义时没有 onupdate
    # competition.updated_at = datetime.datetime.now(datetime.timezone.utc) # 如果需要手动设置

    try:
        db.session.commit()  # SQLAlchemy 会检测到对象的更改并提交
    except Exception as e:
        db.session.rollback()
        return jsonify({"msg": "Failed to update competition", "error": str(e)}), 500

    return jsonify({
        "msg": "Competition updated successfully",
        "competition": competition.to_dict()
    }), 200




# --- 删除竞赛信息 ---
@bp.route('/<int:competition_id>', methods=['DELETE'])
@jwt_required() # 需要登录
def delete_competition(competition_id):
    current_user_id_str = get_jwt_identity()
    try:
        current_user_id = int(current_user_id_str)
    except ValueError:
        return jsonify({"msg": "Invalid user ID in token"}), 400

    competition = Competition.query.get_or_404(competition_id) # 获取要删除的竞赛

    # 权限检查：只有创建者才能删除
    if competition.created_by_user_id != current_user_id:
        return jsonify({"msg": "Forbidden: You are not the creator of this competition"}), 403

    try:
        # 在删除竞赛前，可能需要考虑与之关联的其他数据如何处理
        # 比如：这个竞赛下的所有队伍是否也需要删除？或者设置为某个特殊状态？
        # 目前我们的模型定义中，如果队伍有 competition_id 外键，直接删除竞赛可能会失败（如果数据库设置了外键约束且没有级联删除）
        # 或者队伍会变成孤儿记录。
        # 一个简单的处理方式是，先删除所有关联的队伍 (如果业务逻辑允许)
        # from app.models import Team # 确保导入 Team 模型
        # Team.query.filter_by(competition_id=competition_id).delete()
        # 上述直接删除可能不会触发Team模型的删除回调（如果有的话），更安全的方式是先查询再逐个删除或批量删除

        # 暂时我们先直接尝试删除竞赛，如果数据库有外键约束且没有设置级联删除，这里可能会报错
        # 如果报错，就需要根据业务逻辑决定如何处理关联数据
        db.session.delete(competition)
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        # 需要检查是否是外键约束导致的错误
        # if "foreign key constraint" in str(e).lower():
        #     return jsonify({"msg": "Cannot delete competition because it has associated teams. Please delete teams first or contact admin."}), 409 # Conflict
        return jsonify({"msg": "Failed to delete competition", "error": str(e)}), 500

    return jsonify({"msg": "Competition deleted successfully"}), 200 # 或者 204 No Content



