import os
from dotenv import load_dotenv

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