def test_update_name(api_client, base_url):
    payload = {
        "name": "morpheus",
        "job": "zion resident"
    }
    response = api_client.put(f"{base_url}/users/2", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "morpheus"
    assert data["job"] == "zion resident"
