def test_delete_user(api_client, base_url):
    response = api_client.delete(f"{base_url}/users/2")
    assert response.status_code == 204