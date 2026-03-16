import pytest
import requests



@pytest.fixture(scope="session")
def base_url():
    return "https://reqres.in/api"


@pytest.fixture(scope="session")
def api_client(base_url):
    session = requests.Session()
    session.headers.update({
        "x-api-key": 'pro_aa28b04e2f3c40c5cec3b2ef8a8e59a5cec718f56508b97edf45a9b78f8fe0e6',
        "content-type": "application/json"
    })
    payload = {"email": "eve.holt@reqres.in", "password": "cityslicka"}
    session.post(url=f'{base_url}/login', json=payload)
    yield session
    session.close()


