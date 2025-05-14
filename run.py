from app import create_app, db # 确保 app/__init__.py 中定义了 db
# 如果有模型，也可以在这里导入，方便 Flask-Migrate 识别
# from app.models import User # 示例，User 模型需要后续创建

app = create_app()

if __name__ == '__main__':
    app.run() # 使用 FLASK_ENV=development 和 FLASK_DEBUG=1 会自动开启调试模式和重载