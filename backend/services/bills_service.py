"""Bill aggregation, status computation, and payment recording."""
import uuid
from typing import Optional, Tuple

from core.db import db
from core.time_utils import iso, now_utc
from models.bills import BillPublic


def compute_status(net_due: float, amount_paid: float) -> str:
    if net_due <= 0 and amount_paid <= 0:
        return "paid"
    if amount_paid <= 0:
        return "unpaid"
    if amount_paid >= net_due:
        return "overpaid" if amount_paid > net_due else "paid"
    return "partial"


def to_bill_public(b: dict) -> BillPublic:
    clothes = float(b.get("clothes_amount", b.get("total_amount", 0)))
    carry = float(b.get("carry_in", 0))
    paid = float(b.get("amount_paid", 0))
    net = float(b.get("net_due", clothes + carry))
    bal = net - paid
    bill_status = b.get("status") or compute_status(net, paid)
    return BillPublic(
        id=b["_id"],
        iron_man_id=b["iron_man_id"],
        client_id=b["client_id"],
        client_name=b.get("client_name", ""),
        client_phone=b.get("client_phone", ""),
        month=b["month"],
        total_quantity=int(b.get("total_quantity", 0)),
        clothes_amount=round(clothes, 2),
        carry_in=round(carry, 2),
        net_due=round(net, 2),
        amount_paid=round(paid, 2),
        balance=round(bal, 2),
        status=bill_status,
        total_amount=round(net, 2),
        paid=bill_status in ("paid", "overpaid"),
        paid_at=b.get("last_paid_at"),
        generated_at=b["generated_at"],
    )


async def aggregate_bill_for(client_id: str, month: str) -> Tuple[int, float]:
    qty = 0
    amt = 0.0
    async for e in db.entries.find({"client_id": client_id, "month_key": month}, {"total_quantity": 1, "total_amount": 1}):
        qty += int(e.get("total_quantity", 0))
        amt += float(e.get("total_amount", 0))
    return qty, round(amt, 2)


async def previous_bill_balance(client_id: str, month: str) -> float:
    """Return the balance (net_due - amount_paid) of the most recent bill before `month`.
    Positive => client still owes; Negative => client overpaid (credit)."""
    prev = await db.bills.find_one(
        {"client_id": client_id, "month": {"$lt": month}},
        sort=[("month", -1)],
    )
    if not prev:
        return 0.0
    net = float(prev.get("net_due", prev.get("total_amount", 0)))
    paid = float(prev.get("amount_paid", 0))
    return round(net - paid, 2)


async def ensure_bill(iron_man_id: str, client_doc: dict, month: str) -> dict:
    qty, clothes_amount = await aggregate_bill_for(client_doc["_id"], month)
    carry_in = await previous_bill_balance(client_doc["_id"], month)
    net_due = round(clothes_amount + carry_in, 2)
    existing = await db.bills.find_one({"client_id": client_doc["_id"], "month": month})
    if existing:
        amount_paid = float(existing.get("amount_paid", 0))
        balance = round(net_due - amount_paid, 2)
        status = compute_status(net_due, amount_paid)
        await db.bills.update_one(
            {"_id": existing["_id"]},
            {"$set": {
                "total_quantity": qty,
                "clothes_amount": clothes_amount,
                "carry_in": carry_in,
                "net_due": net_due,
                "balance": balance,
                "status": status,
                "total_amount": net_due,
                "paid": status in ("paid", "overpaid"),
            }},
        )
        return await db.bills.find_one({"_id": existing["_id"]})
    bid = str(uuid.uuid4())
    status = compute_status(net_due, 0.0)
    doc = {
        "_id": bid,
        "iron_man_id": iron_man_id,
        "client_id": client_doc["_id"],
        "client_name": client_doc["name"],
        "client_phone": client_doc["phone"],
        "linked_user_id": client_doc.get("linked_user_id"),
        "month": month,
        "total_quantity": qty,
        "clothes_amount": clothes_amount,
        "carry_in": carry_in,
        "net_due": net_due,
        "amount_paid": 0.0,
        "balance": net_due,
        "status": status,
        "last_paid_at": None,
        "total_amount": net_due,
        "paid": False,
        "paid_at": None,
        "generated_at": iso(now_utc()),
    }
    await db.bills.insert_one(doc)
    return doc


async def create_payment(bill: dict, amount: float, notes: Optional[str]) -> dict:
    pid = str(uuid.uuid4())
    now = iso(now_utc())
    pdoc = {
        "_id": pid,
        "iron_man_id": bill["iron_man_id"],
        "client_id": bill["client_id"],
        "client_name": bill.get("client_name", ""),
        "client_phone": bill.get("client_phone", ""),
        "bill_id": bill["_id"],
        "month": bill["month"],
        "amount": float(amount),
        "paid_at": now,
        "notes": notes,
    }
    await db.payments.insert_one(pdoc)
    new_paid = round(float(bill.get("amount_paid", 0)) + float(amount), 2)
    net_due = float(bill.get("net_due", bill.get("total_amount", 0)))
    balance = round(net_due - new_paid, 2)
    bs = compute_status(net_due, new_paid)
    await db.bills.update_one(
        {"_id": bill["_id"]},
        {"$set": {
            "amount_paid": new_paid,
            "balance": balance,
            "status": bs,
            "last_paid_at": now,
            "paid": bs in ("paid", "overpaid"),
            "paid_at": now if bs in ("paid", "overpaid") else None,
        }},
    )
    return pdoc
