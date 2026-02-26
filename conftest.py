import pytest
import requests
from flask import session



@pytest.fixture(scope="session")
def base_url():
    return "https://reqres.in/api/users?page=1"

@pytest.fixture
def api_client():
    session = requests.Session()

    yield session
    session.close()

@pytest.fixture
def auth_token():
    response = requests.post(
        "https://reqres.in/api/login",
        json={
            "email": "eve.holt@reqres.in",
            "password": "cityslicka"
        }
    )

    print("STATUS:", response.status_code)
    print("BODY:", response.text)

    assert response.status_code == 200

    return response.json()["token"]

# @pytest.fixture
# def api_client(base_url, auth_token):
#     session = requests.Session()
#     session.headers.update({
#         "x-api-key": f"Bearer {auth_token}",
#         "Content-Type": "application/json"
#     })
#     yield session
#     session.close()