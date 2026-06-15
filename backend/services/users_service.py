"""User-related helpers: public serialization + subscription state refresh."""
from core.db import db
from core.time_utils import now_utc, parse_iso
from models.auth import UserPublic


def to_user_public(u: dict) -> UserPublic:
    return UserPublic(
        id=u["_id"],
        name=u["name"],
        phone=u["phone"],
        role=u["role"],
        address=u.get("address"),
        trial_ends_at=u.get("trial_ends_at"),
        subscription_status=u.get("subscription_status", "trial"),
        subscription_ends_at=u.get("subscription_ends_at"),
        created_at=u["created_at"],
    )


async def refresh_subscription(user: dict) -> None:
    """Derive current subscription status from trial_ends_at and subscription_ends_at.
    - 'trial'   = trial period still active (regardless of payment)
    - 'active'  = paid period active, trial has ended
    - 'expired' = both ended
    Paying during trial extends subscription_ends_at past trial_ends_at so user
    gets BOTH the remaining trial days AND the full paid period.
    """
    now = now_utc()
    sub_end_iso = user.get("subscription_ends_at")
    trial_end_iso = user.get("trial_ends_at")
    sub_end = parse_iso(sub_end_iso) if sub_end_iso else None
    trial_end = parse_iso(trial_end_iso) if trial_end_iso else None

    new_status = "expired"
    if sub_end and sub_end > now:
        if trial_end and trial_end > now:
            new_status = "trial"
        else:
            new_status = "active"

    if user.get("subscription_status") != new_status:
        await db.users.update_one(
            {"_id": user["_id"]}, {"$set": {"subscription_status": new_status}}
        )
        user["subscription_status"] = new_status
