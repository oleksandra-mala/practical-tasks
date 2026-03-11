def test_single_user(api_client, base_url):
    response = api_client.get(f"{base_url}/users/2")
    assert response.status_code == 200
    data = response.json()
    assert data['data']['id'] == 2
    assert data['data']['first_name'] == 'Janet'

def test_list_users(api_client, base_url):
    response = api_client.get(f"{base_url}/users")
    assert response.status_code == 200
    data = response.json()
    assert data['data']['last_name'] == 'Wong'

def test_get_user_by_id(api_client, base_url):
    user_id = 1
    response = api_client.get(f"{base_url}/users/{user_id}")
    assert response.status_code == 200
    data = response.json()
    assert data['data']['first_name'] == 'George'



