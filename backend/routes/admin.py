"""Admin routes: list users, reset password."""
from typing import Optional

from fastapi import APIRouter, HTTPException

from core.config import ADMIN_PASSWORD
from core.db import db
from core.deps import check_admin
from core.security import hash_pw
from models.auth import AdminLoginReq, AdminResetReq

router = APIRouter(prefix="/admin", tags=["admin"])


@router.post("/login")
async def admin_login(req: AdminLoginReq):
    if not ADMIN_PASSWORD or req.password != ADMIN_PASSWORD:
        raise HTTPException(status_code=401, detail="Invalid admin password")
    return {"token": f"admin:{ADMIN_PASSWORD}"}


@router.get("/users")
async def admin_list_users(q: Optional[str] = None, admin_token: str = ""):
    check_admin(admin_token)
    query: dict = {}
    if q:
        query = {"$or": [
            {"name": {"$regex": q, "$options": "i"}},
            {"phone": {"$regex": q}},
        ]}
    out = []
    async for u in db.users.find(query, {"password_hash": 0, "security_answer_hash": 0}).limit(100):
        out.append({
            "id": u["_id"],
            "name": u["name"],
            "phone": u["phone"],
            "role": u["role"],
            "security_question": u.get("security_question"),
            "subscription_status": u.get("subscription_status"),
            "created_at": u.get("created_at"),
        })
    return out


@router.post("/users/{user_id}/reset-password")
async def admin_reset_password(user_id: str, req: AdminResetReq, admin_token: str = ""):
    check_admin(admin_token)
    u = await db.users.find_one({"_id": user_id})
    if not u:
        raise HTTPException(status_code=404, detail="User not found")
    await db.users.update_one(
        {"_id": user_id}, {"$set": {"password_hash": hash_pw(req.new_password)}}
    )
    return {"ok": True, "user_id": user_id, "name": u["name"], "phone": u["phone"]}
