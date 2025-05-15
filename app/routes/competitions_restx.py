from flask import request
from flask_restx import Namespace, Resource, fields, reqparse  # 导入 reqparse 用于查询参数
from app import db
from app.models import User, Competition
from flask_jwt_extended import jwt_required, get_jwt_identity
import datetime

ns = Namespace('competitions', description='Competition related operations')

# --- 定义数据模型 (Models) 和解析器 (Parsers) ---

# Competition 模型 (用于响应)
competition_model = ns.model('Competition', {
    'id': fields.Integer(readonly=True, description='The competition unique identifier'),
    'name': fields.String(required=True, description='The name of the competition'),
    'category': fields.String(description='The category of the competition'),
    'description': fields.String(required=True, description='Detailed description of the competition'),
    'start_time': fields.DateTime(description='Start time of the competition (ISO format)'),
    'end_time': fields.DateTime(description='End time of the competition (ISO format)'),
    'organizer': fields.String(description='Organizer of the competition'),
    'status': fields.String(description='Status of the competition (e.g., recruiting, ongoing, ended)'),
    'created_by_user_id': fields.Integer(readonly=True, description='ID of the user who created the competition'),
    'creator_username': fields.String(readonly=True, attribute='creator.username',
                                      description='Username of the creator'),  # 通过关系获取
    'created_at': fields.DateTime(readonly=True, description='Timestamp of competition creation')
})

# 用于创建竞赛的请求体解析器
competition_creation_parser = ns.parser()
competition_creation_parser.add_argument('name', type=str, required=True, help='Name of the competition',
                                         location='json')
competition_creation_parser.add_argument('category', type=str, help='Category of the competition', location='json')
competition_creation_parser.add_argument('description', type=str, required=True, help='Description of the competition',
                                         location='json')
competition_creation_parser.add_argument('start_time', type=str,
                                         help='Start time (ISO format, e.g., 2025-06-01T09:00:00Z)', location='json')
competition_creation_parser.add_argument('end_time', type=str, help='End time (ISO format)', location='json')
competition_creation_parser.add_argument('organizer', type=str, help='Organizer', location='json')
competition_creation_parser.add_argument('status', type=str,
                                         help='Initial status (defaults to recruiting if not provided)',
                                         location='json')

# 用于更新竞赛的请求体解析器 (很多字段是可选的)
competition_update_parser = ns.parser()
competition_update_parser.add_argument('name', type=str, help='New name of the competition', location='json')
competition_update_parser.add_argument('category', type=str, help='New category', location='json')
competition_update_parser.add_argument('description', type=str, help='New description', location='json')
competition_update_parser.add_argument('start_time', type=str, help='New start time (ISO format)', location='json')
competition_update_parser.add_argument('end_time', type=str, help='New end time (ISO format)', location='json')
competition_update_parser.add_argument('organizer', type=str, help='New organizer', location='json')
competition_update_parser.add_argument('status', type=str, help='New status', location='json')

# 用于获取竞赛列表的查询参数解析器
competition_query_parser = reqparse.RequestParser()  # 使用 reqparse 处理 URL query params
competition_query_parser.add_argument('page', type=int, default=1, help='Page number', location='args')
competition_query_parser.add_argument('per_page', type=int, default=10, help='Items per page', location='args')
competition_query_parser.add_argument('category', type=str, help='Filter by category (case-insensitive, partial match)',
                                      location='args')
competition_query_parser.add_argument('status', type=str, help='Filter by status', location='args')
competition_query_parser.add_argument('search', type=str, help='Search term for name or description', location='args')

# 竞赛列表响应模型 (包含分页信息)
paginated_competition_model = ns.model('PaginatedCompetitionList', {
    'competitions': fields.List(fields.Nested(competition_model)),
    'total': fields.Integer(description='Total number of competitions'),
    'pages': fields.Integer(description='Total number of pages'),
    'current_page': fields.Integer(description='Current page number')
})

# 通用消息模型 (可以复用 auth_restx.py 中定义的，或者在这里再定义一个)
message_model = ns.model('MessageCompetition', {  # 加个后缀避免和 auth_restx 中的 Message 冲突（如果它们不同）
    'msg': fields.String(description='A message describing the result of the operation')
})


# --- 定义资源类 ---

@ns.route('')  # 对应 /api/competitions
class CompetitionList(Resource):
    @ns.doc('list_competitions')
    @ns.expect(competition_query_parser)  # 期望查询参数
    @ns.response(200, 'List of competitions', model=paginated_competition_model)
    def get(self):
        """Lists all competitions with optional filtering and pagination."""
        args = competition_query_parser.parse_args()
        page = args['page']
        per_page = args['per_page']
        category_filter = args.get('category')
        status_filter = args.get('status')
        search_term = args.get('search')

        query = Competition.query.order_by(Competition.created_at.desc())
        if category_filter:
            query = query.filter(Competition.category.ilike(f"%{category_filter}%"))
        if status_filter:
            query = query.filter_by(status=status_filter)
        if search_term:
            query = query.filter(
                db.or_(Competition.name.ilike(f"%{search_term}%"), Competition.description.ilike(f"%{search_term}%")))

        paginated_competitions = query.paginate(page=page, per_page=per_page, error_out=False)

        # 使用 marshal 来确保输出符合 competition_model 定义
        # from flask_restx import marshal
        # competitions_data = marshal(paginated_competitions.items, competition_model)
        # return {'competitions': competitions_data, ...}

        # 或者继续用 to_dict()，但要确保它返回的字段和 competition_model 一致
        competitions_data = [comp.to_dict() for comp in paginated_competitions.items]

        return {
            'competitions': competitions_data,
            'total': paginated_competitions.total,
            'pages': paginated_competitions.pages,
            'current_page': paginated_competitions.page
        }, 200

    @ns.doc('create_competition', security='jsonWebToken')  # 指明需要 JWT 认证
    @jwt_required()
    @ns.expect(competition_creation_parser)  # 期望请求体
    @ns.response(201, 'Competition created successfully', model=competition_model)  # 返回创建的竞赛信息
    @ns.response(400, 'Validation error / Missing data', model=message_model)
    @ns.response(401, 'Unauthorized / Invalid Token', model=message_model)
    @ns.response(500, 'Failed to create competition', model=message_model)
    def post(self):
        """Creates a new competition."""
        current_user_id_str = get_jwt_identity()
        try:
            current_user_id = int(current_user_id_str)
        except ValueError:
            return {'msg': 'Invalid user ID in token'}, 400  # RESTX 会自动处理一些400，但显式返回也可以

        args = competition_creation_parser.parse_args()

        start_time, end_time = None, None
        if args.get('start_time'):
            try:
                start_time = datetime.datetime.fromisoformat(args['start_time'].replace('Z', '+00:00'))
            except ValueError:
                return {'msg': 'Invalid start_time format'}, 400
        if args.get('end_time'):
            try:
                end_time = datetime.datetime.fromisoformat(args['end_time'].replace('Z', '+00:00'))
            except ValueError:
                return {'msg': 'Invalid end_time format'}, 400

        new_competition = Competition(
            name=args['name'],
            category=args.get('category'),
            description=args['description'],
            start_time=start_time,
            end_time=end_time,
            organizer=args.get('organizer'),
            status=args.get('status') or 'recruiting',  # 如果没提供status，默认为recruiting
            created_by_user_id=current_user_id
        )
        try:
            db.session.add(new_competition)
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            return {'msg': f'Failed to create competition: {str(e)}'}, 500

        # from flask_restx import marshal
        # return marshal(new_competition, competition_model), 201
        return new_competition.to_dict(), 201


@ns.route('/<int:competition_id>')  # 对应 /api/competitions/<id>
@ns.response(404, 'Competition not found', model=message_model)  # 对这个路径下的所有方法都可能返回404
@ns.param('competition_id', 'The competition identifier')  # 描述路径参数
class CompetitionResource(Resource):
    @ns.doc('get_competition')
    @ns.response(200, 'Competition details', model=competition_model)
    def get(self, competition_id):
        """Fetches a specific competition by its ID."""
        competition = Competition.query.get_or_404(competition_id)
        # from flask_restx import marshal
        # return marshal(competition, competition_model), 200
        return competition.to_dict(), 200

    @ns.doc('update_competition', security='jsonWebToken')
    @jwt_required()
    @ns.expect(competition_update_parser)  # 期望请求体
    @ns.response(200, 'Competition updated successfully', model=competition_model)
    @ns.response(400, 'Validation error', model=message_model)
    @ns.response(401, 'Unauthorized', model=message_model)
    @ns.response(403, 'Forbidden (not the creator)', model=message_model)
    @ns.response(500, 'Failed to update competition', model=message_model)
    def put(self, competition_id):
        """Updates an existing competition. Only the creator can update."""
        current_user_id_str = get_jwt_identity()
        # ... (获取 current_user_id, competition 对象, 权限检查 和之前一样) ...
        competition = Competition.query.get_or_404(competition_id)
        current_user_id = int(current_user_id_str)
        if competition.created_by_user_id != current_user_id:
            return {'msg': 'Forbidden: You are not the creator of this competition'}, 403

        args = competition_update_parser.parse_args()
        # 只有当参数在请求中提供了才更新
        if args.get('name') is not None: competition.name = args['name']
        if args.get('category') is not None: competition.category = args['category']
        # ... (更新其他字段) ...
        if args.get('start_time') is not None:
            try:
                competition.start_time = datetime.datetime.fromisoformat(args['start_time'].replace('Z', '+00:00')) if \
                args['start_time'] else None
            except ValueError:
                return {'msg': 'Invalid start_time format'}, 400
        # ... (更新 end_time, organizer, status) ...
        if args.get('status') is not None: competition.status = args['status']

        try:
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            return {'msg': f'Failed to update competition: {str(e)}'}, 500
        # from flask_restx import marshal
        # return marshal(competition, competition_model), 200
        return competition.to_dict(), 200

    @ns.doc('delete_competition', security='jsonWebToken')
    @jwt_required()
    @ns.response(200, 'Competition deleted successfully', model=message_model)  # 或者 204 No Content
    @ns.response(401, 'Unauthorized', model=message_model)
    @ns.response(403, 'Forbidden (not the creator)', model=message_model)
    @ns.response(500, 'Failed to delete competition', model=message_model)
    def delete(self, competition_id):
        """Deletes a competition. Only the creator can delete."""
        current_user_id_str = get_jwt_identity()
        # ... (获取 current_user_id, competition 对象, 权限检查 和之前一样) ...
        competition = Competition.query.get_or_404(competition_id)
        current_user_id = int(current_user_id_str)
        if competition.created_by_user_id != current_user_id:
            return {'msg': 'Forbidden: You are not the creator of this competition'}, 403

        try:
            db.session.delete(competition)
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            # 考虑外键约束错误
            if "foreign key constraint" in str(e).lower():
                return {'msg': "Cannot delete competition because it has associated teams."}, 409
            return {'msg': f'Failed to delete competition: {str(e)}'}, 500
        return {'msg': 'Competition deleted successfully'}, 200