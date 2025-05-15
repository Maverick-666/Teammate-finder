import pytest
from flask import jsonify  # 可能不需要，看你断言方式


# from app.models import User # 如果需要直接操作模型进行断言

# 注意：因为我们用了 fixture，所以测试函数的参数名要和 fixture 名对应
# pytest 会自动把 fixture 的返回值注入到测试函数中

def test_register_user(client):  # client fixture 会被注入
    """Test user registration."""
    response = client.post('/api/auth/register', json={
        'username': 'testuser1',
        'email': 'test1@example.com',
        'password': 'password123'
    })
    assert response.status_code == 201  # 断言状态码
    json_data = response.get_json()
    assert json_data['msg'] == 'User registered successfully'

    # 尝试注册已存在的用户名
    response_conflict_username = client.post('/api/auth/register', json={
        'username': 'testuser1',  # 用户名已存在
        'email': 'test_another@example.com',
        'password': 'password456'
    })
    assert response_conflict_username.status_code == 409
    assert response_conflict_username.get_json()['msg'] == 'Username already exists'

    # 尝试注册已存在的邮箱
    response_conflict_email = client.post('/api/auth/register', json={
        'username': 'testuser_another',
        'email': 'test1@example.com',  # 邮箱已存在
        'password': 'password789'
    })
    assert response_conflict_email.status_code == 409
    assert response_conflict_email.get_json()['msg'] == 'Email already exists'

    # 尝试注册缺少必要字段
    response_missing_field = client.post('/api/auth/register', json={
        'username': 'testuser_missing'
        # 缺少 email 和 password
    })
    assert response_missing_field.status_code == 400  # Flask-RESTX 的 @ns.expect 会处理这个
    # Flask-RESTX 的校验错误信息可能更具体，例如：
    # {'errors': {'email': "'email' is a required property", 'password': "'password' is a required property"}, 'message': 'Input payload validation failed'}
    # 你需要根据实际返回的错误信息来写断言


def test_login_user(client):
    """Test user login."""
    # 先注册一个用户才能登录
    client.post('/api/auth/register', json={
        'username': 'logintestuser',
        'email': 'login@example.com',
        'password': 'loginpassword'
    })

    # 成功登录
    response_success = client.post('/api/auth/login', json={
        'identifier': 'login@example.com',
        'password': 'loginpassword'
    })
    assert response_success.status_code == 200
    json_data_success = response_success.get_json()
    assert json_data_success['msg'] == 'Login successful'
    assert 'access_token' in json_data_success['tokens']
    assert 'refresh_token' in json_data_success['tokens']
    assert json_data_success['user']['username'] == 'logintestuser'

    # 错误密码登录
    response_wrong_pass = client.post('/api/auth/login', json={
        'identifier': 'login@example.com',
        'password': 'wrongpassword'
    })
    assert response_wrong_pass.status_code == 401
    assert response_wrong_pass.get_json()['msg'] == 'Bad username or password'

    # 用户不存在登录
    response_no_user = client.post('/api/auth/login', json={
        'identifier': 'nouser@example.com',
        'password': 'anypassword'
    })
    assert response_no_user.status_code == 401  # 通常也是返回 401，不暴露用户是否存在
    assert response_no_user.get_json()['msg'] == 'Bad username or password'


def test_get_profile_unauthorized(client):
    """Test accessing profile without token."""
    response = client.get('/api/auth/profile')
    assert response.status_code == 401  # Flask-JWT-Extended 会返回 401
    # 具体的 msg 可能依赖于 Flask-JWT-Extended 的错误处理器
    # 例如：{'msg': 'Missing Authorization Header'}


def test_get_and_update_profile_authorized(authenticated_client):  # 使用我们定义的 authenticated_client fixture
    """Test getting and updating profile with token."""
    # authenticated_client fixture 已经帮我们注册登录了一个用户，并设置了 Authorization 头

    # 获取个人资料
    response_get = authenticated_client.get('/api/auth/profile')
    assert response_get.status_code == 200
    profile_data = response_get.get_json()
    assert profile_data['username'] == 'testuser_for_fixture'  # fixture 中注册的用户名
    assert profile_data['email'] == 'test_fixture@example.com'

    # 更新个人资料
    update_payload = {
        "nickname": "Updated Nickname",
        "major": "Computer Science Test",
        "bio": "This is an updated bio for testing."
    }
    response_put = authenticated_client.put('/api/auth/profile', json=update_payload)
    assert response_put.status_code == 200
    updated_profile_data = response_put.get_json()['user']
    assert updated_profile_data['nickname'] == "Updated Nickname"
    assert updated_profile_data['major'] == "Computer Science Test"
    assert updated_profile_data['bio'] == "This is an updated bio for testing."
    assert updated_profile_data['username'] == 'testuser_for_fixture'  # 用户名不应改变

    # 再次获取，确认已更新
    response_get_again = authenticated_client.get('/api/auth/profile')
    assert response_get_again.status_code == 200
    assert response_get_again.get_json()['nickname'] == "Updated Nickname"


def test_refresh_token(client, auth_tokens):  # 使用 client 和 auth_tokens fixture
    """Test refreshing an access token."""
    refresh_token = auth_tokens['refresh_token']

    response = client.post('/api/auth/refresh', headers={
        'Authorization': f'Bearer {refresh_token}'
    })
    assert response.status_code == 200
    json_data = response.get_json()
    assert 'access_token' in json_data
    assert json_data['access_token'] != auth_tokens['access_token']  # 新的 access token

    # 尝试用 access token 去刷新 (应该失败)
    access_token = auth_tokens['access_token']
    response_wrong_token = client.post('/api/auth/refresh', headers={
        'Authorization': f'Bearer {access_token}'
    })
    assert response_wrong_token.status_code == 422  # 或者 422 Unprocessable Entity，取决于 JWT 扩展如何处理
    # Flask-JWT-Extended 对 refresh=True 的接口，如果用 access token 会报 "Only refresh tokens are allowed" (422)
    # 如果你的 @jwt.invalid_token_loader 返回的是401，那么就是401