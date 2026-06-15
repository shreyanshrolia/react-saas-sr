"""Notification creation + serialization."""
import uuid
from typing import Optional

from core.db import db
from core.time_utils import iso, now_utc
from models.notifications import NotificationPublic


async def create_notification(
    user_id: str,
    type_: str,
    title: str,
    message: str,
    entry_id: Optional[str] = None,
    client_id: Optional[str] = None,
    iron_man_id: Optional[str] = None,
) -> None:
    if not user_id:
        return
    nid = str(uuid.uuid4())
    await db.notifications.insert_one({
        "_id": nid,
        "user_id": user_id,
        "type": type_,
        "title": title,
        "message": message,
        "entry_id": entry_id,
        "client_id": client_id,
        "iron_man_id": iron_man_id,
        "read": False,
        "created_at": iso(now_utc()),
    })


def to_notification_public(n: dict) -> NotificationPublic:
    return NotificationPublic(
        id=n["_id"],
        type=n["type"],
        title=n["title"],
        message=n["message"],
        entry_id=n.get("entry_id"),
        client_id=n.get("client_id"),
        iron_man_id=n.get("iron_man_id"),
        read=bool(n.get("read", False)),
        created_at=n["created_at"],
    )


def items_summary(items: list) -> str:
    parts = []
    for it in items[:3]:
        parts.append(f"{it.get('cloth_type', '')}×{it.get('quantity', 0)}")
    extra = len(items) - 3
    if extra > 0:
        parts.append(f"+{extra} more")
    return ", ".join(parts)
