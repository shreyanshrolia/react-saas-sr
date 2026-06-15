"""Iteration 5 tests: notifications + entry confirmation flows + delete gating + trial subscription stacking.

Covers:
- New entry creates notification for linked client (type='new_entry')
- Mark returned (linked) -> status='return_pending' + 'return_requested' notification
- Client confirm return -> status='returned' + 'return_confirmed' notification for iron man
- Client deny return -> status back to 'pending' + 'return_denied' notification
- Mark returned (UNLINKED) -> directly 'returned', no notification
- DELETE /entries/{id} blocked (403) when linked; allowed when unlinked
- Client delete-request -> iron-man notification (type='delete_requested')
- Iron man delete-confirm -> entry deleted + client 'delete_confirmed' notification
- Iron man delete-deny -> delete_requested_at cleared + 'delete_denied' notification
- Authorization: client cannot confirm return on someone else's entry (404)
- Iron man cannot confirm/deny delete on entry that isn't theirs (404)
- Notifications endpoints: list, unread-count, mark-one-read, mark-all-read
- Subscription derivation: trial vs active vs expired via direct mongo manipulation
"""
import os
import time
import uuid
from datetime import datetime, timedelta, timezone

import pytest
import requests
from pymongo import MongoClient
from dotenv import load_dotenv
from pathlib import Path

load_dotenv(Path("/app/backend/.env"))

BASE_URL = "https://grihkari-laundry.preview.emergentagent.com"
MONGO_URL = os.environ["MONGO_URL"]
DB_NAME = os.environ["DB_NAME"]

_mc = MongoClient(MONGO_URL)
_db = _mc[DB_NAME]


def _signup_or_login(phone, password, name, role):
    r = requests.post(f"{BASE_URL}/api/auth/signup",
                      json={"name": name, "phone": phone, "password": password, "role": role},
                      timeout=20)
    if r.status_code == 200:
        return r.json()
    r = requests.post(f"{BASE_URL}/api/auth/login",
                      json={"phone": phone, "password": password}, timeout=20)
    assert r.status_code == 200, r.text
    return r.json()


@pytest.fixture(scope="module")
def iron():
    return _signup_or_login("9999999991", "test123", "Test Iron", "iron_man")


@pytest.fixture(scope="module")
def client_user():
    return _signup_or_login("9999999992", "test123", "Test Client", "client")


@pytest.fixture(scope="module")
def iron_h(iron):
    return {"Authorization": f"Bearer {iron['token']}", "Content-Type": "application/json"}


@pytest.fixture(scope="module")
def client_h(client_user):
    return {"Authorization": f"Bearer {client_user['token']}", "Content-Type": "application/json"}


@pytest.fixture(scope="module", autouse=True)
def ensure_linked_client(iron_h, client_user):
    """Ensure iron has a client record for the test client (linked)."""
    # find or add the client record for phone 9999999992
    r = requests.get(f"{BASE_URL}/api/clients", headers=iron_h, timeout=20)
    assert r.status_code == 200, r.text
    existing = [c for c in r.json() if c["phone"] == "9999999992"]
    if not existing:
        r = requests.post(f"{BASE_URL}/api/clients", headers=iron_h, json={
            "name": "Test Client", "phone": "9999999992", "default_rate": 10.0
        }, timeout=20)
        assert r.status_code == 200, r.text
        cid = r.json()["id"]
    else:
        cid = existing[0]["id"]
    # Make sure linked_user_id is set (should auto-link since client signed up)
    _db.clients.update_one({"_id": cid}, {"$set": {"linked_user_id": client_user["user"]["id"]}})
    return cid


def _new_entry(iron_h, client_id, qty=3, rate=10):
    r = requests.post(f"{BASE_URL}/api/entries", headers=iron_h, json={
        "client_id": client_id,
        "items": [{"cloth_type": "shirt", "quantity": qty, "rate": rate}],
        "notes": "TEST_iter5"
    }, timeout=20)
    assert r.status_code == 200, r.text
    return r.json()


def _clear_notifications(user_id):
    _db.notifications.delete_many({"user_id": user_id})


# ---------- Entry lifecycle (linked client) ----------
class TestEntryLifecycleLinked:

    def test_new_entry_creates_client_notification(self, iron_h, client_user, ensure_linked_client):
        client_uid = client_user["user"]["id"]
        _clear_notifications(client_uid)
        entry = _new_entry(iron_h, ensure_linked_client, qty=5)
        assert entry["status"] == "pending"
        assert entry["linked_user_id"] == client_uid

        notifs = list(_db.notifications.find({"user_id": client_uid, "entry_id": entry["id"]}))
        assert len(notifs) == 1
        assert notifs[0]["type"] == "new_entry"
        assert notifs[0]["read"] is False

    def test_mark_returned_linked_goes_to_return_pending(self, iron_h, client_user, ensure_linked_client):
        client_uid = client_user["user"]["id"]
        entry = _new_entry(iron_h, ensure_linked_client)
        _clear_notifications(client_uid)
        r = requests.post(f"{BASE_URL}/api/entries/{entry['id']}/return",
                          headers=iron_h, json={}, timeout=20)
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["status"] == "return_pending"
        assert body["return_requested_at"] is not None

        notifs = list(_db.notifications.find({"user_id": client_uid, "entry_id": entry["id"], "type": "return_requested"}))
        assert len(notifs) == 1

    def test_client_confirm_return(self, iron_h, client_h, client_user, iron, ensure_linked_client):
        iron_uid = iron["user"]["id"]
        entry = _new_entry(iron_h, ensure_linked_client)
        # iron marks returned
        r = requests.post(f"{BASE_URL}/api/entries/{entry['id']}/return", headers=iron_h, json={}, timeout=20)
        assert r.status_code == 200
        _clear_notifications(iron_uid)
        # client confirms
        r = requests.post(f"{BASE_URL}/api/entries/{entry['id']}/return/confirm", headers=client_h, timeout=20)
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["status"] == "returned"
        assert body["date_returned"] is not None

        # iron man receives 'return_confirmed'
        notifs = list(_db.notifications.find({"user_id": iron_uid, "entry_id": entry["id"], "type": "return_confirmed"}))
        assert len(notifs) == 1

    def test_client_deny_return(self, iron_h, client_h, iron, ensure_linked_client):
        iron_uid = iron["user"]["id"]
        entry = _new_entry(iron_h, ensure_linked_client)
        r = requests.post(f"{BASE_URL}/api/entries/{entry['id']}/return", headers=iron_h, json={}, timeout=20)
        assert r.status_code == 200
        _clear_notifications(iron_uid)
        r = requests.post(f"{BASE_URL}/api/entries/{entry['id']}/return/deny", headers=client_h, timeout=20)
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["status"] == "pending"
        assert body["return_requested_at"] is None

        notifs = list(_db.notifications.find({"user_id": iron_uid, "entry_id": entry["id"], "type": "return_denied"}))
        assert len(notifs) == 1


# ---------- Entry lifecycle (UNLINKED client) ----------
class TestEntryLifecycleUnlinked:

    @pytest.fixture
    def unlinked_client_id(self, iron_h):
        # create a client with a unique phone not registered as user
        phone = f"77{int(time.time()) % 100000000:08d}"
        r = requests.post(f"{BASE_URL}/api/clients", headers=iron_h, json={
            "name": "TEST_Unlinked", "phone": phone, "default_rate": 10
        }, timeout=20)
        assert r.status_code == 200, r.text
        cid = r.json()["id"]
        # ensure unlinked
        _db.clients.update_one({"_id": cid}, {"$set": {"linked_user_id": None}})
        yield cid
        # cleanup
        requests.delete(f"{BASE_URL}/api/clients/{cid}", headers=iron_h, timeout=20)

    def test_unlinked_return_goes_directly_to_returned(self, iron_h, unlinked_client_id):
        entry = _new_entry(iron_h, unlinked_client_id)
        assert entry["linked_user_id"] is None
        r = requests.post(f"{BASE_URL}/api/entries/{entry['id']}/return", headers=iron_h, json={}, timeout=20)
        assert r.status_code == 200
        body = r.json()
        assert body["status"] == "returned"
        assert body["date_returned"] is not None
        # no notification created (no recipient)
        # (Iron man should not get a notification for their own action on unlinked)
        notifs = list(_db.notifications.find({"entry_id": entry["id"]}))
        assert notifs == []

    def test_unlinked_delete_works(self, iron_h, unlinked_client_id):
        entry = _new_entry(iron_h, unlinked_client_id)
        r = requests.delete(f"{BASE_URL}/api/entries/{entry['id']}", headers=iron_h, timeout=20)
        assert r.status_code == 200
        assert _db.entries.find_one({"_id": entry["id"]}) is None


# ---------- Entry deletion (linked) ----------
class TestEntryDeletionLinked:

    def test_iron_cannot_delete_linked_entry(self, iron_h, ensure_linked_client):
        entry = _new_entry(iron_h, ensure_linked_client)
        r = requests.delete(f"{BASE_URL}/api/entries/{entry['id']}", headers=iron_h, timeout=20)
        assert r.status_code == 403, r.text
        assert "signed up" in r.text.lower()
        # entry still exists
        assert _db.entries.find_one({"_id": entry["id"]}) is not None

    def test_client_delete_request_creates_notification(self, iron_h, client_h, iron, ensure_linked_client):
        iron_uid = iron["user"]["id"]
        entry = _new_entry(iron_h, ensure_linked_client)
        _clear_notifications(iron_uid)
        r = requests.post(f"{BASE_URL}/api/entries/{entry['id']}/delete-request", headers=client_h, timeout=20)
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["delete_requested_at"] is not None
        notifs = list(_db.notifications.find({"user_id": iron_uid, "entry_id": entry["id"], "type": "delete_requested"}))
        assert len(notifs) == 1

    def test_iron_delete_confirm(self, iron_h, client_h, client_user, ensure_linked_client):
        client_uid = client_user["user"]["id"]
        entry = _new_entry(iron_h, ensure_linked_client)
        r = requests.post(f"{BASE_URL}/api/entries/{entry['id']}/delete-request", headers=client_h, timeout=20)
        assert r.status_code == 200
        _clear_notifications(client_uid)
        r = requests.post(f"{BASE_URL}/api/entries/{entry['id']}/delete-confirm", headers=iron_h, timeout=20)
        assert r.status_code == 200, r.text
        assert _db.entries.find_one({"_id": entry["id"]}) is None
        notifs = list(_db.notifications.find({"user_id": client_uid, "type": "delete_confirmed"}))
        assert len(notifs) >= 1

    def test_iron_delete_deny(self, iron_h, client_h, client_user, ensure_linked_client):
        client_uid = client_user["user"]["id"]
        entry = _new_entry(iron_h, ensure_linked_client)
        r = requests.post(f"{BASE_URL}/api/entries/{entry['id']}/delete-request", headers=client_h, timeout=20)
        assert r.status_code == 200
        _clear_notifications(client_uid)
        r = requests.post(f"{BASE_URL}/api/entries/{entry['id']}/delete-deny", headers=iron_h, timeout=20)
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["delete_requested_at"] is None
        # entry still exists
        assert _db.entries.find_one({"_id": entry["id"]}) is not None
        notifs = list(_db.notifications.find({"user_id": client_uid, "entry_id": entry["id"], "type": "delete_denied"}))
        assert len(notifs) == 1

    def test_delete_confirm_requires_pending_request(self, iron_h, ensure_linked_client):
        entry = _new_entry(iron_h, ensure_linked_client)
        r = requests.post(f"{BASE_URL}/api/entries/{entry['id']}/delete-confirm", headers=iron_h, timeout=20)
        assert r.status_code == 400


# ---------- Authorization ----------
class TestAuthorization:

    def test_client_cannot_confirm_return_on_others_entry(self, iron_h, client_h, ensure_linked_client):
        entry = _new_entry(iron_h, ensure_linked_client)
        r = requests.post(f"{BASE_URL}/api/entries/{entry['id']}/return", headers=iron_h, json={}, timeout=20)
        assert r.status_code == 200
        # tamper: linked_user_id is set to someone else
        _db.entries.update_one({"_id": entry["id"]}, {"$set": {"linked_user_id": "fake-user-id"}})
        r = requests.post(f"{BASE_URL}/api/entries/{entry['id']}/return/confirm", headers=client_h, timeout=20)
        assert r.status_code == 404

    def test_iron_cannot_act_on_other_irons_entry(self, iron_h, client_h, client_user):
        # Insert a fake entry owned by another iron-man directly
        fake_id = str(uuid.uuid4())
        _db.entries.insert_one({
            "_id": fake_id,
            "iron_man_id": "other-iron",
            "client_id": "x",
            "client_name": "x",
            "client_phone": "0000000000",
            "linked_user_id": client_user["user"]["id"],
            "date_given": datetime.now(timezone.utc).isoformat(),
            "items": [{"cloth_type": "t", "quantity": 1, "rate": 1}],
            "total_quantity": 1, "total_amount": 1.0,
            "status": "pending", "delete_requested_at": datetime.now(timezone.utc).isoformat(),
            "month_key": datetime.now(timezone.utc).strftime("%Y-%m"),
            "created_at": datetime.now(timezone.utc).isoformat(),
        })
        try:
            r = requests.post(f"{BASE_URL}/api/entries/{fake_id}/delete-confirm", headers=iron_h, timeout=20)
            assert r.status_code == 404
            r = requests.post(f"{BASE_URL}/api/entries/{fake_id}/delete-deny", headers=iron_h, timeout=20)
            assert r.status_code == 404
        finally:
            _db.entries.delete_one({"_id": fake_id})


# ---------- Notifications endpoints ----------
class TestNotificationsEndpoints:

    def test_list_notifications_sorted_desc_and_unread_count(self, iron_h, client_h, client_user, ensure_linked_client):
        client_uid = client_user["user"]["id"]
        _clear_notifications(client_uid)
        # trigger 3 notifs
        _new_entry(iron_h, ensure_linked_client)
        _new_entry(iron_h, ensure_linked_client)
        _new_entry(iron_h, ensure_linked_client)

        r = requests.get(f"{BASE_URL}/api/notifications", headers=client_h, timeout=20)
        assert r.status_code == 200, r.text
        items = r.json()
        assert len(items) >= 3
        created = [n["created_at"] for n in items]
        assert created == sorted(created, reverse=True), "should be desc"

        r = requests.get(f"{BASE_URL}/api/notifications/unread-count", headers=client_h, timeout=20)
        assert r.status_code == 200
        assert r.json()["count"] >= 3

    def test_mark_one_read(self, iron_h, client_h, client_user, ensure_linked_client):
        client_uid = client_user["user"]["id"]
        _clear_notifications(client_uid)
        _new_entry(iron_h, ensure_linked_client)
        r = requests.get(f"{BASE_URL}/api/notifications", headers=client_h, timeout=20)
        nid = r.json()[0]["id"]
        r = requests.post(f"{BASE_URL}/api/notifications/{nid}/read", headers=client_h, timeout=20)
        assert r.status_code == 200
        n = _db.notifications.find_one({"_id": nid})
        assert n["read"] is True

    def test_mark_all_read(self, iron_h, client_h, client_user, ensure_linked_client):
        client_uid = client_user["user"]["id"]
        _clear_notifications(client_uid)
        _new_entry(iron_h, ensure_linked_client)
        _new_entry(iron_h, ensure_linked_client)
        r = requests.post(f"{BASE_URL}/api/notifications/read-all", headers=client_h, timeout=20)
        assert r.status_code == 200
        assert r.json()["updated"] >= 2
        r = requests.get(f"{BASE_URL}/api/notifications/unread-count", headers=client_h, timeout=20)
        assert r.json()["count"] == 0

    def test_mark_read_404_for_other_users_notification(self, iron_h, client_h, client_user, ensure_linked_client):
        # create a notif for client; try to mark via iron's token => 404
        _clear_notifications(client_user["user"]["id"])
        _new_entry(iron_h, ensure_linked_client)
        r = requests.get(f"{BASE_URL}/api/notifications", headers=client_h, timeout=20)
        nid = r.json()[0]["id"]
        r = requests.post(f"{BASE_URL}/api/notifications/{nid}/read", headers=iron_h, timeout=20)
        assert r.status_code == 404


# ---------- Subscription status derivation ----------
class TestSubscriptionStatus:
    """Manipulate trial/sub dates via pymongo and verify /auth/me derives status correctly."""

    def _set_dates(self, user_id, trial_end, sub_end):
        _db.users.update_one({"_id": user_id}, {"$set": {
            "trial_ends_at": trial_end.isoformat() if trial_end else None,
            "subscription_ends_at": sub_end.isoformat() if sub_end else None,
        }})

    def _me(self, headers):
        r = requests.get(f"{BASE_URL}/api/auth/me", headers=headers, timeout=20)
        assert r.status_code == 200, r.text
        return r.json()

    def test_status_trial_when_both_in_future(self, iron, iron_h):
        now = datetime.now(timezone.utc)
        self._set_dates(iron["user"]["id"], now + timedelta(days=10), now + timedelta(days=40))
        me = self._me(iron_h)
        assert me["subscription_status"] == "trial"

    def test_status_active_when_trial_past_sub_future(self, iron, iron_h):
        now = datetime.now(timezone.utc)
        self._set_dates(iron["user"]["id"], now - timedelta(days=1), now + timedelta(days=20))
        me = self._me(iron_h)
        assert me["subscription_status"] == "active"

    def test_status_expired_when_both_past(self, iron, iron_h):
        now = datetime.now(timezone.utc)
        self._set_dates(iron["user"]["id"], now - timedelta(days=10), now - timedelta(days=1))
        me = self._me(iron_h)
        assert me["subscription_status"] == "expired"

    def test_teardown_restore_trial(self, iron):
        # restore to a healthy trial state for other tests/users
        now = datetime.now(timezone.utc)
        self._set_dates(iron["user"]["id"], now + timedelta(days=45), now + timedelta(days=45))
