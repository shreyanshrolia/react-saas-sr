"""Client CRUD + delete-request/confirm/deny workflow."""
import uuid
from typing import List

from fastapi import APIRouter, Depends, HTTPException

from core.db import db
from core.deps import get_current_user, require_client, require_iron
from core.time_utils import iso, now_utc
from models.clients import ClientAddReq, ClientPublic, ClientUpdateReq
from services.clients_service import client_stats, to_client_public
from services.notifications_service import create_notification

router = APIRouter(prefix="/clients", tags=["clients"])


@router.get("", response_model=List[ClientPublic])
async def list_clients(user=Depends(get_current_user)):
    require_iron(user)
    out: List[ClientPublic] = []
    async for c in db.clients.find({"iron_man_id": user["_id"]}).sort("created_at", -1):
        stats = await client_stats(c)
        out.append(to_client_public(c, stats))
    return out


@router.post("", response_model=ClientPublic)
async def add_client(req: ClientAddReq, user=Depends(get_current_user)):
    require_iron(user)
    dup = await db.clients.find_one(
        {"iron_man_id": user["_id"], "phone": req.phone}
    )
    if dup:
        raise HTTPException(status_code=400, detail="Client with this phone already exists")
    cid = str(uuid.uuid4())
    linked = await db.users.find_one({"phone": req.phone, "role": "client"})
    doc = {
        "_id": cid,
        "iron_man_id": user["_id"],
        "name": req.name.strip(),
        "phone": req.phone,
        "address": req.address,
        "default_rate": float(req.default_rate or 10.0),
        "linked_user_id": linked["_id"] if linked else None,
        "created_at": iso(now_utc()),
    }
    await db.clients.insert_one(doc)
    stats = await client_stats(doc)
    return to_client_public(doc, stats)


@router.get("/{client_id}", response_model=ClientPublic)
async def get_client(client_id: str, user=Depends(get_current_user)):
    require_iron(user)
    c = await db.clients.find_one({"_id": client_id, "iron_man_id": user["_id"]})
    if not c:
        raise HTTPException(status_code=404, detail="Client not found")
    stats = await client_stats(c)
    return to_client_public(c, stats)


@router.patch("/{client_id}", response_model=ClientPublic)
async def update_client(client_id: str, req: ClientUpdateReq, user=Depends(get_current_user)):
    require_iron(user)
    c = await db.clients.find_one({"_id": client_id, "iron_man_id": user["_id"]})
    if not c:
        raise HTTPException(status_code=404, detail="Client not found")
    updates = {k: v for k, v in req.dict(exclude_unset=True).items() if v is not None}
    if updates:
        await db.clients.update_one({"_id": client_id}, {"$set": updates})
    c2 = await db.clients.find_one({"_id": client_id})
    stats = await client_stats(c2)
    return to_client_public(c2, stats)


@router.delete("/{client_id}")
async def delete_client(client_id: str, user=Depends(get_current_user)):
    """Hard-delete a client. Only allowed for iron-man IF the client is not signed up.
    For signed-up clients, iron-man must use /clients/{id}/delete-request and the
    client must confirm via /clients/{id}/delete-confirm."""
    require_iron(user)
    c = await db.clients.find_one({"_id": client_id, "iron_man_id": user["_id"]})
    if not c:
        raise HTTPException(status_code=404, detail="Client not found")
    if c.get("linked_user_id"):
        raise HTTPException(
            status_code=403,
            detail="Client is signed up. Use /clients/{id}/delete-request and ask client to confirm.",
        )
    await db.clients.delete_one({"_id": client_id})
    await db.entries.delete_many({"client_id": client_id})
    await db.bills.delete_many({"client_id": client_id})
    return {"ok": True}


@router.post("/{client_id}/delete-request", response_model=ClientPublic)
async def request_client_delete(client_id: str, user=Depends(get_current_user)):
    """Iron man requests to remove a linked client. Client must confirm."""
    require_iron(user)
    c = await db.clients.find_one({"_id": client_id, "iron_man_id": user["_id"]})
    if not c:
        raise HTTPException(status_code=404, detail="Client not found")
    if not c.get("linked_user_id"):
        raise HTTPException(status_code=400, detail="Client not linked. Use DELETE directly.")
    await db.clients.update_one(
        {"_id": client_id},
        {"$set": {"delete_requested_at": iso(now_utc())}},
    )
    await create_notification(
        user_id=c["linked_user_id"],
        type_="client_delete_requested",
        title="Your Iron Man wants to remove you",
        message=f"{user['name']} wants to remove you as a client. Confirm to delete your shared records, or deny to keep them.",
        client_id=client_id,
        iron_man_id=user["_id"],
    )
    c2 = await db.clients.find_one({"_id": client_id})
    stats = await client_stats(c2)
    return to_client_public(c2, stats)


@router.post("/{client_id}/delete-confirm")
async def confirm_client_delete(client_id: str, user=Depends(get_current_user)):
    """Client confirms removal of the relationship; deletes client + entries + bills."""
    require_client(user)
    c = await db.clients.find_one({"_id": client_id, "linked_user_id": user["_id"]})
    if not c:
        raise HTTPException(status_code=404, detail="Client record not found")
    if not c.get("delete_requested_at"):
        raise HTTPException(status_code=400, detail="No delete request pending")
    await db.clients.delete_one({"_id": client_id})
    await db.entries.delete_many({"client_id": client_id})
    await db.bills.delete_many({"client_id": client_id})
    await create_notification(
        user_id=c["iron_man_id"],
        type_="client_delete_confirmed",
        title="Client removed",
        message=f"{c['name']} confirmed removal. Records have been deleted.",
        iron_man_id=c["iron_man_id"],
    )
    return {"ok": True}


@router.post("/{client_id}/delete-deny", response_model=ClientPublic)
async def deny_client_delete(client_id: str, user=Depends(get_current_user)):
    """Client denies the iron-man's removal request."""
    require_client(user)
    c = await db.clients.find_one({"_id": client_id, "linked_user_id": user["_id"]})
    if not c:
        raise HTTPException(status_code=404, detail="Client record not found")
    if not c.get("delete_requested_at"):
        raise HTTPException(status_code=400, detail="No delete request pending")
    await db.clients.update_one(
        {"_id": client_id}, {"$set": {"delete_requested_at": None}}
    )
    await create_notification(
        user_id=c["iron_man_id"],
        type_="client_delete_denied",
        title="Removal rejected",
        message=f"{c['name']} did not approve removal. The relationship continues.",
        client_id=client_id,
        iron_man_id=c["iron_man_id"],
    )
    c2 = await db.clients.find_one({"_id": client_id})
    stats = await client_stats(c2)
    return to_client_public(c2, stats)
