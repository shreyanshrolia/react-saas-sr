"""Subscription plans + Razorpay checkout + verification."""
import hashlib
import hmac
import logging

from fastapi import APIRouter, Depends, HTTPException

from core.config import (
    CLIENT_PLAN_INR,
    IRON_PLAN_INR,
    RAZORPAY_ENABLED,
    RAZORPAY_KEY_ID,
    RAZORPAY_KEY_SECRET,
    TRIAL_DAYS,
)
from core.db import db
from core.deps import get_current_user
from core.time_utils import iso, now_utc
from models.auth import UserPublic
from models.subscription import CreateOrderReq, SubscribeReq, VerifyPaymentReq
from services.subscription_service import (
    activate_subscription,
    plan_amount,
    razorpay_client,
)
from services.users_service import refresh_subscription, to_user_public

log = logging.getLogger("grihkari")
router = APIRouter(prefix="/subscription", tags=["subscription"])


@router.get("/plans")
async def get_plans():
    return {
        "iron_man": {"amount": IRON_PLAN_INR, "currency": "INR", "interval": "monthly"},
        "client": {"amount": CLIENT_PLAN_INR, "currency": "INR", "interval": "monthly"},
        "trial_days": TRIAL_DAYS,
        "razorpay_enabled": RAZORPAY_ENABLED,
        "razorpay_key_id": RAZORPAY_KEY_ID if RAZORPAY_ENABLED else None,
    }


@router.post("/create-order")
async def create_subscription_order(req: CreateOrderReq, user=Depends(get_current_user)):
    """Creates a Razorpay Order for the user's plan. Returns details the client uses to open Checkout."""
    if not RAZORPAY_ENABLED or razorpay_client is None:
        raise HTTPException(status_code=503, detail="Payment gateway not configured")
    if req.plan != user["role"]:
        raise HTTPException(status_code=400, detail="Plan does not match user role")
    amount_inr = plan_amount(req.plan)
    amount_paise = amount_inr * 100
    receipt = f"grihkari_{user['_id'][:8]}_{int(now_utc().timestamp())}"
    try:
        order = razorpay_client.order.create({
            "amount": amount_paise,
            "currency": "INR",
            "receipt": receipt,
            "payment_capture": 1,
            "notes": {
                "user_id": user["_id"],
                "phone": user["phone"],
                "plan": req.plan,
            },
        })
    except Exception as e:
        log.exception("Razorpay order create failed")
        raise HTTPException(status_code=502, detail=f"Razorpay error: {e}") from e

    await db.subscription_orders.insert_one({
        "_id": order["id"],
        "user_id": user["_id"],
        "plan": req.plan,
        "amount": amount_paise,
        "currency": "INR",
        "status": "created",
        "created_at": iso(now_utc()),
    })
    return {
        "order_id": order["id"],
        "amount": amount_paise,
        "amount_inr": amount_inr,
        "currency": "INR",
        "key_id": RAZORPAY_KEY_ID,
        "name": "Grihkari",
        "description": f"{'Iron Man' if req.plan == 'iron_man' else 'Client'} Premium \u2014 Monthly",
        "prefill": {
            "name": user["name"],
            "contact": user["phone"],
        },
        "theme_color": "#1E3A8A",
    }


@router.post("/verify-payment", response_model=UserPublic)
async def verify_subscription_payment(req: VerifyPaymentReq, user=Depends(get_current_user)):
    """Verifies the Razorpay payment signature and activates the user's subscription."""
    if not RAZORPAY_ENABLED:
        raise HTTPException(status_code=503, detail="Payment gateway not configured")

    body = f"{req.razorpay_order_id}|{req.razorpay_payment_id}".encode()
    expected = hmac.new(
        RAZORPAY_KEY_SECRET.encode(),
        body,
        hashlib.sha256,
    ).hexdigest()
    if not hmac.compare_digest(expected, req.razorpay_signature):
        await db.subscription_orders.update_one(
            {"_id": req.razorpay_order_id, "status": {"$ne": "paid"}},
            {"$set": {"status": "signature_failed", "verified_at": iso(now_utc())}},
        )
        raise HTTPException(status_code=400, detail="Invalid payment signature")

    order_doc = await db.subscription_orders.find_one({"_id": req.razorpay_order_id})
    if not order_doc:
        raise HTTPException(status_code=404, detail="Order not found")
    if order_doc["user_id"] != user["_id"]:
        raise HTTPException(status_code=403, detail="Order does not belong to user")

    # Idempotent: if already paid, just return current user state
    if order_doc.get("status") == "paid":
        fresh = await db.users.find_one({"_id": user["_id"]}, {"password_hash": 0})
        return to_user_public(fresh)

    await db.subscription_orders.update_one(
        {"_id": req.razorpay_order_id},
        {"$set": {
            "status": "paid",
            "razorpay_payment_id": req.razorpay_payment_id,
            "verified_at": iso(now_utc()),
        }},
    )
    fresh = await activate_subscription(user["_id"])
    await refresh_subscription(fresh)
    return to_user_public(fresh)


@router.post("/activate", response_model=UserPublic)
async def activate(req: SubscribeReq, user=Depends(get_current_user)):
    """Legacy placeholder activation. Only allowed when Razorpay is NOT configured."""
    if RAZORPAY_ENABLED:
        raise HTTPException(status_code=400, detail="Use /subscription/create-order + /subscription/verify-payment")
    if req.plan != user["role"]:
        raise HTTPException(status_code=400, detail="Plan does not match user role")
    fresh = await activate_subscription(user["_id"])
    await refresh_subscription(fresh)
    return to_user_public(fresh)
