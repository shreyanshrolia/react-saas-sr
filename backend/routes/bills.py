"""Bill generation, listing, payments."""
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException

from core.db import db
from core.deps import get_current_user, require_iron
from core.time_utils import current_month_key
from models.bills import BillPublic, MarkPaidReq, PaymentCreateReq, PaymentPublic
from services.bills_service import (
    compute_status,
    create_payment,
    ensure_bill,
    to_bill_public,
)

router = APIRouter(tags=["bills"])


@router.post("/bills/generate", response_model=List[BillPublic])
async def generate_bills(month: Optional[str] = None, user=Depends(get_current_user)):
    require_iron(user)
    target_month = month or current_month_key()
    out = []
    async for c in db.clients.find({"iron_man_id": user["_id"]}):
        b = await ensure_bill(user["_id"], c, target_month)
        if b["net_due"] > 0 or b["total_quantity"] > 0 or b.get("carry_in", 0) != 0 or b.get("amount_paid", 0) > 0:
            out.append(to_bill_public(b))
    return out


@router.get("/bills", response_model=List[BillPublic])
async def list_bills(
    month: Optional[str] = None,
    client_id: Optional[str] = None,
    user=Depends(get_current_user),
):
    q: dict = {}
    if user["role"] == "iron_man":
        q["iron_man_id"] = user["_id"]
        if client_id:
            q["client_id"] = client_id
    else:
        q["linked_user_id"] = user["_id"]
    if month:
        q["month"] = month

    # For iron_man, refresh current-month bills for all clients
    if user["role"] == "iron_man" and (not month or month == current_month_key()):
        async for c in db.clients.find({"iron_man_id": user["_id"]}):
            await ensure_bill(user["_id"], c, current_month_key())

    out = []
    async for b in db.bills.find(q).sort("month", -1).limit(500):
        out.append(to_bill_public(b))
    return out


@router.post("/bills/{bill_id}/paid", response_model=BillPublic)
async def mark_bill_paid(bill_id: str, req: MarkPaidReq, user=Depends(get_current_user)):
    """Legacy: marks the full balance as paid (or unpaid by deleting all payments)."""
    require_iron(user)
    b = await db.bills.find_one({"_id": bill_id, "iron_man_id": user["_id"]})
    if not b:
        raise HTTPException(status_code=404, detail="Bill not found")
    if req.paid:
        net_due = float(b.get("net_due", b.get("total_amount", 0)))
        paid = float(b.get("amount_paid", 0))
        remaining = round(net_due - paid, 2)
        if remaining > 0:
            await create_payment(b, remaining, None)
    else:
        await db.payments.delete_many({"bill_id": bill_id})
        await db.bills.update_one(
            {"_id": bill_id},
            {"$set": {"amount_paid": 0.0, "balance": float(b.get("net_due", 0)),
                      "status": "unpaid", "last_paid_at": None, "paid": False, "paid_at": None}},
        )
    b2 = await db.bills.find_one({"_id": bill_id})
    return to_bill_public(b2)


@router.post("/bills/{bill_id}/payments", response_model=PaymentPublic)
async def record_payment(bill_id: str, req: PaymentCreateReq, user=Depends(get_current_user)):
    require_iron(user)
    b = await db.bills.find_one({"_id": bill_id, "iron_man_id": user["_id"]})
    if not b:
        raise HTTPException(status_code=404, detail="Bill not found")
    pdoc = await create_payment(b, req.amount, req.notes)
    return PaymentPublic(
        id=pdoc["_id"],
        bill_id=pdoc["bill_id"],
        iron_man_id=pdoc["iron_man_id"],
        client_id=pdoc["client_id"],
        client_name=pdoc.get("client_name", ""),
        amount=float(pdoc["amount"]),
        paid_at=pdoc["paid_at"],
        notes=pdoc.get("notes"),
    )


@router.get("/bills/{bill_id}/payments", response_model=List[PaymentPublic])
async def list_bill_payments(bill_id: str, user=Depends(get_current_user)):
    b = await db.bills.find_one({"_id": bill_id})
    if not b:
        raise HTTPException(status_code=404, detail="Bill not found")
    if user["role"] == "iron_man" and b["iron_man_id"] != user["_id"]:
        raise HTTPException(status_code=403, detail="Forbidden")
    if user["role"] == "client" and b.get("linked_user_id") != user["_id"]:
        raise HTTPException(status_code=403, detail="Forbidden")
    out = []
    async for p in db.payments.find({"bill_id": bill_id}).sort("paid_at", -1).limit(200):
        out.append(PaymentPublic(
            id=p["_id"],
            bill_id=p["bill_id"],
            iron_man_id=p["iron_man_id"],
            client_id=p["client_id"],
            client_name=p.get("client_name", ""),
            amount=float(p["amount"]),
            paid_at=p["paid_at"],
            notes=p.get("notes"),
        ))
    return out


@router.delete("/payments/{payment_id}")
async def delete_payment(payment_id: str, user=Depends(get_current_user)):
    require_iron(user)
    p = await db.payments.find_one({"_id": payment_id, "iron_man_id": user["_id"]})
    if not p:
        raise HTTPException(status_code=404, detail="Payment not found")
    await db.payments.delete_one({"_id": payment_id})
    b = await db.bills.find_one({"_id": p["bill_id"]})
    if b:
        total_paid = 0.0
        last_at: Optional[str] = None
        async for pp in db.payments.find({"bill_id": b["_id"]}).sort("paid_at", -1):
            total_paid += float(pp["amount"])
            if last_at is None:
                last_at = pp["paid_at"]
        net_due = float(b.get("net_due", b.get("total_amount", 0)))
        bs = compute_status(net_due, total_paid)
        await db.bills.update_one(
            {"_id": b["_id"]},
            {"$set": {
                "amount_paid": round(total_paid, 2),
                "balance": round(net_due - total_paid, 2),
                "status": bs,
                "last_paid_at": last_at,
                "paid": bs in ("paid", "overpaid"),
                "paid_at": last_at if bs in ("paid", "overpaid") else None,
            }},
        )
    return {"ok": True}
