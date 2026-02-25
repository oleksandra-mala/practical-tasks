def test_get_users(api_client, base_url):
    response = api_client.get(f"{base_url}/users")
    assert response.status_code == 200