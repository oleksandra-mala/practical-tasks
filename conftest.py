import pytest
import requests

@pytest.fixture(scope="session")
def base_url():
    return "https://reqres.in/api/users?page=1"

@pytest.fixture
def api_client(base_url):
    session = requests.Session()
    session.headers.update({
        "x-api-key": 'reqres_c1f61551245340e9ba114b43d8f6d15b',
        "Content-Type": "application/json"
    })
    yield session
    session.close()