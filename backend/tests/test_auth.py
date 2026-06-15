"""Auth tests: signup, login, me, duplicate, autolink"""
import requests
import uuid

BASE = "https://grihkari-laundry.preview.emergentagent.com"


def _rand_phone():
    # 10 digit starting non-zero
    return "8" + str(uuid.uuid4().int)[:9]


def test_health(api_client):
    r = api_client.get(f"{BASE}/api/")
    assert r.status_code == 200
    assert r.json().get("status") == "ok"


def test_signup_iron_man_idempotent_or_login(iron_auth):
    assert "token" in iron_auth and "user" in iron_auth
    u = iron_auth["user"]
    assert u["role"] == "iron_man"
    assert u["phone"] == "9999999991"
    assert u["subscription_status"] in ("trial", "active", "expired")


def test_signup_client_idempotent_or_login(client_auth):
    assert client_auth["user"]["role"] == "client"
    assert client_auth["user"]["phone"] == "9999999992"


def test_signup_duplicate_phone_400(api_client):
    # Iron man phone already exists
    r = api_client.post(f"{BASE}/api/auth/signup", json={
        "name": "Dup", "phone": "9999999991", "password": "test123", "role": "iron_man"
    })
    assert r.status_code == 400


def test_login_wrong_password_401(api_client):
    r = api_client.post(f"{BASE}/api/auth/login", json={
        "phone": "9999999991", "password": "wrongpass"
    })
    assert r.status_code == 401


def test_login_correct_returns_token_and_user(api_client):
    r = api_client.post(f"{BASE}/api/auth/login", json={
        "phone": "9999999991", "password": "test123"
    })
    assert r.status_code == 200
    data = r.json()
    assert "token" in data
    assert data["user"]["phone"] == "9999999991"


def test_get_me_with_bearer(api_client, iron_auth):
    r = api_client.get(f"{BASE}/api/auth/me",
                       headers={"Authorization": f"Bearer {iron_auth['token']}"})
    assert r.status_code == 200
    u = r.json()
    assert u["phone"] == "9999999991"
    # trial_ends_at should be set
    assert u.get("trial_ends_at") is not None


def test_get_me_without_token_401(api_client):
    r = api_client.get(f"{BASE}/api/auth/me")
    assert r.status_code == 401


def test_autolink_client_on_signup(api_client, iron_headers):
    """Iron man pre-adds a client phone, then that user signs up as client."""
    phone = _rand_phone()
    # 1) iron adds client by phone (user does not exist yet)
    r = api_client.post(f"{BASE}/api/clients",
                        headers=iron_headers,
                        json={"name": "TEST_AutoLink", "phone": phone, "default_rate": 12.0})
    assert r.status_code == 200, r.text
    cdoc = r.json()
    client_record_id = cdoc["id"]
    assert cdoc["linked_user_id"] is None

    # 2) user signs up with same phone+role=client => should be auto-linked
    r2 = api_client.post(f"{BASE}/api/auth/signup", json={
        "name": "TEST_AutoLinkUser", "phone": phone, "password": "test123", "role": "client"
    })
    assert r2.status_code == 200, r2.text
    new_user_id = r2.json()["user"]["id"]

    # 3) verify client record now linked
    r3 = api_client.get(f"{BASE}/api/clients/{client_record_id}", headers=iron_headers)
    assert r3.status_code == 200
    assert r3.json()["linked_user_id"] == new_user_id

    # cleanup
    api_client.delete(f"{BASE}/api/clients/{client_record_id}", headers=iron_headers)
