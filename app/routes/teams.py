# teams.py (修改后)

from flask import request, jsonify, Blueprint
from app import db
from app.models import User, Competition, Team, team_members_association
from flask_jwt_extended import jwt_required, get_jwt_identity
import datetime

bp = Blueprint('teams', __name__)  # 蓝图名称 teams


# --- 创建新队伍 ---
# POST /api/teams (蓝图前缀) -> 实际路径 POST /api/teams (如果 __init__.py 中 teams_bp 的 url_prefix 是 '/api/teams')
@bp.route('', methods=['POST'])  # 路由是相对于蓝图前缀的根路径
@jwt_required()
def create_team():
    current_user_id_str = get_jwt_identity()
    try:
        current_user_id = int(current_user_id_str)
    except ValueError:
        return jsonify({"msg": "Invalid user ID in token"}), 400

    data = request.get_json()
    if not data:
        return jsonify({"msg": "Missing JSON in request"}), 400

    name = data.get('name')
    description = data.get('description')
    competition_id = data.get('competition_id')  # 从请求体获取

    if not name:
        return jsonify({"msg": "Team name is required"}), 400
    if not competition_id:
        return jsonify({"msg": "competition_id is required in request body"}), 400

    # 检查竞赛是否存在
    competition = Competition.query.get_or_404(competition_id)

    # ... (可选的：检查用户是否已在该竞赛的队伍中) ...

    new_team = Team(
        name=name,
        description=description,
        competition_id=int(competition_id),  # 确保是整数
        leader_id=current_user_id
    )

    leader_user = User.query.get(current_user_id)
    if not leader_user:
        return jsonify({"msg": "Leader user not found"}), 500
    new_team.members.append(leader_user)

    try:
        db.session.add(new_team)
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        return jsonify({"msg": "Failed to create team", "error": str(e)}), 500

    return jsonify({
        "msg": "Team created successfully",
        "team": new_team.to_dict(include_members=True, include_competition_details=True)
    }), 201


# --- 获取队伍列表 (可通过 competition_id 筛选) ---
# GET /api/teams (蓝图前缀) -> 实际路径 GET /api/teams  或 GET /api/teams?competition_id=<id>
@bp.route('', methods=['GET'])  # 和创建队伍共用相对于蓝图前缀的根路径，但方法是 GET
def get_all_teams():
    competition_id_filter = request.args.get('competition_id', type=int)
    # 也可以添加其他过滤条件，比如按队伍名称搜索等
    # search_term = request.args.get('search', type=str)

    query = Team.query.order_by(Team.created_at.desc())  # 按创建时间降序

    if competition_id_filter:
        # 最好也检查一下这个 competition_id 是否有效，或者直接筛选
        # competition = Competition.query.get(competition_id_filter)
        # if not competition:
        #     return jsonify({"msg": f"Competition with id {competition_id_filter} not found"}), 404
        query = query.filter_by(competition_id=competition_id_filter)

    # if search_term:
    #     query = query.filter(Team.name.ilike(f"%{search_term}%"))

    # 添加分页 (可选但推荐)
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 10, type=int)
    paginated_teams = query.paginate(page=page, per_page=per_page, error_out=False)

    teams_list = [team.to_dict(include_members=True, include_competition_details=True) for team in
                  paginated_teams.items]

    return jsonify({
        "teams": teams_list,
        "total": paginated_teams.total,
        "pages": paginated_teams.pages,
        "current_page": paginated_teams.page
    }), 200


# --- 获取单个队伍的详细信息 ---
# GET /api/teams/<int:team_id> (蓝图前缀) -> 实际路径 GET /api/teams/<int:team_id>
@bp.route('/<int:team_id>', methods=['GET'])  # 路径是相对于蓝图前缀的 /<id>
def get_team_detail(team_id):
    team = Team.query.get_or_404(team_id)
    return jsonify(team.to_dict(include_members=True, include_competition_details=True)), 200


# --- 用户加入队伍 ---
# POST /api/teams/<int:team_id>/join (蓝图前缀) -> 实际路径 POST /api/teams/<int:team_id>/join
@bp.route('/<int:team_id>/join', methods=['POST'])  # 路径是相对于蓝图前缀的 /<id>/join
@jwt_required()
def join_team(team_id):
    current_user_id_str = get_jwt_identity()
    try:
        current_user_id = int(current_user_id_str)
    except ValueError:
        return jsonify({"msg": "Invalid user ID in token"}), 400

    team = Team.query.get_or_404(team_id)
    user_to_join = User.query.get(current_user_id)

    if not user_to_join:
        return jsonify({"msg": "User not found"}), 404

    if user_to_join in team.members:
        return jsonify({"msg": "You are already a member of this team"}), 409

    if team.status != 'open':
        return jsonify({"msg": f"Team is not open for new members. Status: {team.status}"}), 403

    try:
        team.members.append(user_to_join)
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        return jsonify({"msg": "Failed to join team", "error": str(e)}), 500

    return jsonify({
        "msg": "Successfully joined the team",
        "team": team.to_dict(include_members=True)
    }), 200



# --- 用户退出队伍 ---
# POST /api/teams/<int:team_id>/leave
@bp.route('/<int:team_id>/leave', methods=['POST'])
@jwt_required()
def leave_team(team_id):
    current_user_id_str = get_jwt_identity()
    try:
        current_user_id = int(current_user_id_str)
    except ValueError:
        return jsonify({"msg": "Invalid user ID in token"}), 400

    team = Team.query.get_or_404(team_id)
    user_to_leave = User.query.get(current_user_id)

    if not user_to_leave:  # 理论上不会
        return jsonify({"msg": "User not found"}), 404

    # 检查用户是否是该队伍成员
    if user_to_leave not in team.members:
        return jsonify({"msg": "You are not a member of this team"}), 403

    # 检查队长是否试图离开队伍
    if team.leader_id == current_user_id:
        # 如果队伍中还有其他成员，队长不能直接离开，需要先转让队长或解散队伍
        if len(team.members.all()) > 1:  # .all() 获取实际成员列表
            return jsonify({
                               "msg": "Captain cannot leave the team if there are other members. Please transfer leadership or disband the team."}), 403
        # 如果队长是唯一成员，离开即等同于解散队伍 (或者队伍变为空队伍，取决于业务逻辑)
        # 这里我们简单处理：如果队长是唯一成员，离开就删除队伍
        else:
            try:
                db.session.delete(team)
                db.session.commit()
                return jsonify({"msg": "Team disbanded as the last member (captain) left."}), 200
            except Exception as e:
                db.session.rollback()
                return jsonify({"msg": "Failed to disband team", "error": str(e)}), 500

    # 普通成员退出
    try:
        team.members.remove(user_to_leave)  # 从多对多关系中移除
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        return jsonify({"msg": "Failed to leave team", "error": str(e)}), 500

    return jsonify({"msg": "Successfully left the team"}), 200


# --- 队长移除成员 ---
# DELETE /api/teams/<int:team_id>/members/<int:user_id_to_remove>
@bp.route('/<int:team_id>/members/<int:user_id_to_remove>', methods=['DELETE'])
@jwt_required()
def remove_member_from_team(team_id, user_id_to_remove):
    current_user_id_str = get_jwt_identity()  # 操作者ID (必须是队长)
    try:
        current_user_id = int(current_user_id_str)
    except ValueError:
        return jsonify({"msg": "Invalid user ID in token"}), 400

    team = Team.query.get_or_404(team_id)

    # 权限检查：只有队长能移除成员
    if team.leader_id != current_user_id:
        return jsonify({"msg": "Forbidden: Only the team leader can remove members"}), 403

    # 检查被移除的用户是否存在
    user_to_remove = User.query.get(user_id_to_remove)
    if not user_to_remove:
        return jsonify({"msg": "User to remove not found"}), 404

    # 检查被移除的用户是否是队伍成员
    if user_to_remove not in team.members:
        return jsonify({"msg": "User is not a member of this team"}), 404

    # 队长不能移除自己
    if user_id_to_remove == current_user_id:  # 或者 team.leader_id == user_id_to_remove
        return jsonify({"msg": "Captain cannot remove themselves"}), 403

    try:
        team.members.remove(user_to_remove)
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        return jsonify({"msg": "Failed to remove member", "error": str(e)}), 500

    return jsonify({"msg": f"User {user_to_remove.username} removed from the team successfully"}), 200


# --- 队长解散队伍 ---
# DELETE /api/teams/<int:team_id>
@bp.route('/<int:team_id>', methods=['DELETE'])  # 和获取队伍详情共用路径，但方法是 DELETE
@jwt_required()
def disband_team(team_id):
    current_user_id_str = get_jwt_identity()
    try:
        current_user_id = int(current_user_id_str)
    except ValueError:
        return jsonify({"msg": "Invalid user ID in token"}), 400

    team = Team.query.get_or_404(team_id)

    # 权限检查：只有队长能解散队伍
    if team.leader_id != current_user_id:
        return jsonify({"msg": "Forbidden: Only the team leader can disband the team"}), 403

    try:
        # 解散队伍时，SQLAlchemy 会自动处理 team_members_association 中间表的相关记录 (因为关系是定义在 Team 和 User 模型上的)
        db.session.delete(team)
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        return jsonify({"msg": "Failed to disband team", "error": str(e)}), 500

    return jsonify({"msg": "Team disbanded successfully"}), 200

