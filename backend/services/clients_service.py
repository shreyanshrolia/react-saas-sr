"""Client aggregations + serialization."""
from core.db import db
from core.time_utils import current_month_key
from models.clients import ClientPublic


async def client_stats(client_doc: dict) -> dict:
    cid = client_doc["_id"]
    pending = await db.entries.count_documents(
        {"client_id": cid, "status": "pending"}
    )
    mk = current_month_key()
    cur = db.entries.find({"client_id": cid, "month_key": mk})
    total = 0.0
    async for e in cur:
        total += float(e.get("total_amount", 0))
    return {"pending_count": pending, "current_month_amount": round(total, 2)}


def to_client_public(c: dict, stats: dict) -> ClientPublic:
    return ClientPublic(
        id=c["_id"],
        iron_man_id=c["iron_man_id"],
        name=c["name"],
        phone=c["phone"],
        address=c.get("address"),
        default_rate=float(c.get("default_rate", 10.0)),
        linked_user_id=c.get("linked_user_id"),
        delete_requested_at=c.get("delete_requested_at"),
        created_at=c["created_at"],
        pending_count=stats["pending_count"],
        current_month_amount=stats["current_month_amount"],
    )
