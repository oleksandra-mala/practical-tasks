def test_get_users(api_client, base_url):
    response = api_client.get(f"{base_url}/users/1")
    assert response.status_code == 200
    data = response.json()
    assert data['data']['id'] == 1


