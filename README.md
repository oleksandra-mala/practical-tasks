REST API tests
Methods: GET, POST, PUT, DELETE
Endpoint structure: https://reqres.in/api/users/2
Library: requests

Project Structure:
/tests/api/
    test_get.py
    test_post.py
    test_put.py
    test_delete.py
/tests/ui/
    test_login.py
conftest.py
requirements.txt
README.md

Submission Requirements:
Code follows PEP8 formatting
Fixtures are used, with yield for setup/teardown
Pytest command-line works:
pytest tests/api
pytest tests/ui