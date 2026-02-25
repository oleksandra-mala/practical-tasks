import pytest
import requests

@pytest.fixture(scope="session")
def base_url():
    return "https://reqres.in/api/users?page=1"

@pytest.fixture
def api_client(base_url):
    session = requests.Session()
    session.headers.update({
        "x-api-key": 'pro_e6006bd8574cee9510665b23fc5430e4ba397d08e4c0992b1b05d9c1f5147ab1',
        "Content-Type": "application/json"
    })
    yield session
    session.close()