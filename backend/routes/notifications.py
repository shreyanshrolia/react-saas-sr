"""Notification list + read endpoints."""
from typing import List

from fastapi import APIRouter, Depends, HTTPException

from core.db import db
from core.deps import get_current_user
from models.notifications import NotificationPublic
from services.notifications_service import to_notification_public

router = APIRouter(prefix="/notifications", tags=["notifications"])


@router.get("", response_model=List[NotificationPublic])
async def list_notifications(unread_only: bool = False, user=Depends(get_current_user)):
    q: dict = {"user_id": user["_id"]}
    if unread_only:
        q["read"] = False
    out: List[NotificationPublic] = []
    async for n in db.notifications.find(q).sort("created_at", -1).limit(100):
        out.append(to_notification_public(n))
    return out


@router.get("/unread-count")
async def unread_count(user=Depends(get_current_user)):
    n = await db.notifications.count_documents({"user_id": user["_id"], "read": False})
    return {"count": n}


@router.post("/{notification_id}/read")
async def mark_notification_read(notification_id: str, user=Depends(get_current_user)):
    res = await db.notifications.update_one(
        {"_id": notification_id, "user_id": user["_id"]},
        {"$set": {"read": True}},
    )
    if res.matched_count == 0:
        raise HTTPException(status_code=404, detail="Notification not found")
    return {"ok": True}


@router.post("/read-all")
async def mark_all_notifications_read(user=Depends(get_current_user)):
    res = await db.notifications.update_many(
        {"user_id": user["_id"], "read": False},
        {"$set": {"read": True}},
    )
    return {"updated": res.modified_count}
