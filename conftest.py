import pytest
import requests



@pytest.fixture(scope="session")
def base_url():
    return "https://reqres.in/api"


@pytest.fixture(scope="session")
def api_client(base_url):
    session = requests.Session()
    session.headers.update({
        "x-api-key": 'pub_90e18fe41c093dff780bafe29a201ae015c5068c10fc8f108285e2b94dd34727',
        "content-type": "application/json"
    })
    yield session
    session.close()

@pytest.fixture(scope="session")
def auth_token():
    