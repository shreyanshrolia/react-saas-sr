import os
import pytest
import requests

# Use external preview URL like main agent
BASE_URL = "https://grihkari-laundry.preview.emergentagent.com"


@pytest.fixture(scope="session")
def base_url():
    return BASE_URL


@pytest.fixture
def api_client():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    return s


def _signup_or_login(s, phone, password, name, role):
    r = s.post(f"{BASE_URL}/api/auth/signup", json={
        "name": name, "phone": phone, "password": password, "role": role
    }, timeout=20)
    if r.status_code == 200:
        return r.json()
    # already exists -> login
    r = s.post(f"{BASE_URL}/api/auth/login",
               json={"phone": phone, "password": password}, timeout=20)
    assert r.status_code == 200, f"login failed: {r.status_code} {r.text}"
    return r.json()


@pytest.fixture(scope="session")
def iron_auth():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    return _signup_or_login(s, "9999999991", "test123", "Test Iron", "iron_man")


@pytest.fixture(scope="session")
def client_auth():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    return _signup_or_login(s, "9999999992", "test123", "Test Client", "client")


@pytest.fixture
def iron_headers(iron_auth):
    return {"Authorization": f"Bearer {iron_auth['token']}",
            "Content-Type": "application/json"}


@pytest.fixture
def client_headers(client_auth):
    return {"Authorization": f"Bearer {client_auth['token']}",
            "Content-Type": "application/json"}
