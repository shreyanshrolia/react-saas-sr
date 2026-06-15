"""Iteration 4: Razorpay subscription integration tests.

Tests for:
- GET /api/subscription/plans
- POST /api/subscription/create-order
- POST /api/subscription/verify-payment (valid, invalid, idempotency, cross-user)
- Legacy /subscription/activate (must be disabled when Razorpay enabled)
- Auth requirements (401 without token)
"""
import os
import hmac
import hashlib
import time
from datetime import datetime, timezone, timedelta

import pytest
import requests
from pymongo import MongoClient

BASE_URL = "https://grihkari-laundry.preview.emergentagent.com"
RAZORPAY_KEY_ID = "rzp_test_T1rAXlvsSt3miO"
RAZORPAY_KEY_SECRET = "7krUcsTLvHw5m2rt2R8JtwAo"


# ---------- Helpers ----------
def _sign(order_id: str, payment_id: str) -> str:
    body = f"{order_id}|{payment_id}".encode()
    return hmac.new(RAZORPAY_KEY_SECRET.encode(), body, hashlib.sha256).hexdigest()


@pytest.fixture(scope="module")
def mongo_db():
    mongo_url = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
    db_name = os.environ.get("DB_NAME", "test_database")
    cli = MongoClient(mongo_url)
    yield cli[db_name]
    cli.close()


def _reset_user_sub(db, user_id: str):
    """Reset subscription to trial so we can re-test activation."""
    trial_end = (datetime.now(timezone.utc) + timedelta(days=45)).isoformat()
    db.users.update_one(
        {"_id": user_id},
        {"$set": {"subscription_status": "trial", "subscription_ends_at": trial_end}},
    )


# ============================================================
# Plans endpoint
# ============================================================
class TestSubscriptionPlans:
    def test_plans_public_no_auth_required(self, api_client):
        r = api_client.get(f"{BASE_URL}/api/subscription/plans", timeout=20)
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["razorpay_enabled"] is True
        assert data["razorpay_key_id"] == RAZORPAY_KEY_ID
        assert data["iron_man"]["amount"] == 49
        assert data["iron_man"]["currency"] == "INR"
        assert data["client"]["amount"] == 19
        assert data["client"]["currency"] == "INR"
        assert data["trial_days"] == 45


# ============================================================
# Auth required
# ============================================================
class TestAuthRequired:
    def test_create_order_requires_auth(self, api_client):
        r = api_client.post(f"{BASE_URL}/api/subscription/create-order",
                            json={"plan": "iron_man"}, timeout=20)
        assert r.status_code == 401, r.text

    def test_verify_payment_requires_auth(self, api_client):
        r = api_client.post(f"{BASE_URL}/api/subscription/verify-payment",
                            json={"razorpay_order_id": "order_x",
                                  "razorpay_payment_id": "pay_x",
                                  "razorpay_signature": "x"}, timeout=20)
        assert r.status_code == 401, r.text

    def test_activate_requires_auth(self, api_client):
        r = api_client.post(f"{BASE_URL}/api/subscription/activate",
                            json={"plan": "iron_man"}, timeout=20)
        assert r.status_code == 401, r.text


# ============================================================
# Create order
# ============================================================
class TestCreateOrder:
    def test_iron_man_create_order_success(self, api_client, iron_headers):
        r = api_client.post(f"{BASE_URL}/api/subscription/create-order",
                            json={"plan": "iron_man"}, headers=iron_headers, timeout=30)
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["order_id"].startswith("order_"), d
        assert d["amount"] == 4900
        assert d["amount_inr"] == 49
        assert d["currency"] == "INR"
        assert d["key_id"] == RAZORPAY_KEY_ID
        assert d["name"] == "Grihkari"
        assert "Iron Man" in d["description"]
        assert d["prefill"]["name"] == "Test Iron"
        assert d["prefill"]["contact"] == "9999999991"
        assert "theme_color" in d

    def test_client_create_order_success(self, api_client, client_headers):
        r = api_client.post(f"{BASE_URL}/api/subscription/create-order",
                            json={"plan": "client"}, headers=client_headers, timeout=30)
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["order_id"].startswith("order_")
        assert d["amount"] == 1900
        assert d["amount_inr"] == 19
        assert d["key_id"] == RAZORPAY_KEY_ID
        assert "Client" in d["description"]
        assert d["prefill"]["contact"] == "9999999992"

    def test_create_order_role_mismatch(self, api_client, iron_headers):
        # iron_man tries client plan
        r = api_client.post(f"{BASE_URL}/api/subscription/create-order",
                            json={"plan": "client"}, headers=iron_headers, timeout=20)
        assert r.status_code == 400, r.text
        assert "match" in r.json()["detail"].lower()

    def test_create_order_role_mismatch_client(self, api_client, client_headers):
        r = api_client.post(f"{BASE_URL}/api/subscription/create-order",
                            json={"plan": "iron_man"}, headers=client_headers, timeout=20)
        assert r.status_code == 400, r.text


# ============================================================
# Verify payment
# ============================================================
class TestVerifyPayment:
    def _create_order(self, api_client, headers, plan):
        r = api_client.post(f"{BASE_URL}/api/subscription/create-order",
                            json={"plan": plan}, headers=headers, timeout=30)
        assert r.status_code == 200, r.text
        return r.json()["order_id"]

    def test_verify_invalid_signature(self, api_client, iron_headers, mongo_db, iron_auth):
        _reset_user_sub(mongo_db, iron_auth["user"]["id"])
        order_id = self._create_order(api_client, iron_headers, "iron_man")
        r = api_client.post(f"{BASE_URL}/api/subscription/verify-payment",
                            json={
                                "razorpay_order_id": order_id,
                                "razorpay_payment_id": "pay_test_bad",
                                "razorpay_signature": "0" * 64,
                            }, headers=iron_headers, timeout=20)
        assert r.status_code == 400, r.text
        assert "signature" in r.json()["detail"].lower()
        # Order audit status should be signature_failed
        order_doc = mongo_db.subscription_orders.find_one({"_id": order_id})
        assert order_doc is not None
        assert order_doc["status"] == "signature_failed"
        # Subscription should still be trial (not active)
        u = mongo_db.users.find_one({"_id": iron_auth["user"]["id"]})
        assert u["subscription_status"] == "trial"

    def test_verify_valid_signature_activates(self, api_client, iron_headers, mongo_db, iron_auth):
        _reset_user_sub(mongo_db, iron_auth["user"]["id"])
        order_id = self._create_order(api_client, iron_headers, "iron_man")
        payment_id = f"pay_test_{int(time.time())}"
        sig = _sign(order_id, payment_id)
        r = api_client.post(f"{BASE_URL}/api/subscription/verify-payment",
                            json={
                                "razorpay_order_id": order_id,
                                "razorpay_payment_id": payment_id,
                                "razorpay_signature": sig,
                            }, headers=iron_headers, timeout=20)
        assert r.status_code == 200, r.text
        user = r.json()
        assert user["subscription_status"] == "active"
        assert user["subscription_ends_at"]
        ends = datetime.fromisoformat(user["subscription_ends_at"].replace("Z", "+00:00"))
        delta_days = (ends - datetime.now(timezone.utc)).days
        # Iteration-5 trial-stacking: paying mid-trial extends from trial_end (~45d) + 30d ≈ 75d
        # _reset_user_sub sets trial_end = now + 45d, so total should be ~74-75 days.
        assert 72 <= delta_days <= 76, f"expected ~75 days (trial+30), got {delta_days}"
        # Audit: order is paid
        order_doc = mongo_db.subscription_orders.find_one({"_id": order_id})
        assert order_doc["status"] == "paid"
        assert order_doc.get("razorpay_payment_id") == payment_id

    def test_verify_idempotency(self, api_client, iron_headers, mongo_db, iron_auth):
        """Calling verify-payment twice with the same valid signature should not double-extend."""
        _reset_user_sub(mongo_db, iron_auth["user"]["id"])
        order_id = self._create_order(api_client, iron_headers, "iron_man")
        payment_id = f"pay_idem_{int(time.time())}"
        sig = _sign(order_id, payment_id)
        body = {
            "razorpay_order_id": order_id,
            "razorpay_payment_id": payment_id,
            "razorpay_signature": sig,
        }
        r1 = api_client.post(f"{BASE_URL}/api/subscription/verify-payment",
                             json=body, headers=iron_headers, timeout=20)
        assert r1.status_code == 200, r1.text
        ends_1 = r1.json()["subscription_ends_at"]

        # Second call
        r2 = api_client.post(f"{BASE_URL}/api/subscription/verify-payment",
                             json=body, headers=iron_headers, timeout=20)
        assert r2.status_code == 200, r2.text
        ends_2 = r2.json()["subscription_ends_at"]
        # End date should NOT advance on idempotent retry
        assert ends_1 == ends_2, f"end date advanced from {ends_1} -> {ends_2}"
        # Status remains paid
        order_doc = mongo_db.subscription_orders.find_one({"_id": order_id})
        assert order_doc["status"] == "paid"

    def test_verify_signature_failed_does_not_overwrite_paid(self, api_client, iron_headers, mongo_db, iron_auth):
        """If order is already paid, a later invalid-signature attempt must NOT downgrade audit status."""
        _reset_user_sub(mongo_db, iron_auth["user"]["id"])
        order_id = self._create_order(api_client, iron_headers, "iron_man")
        payment_id = f"pay_paidfirst_{int(time.time())}"
        sig = _sign(order_id, payment_id)
        # First: legitimate payment
        r1 = api_client.post(f"{BASE_URL}/api/subscription/verify-payment",
                             json={"razorpay_order_id": order_id,
                                   "razorpay_payment_id": payment_id,
                                   "razorpay_signature": sig},
                             headers=iron_headers, timeout=20)
        assert r1.status_code == 200
        # Now an invalid-signature attempt on same order_id
        r2 = api_client.post(f"{BASE_URL}/api/subscription/verify-payment",
                             json={"razorpay_order_id": order_id,
                                   "razorpay_payment_id": payment_id,
                                   "razorpay_signature": "0" * 64},
                             headers=iron_headers, timeout=20)
        assert r2.status_code == 400
        # Audit must still be 'paid'
        order_doc = mongo_db.subscription_orders.find_one({"_id": order_id})
        assert order_doc["status"] == "paid", f"got {order_doc['status']}"

    def test_verify_cross_user_attack(self, api_client, iron_headers, client_headers, mongo_db, iron_auth):
        """User A creates order; User B tries to verify with correct signature -> 403."""
        _reset_user_sub(mongo_db, iron_auth["user"]["id"])
        order_id = self._create_order(api_client, iron_headers, "iron_man")
        payment_id = f"pay_xuser_{int(time.time())}"
        sig = _sign(order_id, payment_id)
        # User B (client) uses iron_man's order
        r = api_client.post(f"{BASE_URL}/api/subscription/verify-payment",
                            json={"razorpay_order_id": order_id,
                                  "razorpay_payment_id": payment_id,
                                  "razorpay_signature": sig},
                            headers=client_headers, timeout=20)
        assert r.status_code == 403, r.text
        assert "does not belong" in r.json()["detail"].lower()


# ============================================================
# Legacy activate endpoint must be disabled
# ============================================================
class TestLegacyActivateDisabled:
    def test_activate_returns_400_when_razorpay_enabled(self, api_client, iron_headers):
        r = api_client.post(f"{BASE_URL}/api/subscription/activate",
                            json={"plan": "iron_man"}, headers=iron_headers, timeout=20)
        assert r.status_code == 400, r.text
        msg = r.json()["detail"].lower()
        assert "create-order" in msg and "verify-payment" in msg
