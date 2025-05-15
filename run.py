# run.py
from app import create_app, db
from app.models import User, Competition, Team, Post, team_members_association # 确保导入所有模型和中间表定义

app = create_app()

# 这个@app.shell_context_processor装饰器注册一个shell上下文处理器函数。
# 当flask shell命令运行时，它会调用这个函数并在shell会话中注册它返回的条目。
# 函数返回一个字典，其中包含数据库实例和模型，这样你就可以在shell中直接使用它们了。
@app.shell_context_processor
def make_shell_context():
    return {'db': db, 'User': User, 'Competition': Competition, 'Team': Team, 'Post': Post, 'team_members_association': team_members_association}

if __name__ == '__main__':
    app.run()