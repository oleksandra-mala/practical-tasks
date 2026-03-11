def test_create_new_user(api_client, base_url):
    payload = {
        "email": "eve.holt@reqres.in",
        "password": "pistol"
    }
    response = api_client.post(f"{base_url}/register", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["token"] != ""
