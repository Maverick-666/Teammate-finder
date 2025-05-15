from . import db # 从当前包 (app) 的 __init__.py 导入 db
from sqlalchemy.sql import func # 用于设置默认时间
from werkzeug.security import generate_password_hash, check_password_hash # 用于密码处理
# 我们后面还会用到 datetime
import datetime


class User(db.Model):
    __tablename__ = 'users'  # 定义在数据库中对应的表名，推荐用复数

    id = db.Column(db.Integer, primary_key=True)  # 用户ID，主键
    username = db.Column(db.String(64), unique=True, nullable=False, index=True)  # 用户名，唯一，不能为空，加索引方便查询
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)  # 邮箱，唯一，不能为空，加索引
    password_hash = db.Column(db.String(255), nullable=False)  # 存储哈希后的密码，不能为空

    nickname = db.Column(db.String(64), nullable=True)  # 昵称，可以为空
    avatar_url = db.Column(db.String(255), nullable=True)  # 头像链接，可以为空
    major = db.Column(db.String(100), nullable=True)  # 专业
    grade = db.Column(db.String(50), nullable=True)  # 年级
    bio = db.Column(db.Text, nullable=True)  # 个人简介
    skills = db.Column(db.Text, nullable=True)  # 技能标签 (可以考虑用逗号分隔的字符串，或者更高级的 JSON 类型)

    created_at = db.Column(db.DateTime(timezone=True), server_default=func.now())  # 注册时间，带时区，数据库层面默认当前时间
    updated_at = db.Column(db.DateTime(timezone=True), onupdate=func.now())  # 最后更新时间，数据库层面更新时自动更新

    # --- 密码处理方法 ---
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    # --- 定义对象被打印时的输出格式，方便调试 ---
    def __repr__(self):
        return f'<User {self.username}>'

    # --- （可选）将模型对象转换为字典，方便 API 返回 JSON ---
    def to_dict(self, include_email=False):
        data = {
            'id': self.id,
            'username': self.username,
            'nickname': self.nickname,
            'avatar_url': self.avatar_url,
            'major': self.major,
            'grade': self.grade,
            'bio': self.bio,
            'skills': self.skills,
            'created_at': self.created_at.isoformat() if self.created_at else None,  # 转为 ISO 格式字符串
        }
        if include_email:  # 敏感信息，选择性暴露
            data['email'] = self.email
        return data








class Competition(db.Model):
    __tablename__ = 'competitions'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False, index=True)  # 竞赛名称
    category = db.Column(db.String(100), nullable=True, index=True)  # 竞赛类别 (如：编程、设计、创业)
    description = db.Column(db.Text, nullable=False)  # 竞赛详细描述

    start_time = db.Column(db.DateTime(timezone=True), nullable=True)  # 报名开始时间或竞赛开始时间
    end_time = db.Column(db.DateTime(timezone=True), nullable=True)  # 报名截止时间或竞赛结束时间

    organizer = db.Column(db.String(150), nullable=True)  # 主办方/发布方
    status = db.Column(db.String(50), default='recruiting')  # 竞赛状态 (如：recruiting招募中, ongoing进行中, ended已结束)

    # 外键，关联到 users 表的 id 字段
    # 表示这个竞赛是谁创建的
    created_by_user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)

    created_at = db.Column(db.DateTime(timezone=True), server_default=func.now())
    updated_at = db.Column(db.DateTime(timezone=True), onupdate=func.now())

    # --- 建立与 User 模型的关系 ---
    # 'User' 是关联的模型的类名
    # backref='created_competitions' 会在 User 模型上动态添加一个属性 created_competitions，
    # 通过 user_instance.created_competitions 就可以获取该用户创建的所有竞赛列表
    # lazy=True (默认) 表示关联的对象会在第一次访问时才从数据库加载
    creator = db.relationship('User', backref=db.backref('created_competitions', lazy='dynamic'))

    def __repr__(self):
        return f'<Competition {self.name}>'

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'category': self.category,
            'description': self.description,
            'start_time': self.start_time.isoformat() if self.start_time else None,
            'end_time': self.end_time.isoformat() if self.end_time else None,
            'organizer': self.organizer,
            'status': self.status,
            'created_by_user_id': self.created_by_user_id,
            # 我们可以通过 creator 关系获取创建者的信息
            'creator_username': self.creator.username if self.creator else None,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }







    # 中间表：用于 User 和 Team 之间的多对多关系
    # 我们不直接创建这个表对应的模型类，SQLAlchemy 会帮我们处理
    # 但我们需要定义这个表结构


team_members_association = db.Table('team_members',
    db.Column('user_id', db.Integer, db.ForeignKey('users.id'), primary_key=True),
    db.Column('team_id', db.Integer, db.ForeignKey('teams.id'), primary_key=True),
    db.Column('role', db.String(50), default='member') # 成员在队伍中的角色，如 'leader', 'member'
    # 可以添加其他关联信息，比如加入时间等
    # db.Column('joined_at', db.DateTime(timezone=True), server_default=func.now())
)


class Team(db.Model):
    __tablename__ = 'teams'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)  # 队伍名称
    description = db.Column(db.Text, nullable=True)  # 队伍简介或招募宣言

    # 外键，关联到 competitions 表的 id 字段
    # 表示这个队伍是为哪个竞赛创建的
    competition_id = db.Column(db.Integer, db.ForeignKey('competitions.id'), nullable=False)

    # 外键，关联到 users 表的 id 字段
    # 表示这个队伍的队长是谁
    leader_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)

    status = db.Column(db.String(50), default='open')  # 队伍状态 (如：open开放招募, closed已满, active活动中)

    created_at = db.Column(db.DateTime(timezone=True), server_default=func.now())
    updated_at = db.Column(db.DateTime(timezone=True), onupdate=func.now())

    # --- 建立与 Competition 模型的关系 (多对一) ---
    competition = db.relationship('Competition', backref=db.backref('teams', lazy='dynamic'))

    # --- 建立与 User 模型的关系 (队长，一对多反向) ---
    # 我们可以通过 team.leader 直接获取队长 User 对象
    leader = db.relationship('User', foreign_keys=[leader_id])  # foreign_keys 需要明确指定，因为 User 可能有多个外键指向 Team

    # --- 建立与 User 模型的多对多关系 (队伍成员) ---
    # secondary 指定了用于多对多关系的中间表
    # backref 会在 User 模型上添加一个 'teams' 属性，表示用户加入的所有队伍
    members = db.relationship('User', secondary=team_members_association,
                              backref=db.backref('member_of_teams', lazy='dynamic'),
                              # 在User模型上叫 member_of_teams，避免和Team上的teams冲突
                              lazy='dynamic')  # lazy='dynamic' 返回查询对象

    def __repr__(self):
        return f'<Team {self.name} for Competition ID {self.competition_id}>'

    # （可选）添加一些辅助方法，比如添加成员、移除成员、判断用户是否是队长/成员等
    def add_member(self, user, role='member'):
        if user not in self.members:
            # 直接操作 members 列表 SQLAlchemy 会处理中间表
            # 但如果中间表有额外字段 (如 role)，直接操作列表可能不够
            # 更稳妥的方式是直接操作中间表，或者使用 Association Object Pattern (更复杂一些)
            # 这里我们先简化，假设 role 是在 team_members_association 中定义的
            # 我们需要确保 SQLAlchemy 知道如何更新 role
            # 一种方式是，在建立 members 关系时，不直接用 secondary=table，而是用一个 Association Object 模型
            # 为了简单起见，我们暂时不在这里直接处理 role 的更新，后续可以在路由逻辑中处理
            self.members.append(user)
            # 如果要设置 role，通常需要更精细的控制，可能要直接操作中间表，或者在User和Team之间建立一个显式的TeamMember模型

    def remove_member(self, user):
        if user in self.members:
            self.members.remove(user)

    def is_member(self, user):
        return user in self.members

    def is_leader(self, user):
        return self.leader_id == user.id

    def to_dict(self, include_members=False, include_competition_details=False, include_leader_details=True):
        data = {
            'id': self.id,
            'name': self.name,
            'description': self.description,
            'competition_id': self.competition_id,
            'leader_id': self.leader_id,
            'status': self.status,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }
        if include_leader_details and self.leader:  # 默认包含队长信息
            data['leader_username'] = self.leader.username
            # data['leader_nickname'] = self.leader.nickname # 如果需要

        if include_competition_details and self.competition:
            data['competition_name'] = self.competition.name
            # data['competition_category'] = self.competition.category # 如果需要

        if include_members:
            # 获取成员列表，并可以简单地只返回用户名或更详细的信息
            members_list = []
            for member_user in self.members.all():  # .all() 执行查询
                member_info = {
                    'id': member_user.id,
                    'username': member_user.username,
                    'nickname': member_user.nickname,
                    # 'avatar_url': member_user.avatar_url # 如果需要
                }
                # 如果中间表有 role 字段，并且我们用了 Association Object Pattern，这里可以获取 role
                # 假设我们能通过某种方式获取角色
                # role_in_team = get_role_for_user_in_team(member_user.id, self.id) # 这是一个假设的函数
                # member_info['role'] = role_in_team
                members_list.append(member_info)
            data['members'] = members_list
            data['member_count'] = len(members_list)  # 可以顺便返回成员数量
        return data


class Post(db.Model):
    __tablename__ = 'posts'

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    body = db.Column(db.Text, nullable=False)

    # 外键，关联到 users 表的 id 字段，表示帖子的作者
    author_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)

    created_at = db.Column(db.DateTime(timezone=True), server_default=func.now())
    updated_at = db.Column(db.DateTime(timezone=True), onupdate=func.now())

    # --- 建立与 User 模型的关系 ---
    author = db.relationship('User', backref=db.backref('posts', lazy='dynamic'))

    def __repr__(self):
        return f'<Post "{self.title[:30]}..."> by User ID {self.author_id}>'

    def to_dict(self):
        return {
            'id': self.id,
            'title': self.title,
            'body': self.body,
            'author_id': self.author_id,
            'author_username': self.author.username if self.author else None,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }