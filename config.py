import os
from dotenv import load_dotenv
import datetime

# 定位 .env 文件所在的目录 (项目根目录)
basedir = os.path.abspath(os.path.dirname(__file__))
load_dotenv(os.path.join(basedir, '.env')) # 加载 .env 文件

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'you-will-never-guess' # 提供一个默认值以防万一

    # SQLAlchemy 配置
    # 格式: 'mysql+pymysql://username:password@host:port/database_name'
    SQLALCHEMY_DATABASE_URI = (
        f"mysql+pymysql://{os.environ.get('DATABASE_USER')}:"
        f"{os.environ.get('DATABASE_PASSWORD')}@"
        f"{os.environ.get('DATABASE_HOST')}:"
        f"{os.environ.get('DATABASE_PORT')}/"
        f"{os.environ.get('DATABASE_NAME')}"
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False # 关闭不必要的追踪，节省资源

    # JWT 配置
    JWT_SECRET_KEY = os.environ.get('JWT_SECRET_KEY') or 'super-secret' # 提供一个默认值

    # 可以添加其他 JWT 配置，比如过期时间等
    # JWT_ACCESS_TOKEN_EXPIRES = timedelta(hours=1)

    # 如果有其他配置，也可以放这里


class TestingConfig(Config):  # <--- 新增测试配置类，继承自 Config
    TESTING = True  # 开启测试模式，Flask 和一些扩展会有不同的行为

    # 使用一个与开发数据库不同的测试数据库 (例如，在同一个 MySQL 实例下创建另一个库)
    # 或者使用 SQLite 内存数据库，这样更快，且每次测试都是干净的
    # 方案一：独立的 MySQL 测试库 (假设已创建 teammate_finder_test_db)
    # SQLALCHEMY_DATABASE_URI = (
    #     f"mysql+pymysql://{os.environ.get('DATABASE_USER')}:"
    #     f"{os.environ.get('DATABASE_PASSWORD')}@"
    #     f"{os.environ.get('DATABASE_HOST')}:"
    #     f"{os.environ.get('DATABASE_PORT')}/"
    #     f"teammate_finder_test_db" # <--- 注意数据库名不同
    # )

    # 方案二：使用 SQLite 内存数据库 (推荐，更快，隔离性好)
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'  # 或者 'sqlite:///test.db' (基于文件的 SQLite)
    JWT_SECRET_KEY = 'test-jwt-super-secret'  # 在测试配置中也明确设置一个
    # 在测试中，通常会禁用 CSRF 保护（如果你的应用有的话，我们目前没有显式添加）
    # WTF_CSRF_ENABLED = False 

    # 可以把 JWT 过期时间设置得非常长，或者禁用过期，方便测试，避免 token 过期导致测试失败
    JWT_ACCESS_TOKEN_EXPIRES = False  # 禁用 access token 过期
    JWT_REFRESH_TOKEN_EXPIRES = False  # 禁用 refresh token 过期