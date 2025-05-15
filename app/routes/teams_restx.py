from flask import request
from flask_restx import Namespace, Resource, fields, reqparse
from app import db
from app.models import User, Competition, Team  # team_members_association 不需要直接在这里用，关系由 SQLAlchemy 处理
from flask_jwt_extended import jwt_required, get_jwt_identity
import datetime

ns = Namespace('teams', description='Team related operations')

# --- 定义数据模型和解析器 ---

# Team 模型 (用于响应)
# 注意：为了避免循环导入或过于复杂的嵌套，成员列表可以简单地只包含用户ID和用户名，或者单独的接口获取成员详情
member_simple_model = ns.model('MemberSimple', {
    'id': fields.Integer,
    'username': fields.String,
    'nickname': fields.String
})

team_model = ns.model('Team', {
    'id': fields.Integer(readonly=True),
    'name': fields.String(required=True),
    'description': fields.String,
    'competition_id': fields.Integer(required=True),
    'competition_name': fields.String(attribute='competition.name', readonly=True),  # 通过关系获取
    'leader_id': fields.Integer(readonly=True),
    'leader_username': fields.String(attribute='leader.username', readonly=True),
    'status': fields.String,
    'created_at': fields.DateTime(readonly=True),
    'members': fields.List(fields.Nested(member_simple_model)),  # 成员列表
    'member_count': fields.Integer(description='Number of members in the team')
})

# 创建队伍的请求体解析器 (需要 competition_id)
team_creation_parser = ns.parser()
team_creation_parser.add_argument('name', type=str, required=True, help='Name of the team', location='json')
team_creation_parser.add_argument('description', type=str, help='Description of the team', location='json')
team_creation_parser.add_argument('competition_id', type=int, required=True,
                                  help='ID of the competition this team belongs to', location='json')

# 获取队伍列表的查询参数解析器
team_query_parser = reqparse.RequestParser()
team_query_parser.add_argument('competition_id', type=int, help='Filter teams by competition ID', location='args')
team_query_parser.add_argument('page', type=int, default=1, help='Page number', location='args')
team_query_parser.add_argument('per_page', type=int, default=10, help='Items per page', location='args')

# 队伍列表响应模型 (包含分页)
paginated_team_model = ns.model('PaginatedTeamList', {
    'teams': fields.List(fields.Nested(team_model)),
    'total': fields.Integer,
    'pages': fields.Integer,
    'current_page': fields.Integer
})

# 通用消息模型
message_model_team = ns.model('MessageTeam', {
    'msg': fields.String
})


# --- 定义资源类 ---

@ns.route('')  # 对应 /api/teams
class TeamList(Resource):
    @ns.doc('list_teams')
    @ns.expect(team_query_parser)
    @ns.response(200, 'List of teams', model=paginated_team_model)
    def get(self):
        """Lists all teams, optionally filtered by competition_id."""
        args = team_query_parser.parse_args()
        # ... (和之前 teams.py 中 get_all_teams 的逻辑类似，使用分页) ...
        query = Team.query.order_by(Team.created_at.desc())
        if args.get('competition_id'):
            query = query.filter_by(competition_id=args['competition_id'])

        paginated_teams = query.paginate(page=args['page'], per_page=args['per_page'], error_out=False)

        # 手动构造 members 和 member_count (如果 to_dict 不完全符合 team_model)
        teams_data = []
        for team_obj in paginated_teams.items:
            team_dict = team_obj.to_dict(include_members=True, include_competition_details=True,
                                         include_leader_details=True)
            # 确保 members 字段符合 member_simple_model (如果 to_dict 返回的更复杂)
            # team_dict['member_count'] = len(team_dict.get('members', [])) # 确保有 member_count
            teams_data.append(team_dict)

        return {
            'teams': teams_data,
            'total': paginated_teams.total,
            'pages': paginated_teams.pages,
            'current_page': paginated_teams.page
        }, 200

    @ns.doc('create_team', security='jsonWebToken')
    @jwt_required()
    @ns.expect(team_creation_parser)
    @ns.response(201, 'Team created successfully', model=team_model)  # 返回创建的队伍
    @ns.response(400, 'Validation error / Missing data', model=message_model_team)
    @ns.response(401, 'Unauthorized', model=message_model_team)
    @ns.response(404, 'Competition not found', model=message_model_team)  # 如果 competition_id 无效
    @ns.response(500, 'Failed to create team', model=message_model_team)
    def post(self):
        """Creates a new team for a specified competition."""
        current_user_id_str = get_jwt_identity()
        # ... (获取 current_user_id, 解析 args, 检查 competition_id, 创建 Team 对象，添加队长为成员，保存到数据库，和之前 teams.py 中 create_team 逻辑类似) ...
        current_user_id = int(current_user_id_str)
        args = team_creation_parser.parse_args()
        Competition.query.get_or_404(args['competition_id'])  # 确保竞赛存在

        new_team = Team(
            name=args['name'],
            description=args.get('description'),
            competition_id=args['competition_id'],
            leader_id=current_user_id
        )
        leader_user = User.query.get(current_user_id)
        new_team.members.append(leader_user)

        try:
            db.session.add(new_team)
            db.session.commit()
        except Exception as e:
            db.session.rollback();
            return {'msg': f'Failed to create team: {str(e)}'}, 500

        # 准备返回的数据，确保符合 team_model
        team_dict = new_team.to_dict(include_members=True, include_competition_details=True,
                                     include_leader_details=True)
        # team_dict['member_count'] = len(team_dict.get('members', []))
        return team_dict, 201


@ns.route('/<int:team_id>')  # 对应 /api/teams/<id>
@ns.response(404, 'Team not found', model=message_model_team)
@ns.param('team_id', 'The team identifier')
class TeamResource(Resource):
    @ns.doc('get_team_detail')
    @ns.response(200, 'Team details', model=team_model)
    def get(self, team_id):
        """Fetches a specific team by its ID."""
        team = Team.query.get_or_404(team_id)
        team_dict = team.to_dict(include_members=True, include_competition_details=True, include_leader_details=True)
        # team_dict['member_count'] = len(team_dict.get('members', []))
        return team_dict, 200

    @ns.doc('disband_team', security='jsonWebToken')
    @jwt_required()
    @ns.response(200, 'Team disbanded successfully', model=message_model_team)
    # ... (其他错误响应：401, 403, 500) ...
    def delete(self, team_id):
        """Disbands a team. Only the team leader can do this."""
        current_user_id_str = get_jwt_identity()
        # ... (获取 current_user_id, team 对象, 权限检查 - 必须是队长, 删除 team, 和之前 teams.py 中 disband_team 逻辑类似) ...
        current_user_id = int(current_user_id_str)
        team = Team.query.get_or_404(team_id)
        if team.leader_id != current_user_id:
            return {'msg': 'Forbidden: Only the team leader can disband the team'}, 403
        try:
            db.session.delete(team);
            db.session.commit()
        except Exception as e:
            db.session.rollback();
            return {'msg': f'Failed to disband team: {str(e)}'}, 500
        return {'msg': 'Team disbanded successfully'}, 200


@ns.route('/<int:team_id>/join')
class TeamJoin(Resource):
    @ns.doc('join_team', security='jsonWebToken')
    @jwt_required()
    @ns.response(200, 'Successfully joined the team', model=team_model)  # 返回更新后的队伍信息
    # ... (其他错误响应：401, 403 (team not open/already member), 404 (team/user not found), 500) ...
    def post(self, team_id):
        """Allows a logged-in user to join a team."""
        current_user_id_str = get_jwt_identity()
        # ... (获取 current_user_id, team 对象, user_to_join 对象, 检查是否已是成员, 检查队伍状态, 添加成员, 保存, 和之前 teams.py 中 join_team 逻辑类似) ...
        current_user_id = int(current_user_id_str)
        team = Team.query.get_or_404(team_id)
        user_to_join = User.query.get(current_user_id)
        if user_to_join in team.members: return {'msg': 'You are already a member'}, 409
        if team.status != 'open': return {'msg': 'Team not open for new members'}, 403

        try:
            team.members.append(user_to_join);
            db.session.commit()
        except Exception as e:
            db.session.rollback();
            return {'msg': f'Failed to join team: {str(e)}'}, 500

        team_dict = team.to_dict(include_members=True, include_competition_details=True, include_leader_details=True)
        # team_dict['member_count'] = len(team_dict.get('members', []))
        return {'msg': 'Successfully joined the team', 'team': team_dict}, 200  # 可以只返回 msg，或者更新后的 team


@ns.route('/<int:team_id>/leave')
class TeamLeave(Resource):
    @ns.doc('leave_team', security='jsonWebToken')
    @jwt_required()
    @ns.response(200, 'Successfully left the team', model=message_model_team)
    # ... (其他错误响应) ...
    def post(self, team_id):
        """Allows a logged-in member to leave a team."""
        current_user_id_str = get_jwt_identity()
        # ... (获取 current_user_id, team 对象, user_to_leave 对象, 检查是否是成员, 处理队长离开的逻辑, 移除成员, 保存, 和之前 teams.py 中 leave_team 逻辑类似) ...
        current_user_id = int(current_user_id_str)
        team = Team.query.get_or_404(team_id)
        user_to_leave = User.query.get(current_user_id)
        if user_to_leave not in team.members: return {'msg': 'You are not a member of this team'}, 403
        if team.leader_id == current_user_id:
            if len(team.members.all()) > 1:
                return {'msg': 'Captain must transfer leadership or disband team'}, 403
            else:  # Captain is last member, disband team
                try:
                    db.session.delete(team); db.session.commit(); return {'msg': 'Team disbanded as captain left'}, 200
                except Exception as e:
                    db.session.rollback(); return {'msg': f'Failed to disband: {str(e)}'}, 500
        try:
            team.members.remove(user_to_leave);
            db.session.commit()
        except Exception as e:
            db.session.rollback();
            return {'msg': f'Failed to leave: {str(e)}'}, 500
        return {'msg': 'Successfully left the team'}, 200


@ns.route('/<int:team_id>/members/<int:user_id_to_remove>')
@ns.param('team_id', 'The team identifier')
@ns.param('user_id_to_remove', 'The identifier of the user to remove')
class TeamMemberRemove(Resource):
    @ns.doc('remove_team_member', security='jsonWebToken')
    @jwt_required()
    @ns.response(200, 'Member removed successfully', model=message_model_team)
    # ... (其他错误响应) ...
    def delete(self, team_id, user_id_to_remove):
        """Removes a member from a team. Only the team leader can do this."""
        current_user_id_str = get_jwt_identity()  # 操作者是队长
        # ... (获取 current_user_id, team 对象, user_to_remove 对象, 权限检查 - 必须是队长, 检查被移除者是否是成员且非队长自己, 移除成员, 保存, 和之前 teams.py 中 remove_member_from_team 逻辑类似) ...
        current_user_id = int(current_user_id_str)
        team = Team.query.get_or_404(team_id)
        if team.leader_id != current_user_id: return {'msg': 'Forbidden: Only leader can remove members'}, 403
        user_to_remove = User.query.get_or_404(user_id_to_remove)
        if user_to_remove not in team.members: return {'msg': 'User is not a member of this team'}, 404
        if user_to_remove.id == team.leader_id: return {'msg': 'Captain cannot remove themselves'}, 403
        try:
            team.members.remove(user_to_remove);
            db.session.commit()
        except Exception as e:
            db.session.rollback();
            return {'msg': f'Failed to remove member: {str(e)}'}, 500
        return {'msg': f'User {user_to_remove.username} removed successfully'}, 200