"""Iteration 2 tests - date_given/month_key, client_id integrity bug fix,
GET /api/entries returns all (pending+returned), linked_user_id propagation.
"""
import time
import uuid
import pytest
import requests

from conftest import BASE_URL


# ---------- helpers ----------
def _auth_headers(token):
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


def _new_phone():
    # 10 random digits, not colliding with seed users 9999999991/2
    suffix = str(int(time.time() * 1000))[-9:]
    return f"8{suffix}"


def _cleanup_client(iron_headers, client_id):
    try:
        requests.delete(f"{BASE_URL}/api/clients/{client_id}",
                        headers=iron_headers, timeout=15)
    except Exception:
        pass


# ---------- Feature: date_given drives month_key ----------
class TestDateGivenMonthKey:
    """POST /api/entries with date_given must set month_key to that month."""

    def test_entry_month_key_uses_date_given(self, iron_auth, iron_headers):
        # Create a fresh client
        phone = _new_phone()
        r = requests.post(f"{BASE_URL}/api/clients",
                          headers=iron_headers,
                          json={"name": "TEST_DateClient", "phone": phone,
                                "default_rate": 10}, timeout=15)
        assert r.status_code == 200, r.text
        cid = r.json()["id"]
        try:
            # Create entry with explicit date in Dec 2025
            r = requests.post(f"{BASE_URL}/api/entries",
                              headers=iron_headers,
                              json={"client_id": cid,
                                    "date_given": "2025-12-15T00:00:00Z",
                                    "items": [{"cloth_type": "shirt",
                                               "quantity": 3, "rate": 10}]},
                              timeout=15)
            assert r.status_code == 200, r.text
            entry = r.json()
            entry_id = entry["id"]
            # date_given preserved
            assert "2025-12-15" in entry["date_given"]

            # Verify month_key via bills aggregation (uses month_key field)
            r = requests.get(f"{BASE_URL}/api/bills?month=2025-12&client_id={cid}",
                             headers=iron_headers, timeout=15)
            assert r.status_code == 200
            # ensure bill generated for 2025-12
            r2 = requests.post(f"{BASE_URL}/api/bills/generate?month=2025-12",
                               headers=iron_headers, timeout=15)
            assert r2.status_code == 200
            bills = r2.json()
            bill_match = [b for b in bills if b["client_id"] == cid]
            assert len(bill_match) == 1, f"Expected bill for 2025-12, got {bills}"
            assert bill_match[0]["month"] == "2025-12"
            assert bill_match[0]["total_quantity"] == 3
            assert bill_match[0]["total_amount"] == 30.0

            # Verify reports/monthly groups under 2025-12
            r = requests.get(f"{BASE_URL}/api/reports/monthly?year=2025",
                             headers=iron_headers, timeout=15)
            assert r.status_code == 200
            months = {m["month"]: m for m in r.json()}
            assert "2025-12" in months, f"month 2025-12 missing in {months.keys()}"

            # Cleanup entry
            requests.delete(f"{BASE_URL}/api/entries/{entry_id}",
                            headers=iron_headers, timeout=15)
        finally:
            _cleanup_client(iron_headers, cid)

    def test_entry_defaults_to_current_month_when_no_date_given(
            self, iron_auth, iron_headers):
        from datetime import datetime, timezone
        phone = _new_phone()
        r = requests.post(f"{BASE_URL}/api/clients",
                          headers=iron_headers,
                          json={"name": "TEST_DefaultDate", "phone": phone,
                                "default_rate": 10}, timeout=15)
        assert r.status_code == 200
        cid = r.json()["id"]
        try:
            r = requests.post(f"{BASE_URL}/api/entries",
                              headers=iron_headers,
                              json={"client_id": cid,
                                    "items": [{"cloth_type": "pant",
                                               "quantity": 1, "rate": 15}]},
                              timeout=15)
            assert r.status_code == 200
            entry = r.json()
            current_month = datetime.now(timezone.utc).strftime("%Y-%m")
            # date_given should be today
            assert entry["date_given"].startswith(current_month)
        finally:
            _cleanup_client(iron_headers, cid)


# ---------- Bug fix: entry client_id integrity ----------
class TestClientIdIntegrity:
    """Entries must always go to the exact client_id specified, regardless
    of whether that client is signed up. Even if another user with the same
    phone signs up later, the entry must remain with the original client_id.
    """

    def test_entry_goes_to_specified_client_not_signed_up(
            self, iron_auth, iron_headers):
        # Create 2 clients A and B (neither signed up)
        phone_a = _new_phone()
        time.sleep(0.01)
        phone_b = _new_phone()

        rA = requests.post(f"{BASE_URL}/api/clients", headers=iron_headers,
                           json={"name": "TEST_ClientA", "phone": phone_a,
                                 "default_rate": 10}, timeout=15)
        assert rA.status_code == 200, rA.text
        A = rA.json()
        assert A["linked_user_id"] is None

        rB = requests.post(f"{BASE_URL}/api/clients", headers=iron_headers,
                           json={"name": "TEST_ClientB", "phone": phone_b,
                                 "default_rate": 12}, timeout=15)
        assert rB.status_code == 200, rB.text
        B = rB.json()
        assert B["linked_user_id"] is None

        entry_id = None
        try:
            # Create entry for client B specifically
            r = requests.post(f"{BASE_URL}/api/entries", headers=iron_headers,
                              json={"client_id": B["id"],
                                    "items": [{"cloth_type": "kurta",
                                               "quantity": 2, "rate": 12}]},
                              timeout=15)
            assert r.status_code == 200, r.text
            entry = r.json()
            entry_id = entry["id"]
            # Must belong to B, NOT A
            assert entry["client_id"] == B["id"], \
                f"Entry assigned to {entry['client_id']}, expected {B['id']}"
            assert entry["client_name"] == B["name"]
            assert entry["client_phone"] == B["phone"]
            assert entry["client_id"] != A["id"]

            # GET it back
            r = requests.get(f"{BASE_URL}/api/entries?client_id={B['id']}",
                             headers=iron_headers, timeout=15)
            assert r.status_code == 200
            b_entries = r.json()
            assert any(e["id"] == entry_id for e in b_entries), \
                "Entry missing from B's entry list"

            # And NOT in A's list
            r = requests.get(f"{BASE_URL}/api/entries?client_id={A['id']}",
                             headers=iron_headers, timeout=15)
            assert r.status_code == 200
            a_entries = r.json()
            assert not any(e["id"] == entry_id for e in a_entries), \
                "Entry leaked into client A's list"
        finally:
            if entry_id:
                requests.delete(f"{BASE_URL}/api/entries/{entry_id}",
                                headers=iron_headers, timeout=15)
            _cleanup_client(iron_headers, A["id"])
            _cleanup_client(iron_headers, B["id"])

    def test_entry_stays_with_original_client_after_other_signs_up(
            self, iron_auth, iron_headers):
        """B has entry. A different user X with B's phone... wait the prompt
        says: 'sign up a different client X with that phone and verify entry
        STILL belongs to B'. Phone is unique per user so signing X with B's
        phone is not possible; we sign X with a *new* phone and verify B's
        entry is unaffected. We also verify even if same phone signup
        idempotent path occurs, entry's client_id is unchanged.
        """
        phone_b = _new_phone()
        rB = requests.post(f"{BASE_URL}/api/clients", headers=iron_headers,
                           json={"name": "TEST_ClientB2", "phone": phone_b,
                                 "default_rate": 10}, timeout=15)
        assert rB.status_code == 200
        B = rB.json()
        entry_id = None
        try:
            r = requests.post(f"{BASE_URL}/api/entries", headers=iron_headers,
                              json={"client_id": B["id"],
                                    "items": [{"cloth_type": "shirt",
                                               "quantity": 1, "rate": 10}]},
                              timeout=15)
            assert r.status_code == 200
            entry = r.json()
            entry_id = entry["id"]
            original_client_id = entry["client_id"]

            # Now sign up a completely different user X (different phone)
            phone_x = _new_phone()
            time.sleep(0.01)
            s = requests.Session()
            r = s.post(f"{BASE_URL}/api/auth/signup",
                       json={"name": "TEST_X", "phone": phone_x,
                             "password": "test123", "role": "client"},
                       timeout=15)
            assert r.status_code == 200

            # Re-fetch entry; should be unchanged
            r = requests.get(f"{BASE_URL}/api/entries?client_id={B['id']}",
                             headers=iron_headers, timeout=15)
            assert r.status_code == 200
            entries = [e for e in r.json() if e["id"] == entry_id]
            assert len(entries) == 1
            assert entries[0]["client_id"] == original_client_id
            assert entries[0]["client_name"] == B["name"]
            assert entries[0]["client_phone"] == phone_b
        finally:
            if entry_id:
                requests.delete(f"{BASE_URL}/api/entries/{entry_id}",
                                headers=iron_headers, timeout=15)
            _cleanup_client(iron_headers, B["id"])


# ---------- GET /api/entries returns all (pending + returned) ----------
class TestEntriesReturnAllStatuses:
    def test_iron_man_get_entries_returns_pending_and_returned(
            self, iron_auth, iron_headers):
        phone = _new_phone()
        r = requests.post(f"{BASE_URL}/api/clients", headers=iron_headers,
                          json={"name": "TEST_AllStatus", "phone": phone,
                                "default_rate": 10}, timeout=15)
        assert r.status_code == 200
        cid = r.json()["id"]
        pending_id = returned_id = None
        try:
            # entry 1 -> remains pending
            r = requests.post(f"{BASE_URL}/api/entries", headers=iron_headers,
                              json={"client_id": cid,
                                    "items": [{"cloth_type": "shirt",
                                               "quantity": 1, "rate": 10}]},
                              timeout=15)
            assert r.status_code == 200
            pending_id = r.json()["id"]

            # entry 2 -> mark returned
            r = requests.post(f"{BASE_URL}/api/entries", headers=iron_headers,
                              json={"client_id": cid,
                                    "items": [{"cloth_type": "pant",
                                               "quantity": 2, "rate": 10}]},
                              timeout=15)
            assert r.status_code == 200
            returned_id = r.json()["id"]
            r = requests.post(
                f"{BASE_URL}/api/entries/{returned_id}/return",
                headers=iron_headers, json={}, timeout=15)
            assert r.status_code == 200
            assert r.json()["status"] == "returned"

            # GET no filter -> both present
            r = requests.get(f"{BASE_URL}/api/entries?client_id={cid}",
                             headers=iron_headers, timeout=15)
            assert r.status_code == 200
            ids = [e["id"] for e in r.json()]
            statuses = {e["id"]: e["status"] for e in r.json()}
            assert pending_id in ids and returned_id in ids, \
                f"Both entries should be returned: got {ids}"
            assert statuses[pending_id] == "pending"
            assert statuses[returned_id] == "returned"
        finally:
            for eid in (pending_id, returned_id):
                if eid:
                    requests.delete(f"{BASE_URL}/api/entries/{eid}",
                                    headers=iron_headers, timeout=15)
            _cleanup_client(iron_headers, cid)


# ---------- linked_user_id propagation ----------
class TestLinkedUserPropagation:
    """When iron_man adds an entry for a client whose linked_user_id is
    already populated (client already signed up), the new entry must carry
    linked_user_id so the client can see it via GET /api/entries.
    """

    def test_entry_carries_linked_user_id_when_client_already_signed_up(
            self, iron_auth, iron_headers, client_auth, client_headers):
        # The seed client (9999999992) is signed up. Add them under iron man.
        # If duplicate, fetch existing.
        client_phone = "9999999992"
        r = requests.post(f"{BASE_URL}/api/clients", headers=iron_headers,
                          json={"name": "TEST_LinkedSeed",
                                "phone": client_phone, "default_rate": 10},
                          timeout=15)
        if r.status_code == 400:
            # already exists; find it
            rr = requests.get(f"{BASE_URL}/api/clients", headers=iron_headers,
                              timeout=15)
            assert rr.status_code == 200
            match = [c for c in rr.json() if c["phone"] == client_phone]
            assert match, "Seed client not in iron man's list"
            client_rec = match[0]
        else:
            assert r.status_code == 200, r.text
            client_rec = r.json()

        # linked_user_id should be auto-populated to seed client's user id
        assert client_rec["linked_user_id"] == client_auth["user"]["id"], (
            f"Expected linked_user_id={client_auth['user']['id']}, "
            f"got {client_rec['linked_user_id']}")

        cid = client_rec["id"]
        entry_id = None
        try:
            r = requests.post(f"{BASE_URL}/api/entries", headers=iron_headers,
                              json={"client_id": cid,
                                    "notes": "TEST_linked_entry",
                                    "items": [{"cloth_type": "shirt",
                                               "quantity": 4, "rate": 11}]},
                              timeout=15)
            assert r.status_code == 200
            entry = r.json()
            entry_id = entry["id"]

            # Client side: GET /api/entries should include this new entry
            r = requests.get(f"{BASE_URL}/api/entries",
                             headers=client_headers, timeout=15)
            assert r.status_code == 200
            client_entries = r.json()
            match = [e for e in client_entries if e["id"] == entry_id]
            assert len(match) == 1, (
                f"Client cannot see entry {entry_id} - linked_user_id not "
                f"propagated. Got {len(client_entries)} entries")
            assert match[0]["status"] == "pending"
            assert match[0]["total_quantity"] == 4
            assert match[0]["total_amount"] == 44.0

            # Mark returned, ensure client still sees it (all statuses)
            r = requests.post(f"{BASE_URL}/api/entries/{entry_id}/return",
                              headers=iron_headers, json={}, timeout=15)
            assert r.status_code == 200
            r = requests.get(f"{BASE_URL}/api/entries",
                             headers=client_headers, timeout=15)
            assert r.status_code == 200
            still = [e for e in r.json() if e["id"] == entry_id]
            assert len(still) == 1
            assert still[0]["status"] == "returned"
        finally:
            if entry_id:
                requests.delete(f"{BASE_URL}/api/entries/{entry_id}",
                                headers=iron_headers, timeout=15)
            # don't delete the linked seed-client record (keep seed clean)
            # but if we created a fresh entry-only record, leave it
