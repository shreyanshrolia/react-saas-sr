"""Clients, Entries, Bills, Reports, Subscriptions, Client-side endpoints."""
import requests
import uuid
from datetime import datetime, timezone

BASE = "https://grihkari-laundry.preview.emergentagent.com"


def _rand_phone():
    return "7" + str(uuid.uuid4().int)[:9]


# ---------- Clients (Iron Man) ----------
class TestClients:
    def test_client_role_cannot_list_clients_403(self, api_client, client_headers):
        r = api_client.get(f"{BASE}/api/clients", headers=client_headers)
        assert r.status_code == 403

    def test_iron_can_list_clients(self, api_client, iron_headers):
        r = api_client.get(f"{BASE}/api/clients", headers=iron_headers)
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    def test_add_client_links_to_existing_client_user(self, api_client, iron_headers, client_auth):
        # client_auth user exists with phone 9999999992 already
        phone = client_auth["user"]["phone"]
        # First, try delete any existing for this iron
        existing = api_client.get(f"{BASE}/api/clients", headers=iron_headers).json()
        for c in existing:
            if c["phone"] == phone:
                api_client.delete(f"{BASE}/api/clients/{c['id']}", headers=iron_headers)

        r = api_client.post(f"{BASE}/api/clients", headers=iron_headers, json={
            "name": "TEST_LinkedClient", "phone": phone, "default_rate": 15.0
        })
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["linked_user_id"] == client_auth["user"]["id"]
        assert body["default_rate"] == 15.0
        assert body["pending_count"] == 0

    def test_add_client_duplicate_400(self, api_client, iron_headers):
        phone = _rand_phone()
        r1 = api_client.post(f"{BASE}/api/clients", headers=iron_headers,
                             json={"name": "TEST_Dup", "phone": phone})
        assert r1.status_code == 200
        cid = r1.json()["id"]
        r2 = api_client.post(f"{BASE}/api/clients", headers=iron_headers,
                             json={"name": "TEST_Dup2", "phone": phone})
        assert r2.status_code == 400
        api_client.delete(f"{BASE}/api/clients/{cid}", headers=iron_headers)


# ---------- Full flow: client -> entries -> bills -> reports ----------
class TestEntriesBillsReports:
    def _setup(self, api_client, iron_headers):
        phone = _rand_phone()
        r = api_client.post(f"{BASE}/api/clients", headers=iron_headers, json={
            "name": "TEST_FlowClient", "phone": phone, "default_rate": 10.0
        })
        assert r.status_code == 200, r.text
        return r.json()

    def test_create_entry_totals_and_status_pending(self, api_client, iron_headers):
        c = self._setup(api_client, iron_headers)
        try:
            payload = {
                "client_id": c["id"],
                "items": [
                    {"cloth_type": "shirt", "quantity": 3, "rate": 10},
                    {"cloth_type": "pant", "quantity": 2, "rate": 15},
                ],
                "notes": "TEST_entry"
            }
            r = api_client.post(f"{BASE}/api/entries", headers=iron_headers, json=payload)
            assert r.status_code == 200, r.text
            e = r.json()
            assert e["total_quantity"] == 5
            assert e["total_amount"] == 60.0
            assert e["status"] == "pending"
            assert e["client_id"] == c["id"]
            assert e["client_name"] == "TEST_FlowClient"

            # GET to verify persistence
            lst = api_client.get(f"{BASE}/api/entries?client_id={c['id']}",
                                 headers=iron_headers)
            assert lst.status_code == 200
            assert any(x["id"] == e["id"] for x in lst.json())
        finally:
            api_client.delete(f"{BASE}/api/clients/{c['id']}", headers=iron_headers)

    def test_mark_returned_sets_date_and_status(self, api_client, iron_headers):
        c = self._setup(api_client, iron_headers)
        try:
            r = api_client.post(f"{BASE}/api/entries", headers=iron_headers, json={
                "client_id": c["id"],
                "items": [{"cloth_type": "saree", "quantity": 1, "rate": 30}]
            })
            eid = r.json()["id"]
            r2 = api_client.post(f"{BASE}/api/entries/{eid}/return",
                                 headers=iron_headers, json={})
            assert r2.status_code == 200
            e2 = r2.json()
            assert e2["status"] == "returned"
            assert e2["date_returned"] is not None
        finally:
            api_client.delete(f"{BASE}/api/clients/{c['id']}", headers=iron_headers)

    def test_bills_generate_aggregation_and_paid(self, api_client, iron_headers):
        c = self._setup(api_client, iron_headers)
        try:
            # 2 entries this month
            api_client.post(f"{BASE}/api/entries", headers=iron_headers, json={
                "client_id": c["id"],
                "items": [{"cloth_type": "shirt", "quantity": 4, "rate": 10}],
            })
            api_client.post(f"{BASE}/api/entries", headers=iron_headers, json={
                "client_id": c["id"],
                "items": [{"cloth_type": "pant", "quantity": 2, "rate": 20}],
            })
            # 4*10 + 2*20 = 80, qty=6
            rg = api_client.post(f"{BASE}/api/bills/generate", headers=iron_headers)
            assert rg.status_code == 200
            bills = rg.json()
            target = [b for b in bills if b["client_id"] == c["id"]]
            assert target, f"No bill for client {c['id']} in {bills}"
            bill = target[0]
            assert bill["total_quantity"] == 6
            assert bill["total_amount"] == 80.0
            assert bill["paid"] is False
            month = bill["month"]

            # mark paid
            rp = api_client.post(f"{BASE}/api/bills/{bill['id']}/paid",
                                 headers=iron_headers, json={"paid": True})
            assert rp.status_code == 200
            assert rp.json()["paid"] is True
            assert rp.json()["paid_at"] is not None

            # GET /api/bills verify
            rl = api_client.get(f"{BASE}/api/bills?client_id={c['id']}&month={month}",
                                headers=iron_headers)
            assert rl.status_code == 200
            assert any(b["id"] == bill["id"] and b["paid"] for b in rl.json())
        finally:
            api_client.delete(f"{BASE}/api/clients/{c['id']}", headers=iron_headers)

    def test_reports_iron(self, api_client, iron_headers):
        # monthly
        r = api_client.get(f"{BASE}/api/reports/monthly", headers=iron_headers)
        assert r.status_code == 200
        data = r.json()
        assert isinstance(data, list)
        if data:
            row = data[0]
            for k in ("month", "total_quantity", "total_amount",
                      "paid_amount", "unpaid_amount", "entries_count"):
                assert k in row
        # yearly
        ry = api_client.get(f"{BASE}/api/reports/yearly", headers=iron_headers)
        assert ry.status_code == 200
        assert isinstance(ry.json(), list)
        # by-client
        rc = api_client.get(f"{BASE}/api/reports/by-client", headers=iron_headers)
        assert rc.status_code == 200
        assert isinstance(rc.json(), list)


class TestClientSide:
    def test_client_sees_entries_via_linked_user_id(self, api_client, iron_headers, client_auth, client_headers):
        # ensure iron has client_auth linked
        existing = api_client.get(f"{BASE}/api/clients", headers=iron_headers).json()
        linked = [c for c in existing if c["phone"] == client_auth["user"]["phone"]]
        if not linked:
            r = api_client.post(f"{BASE}/api/clients", headers=iron_headers, json={
                "name": "TEST_ClientLinked", "phone": client_auth["user"]["phone"]
            })
            assert r.status_code == 200, r.text
            cid = r.json()["id"]
        else:
            cid = linked[0]["id"]

        # create an entry
        r = api_client.post(f"{BASE}/api/entries", headers=iron_headers, json={
            "client_id": cid,
            "items": [{"cloth_type": "shirt", "quantity": 1, "rate": 11}],
        })
        assert r.status_code == 200, r.text
        eid = r.json()["id"]

        # client lists entries
        rl = api_client.get(f"{BASE}/api/entries", headers=client_headers)
        assert rl.status_code == 200
        assert any(x["id"] == eid for x in rl.json()), "Client cannot see linked entry"

    def test_my_iron_men(self, api_client, client_headers):
        r = api_client.get(f"{BASE}/api/my/iron-men", headers=client_headers)
        assert r.status_code == 200
        data = r.json()
        assert isinstance(data, list)
        if data:
            row = data[0]
            for k in ("client_record_id", "iron_man_id", "iron_man_name",
                      "iron_man_phone", "default_rate"):
                assert k in row


class TestSubscription:
    def test_plans(self, api_client):
        r = api_client.get(f"{BASE}/api/subscription/plans")
        assert r.status_code == 200
        p = r.json()
        assert p["iron_man"]["amount"] == 49
        assert p["client"]["amount"] == 19
        assert p["iron_man"]["currency"] == "INR"
        assert p["trial_days"] == 45

    def test_activate_for_iron(self, api_client, iron_headers):
        # Iteration 4: legacy /subscription/activate is disabled when Razorpay is enabled.
        # Real activation now goes through create-order + verify-payment (covered in
        # test_iteration4_razorpay.py).
        r = api_client.post(f"{BASE}/api/subscription/activate",
                            headers=iron_headers, json={"plan": "iron_man"})
        assert r.status_code == 400, r.text
        assert "create-order" in r.json()["detail"]

    def test_activate_wrong_plan_400(self, api_client, iron_headers):
        r = api_client.post(f"{BASE}/api/subscription/activate",
                            headers=iron_headers, json={"plan": "client"})
        assert r.status_code == 400
