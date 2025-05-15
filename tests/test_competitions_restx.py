import pytest


# from app.models import Competition # 如果需要直接验证数据库中的数据

def test_create_competition_unauthorized(client):
    """Test creating a competition without authentication."""
    response = client.post('/api/competitions', json={
        'name': 'Unauthorized Test Comp',
        'description': 'This should fail.'
    })
    assert response.status_code == 401  # 因为 @jwt_required()


def test_create_and_get_competition(authenticated_client, client):  # 用 authenticated_client 创建，用普通 client 获取
    """Test creating a new competition and then fetching it."""
    # 使用 authenticated_client (已登录用户) 创建竞赛
    create_payload = {
        'name': 'My Awesome Competition',
        'category': 'Coding Challenge',
        'description': 'The best coding challenge ever!',
        'organizer': 'Tech Club'
        # 可以添加 start_time, end_time, status 等
    }
    response_create = authenticated_client.post('/api/competitions', json=create_payload)
    assert response_create.status_code == 201
    created_competition_data = response_create.get_json()
    assert created_competition_data['name'] == 'My Awesome Competition'
    assert 'id' in created_competition_data
    competition_id = created_competition_data['id']
    assert created_competition_data['creator_username'] == 'testuser_for_fixture'  # fixture 用户的名字

    # 使用普通 client (无需登录) 获取单个竞赛详情
    response_get_detail = client.get(f'/api/competitions/{competition_id}')
    assert response_get_detail.status_code == 200
    detail_data = response_get_detail.get_json()
    assert detail_data['id'] == competition_id
    assert detail_data['name'] == 'My Awesome Competition'

    # 使用普通 client 获取竞赛列表，应该能看到我们刚创建的
    response_get_list = client.get('/api/competitions')
    assert response_get_list.status_code == 200
    list_data = response_get_list.get_json()
    assert 'competitions' in list_data
    found_in_list = any(comp['id'] == competition_id for comp in list_data['competitions'])
    assert found_in_list, "Newly created competition not found in the list"

    # 测试获取不存在的竞赛
    response_get_non_existent = client.get('/api/competitions/99999')  # 假设 99999 不存在
    assert response_get_non_existent.status_code == 404


def test_list_competitions_with_filters(client, authenticated_client):
    """Test listing competitions with various filters."""
    # 先创建几个不同类别和状态的竞赛以便测试过滤
    authenticated_client.post('/api/competitions',
                              json={'name': 'Comp A - Coding', 'category': 'Coding', 'status': 'recruiting',
                                    'description': 'd'})
    authenticated_client.post('/api/competitions',
                              json={'name': 'Comp B - Design', 'category': 'Design', 'status': 'ongoing',
                                    'description': 'd'})
    authenticated_client.post('/api/competitions',
                              json={'name': 'Comp C - Coding Special', 'category': 'Coding', 'status': 'recruiting',
                                    'description': 'd'})

    # 测试按类别过滤
    response_cat = client.get('/api/competitions?category=Coding')
    assert response_cat.status_code == 200
    competitions_cat = response_cat.get_json()['competitions']
    assert len(competitions_cat) >= 2  # 至少有两个 "Coding" 相关的
    for comp in competitions_cat:
        assert 'Coding' in comp['category']

    # 测试按状态过滤
    response_status = client.get('/api/competitions?status=ongoing')
    assert response_status.status_code == 200
    competitions_status = response_status.get_json()['competitions']
    assert len(competitions_status) >= 1
    for comp in competitions_status:
        assert comp['status'] == 'ongoing'

    # 测试搜索 (假设 Comp C 有 "Special" 关键词)
    response_search = client.get('/api/competitions?search=Special')
    assert response_search.status_code == 200
    competitions_search = response_search.get_json()['competitions']
    assert len(competitions_search) >= 1
    assert any('Comp C - Coding Special' in comp['name'] for comp in competitions_search)

    # ... 还可以测试分页等 ...

# --- 接下来是测试更新 (PUT) 和删除 (DELETE) 竞赛的用例 ---
# 这些会更侧重权限检查 (只有创建者能操作)

# def test_update_competition_by_creator(authenticated_client, client): ...
# def test_update_competition_by_another_user(authenticated_client, client): ... (需要第二个认证用户)
# def test_delete_competition_by_creator(authenticated_client): ...
# def test_delete_competition_by_another_user(authenticated_client, client): ...