"""Iteration 3 tests:
- TRIAL_DAYS = 45 for signup
- GET /api/subscription/plans returns trial_days=45
- Bill carry-forward (partial / overpaid)
- POST /api/bills/{id}/payments (single + multiple)
- GET /api/bills/{id}/payments (iron_man + linked client)
- DELETE /api/payments/{id}
- Legacy POST /api/bills/{id}/paid still works
- Auth: only iron_man can create/delete payments
"""
import time
import os
import pytest
import requests
from datetime import datetime, timezone, timedelta
from pymongo import MongoClient

from conftest import BASE_URL

# ---------------- helpers ----------------
MONGO_URL = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
DB_NAME = os.environ.get("DB_NAME", "test_database")
_mongo = MongoClient(MONGO_URL)[DB_NAME]


def _auth_headers(token):
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


def _new_phone():
    return f"8{str(int(time.time() * 1000))[-9:]}"


def _delete_user_by_phone(phone):
    """Direct DB cleanup — used only for the explicit trial-test phones."""
    try:
        _mongo.users.delete_many({"phone": phone})
        # cascade lightweight cleanup so re-signup is safe
        _mongo.clients.delete_many({"phone": phone, "iron_man_id": {"$exists": True, "$ne": None}})
    except Exception:
        pass


def _signup(phone, name, role, password="test123"):
    return requests.post(
        f"{BASE_URL}/api/auth/signup",
        json={"name": name, "phone": phone, "password": password, "role": role},
        timeout=15,
    )


def _cleanup_client(iron_headers, cid):
    try:
        requests.delete(f"{BASE_URL}/api/clients/{cid}", headers=iron_headers, timeout=15)
    except Exception:
        pass


def _make_client(iron_headers, name="TEST_BillClient"):
    phone = _new_phone()
    r = requests.post(
        f"{BASE_URL}/api/clients",
        headers=iron_headers,
        json={"name": name, "phone": phone, "default_rate": 10},
        timeout=15,
    )
    assert r.status_code == 200, r.text
    return r.json()


def _add_entry(iron_headers, cid, amount, date_iso, items_qty=None):
    """Create an entry summing to `amount` rupees on the given date.
    Uses a single item: rate=`amount`, qty=1 (works for any amount)."""
    qty = items_qty if items_qty is not None else 1
    rate = amount / qty
    r = requests.post(
        f"{BASE_URL}/api/entries",
        headers=iron_headers,
        json={
            "client_id": cid,
            "date_given": date_iso,
            "items": [{"cloth_type": "shirt", "quantity": qty, "rate": rate}],
        },
        timeout=15,
    )
    assert r.status_code == 200, r.text
    return r.json()


def _generate_month_bill(iron_headers, month, cid):
    r = requests.post(
        f"{BASE_URL}/api/bills/generate?month={month}",
        headers=iron_headers,
        timeout=20,
    )
    assert r.status_code == 200, r.text
    bills = r.json()
    match = [b for b in bills if b["client_id"] == cid]
    assert match, f"No bill for client {cid} in {month}; got {bills}"
    return match[0]


# ---------------- Trial 45 days ----------------
class TestTrial45Days:
    def test_signup_trial_is_45_days_iron_man(self):
        phone = "9888777111"
        _delete_user_by_phone(phone)
        r = _signup(phone, "TEST_TrialIron", "iron_man")
        assert r.status_code == 200, r.text
        data = r.json()
        trial_ends_at = data["user"]["trial_ends_at"]
        dt = datetime.fromisoformat(trial_ends_at.replace("Z", "+00:00"))
        delta_days = (dt - datetime.now(timezone.utc)).total_seconds() / 86400.0
        assert 44 <= delta_days <= 46, (
            f"trial_ends_at delta is {delta_days} days, expected ~45")
        assert data["user"]["subscription_status"] == "trial"
        _delete_user_by_phone(phone)

    def test_signup_trial_is_45_days_client(self):
        phone = "9888777112"
        _delete_user_by_phone(phone)
        r = _signup(phone, "TEST_TrialClient", "client")
        assert r.status_code == 200, r.text
        data = r.json()
        trial_ends_at = data["user"]["trial_ends_at"]
        dt = datetime.fromisoformat(trial_ends_at.replace("Z", "+00:00"))
        delta_days = (dt - datetime.now(timezone.utc)).total_seconds() / 86400.0
        assert 44 <= delta_days <= 46, (
            f"trial_ends_at delta is {delta_days} days, expected ~45")
        _delete_user_by_phone(phone)

    def test_subscription_plans_trial_days_45(self, iron_auth, iron_headers):
        r = requests.get(
            f"{BASE_URL}/api/subscription/plans", headers=iron_headers, timeout=10)
        assert r.status_code == 200, r.text
        data = r.json()
        assert data.get("trial_days") == 45, (
            f"Expected trial_days=45, got {data.get('trial_days')}")


# ---------------- Bill carry-forward (partial) ----------------
class TestCarryForwardPartial:
    def test_partial_payment_carries_to_next_month(self, iron_auth, iron_headers):
        c = _make_client(iron_headers, "TEST_CarryPartial")
        cid = c["id"]
        try:
            # Dec 2025 entries totaling 100
            e1 = _add_entry(iron_headers, cid, 60.0, "2025-12-05T00:00:00Z")
            e2 = _add_entry(iron_headers, cid, 40.0, "2025-12-20T00:00:00Z")

            # Generate Dec bill
            dec_bill = _generate_month_bill(iron_headers, "2025-12", cid)
            assert dec_bill["clothes_amount"] == 100.0
            assert dec_bill["carry_in"] == 0.0
            assert dec_bill["net_due"] == 100.0
            assert dec_bill["amount_paid"] == 0.0
            assert dec_bill["balance"] == 100.0
            assert dec_bill["status"] == "unpaid"
            dec_bill_id = dec_bill["id"]

            # Pay 60 partial
            r = requests.post(
                f"{BASE_URL}/api/bills/{dec_bill_id}/payments",
                headers=iron_headers, json={"amount": 60}, timeout=15)
            assert r.status_code == 200, r.text
            p = r.json()
            assert p["amount"] == 60.0
            assert p["bill_id"] == dec_bill_id

            # Re-fetch bill (use list endpoint filtered by month + client)
            r = requests.get(
                f"{BASE_URL}/api/bills?month=2025-12&client_id={cid}",
                headers=iron_headers, timeout=15)
            assert r.status_code == 200
            dec_b = [b for b in r.json() if b["id"] == dec_bill_id][0]
            assert dec_b["net_due"] == 100.0
            assert dec_b["amount_paid"] == 60.0
            assert dec_b["balance"] == 40.0
            assert dec_b["status"] == "partial"

            # Jan 2026 entries totaling 50
            _add_entry(iron_headers, cid, 50.0, "2026-01-10T00:00:00Z")
            jan_bill = _generate_month_bill(iron_headers, "2026-01", cid)
            assert jan_bill["clothes_amount"] == 50.0
            assert jan_bill["carry_in"] == 40.0, (
                f"Expected carry_in=40 from Dec balance, got {jan_bill['carry_in']}")
            assert jan_bill["net_due"] == 90.0
            assert jan_bill["amount_paid"] == 0.0
            assert jan_bill["balance"] == 90.0
            assert jan_bill["status"] == "unpaid"

            # cleanup entries / bills via client delete cascade if possible;
            # but we'll just delete entries + bills via DELETE entries
            for eid in (e1["id"], e2["id"]):
                requests.delete(f"{BASE_URL}/api/entries/{eid}",
                                headers=iron_headers, timeout=10)
        finally:
            # Best-effort cleanup
            _cleanup_client(iron_headers, cid)


# ---------------- Overpaid carry-forward ----------------
class TestCarryForwardOverpaid:
    def test_overpayment_credits_next_month(self, iron_auth, iron_headers):
        c = _make_client(iron_headers, "TEST_CarryOver")
        cid = c["id"]
        try:
            _add_entry(iron_headers, cid, 100.0, "2025-10-05T00:00:00Z")
            oct_bill = _generate_month_bill(iron_headers, "2025-10", cid)
            assert oct_bill["net_due"] == 100.0

            # Pay 150 (overpay)
            r = requests.post(
                f"{BASE_URL}/api/bills/{oct_bill['id']}/payments",
                headers=iron_headers, json={"amount": 150}, timeout=15)
            assert r.status_code == 200, r.text

            r = requests.get(
                f"{BASE_URL}/api/bills?month=2025-10&client_id={cid}",
                headers=iron_headers, timeout=15)
            ob = [b for b in r.json() if b["id"] == oct_bill["id"]][0]
            assert ob["amount_paid"] == 150.0
            assert ob["balance"] == -50.0
            assert ob["status"] == "overpaid"

            # Nov entry of 30
            _add_entry(iron_headers, cid, 30.0, "2025-11-10T00:00:00Z")
            nov_bill = _generate_month_bill(iron_headers, "2025-11", cid)
            assert nov_bill["clothes_amount"] == 30.0
            assert nov_bill["carry_in"] == -50.0, (
                f"Expected carry_in=-50, got {nov_bill['carry_in']}")
            assert nov_bill["net_due"] == -20.0
            assert nov_bill["balance"] == -20.0
        finally:
            _cleanup_client(iron_headers, cid)


# ---------------- Multiple payments ----------------
class TestMultiplePayments:
    def test_two_partial_payments_settle_bill(self, iron_auth, iron_headers):
        c = _make_client(iron_headers, "TEST_MultiPay")
        cid = c["id"]
        try:
            _add_entry(iron_headers, cid, 50.0, "2025-09-05T00:00:00Z")
            sep_bill = _generate_month_bill(iron_headers, "2025-09", cid)
            bid = sep_bill["id"]
            assert sep_bill["net_due"] == 50.0

            # First 30
            r1 = requests.post(f"{BASE_URL}/api/bills/{bid}/payments",
                               headers=iron_headers, json={"amount": 30},
                               timeout=15)
            assert r1.status_code == 200
            time.sleep(0.05)  # ensure paid_at ordering differs
            # Then 20
            r2 = requests.post(f"{BASE_URL}/api/bills/{bid}/payments",
                               headers=iron_headers, json={"amount": 20},
                               timeout=15)
            assert r2.status_code == 200

            # Bill should now be paid in full
            r = requests.get(
                f"{BASE_URL}/api/bills?month=2025-09&client_id={cid}",
                headers=iron_headers, timeout=15)
            b = [x for x in r.json() if x["id"] == bid][0]
            assert b["amount_paid"] == 50.0
            assert b["balance"] == 0.0
            assert b["status"] == "paid"
            assert b["paid"] is True

            # GET payments
            r = requests.get(f"{BASE_URL}/api/bills/{bid}/payments",
                             headers=iron_headers, timeout=15)
            assert r.status_code == 200
            payments = r.json()
            assert len(payments) == 2
            # sorted by paid_at desc
            assert payments[0]["paid_at"] >= payments[1]["paid_at"]
            amounts = sorted([p["amount"] for p in payments])
            assert amounts == [20.0, 30.0]
        finally:
            _cleanup_client(iron_headers, cid)


# ---------------- Delete payment ----------------
class TestDeletePayment:
    def test_delete_payment_recomputes_bill(self, iron_auth, iron_headers):
        c = _make_client(iron_headers, "TEST_DelPay")
        cid = c["id"]
        try:
            _add_entry(iron_headers, cid, 80.0, "2025-08-05T00:00:00Z")
            aug_bill = _generate_month_bill(iron_headers, "2025-08", cid)
            bid = aug_bill["id"]

            r1 = requests.post(f"{BASE_URL}/api/bills/{bid}/payments",
                               headers=iron_headers, json={"amount": 30},
                               timeout=15)
            assert r1.status_code == 200
            p1_id = r1.json()["id"]

            time.sleep(0.05)
            r2 = requests.post(f"{BASE_URL}/api/bills/{bid}/payments",
                               headers=iron_headers, json={"amount": 20},
                               timeout=15)
            assert r2.status_code == 200

            # Current state: paid=50, balance=30
            r = requests.get(
                f"{BASE_URL}/api/bills?month=2025-08&client_id={cid}",
                headers=iron_headers, timeout=15)
            b_before = [x for x in r.json() if x["id"] == bid][0]
            assert b_before["amount_paid"] == 50.0

            # Delete first payment (30)
            rd = requests.delete(f"{BASE_URL}/api/payments/{p1_id}",
                                 headers=iron_headers, timeout=15)
            assert rd.status_code == 200, rd.text

            # Bill should now show only 20 paid
            r = requests.get(
                f"{BASE_URL}/api/bills?month=2025-08&client_id={cid}",
                headers=iron_headers, timeout=15)
            b_after = [x for x in r.json() if x["id"] == bid][0]
            assert b_after["amount_paid"] == 20.0
            assert b_after["balance"] == 60.0
            assert b_after["status"] == "partial"
        finally:
            _cleanup_client(iron_headers, cid)


# ---------------- Legacy mark_paid endpoint ----------------
class TestLegacyMarkPaid:
    def test_mark_paid_true_then_false(self, iron_auth, iron_headers):
        c = _make_client(iron_headers, "TEST_Legacy")
        cid = c["id"]
        try:
            _add_entry(iron_headers, cid, 70.0, "2025-07-05T00:00:00Z")
            jul_bill = _generate_month_bill(iron_headers, "2025-07", cid)
            bid = jul_bill["id"]

            # paid=true -> synthetic payment for full balance
            r = requests.post(f"{BASE_URL}/api/bills/{bid}/paid",
                              headers=iron_headers, json={"paid": True},
                              timeout=15)
            assert r.status_code == 200, r.text
            b = r.json()
            assert b["status"] == "paid"
            assert b["amount_paid"] == 70.0
            assert b["balance"] == 0.0

            # payments listing should have 1
            r = requests.get(f"{BASE_URL}/api/bills/{bid}/payments",
                             headers=iron_headers, timeout=15)
            assert r.status_code == 200
            assert len(r.json()) == 1

            # paid=false -> deletes all payments
            r = requests.post(f"{BASE_URL}/api/bills/{bid}/paid",
                              headers=iron_headers, json={"paid": False},
                              timeout=15)
            assert r.status_code == 200, r.text
            b = r.json()
            assert b["status"] == "unpaid"
            assert b["amount_paid"] == 0.0
            assert b["balance"] == 70.0
            assert b["paid"] is False

            r = requests.get(f"{BASE_URL}/api/bills/{bid}/payments",
                             headers=iron_headers, timeout=15)
            assert r.status_code == 200
            assert len(r.json()) == 0
        finally:
            _cleanup_client(iron_headers, cid)


# ---------------- Client visibility & auth ----------------
class TestClientVisibilityAndAuth:
    def _setup_linked_bill(self, iron_headers, client_user_id):
        """Create a client tied to the seed client user and a bill for them."""
        client_phone = "9999999992"
        # Try to (re)create the client record under iron_man
        r = requests.post(
            f"{BASE_URL}/api/clients", headers=iron_headers,
            json={"name": "TEST_LinkedBilling", "phone": client_phone,
                  "default_rate": 10}, timeout=15)
        if r.status_code == 400:
            rr = requests.get(f"{BASE_URL}/api/clients",
                              headers=iron_headers, timeout=15)
            match = [c for c in rr.json() if c["phone"] == client_phone]
            assert match
            client_rec = match[0]
        else:
            assert r.status_code == 200, r.text
            client_rec = r.json()
        cid = client_rec["id"]
        assert client_rec["linked_user_id"] == client_user_id

        _add_entry(iron_headers, cid, 100.0, "2025-06-05T00:00:00Z")
        bill = _generate_month_bill(iron_headers, "2025-06", cid)
        return cid, bill

    def test_linked_client_can_read_bill_and_payments(
            self, iron_auth, iron_headers, client_auth, client_headers):
        cid, bill = self._setup_linked_bill(
            iron_headers, client_auth["user"]["id"])
        bid = bill["id"]
        # Iron man records a payment
        r = requests.post(f"{BASE_URL}/api/bills/{bid}/payments",
                          headers=iron_headers, json={"amount": 40},
                          timeout=15)
        assert r.status_code == 200

        # Client GET /api/bills should include this bill with all new fields
        r = requests.get(f"{BASE_URL}/api/bills?month=2025-06",
                         headers=client_headers, timeout=15)
        assert r.status_code == 200
        match = [b for b in r.json() if b["id"] == bid]
        assert match, "Linked client cannot see their own bill"
        cb = match[0]
        for field in ("carry_in", "clothes_amount", "amount_paid",
                      "balance", "status", "net_due"):
            assert field in cb, f"Missing field {field} in client bill view"
        assert cb["amount_paid"] == 40.0
        assert cb["balance"] == 60.0
        assert cb["status"] == "partial"

        # Client GET /api/bills/{id}/payments should work
        r = requests.get(f"{BASE_URL}/api/bills/{bid}/payments",
                         headers=client_headers, timeout=15)
        assert r.status_code == 200, r.text
        assert len(r.json()) == 1
        assert r.json()[0]["amount"] == 40.0

    def test_client_cannot_create_payment(
            self, iron_auth, iron_headers, client_auth, client_headers):
        cid, bill = self._setup_linked_bill(
            iron_headers, client_auth["user"]["id"])
        bid = bill["id"]
        r = requests.post(f"{BASE_URL}/api/bills/{bid}/payments",
                          headers=client_headers, json={"amount": 10},
                          timeout=15)
        assert r.status_code == 403, (
            f"Client should be forbidden, got {r.status_code}: {r.text}")

    def test_client_cannot_delete_payment(
            self, iron_auth, iron_headers, client_auth, client_headers):
        cid, bill = self._setup_linked_bill(
            iron_headers, client_auth["user"]["id"])
        bid = bill["id"]
        r = requests.post(f"{BASE_URL}/api/bills/{bid}/payments",
                          headers=iron_headers, json={"amount": 5},
                          timeout=15)
        assert r.status_code == 200
        pid = r.json()["id"]
        r = requests.delete(f"{BASE_URL}/api/payments/{pid}",
                            headers=client_headers, timeout=15)
        assert r.status_code == 403, (
            f"Client should be forbidden, got {r.status_code}: {r.text}")
        # Cleanup so subsequent tests don't see lingering payment
        requests.delete(f"{BASE_URL}/api/payments/{pid}",
                        headers=iron_headers, timeout=15)
