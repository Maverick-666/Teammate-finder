# tests/test_teams_restx.py

import pytest
# from app.models import Team, Competition

# --- 测试我们新加的普通 Flask JWT 保护路由 ---
def test_plain_flask_jwt_unauthorized(client):
    response = client.post('/api/test_jwt_protection') # 无 token 访问
    print(f"DEBUG (Plain Flask Unauthorized): Status={response.status_code}, Data={response.data.decode() if response.data else 'No data'}")
    assert response.status_code == 401
    json_data = response.get_json()
    assert "Missing Authorization Header" in json_data.get("msg", "") # Flask-JWT-Extended 默认的 unauthorized_loader 返回的消息

def test_plain_flask_jwt_authorized(authenticated_client): # authenticated_client 是带token的
    response = authenticated_client.post('/api/test_jwt_protection')
    print(f"DEBUG (Plain Flask Authorized): Status={response.status_code}, Data={response.data.decode() if response.data else 'No data'}")
    assert response.status_code == 200
    json_data = response.get_json()
    assert "You are authorized for plain Flask route!" in json_data.get("msg", "")

# 先决条件：需要一个竞赛ID来创建队伍
# 我们可以在测试开始前，用 authenticated_client 创建一个竞赛
@pytest.fixture
def sample_competition_id(authenticated_client):
    """Creates a sample competition and returns its ID."""
    response = authenticated_client.post('/api/competitions', json={
        'name': 'Competition for Teams Test',
        'description': 'A competition to test team functionalities.'
    })
    assert response.status_code == 201
    return response.get_json()['id']

def test_create_team_unauthorized(client, sample_competition_id):
    """Test creating a team without authentication."""
    response = client.post('/api/teams', json={
        'name': 'Unauthorized Team',
        'competition_id': sample_competition_id
    })
    assert response.status_code == 201

def test_create_and_get_team(authenticated_client, client, sample_competition_id):
    """Test creating a new team for a competition and then fetching it."""
    user_id_of_authenticated_client = 1 # 假设 authenticated_client 注册的 user_id 是 1 (或者从token解析)
                                        # 注意：authenticated_client fixture 内部注册的用户是 testuser_for_fixture
                                        # 我们需要知道它的 ID，或者让 fixture 返回用户对象/ID
                                        # 更好的做法是，让 auth_tokens fixture 也返回 user_id

    create_payload = {
        'name': 'The Avengers',
        'description': 'Earths Mightiest Heroes',
        'competition_id': sample_competition_id
    }
    response_create = authenticated_client.post('/api/teams', json=create_payload)
    assert response_create.status_code == 201
    created_team_data = response_create.get_json()
    assert created_team_data['name'] == 'The Avengers'
    assert created_team_data['competition_id'] == sample_competition_id
    assert 'id' in created_team_data
    team_id = created_team_data['id']
    # 断言队长是当前用户
    assert created_team_data['leader_username'] == 'testuser_for_fixture'
    # 断言成员列表中有队长
    assert any(member['username'] == 'testuser_for_fixture' for member in created_team_data['members'])
    assert created_team_data['member_count'] == 1


    # 获取该竞赛下的队伍列表
    response_list = client.get(f'/api/teams?competition_id={sample_competition_id}')
    assert response_list.status_code == 200
    teams_in_competition = response_list.get_json()['teams']
    assert any(team['id'] == team_id for team in teams_in_competition)

    # 获取单个队伍详情
    response_detail = client.get(f'/api/teams/{team_id}')
    assert response_detail.status_code == 200
    detail_data = response_detail.get_json()
    assert detail_data['id'] == team_id
    assert detail_data['name'] == 'The Avengers'


# --- 接下来是测试加入队伍、退出队伍、队长移除成员、解散队伍等 ---
# 这些会涉及到多个用户和更复杂的权限/逻辑判断

# def test_join_team(client, authenticated_client, sample_competition_id, team_id_created_by_another): ...
# (需要一个用户创建队伍，另一个用户加入)
# ...