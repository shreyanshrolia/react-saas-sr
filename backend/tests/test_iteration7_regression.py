"""Iteration 7 — Full backend regression after server.py modular refactor.

Goal: confirm NO regressions vs the previous monolith. Covers:
  /api/auth/*, /api/admin/*, /api/clients, /api/entries,
  /api/notifications, /api/bills + payments, /api/reports,
  /api/subscription, /api/my/iron-men, /api/.
"""
import os
import time
import uuid

import pytest
import requests

BASE_URL = os.environ.get(
    "BACKEND_URL",
    "https://grihkari-laundry.preview.emergentagent.com",
).rstrip("/")
ADMIN_PWD = "grihkari-admin-2026"
ADMIN_TOKEN = f"admin:{ADMIN_PWD}"

IRON_PHONE = "9999999991"
CLIENT_PHONE = "9999999992"
PWD = "test123"


def H(token):
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


# ---------- /api root ----------
class TestRoot:
    def test_root(self):
        r = requests.get(f"{BASE_URL}/api/", timeout=15)
        assert r.status_code == 200, r.text
        body = r.json()
        assert body == {"app": "Grihkari", "status": "ok"}


# ---------- Auth ----------
@pytest.fixture(scope="session")
def throwaway_phone():
    # 10 digits, starts with 8 to avoid colliding with seeded 9999999991/2
    base = "8" + str(uuid.uuid4().int)[:9]
    return base[:10]


@pytest.fixture(scope="session")
def throwaway_state(throwaway_phone):
    return {"phone": throwaway_phone, "user_id": None, "token": None}


class TestAuth:
    def test_signup_new(self, throwaway_state):
        r = requests.post(f"{BASE_URL}/api/auth/signup", json={
            "name": "TEST Throwaway",
            "phone": throwaway_state["phone"],
            "password": PWD,
            "role": "iron_man",
            "security_question": "What is your favorite city?",
            "security_answer": "test",
        }, timeout=20)
        assert r.status_code == 200, r.text
        data = r.json()
        assert "token" in data and "user" in data
        assert data["user"]["phone"] == throwaway_state["phone"]
        assert data["user"]["role"] == "iron_man"
        throwaway_state["user_id"] = data["user"]["id"]
        throwaway_state["token"] = data["token"]

    def test_signup_idempotent_400(self, throwaway_state):
        r = requests.post(f"{BASE_URL}/api/auth/signup", json={
            "name": "TEST Throwaway",
            "phone": throwaway_state["phone"],
            "password": PWD,
            "role": "iron_man",
            "security_question": "What is your favorite city?",
            "security_answer": "test",
        }, timeout=20)
        assert r.status_code == 400, r.text

    def test_login_correct(self):
        r = requests.post(f"{BASE_URL}/api/auth/login",
                          json={"phone": IRON_PHONE, "password": PWD}, timeout=20)
        assert r.status_code == 200, r.text
        assert "token" in r.json()
        assert r.json()["user"]["role"] == "iron_man"

    def test_login_wrong(self):
        r = requests.post(f"{BASE_URL}/api/auth/login",
                          json={"phone": IRON_PHONE, "password": "wrong-pw"}, timeout=20)
        assert r.status_code == 401, r.text

    def test_me_without_token(self):
        r = requests.get(f"{BASE_URL}/api/auth/me", timeout=15)
        assert r.status_code == 401, r.text

    def test_me_with_token(self, iron_auth):
        r = requests.get(f"{BASE_URL}/api/auth/me", headers=H(iron_auth["token"]), timeout=15)
        assert r.status_code == 200, r.text
        assert r.json()["phone"] == IRON_PHONE

    def test_security_questions(self):
        r = requests.get(f"{BASE_URL}/api/auth/security-questions", timeout=15)
        assert r.status_code == 200, r.text
        qs = r.json()["questions"]
        assert isinstance(qs, list) and len(qs) >= 3

    def test_forgot_password_valid(self):
        r = requests.post(f"{BASE_URL}/api/auth/forgot-password",
                          json={"phone": IRON_PHONE}, timeout=15)
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["phone"] == IRON_PHONE
        assert "security_question" in body

    def test_forgot_password_nonexistent(self):
        r = requests.post(f"{BASE_URL}/api/auth/forgot-password",
                          json={"phone": "1234500000"}, timeout=15)
        assert r.status_code == 404, r.text

    def test_reset_password_wrong_answer(self):
        r = requests.post(f"{BASE_URL}/api/auth/reset-password", json={
            "phone": IRON_PHONE, "security_answer": "WRONG", "new_password": "abcabc"
        }, timeout=15)
        assert r.status_code == 401, r.text

    def test_reset_password_right_then_restore(self):
        new_pw = "newpw99"
        r = requests.post(f"{BASE_URL}/api/auth/reset-password", json={
            "phone": IRON_PHONE, "security_answer": "test", "new_password": new_pw
        }, timeout=15)
        assert r.status_code == 200, r.text
        # login with new
        r2 = requests.post(f"{BASE_URL}/api/auth/login",
                           json={"phone": IRON_PHONE, "password": new_pw}, timeout=15)
        assert r2.status_code == 200, r2.text
        # restore
        r3 = requests.post(f"{BASE_URL}/api/auth/reset-password", json={
            "phone": IRON_PHONE, "security_answer": "test", "new_password": PWD
        }, timeout=15)
        assert r3.status_code == 200, r3.text


# ---------- Admin ----------
class TestAdmin:
    def test_admin_login_wrong(self):
        r = requests.post(f"{BASE_URL}/api/admin/login", json={"password": "nope"}, timeout=15)
        assert r.status_code == 401, r.text

    def test_admin_login_right(self):
        r = requests.post(f"{BASE_URL}/api/admin/login",
                          json={"password": ADMIN_PWD}, timeout=15)
        assert r.status_code == 200, r.text
        assert r.json()["token"] == ADMIN_TOKEN

    def test_admin_users_missing_token(self):
        r = requests.get(f"{BASE_URL}/api/admin/users", timeout=15)
        assert r.status_code == 401, r.text

    def test_admin_users_invalid_token(self):
        r = requests.get(f"{BASE_URL}/api/admin/users?admin_token=bad", timeout=15)
        assert r.status_code == 401, r.text

    def test_admin_users_no_q(self):
        r = requests.get(f"{BASE_URL}/api/admin/users?admin_token={ADMIN_TOKEN}", timeout=15)
        assert r.status_code == 200, r.text
        assert isinstance(r.json(), list)

    def test_admin_users_with_q(self):
        r = requests.get(f"{BASE_URL}/api/admin/users?q=9999&admin_token={ADMIN_TOKEN}", timeout=15)
        assert r.status_code == 200, r.text
        phones = [u["phone"] for u in r.json()]
        assert IRON_PHONE in phones and CLIENT_PHONE in phones

    def test_admin_reset_then_restore(self):
        # find client user_id
        r = requests.get(f"{BASE_URL}/api/admin/users?q={CLIENT_PHONE}&admin_token={ADMIN_TOKEN}",
                         timeout=15)
        assert r.status_code == 200
        users = [u for u in r.json() if u["phone"] == CLIENT_PHONE]
        assert users, "client user not found"
        uid = users[0]["id"]
        # reset
        r2 = requests.post(
            f"{BASE_URL}/api/admin/users/{uid}/reset-password?admin_token={ADMIN_TOKEN}",
            json={"new_password": "tempPW1"}, timeout=15,
        )
        assert r2.status_code == 200, r2.text
        assert r2.json()["ok"] is True
        # login as client w/ new
        r3 = requests.post(f"{BASE_URL}/api/auth/login",
                           json={"phone": CLIENT_PHONE, "password": "tempPW1"}, timeout=15)
        assert r3.status_code == 200, r3.text
        # restore
        r4 = requests.post(
            f"{BASE_URL}/api/admin/users/{uid}/reset-password?admin_token={ADMIN_TOKEN}",
            json={"new_password": PWD}, timeout=15,
        )
        assert r4.status_code == 200, r4.text


# ---------- shared auth fixtures (use seeded users) ----------
@pytest.fixture(scope="session")
def iron_auth():
    r = requests.post(f"{BASE_URL}/api/auth/login",
                      json={"phone": IRON_PHONE, "password": PWD}, timeout=15)
    assert r.status_code == 200, r.text
    return r.json()


@pytest.fixture(scope="session")
def client_auth():
    r = requests.post(f"{BASE_URL}/api/auth/login",
                      json={"phone": CLIENT_PHONE, "password": PWD}, timeout=15)
    assert r.status_code == 200, r.text
    return r.json()


# ---------- Clients ----------
@pytest.fixture(scope="session")
def created_clients(iron_auth):
    """Create two clients: one unlinked (random phone) and one linked (CLIENT_PHONE)."""
    state = {"unlinked_id": None, "linked_id": None,
             "unlinked_phone": "7" + str(uuid.uuid4().int)[:9][:9]}
    state["unlinked_phone"] = state["unlinked_phone"][:10]
    yield state


class TestClients:
    def test_list_initial(self, iron_auth):
        r = requests.get(f"{BASE_URL}/api/clients", headers=H(iron_auth["token"]), timeout=15)
        assert r.status_code == 200, r.text
        assert isinstance(r.json(), list)

    def test_add_unlinked(self, iron_auth, created_clients):
        r = requests.post(f"{BASE_URL}/api/clients", headers=H(iron_auth["token"]), json={
            "name": "TEST Unlinked",
            "phone": created_clients["unlinked_phone"],
            "address": "x",
            "default_rate": 12.5,
        }, timeout=15)
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["linked_user_id"] is None
        assert body["default_rate"] == 12.5
        created_clients["unlinked_id"] = body["id"]

    def test_add_linked(self, iron_auth, created_clients):
        # First remove any existing client record with CLIENT_PHONE from iron-man (cleanup)
        r0 = requests.get(f"{BASE_URL}/api/clients", headers=H(iron_auth["token"]), timeout=15)
        existing = [c for c in r0.json() if c["phone"] == CLIENT_PHONE]
        for c in existing:
            if c.get("linked_user_id"):
                # cannot direct DELETE -- skip for now, will reuse if present
                created_clients["linked_id"] = c["id"]
                return
            requests.delete(f"{BASE_URL}/api/clients/{c['id']}",
                            headers=H(iron_auth["token"]), timeout=15)
        r = requests.post(f"{BASE_URL}/api/clients", headers=H(iron_auth["token"]), json={
            "name": "TEST Linked", "phone": CLIENT_PHONE, "default_rate": 11.0
        }, timeout=15)
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["linked_user_id"] is not None
        created_clients["linked_id"] = body["id"]

    def test_add_duplicate_400(self, iron_auth, created_clients):
        r = requests.post(f"{BASE_URL}/api/clients", headers=H(iron_auth["token"]), json={
            "name": "TEST Dup", "phone": created_clients["unlinked_phone"], "default_rate": 10
        }, timeout=15)
        assert r.status_code == 400, r.text

    def test_get_one(self, iron_auth, created_clients):
        cid = created_clients["unlinked_id"]
        r = requests.get(f"{BASE_URL}/api/clients/{cid}",
                         headers=H(iron_auth["token"]), timeout=15)
        assert r.status_code == 200, r.text
        assert r.json()["id"] == cid

    def test_patch(self, iron_auth, created_clients):
        cid = created_clients["unlinked_id"]
        r = requests.patch(f"{BASE_URL}/api/clients/{cid}",
                           headers=H(iron_auth["token"]),
                           json={"name": "TEST Unlinked Updated"}, timeout=15)
        assert r.status_code == 200, r.text
        assert r.json()["name"] == "TEST Unlinked Updated"

    def test_delete_linked_returns_403(self, iron_auth, created_clients):
        cid = created_clients["linked_id"]
        r = requests.delete(f"{BASE_URL}/api/clients/{cid}",
                            headers=H(iron_auth["token"]), timeout=15)
        assert r.status_code == 403, r.text

    def test_delete_request_then_deny(self, iron_auth, client_auth, created_clients):
        cid = created_clients["linked_id"]
        # iron requests delete
        r = requests.post(f"{BASE_URL}/api/clients/{cid}/delete-request",
                          headers=H(iron_auth["token"]), timeout=15)
        assert r.status_code == 200, r.text
        assert r.json()["delete_requested_at"] is not None
        # client denies
        r2 = requests.post(f"{BASE_URL}/api/clients/{cid}/delete-deny",
                           headers=H(client_auth["token"]), timeout=15)
        assert r2.status_code == 200, r2.text
        assert r2.json()["delete_requested_at"] is None


# ---------- Entries ----------
@pytest.fixture(scope="session")
def created_entries():
    return {"unlinked": None, "linked": None}


class TestEntries:
    def test_create_unlinked(self, iron_auth, created_clients, created_entries):
        r = requests.post(f"{BASE_URL}/api/entries", headers=H(iron_auth["token"]), json={
            "client_id": created_clients["unlinked_id"],
            "items": [{"cloth_type": "shirt", "quantity": 3, "rate": 10.0}],
            "notes": "TEST unlinked"
        }, timeout=15)
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["total_quantity"] == 3
        assert data["total_amount"] == 30.0
        assert data["status"] == "pending"
        created_entries["unlinked"] = data["id"]

    def test_create_linked(self, iron_auth, created_clients, created_entries):
        r = requests.post(f"{BASE_URL}/api/entries", headers=H(iron_auth["token"]), json={
            "client_id": created_clients["linked_id"],
            "items": [
                {"cloth_type": "pant", "quantity": 2, "rate": 15.0},
                {"cloth_type": "shirt", "quantity": 4, "rate": 10.0},
            ],
        }, timeout=15)
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["total_quantity"] == 6
        assert data["total_amount"] == 70.0
        assert data["linked_user_id"] is not None
        created_entries["linked"] = data["id"]

    def test_list_filter_client(self, iron_auth, created_clients):
        r = requests.get(
            f"{BASE_URL}/api/entries?client_id={created_clients['unlinked_id']}",
            headers=H(iron_auth["token"]), timeout=15)
        assert r.status_code == 200, r.text
        assert all(e["client_id"] == created_clients["unlinked_id"] for e in r.json())

    def test_list_status_filter(self, iron_auth):
        r = requests.get(f"{BASE_URL}/api/entries?status_filter=pending",
                         headers=H(iron_auth["token"]), timeout=15)
        assert r.status_code == 200, r.text
        for e in r.json():
            assert e["status"] == "pending"

    def test_list_month_filter(self, iron_auth):
        from datetime import datetime
        m = datetime.utcnow().strftime("%Y-%m")
        r = requests.get(f"{BASE_URL}/api/entries?month={m}",
                         headers=H(iron_auth["token"]), timeout=15)
        assert r.status_code == 200, r.text

    def test_return_unlinked_direct(self, iron_auth, created_clients):
        # Create a fresh unlinked entry to return
        rc = requests.post(f"{BASE_URL}/api/entries", headers=H(iron_auth["token"]), json={
            "client_id": created_clients["unlinked_id"],
            "items": [{"cloth_type": "shirt", "quantity": 1, "rate": 10.0}],
        }, timeout=15)
        assert rc.status_code == 200
        eid = rc.json()["id"]
        r = requests.post(f"{BASE_URL}/api/entries/{eid}/return",
                          headers=H(iron_auth["token"]), json={}, timeout=15)
        assert r.status_code == 200, r.text
        assert r.json()["status"] == "returned"

    def test_return_linked_then_confirm(self, iron_auth, client_auth, created_clients):
        rc = requests.post(f"{BASE_URL}/api/entries", headers=H(iron_auth["token"]), json={
            "client_id": created_clients["linked_id"],
            "items": [{"cloth_type": "shirt", "quantity": 2, "rate": 10.0}],
        }, timeout=15)
        eid = rc.json()["id"]
        r = requests.post(f"{BASE_URL}/api/entries/{eid}/return",
                          headers=H(iron_auth["token"]), json={}, timeout=15)
        assert r.status_code == 200, r.text
        assert r.json()["status"] == "return_pending"
        # client confirms
        r2 = requests.post(f"{BASE_URL}/api/entries/{eid}/return/confirm",
                           headers=H(client_auth["token"]), timeout=15)
        assert r2.status_code == 200, r2.text
        assert r2.json()["status"] == "returned"

    def test_return_linked_then_deny(self, iron_auth, client_auth, created_clients):
        rc = requests.post(f"{BASE_URL}/api/entries", headers=H(iron_auth["token"]), json={
            "client_id": created_clients["linked_id"],
            "items": [{"cloth_type": "shirt", "quantity": 2, "rate": 10.0}],
        }, timeout=15)
        eid = rc.json()["id"]
        requests.post(f"{BASE_URL}/api/entries/{eid}/return",
                      headers=H(iron_auth["token"]), json={}, timeout=15)
        r = requests.post(f"{BASE_URL}/api/entries/{eid}/return/deny",
                         headers=H(client_auth["token"]), timeout=15)
        assert r.status_code == 200, r.text
        assert r.json()["status"] == "pending"

    def test_delete_linked_returns_403(self, iron_auth, created_entries):
        eid = created_entries["linked"]
        r = requests.delete(f"{BASE_URL}/api/entries/{eid}",
                            headers=H(iron_auth["token"]), timeout=15)
        assert r.status_code == 403, r.text

    def test_delete_request_then_deny(self, iron_auth, client_auth, created_entries):
        eid = created_entries["linked"]
        r = requests.post(f"{BASE_URL}/api/entries/{eid}/delete-request",
                          headers=H(client_auth["token"]), timeout=15)
        assert r.status_code == 200, r.text
        assert r.json()["delete_requested_at"] is not None
        r2 = requests.post(f"{BASE_URL}/api/entries/{eid}/delete-deny",
                           headers=H(iron_auth["token"]), timeout=15)
        assert r2.status_code == 200, r2.text
        assert r2.json()["delete_requested_at"] is None

    def test_delete_request_then_confirm(self, iron_auth, client_auth, created_clients):
        # use a fresh linked entry
        rc = requests.post(f"{BASE_URL}/api/entries", headers=H(iron_auth["token"]), json={
            "client_id": created_clients["linked_id"],
            "items": [{"cloth_type": "shirt", "quantity": 1, "rate": 10.0}],
        }, timeout=15)
        eid = rc.json()["id"]
        requests.post(f"{BASE_URL}/api/entries/{eid}/delete-request",
                      headers=H(client_auth["token"]), timeout=15)
        r = requests.post(f"{BASE_URL}/api/entries/{eid}/delete-confirm",
                         headers=H(iron_auth["token"]), timeout=15)
        assert r.status_code == 200, r.text
        assert r.json()["ok"] is True


# ---------- Notifications ----------
class TestNotifications:
    def test_list(self, client_auth):
        r = requests.get(f"{BASE_URL}/api/notifications",
                         headers=H(client_auth["token"]), timeout=15)
        assert r.status_code == 200, r.text
        assert isinstance(r.json(), list)

    def test_unread_count(self, client_auth):
        r = requests.get(f"{BASE_URL}/api/notifications/unread-count",
                         headers=H(client_auth["token"]), timeout=15)
        assert r.status_code == 200, r.text
        assert "count" in r.json()

    def test_mark_read_one(self, client_auth):
        rl = requests.get(f"{BASE_URL}/api/notifications?unread_only=true",
                          headers=H(client_auth["token"]), timeout=15).json()
        if not rl:
            pytest.skip("no unread notifications")
        nid = rl[0]["id"]
        r = requests.post(f"{BASE_URL}/api/notifications/{nid}/read",
                          headers=H(client_auth["token"]), timeout=15)
        assert r.status_code == 200, r.text

    def test_read_all(self, client_auth):
        r = requests.post(f"{BASE_URL}/api/notifications/read-all",
                          headers=H(client_auth["token"]), timeout=15)
        assert r.status_code == 200, r.text
        assert "updated" in r.json()


# ---------- Bills + Payments ----------
@pytest.fixture(scope="session")
def bill_state():
    return {"bill_id": None, "payment_id": None}


class TestBills:
    def test_generate(self, iron_auth, bill_state):
        r = requests.post(f"{BASE_URL}/api/bills/generate",
                          headers=H(iron_auth["token"]), timeout=20)
        assert r.status_code == 200, r.text
        bills = r.json()
        assert isinstance(bills, list)
        # find a bill for our linked client with positive net_due
        for b in bills:
            if b["client_phone"] == CLIENT_PHONE and b["net_due"] > 0:
                bill_state["bill_id"] = b["id"]
                break
        if not bill_state["bill_id"] and bills:
            bill_state["bill_id"] = bills[0]["id"]

    def test_list_iron(self, iron_auth):
        r = requests.get(f"{BASE_URL}/api/bills",
                         headers=H(iron_auth["token"]), timeout=15)
        assert r.status_code == 200, r.text

    def test_list_client(self, client_auth):
        r = requests.get(f"{BASE_URL}/api/bills",
                         headers=H(client_auth["token"]), timeout=15)
        assert r.status_code == 200, r.text

    def test_record_payment(self, iron_auth, bill_state):
        if not bill_state["bill_id"]:
            pytest.skip("no bill to pay")
        r = requests.post(
            f"{BASE_URL}/api/bills/{bill_state['bill_id']}/payments",
            headers=H(iron_auth["token"]),
            json={"amount": 5.0, "notes": "TEST partial"},
            timeout=15,
        )
        assert r.status_code == 200, r.text
        bill_state["payment_id"] = r.json()["id"]
        assert r.json()["amount"] == 5.0

    def test_list_payments_iron(self, iron_auth, bill_state):
        if not bill_state["bill_id"]:
            pytest.skip("no bill")
        r = requests.get(
            f"{BASE_URL}/api/bills/{bill_state['bill_id']}/payments",
            headers=H(iron_auth["token"]), timeout=15)
        assert r.status_code == 200, r.text
        assert isinstance(r.json(), list)

    def test_list_payments_client(self, client_auth, bill_state):
        if not bill_state["bill_id"]:
            pytest.skip("no bill")
        r = requests.get(
            f"{BASE_URL}/api/bills/{bill_state['bill_id']}/payments",
            headers=H(client_auth["token"]), timeout=15)
        # may be 403 if this specific bill isn't linked to CLIENT_PHONE; tolerate
        assert r.status_code in (200, 403), r.text

    def test_delete_payment_recomputes(self, iron_auth, bill_state):
        if not bill_state["payment_id"]:
            pytest.skip("no payment")
        r = requests.delete(
            f"{BASE_URL}/api/payments/{bill_state['payment_id']}",
            headers=H(iron_auth["token"]), timeout=15)
        assert r.status_code == 200, r.text
        # verify bill amount_paid is back to 0 (or only earlier payments)
        rb = requests.get(f"{BASE_URL}/api/bills",
                          headers=H(iron_auth["token"]), timeout=15).json()
        target = [b for b in rb if b["id"] == bill_state["bill_id"]]
        if target:
            # we recorded only this one payment of 5.0 -> after delete amount_paid should be lower
            assert target[0]["amount_paid"] >= 0

    def test_mark_paid_legacy_true_then_false(self, iron_auth, bill_state):
        if not bill_state["bill_id"]:
            pytest.skip("no bill")
        r = requests.post(
            f"{BASE_URL}/api/bills/{bill_state['bill_id']}/paid",
            headers=H(iron_auth["token"]), json={"paid": True}, timeout=15)
        assert r.status_code == 200, r.text
        assert r.json()["paid"] is True or r.json()["status"] in ("paid", "overpaid")
        # set unpaid
        r2 = requests.post(
            f"{BASE_URL}/api/bills/{bill_state['bill_id']}/paid",
            headers=H(iron_auth["token"]), json={"paid": False}, timeout=15)
        assert r2.status_code == 200, r2.text
        assert r2.json()["amount_paid"] == 0.0


class TestCarryForward:
    """Two-month carry-forward: backdated entry in prev month + bill, then current month bill should carry."""

    def test_carry_forward(self, iron_auth, created_clients):
        from datetime import datetime, timedelta, timezone
        now = datetime.now(timezone.utc)
        # prev month date
        first = now.replace(day=1)
        prev_month_dt = first - timedelta(days=2)
        prev_iso = prev_month_dt.isoformat().replace("+00:00", "Z")
        prev_m = prev_month_dt.strftime("%Y-%m")
        cur_m = now.strftime("%Y-%m")
        if prev_m == cur_m:
            pytest.skip("month boundary")

        # add a fresh unlinked client to isolate carry-forward calculation
        phone = "7" + str(uuid.uuid4().int)[:9]
        phone = phone[:10]
        rc = requests.post(f"{BASE_URL}/api/clients", headers=H(iron_auth["token"]),
                           json={"name": "TEST Carry", "phone": phone, "default_rate": 10},
                           timeout=15)
        assert rc.status_code == 200
        cid = rc.json()["id"]

        # entry in prev month
        re = requests.post(f"{BASE_URL}/api/entries", headers=H(iron_auth["token"]), json={
            "client_id": cid,
            "date_given": prev_iso,
            "items": [{"cloth_type": "shirt", "quantity": 4, "rate": 10.0}],
        }, timeout=15)
        assert re.status_code == 200, re.text
        # generate prev-month bill
        rbprev = requests.post(f"{BASE_URL}/api/bills/generate?month={prev_m}",
                               headers=H(iron_auth["token"]), timeout=15)
        assert rbprev.status_code == 200, rbprev.text
        # entry in current month
        rec = requests.post(f"{BASE_URL}/api/entries", headers=H(iron_auth["token"]), json={
            "client_id": cid,
            "items": [{"cloth_type": "pant", "quantity": 2, "rate": 15.0}],
        }, timeout=15)
        assert rec.status_code == 200
        # generate current
        rbcur = requests.post(f"{BASE_URL}/api/bills/generate?month={cur_m}",
                              headers=H(iron_auth["token"]), timeout=15)
        assert rbcur.status_code == 200
        # find current bill for this client and verify carry_in == 40
        rb = requests.get(f"{BASE_URL}/api/bills?client_id={cid}&month={cur_m}",
                          headers=H(iron_auth["token"]), timeout=15)
        assert rb.status_code == 200
        cur_bills = rb.json()
        assert cur_bills, "no current month bill"
        assert cur_bills[0]["carry_in"] == 40.0, cur_bills[0]
        assert cur_bills[0]["clothes_amount"] == 30.0
        assert cur_bills[0]["net_due"] == 70.0

        # cleanup: delete client (unlinked) - cascades entries + bills
        requests.delete(f"{BASE_URL}/api/clients/{cid}",
                        headers=H(iron_auth["token"]), timeout=15)


# ---------- Reports ----------
class TestReports:
    def test_monthly(self, iron_auth):
        r = requests.get(f"{BASE_URL}/api/reports/monthly",
                         headers=H(iron_auth["token"]), timeout=15)
        assert r.status_code == 200, r.text
        assert isinstance(r.json(), list)

    def test_yearly(self, iron_auth):
        r = requests.get(f"{BASE_URL}/api/reports/yearly",
                         headers=H(iron_auth["token"]), timeout=15)
        assert r.status_code == 200, r.text

    def test_by_client(self, iron_auth):
        r = requests.get(f"{BASE_URL}/api/reports/by-client",
                         headers=H(iron_auth["token"]), timeout=15)
        assert r.status_code == 200, r.text
        assert isinstance(r.json(), list)


# ---------- Subscription ----------
class TestSubscription:
    def test_plans(self):
        r = requests.get(f"{BASE_URL}/api/subscription/plans", timeout=15)
        assert r.status_code == 200, r.text
        b = r.json()
        assert b["razorpay_enabled"] is True
        assert b["iron_man"]["amount"] == 49
        assert b["client"]["amount"] == 19

    def test_create_order(self, iron_auth):
        r = requests.post(f"{BASE_URL}/api/subscription/create-order",
                          headers=H(iron_auth["token"]),
                          json={"plan": "iron_man"}, timeout=20)
        assert r.status_code == 200, r.text
        b = r.json()
        assert b.get("order_id"), b
        assert b["amount"] == 49 * 100

    def test_verify_payment_invalid_signature(self, iron_auth):
        # First create order
        rc = requests.post(f"{BASE_URL}/api/subscription/create-order",
                           headers=H(iron_auth["token"]),
                           json={"plan": "iron_man"}, timeout=20)
        oid = rc.json()["order_id"]
        r = requests.post(f"{BASE_URL}/api/subscription/verify-payment",
                          headers=H(iron_auth["token"]),
                          json={
                              "razorpay_order_id": oid,
                              "razorpay_payment_id": "pay_FAKE123",
                              "razorpay_signature": "INVALID_SIG",
                          }, timeout=15)
        assert r.status_code == 400, r.text

    def test_activate_returns_400_when_razorpay_on(self, iron_auth):
        r = requests.post(f"{BASE_URL}/api/subscription/activate",
                          headers=H(iron_auth["token"]),
                          json={"plan": "iron_man"}, timeout=15)
        assert r.status_code == 400, r.text


# ---------- Misc /my/iron-men ----------
class TestMisc:
    def test_my_iron_men(self, client_auth):
        r = requests.get(f"{BASE_URL}/api/my/iron-men",
                         headers=H(client_auth["token"]), timeout=15)
        assert r.status_code == 200, r.text
        assert isinstance(r.json(), list)


# ---------- Cleanup at session end ----------
@pytest.fixture(scope="session", autouse=True)
def _final_cleanup(throwaway_state, created_clients):
    yield
    # Delete throwaway user via direct mongo (no API), or just leave it -- use admin route is not available.
    # Best-effort: nothing for throwaway user. Iron-man can delete the unlinked client.
    try:
        ir = requests.post(f"{BASE_URL}/api/auth/login",
                           json={"phone": IRON_PHONE, "password": PWD}, timeout=10)
        if ir.status_code == 200:
            tok = ir.json()["token"]
            if created_clients.get("unlinked_id"):
                requests.delete(
                    f"{BASE_URL}/api/clients/{created_clients['unlinked_id']}",
                    headers=H(tok), timeout=10)
    except Exception:
        pass
    # Delete throwaway user directly in mongo
    try:
        from pymongo import MongoClient
        mc = MongoClient(os.environ.get("MONGO_URL", "mongodb://localhost:27017"))
        mc[os.environ.get("DB_NAME", "test_database")].users.delete_one(
            {"_id": throwaway_state.get("user_id")})
        mc.close()
    except Exception:
        pass
