"""Subscription pricing + activation."""
from datetime import timedelta

import razorpay
from fastapi import HTTPException

from core.config import (
    CLIENT_PLAN_INR,
    IRON_PLAN_INR,
    RAZORPAY_ENABLED,
    RAZORPAY_KEY_ID,
    RAZORPAY_KEY_SECRET,
    SUBSCRIPTION_DAYS,
)
from core.db import db
from core.time_utils import iso, now_utc, parse_iso

razorpay_client = (
    razorpay.Client(auth=(RAZORPAY_KEY_ID, RAZORPAY_KEY_SECRET)) if RAZORPAY_ENABLED else None
)


def plan_amount(plan: str) -> int:
    if plan == "iron_man":
        return IRON_PLAN_INR
    if plan == "client":
        return CLIENT_PLAN_INR
    raise HTTPException(status_code=400, detail="Invalid plan")


async def activate_subscription(user_id: str) -> dict:
    # Start from the later of: now, or current subscription_ends_at.
    # Preserves any unused trial days when the user pays mid-trial.
    user = await db.users.find_one({"_id": user_id})
    current_end_iso = user.get("subscription_ends_at") if user else None
    base = now_utc()
    if current_end_iso:
        try:
            cur_end = parse_iso(current_end_iso)
            if cur_end > base:
                base = cur_end
        except Exception:
            pass
    new_end = base + timedelta(days=SUBSCRIPTION_DAYS)
    await db.users.update_one(
        {"_id": user_id},
        {"$set": {
            "subscription_status": "active",
            "subscription_ends_at": iso(new_end),
        }},
    )
    return await db.users.find_one({"_id": user_id}, {"password_hash": 0})
