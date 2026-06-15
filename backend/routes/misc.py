"""Misc endpoints (client-side iron-men list, health check)."""
from fastapi import APIRouter, Depends

from core.db import db
from core.deps import get_current_user, require_client

router = APIRouter(tags=["misc"])


@router.get("/my/iron-men")
async def my_iron_men(user=Depends(get_current_user)):
    """For client role: list of iron_men who have added them as client."""
    require_client(user)
    out = []
    async for c in db.clients.find({"linked_user_id": user["_id"]}):
        im = await db.users.find_one({"_id": c["iron_man_id"]}, {"password_hash": 0})
        if im:
            out.append({
                "client_record_id": c["_id"],
                "iron_man_id": im["_id"],
                "iron_man_name": im["name"],
                "iron_man_phone": im["phone"],
                "default_rate": float(c.get("default_rate", 10.0)),
            })
    return out


@router.get("/")
async def root():
    return {"app": "Grihkari", "status": "ok"}
