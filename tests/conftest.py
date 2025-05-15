import os
import sys

# 将项目根目录添加到 Python 的模块搜索路径中
# __file__ 是当前文件 (conftest.py) 的路径
# os.path.dirname(__file__) 是 tests 目录
# os.path.join(..., '..') 是 tests 目录的上一级，也就是项目根目录
# os.path.abspath(...) 确保是绝对路径
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))



import pytest
from app import create_app, db  # 从你的 app 包导入 create_app 和 db 对象
from config import TestingConfig  # 导入我们定义的测试配置


from app.models import User, Competition, Team # 如果需要预置数据，可能会用到

@pytest.fixture(scope='session')  # session 级别的 fixture，整个测试会话只执行一次
def app():
    """Create and configure a new app instance for each test session."""
    _app = create_app(TestingConfig)  # 使用测试配置创建 app

    # 如果用的是 SQLite 内存数据库，下面的 db.create_all() 需要在 app context 内
    # 如果用的是持久化的测试数据库，你可能需要在测试开始前确保数据库和表已创建
    # (例如，通过 Flask-Migrate 的升级命令)

    # 如果你需要在测试开始前创建所有表 (特别是对于 SQLite 内存数据库)
    with _app.app_context():
        db.create_all()  # 创建所有在模型中定义的表

    yield _app  # 使用 yield，测试结束后可以执行一些清理操作 (如果需要)

    # 测试结束后的清理 (如果需要)
    # with _app.app_context():
    #     db.drop_all() # 如果用的是持久化测试数据库，并且想每次测试后清空


@pytest.fixture()  # function 级别的 fixture，每个测试函数执行前都会调用
def client(app):
    """A test client for the app."""
    return app.test_client()  # Flask app 自带的测试客户端


@pytest.fixture()
def runner(app):
    """A test runner for the app's Click commands."""
    return app.test_cli_runner()


# 如果你需要在很多测试中用到一个已认证的用户和他的 token，可以创建一个 fixture
@pytest.fixture
def auth_tokens(client):
    """Fixture to register and login a test user, returns auth tokens."""
    # 确保每次测试用户都是新的，或者数据库是干净的
    # 如果数据库不是每次都清空，这里可能需要先删除同名用户

    # 注册一个测试用户
    client.post('/api/auth/register', json={
        'username': 'testuser_for_fixture',
        'email': 'test_fixture@example.com',
        'password': 'password'
    })
    # 登录该用户
    response = client.post('/api/auth/login', json={
        'identifier': 'test_fixture@example.com',
        'password': 'password'
    })
    tokens = response.get_json()['tokens']
    return tokens


# 如果你需要一个已认证的 client (自动带上 access_token)
@pytest.fixture
def authenticated_client(client, auth_tokens):
    """A test client authenticated with a test user's access token."""
    access_token = auth_tokens['access_token']
    client.environ_base['HTTP_AUTHORIZATION'] = f'Bearer {access_token}'  # 设置认证头
    return client


@pytest.fixture
def another_auth_tokens(client):
    """Registers and logs in a second distinct test user."""
    client.post('/api/auth/register', json={
        'username': 'another_testuser',
        'email': 'another@example.com',
        'password': 'password'
    })
    response = client.post('/api/auth/login', json={
        'identifier': 'another@example.com',
        'password': 'password'
    })
    return response.get_json()['tokens']


@pytest.fixture
def another_authenticated_client(client, another_auth_tokens):
    """A test client authenticated as a second distinct test user."""
    access_token = another_auth_tokens['access_token']
    # 创建一个新的 client 实例，或者想办法不污染全局 client 的认证头
    # 一个简单的方法是，在测试函数内需要时，临时设置 client 的认证头
    # 或者，让这个 fixture 返回一个配置好认证头的 client 副本

    # 更稳妥的做法是，如果 pytest-flask 的 client 是可重入的，
    # 我们可以直接修改它的 environ_base，但要注意测试间的隔离。
    # 如果不行，可能需要每次都创建一个新的 app.test_client() 实例。

    # 让我们尝试直接修改传入的 client，但要小心副作用。
    # 更好的做法是，让 authenticated_client fixture 返回的 client 就是带 token 的，
    # 而不是修改全局的 client。
    # 不过 pytest-flask 的 client fixture 通常是函数级别的，每次测试都会重新创建。

    # 对于第二个用户，我们可以这样做：
    from flask.testing import FlaskClient
    new_client = FlaskClient(client.application, response_wrapper=client.response_wrapper)  # 基于同一个 app 创建
    new_client.environ_base['HTTP_AUTHORIZATION'] = f'Bearer {access_token}'
    return new_client