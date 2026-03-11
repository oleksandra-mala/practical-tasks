import pytest
import requests
import logging



@pytest.fixture(scope="session")
def base_url():
    return "https://reqres.in/api"


@pytest.fixture(scope="session")
def api_client(base_url):
    session = requests.Session()
    session.headers.update({
        "x-api-key": 'reqres_c1f61551245340e9ba114b43d8f6d15b',
        "content-type": "application/json"
    })
    payload = {"email": "eve.holt@reqres.in", "password": "cityslicka"}
    session.post(url=f'{base_url}/login', json=payload)
    yield session
    session.close()


