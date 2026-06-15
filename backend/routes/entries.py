"""Entry CRUD + return + delete-request workflows."""
import uuid
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException

from core.db import db
from core.deps import get_current_user, require_client, require_iron
from core.time_utils import iso, month_key, now_utc, parse_iso
from models.entries import EntryCreateReq, EntryMarkReturnedReq, EntryPublic
from services.entries_service import entry_total, to_entry_public
from services.notifications_service import create_notification, items_summary

router = APIRouter(prefix="/entries", tags=["entries"])


@router.post("", response_model=EntryPublic)
async def create_entry(req: EntryCreateReq, user=Depends(get_current_user)):
    require_iron(user)
    c = await db.clients.find_one({"_id": req.client_id, "iron_man_id": user["_id"]})
    if not c:
        raise HTTPException(status_code=404, detail="Client not found")
    given_dt = parse_iso(req.date_given) if req.date_given else now_utc()
    qty, amt = entry_total(req.items)
    eid = str(uuid.uuid4())
    doc = {
        "_id": eid,
        "iron_man_id": user["_id"],
        "client_id": c["_id"],
        "client_name": c["name"],
        "client_phone": c["phone"],
        "linked_user_id": c.get("linked_user_id"),
        "date_given": iso(given_dt),
        "date_returned": None,
        "items": [i.dict() for i in req.items],
        "total_quantity": qty,
        "total_amount": amt,
        "notes": req.notes,
        "status": "pending",
        "return_requested_at": None,
        "delete_requested_at": None,
        "month_key": month_key(given_dt),
        "created_at": iso(now_utc()),
    }
    await db.entries.insert_one(doc)
    if c.get("linked_user_id"):
        await create_notification(
            user_id=c["linked_user_id"],
            type_="new_entry",
            title="New clothes added",
            message=f"{user['name']} added {qty} pcs ({items_summary([i.dict() for i in req.items])}) on {iso(given_dt)[:10]}",
            entry_id=eid,
            iron_man_id=user["_id"],
            client_id=c["_id"],
        )
    return to_entry_public(doc)


@router.get("", response_model=List[EntryPublic])
async def list_entries(
    client_id: Optional[str] = None,
    status_filter: Optional[str] = None,
    month: Optional[str] = None,
    user=Depends(get_current_user),
):
    q: dict = {}
    if user["role"] == "iron_man":
        q["iron_man_id"] = user["_id"]
        if client_id:
            q["client_id"] = client_id
    else:
        q["linked_user_id"] = user["_id"]
    if status_filter in ("pending", "return_pending", "returned"):
        q["status"] = status_filter
    if month:
        q["month_key"] = month
    out = []
    async for e in db.entries.find(q).sort("date_given", -1):
        out.append(to_entry_public(e))
    return out


@router.post("/{entry_id}/return", response_model=EntryPublic)
async def mark_returned(entry_id: str, req: EntryMarkReturnedReq, user=Depends(get_current_user)):
    """Iron man marks entry as returned. If the client is signed up (linked_user_id),
    transitions to 'return_pending' and creates a notification for the client to confirm.
    If unlinked, transitions directly to 'returned'."""
    require_iron(user)
    e = await db.entries.find_one({"_id": entry_id, "iron_man_id": user["_id"]})
    if not e:
        raise HTTPException(status_code=404, detail="Entry not found")
    if e["status"] == "returned":
        return to_entry_public(e)
    now = iso(now_utc())
    if e.get("linked_user_id"):
        await db.entries.update_one(
            {"_id": entry_id},
            {"$set": {"status": "return_pending", "return_requested_at": now}},
        )
        await create_notification(
            user_id=e["linked_user_id"],
            type_="return_requested",
            title="Iron Man returned your clothes",
            message=f"{user['name']} says they returned your clothes ({e['total_quantity']} pcs). Please confirm.",
            entry_id=entry_id,
            iron_man_id=user["_id"],
            client_id=e["client_id"],
        )
    else:
        ret_dt = parse_iso(req.date_returned) if req.date_returned else now_utc()
        await db.entries.update_one(
            {"_id": entry_id},
            {"$set": {"status": "returned", "date_returned": iso(ret_dt), "return_requested_at": None}},
        )
    return to_entry_public(await db.entries.find_one({"_id": entry_id}))


@router.post("/{entry_id}/return/confirm", response_model=EntryPublic)
async def confirm_return(entry_id: str, user=Depends(get_current_user)):
    """Client confirms the iron-man's return claim."""
    require_client(user)
    e = await db.entries.find_one({"_id": entry_id, "linked_user_id": user["_id"]})
    if not e:
        raise HTTPException(status_code=404, detail="Entry not found")
    if e["status"] != "return_pending":
        raise HTTPException(status_code=400, detail="Entry not awaiting confirmation")
    now = iso(now_utc())
    await db.entries.update_one(
        {"_id": entry_id},
        {"$set": {"status": "returned", "date_returned": now, "return_requested_at": None}},
    )
    await create_notification(
        user_id=e["iron_man_id"],
        type_="return_confirmed",
        title="Return confirmed",
        message=f"{user['name']} confirmed receipt of {e['total_quantity']} pcs.",
        entry_id=entry_id,
        iron_man_id=e["iron_man_id"],
        client_id=e["client_id"],
    )
    return to_entry_public(await db.entries.find_one({"_id": entry_id}))


@router.post("/{entry_id}/return/deny", response_model=EntryPublic)
async def deny_return(entry_id: str, user=Depends(get_current_user)):
    """Client denies the iron-man's return claim."""
    require_client(user)
    e = await db.entries.find_one({"_id": entry_id, "linked_user_id": user["_id"]})
    if not e:
        raise HTTPException(status_code=404, detail="Entry not found")
    if e["status"] != "return_pending":
        raise HTTPException(status_code=400, detail="Entry not awaiting confirmation")
    await db.entries.update_one(
        {"_id": entry_id},
        {"$set": {"status": "pending", "return_requested_at": None}},
    )
    await create_notification(
        user_id=e["iron_man_id"],
        type_="return_denied",
        title="Return rejected",
        message=f"{user['name']} did NOT receive the clothes yet.",
        entry_id=entry_id,
        iron_man_id=e["iron_man_id"],
        client_id=e["client_id"],
    )
    return to_entry_public(await db.entries.find_one({"_id": entry_id}))


@router.post("/{entry_id}/delete-request", response_model=EntryPublic)
async def request_entry_delete(entry_id: str, user=Depends(get_current_user)):
    """Client requests deletion of an entry. Iron man must confirm."""
    require_client(user)
    e = await db.entries.find_one({"_id": entry_id, "linked_user_id": user["_id"]})
    if not e:
        raise HTTPException(status_code=404, detail="Entry not found")
    await db.entries.update_one(
        {"_id": entry_id},
        {"$set": {"delete_requested_at": iso(now_utc())}},
    )
    await create_notification(
        user_id=e["iron_man_id"],
        type_="delete_requested",
        title="Client wants to delete an entry",
        message=f"{user['name']} requested deletion of an entry ({e['total_quantity']} pcs on {e['date_given'][:10]}).",
        entry_id=entry_id,
        iron_man_id=e["iron_man_id"],
        client_id=e["client_id"],
    )
    return to_entry_public(await db.entries.find_one({"_id": entry_id}))


@router.post("/{entry_id}/delete-confirm")
async def confirm_entry_delete(entry_id: str, user=Depends(get_current_user)):
    """Iron man confirms deletion."""
    require_iron(user)
    e = await db.entries.find_one({"_id": entry_id, "iron_man_id": user["_id"]})
    if not e:
        raise HTTPException(status_code=404, detail="Entry not found")
    if not e.get("delete_requested_at"):
        raise HTTPException(status_code=400, detail="No delete request pending")
    await db.entries.delete_one({"_id": entry_id})
    if e.get("linked_user_id"):
        await create_notification(
            user_id=e["linked_user_id"],
            type_="delete_confirmed",
            title="Entry deleted",
            message=f"Your entry for {e['total_quantity']} pcs on {e['date_given'][:10]} was deleted.",
            entry_id=None,
            iron_man_id=e["iron_man_id"],
            client_id=e["client_id"],
        )
    return {"ok": True}


@router.post("/{entry_id}/delete-deny", response_model=EntryPublic)
async def deny_entry_delete(entry_id: str, user=Depends(get_current_user)):
    """Iron man denies the client's deletion request."""
    require_iron(user)
    e = await db.entries.find_one({"_id": entry_id, "iron_man_id": user["_id"]})
    if not e:
        raise HTTPException(status_code=404, detail="Entry not found")
    if not e.get("delete_requested_at"):
        raise HTTPException(status_code=400, detail="No delete request pending")
    await db.entries.update_one(
        {"_id": entry_id}, {"$set": {"delete_requested_at": None}}
    )
    if e.get("linked_user_id"):
        await create_notification(
            user_id=e["linked_user_id"],
            type_="delete_denied",
            title="Deletion rejected",
            message=f"{user['name']} did not approve deletion of your entry from {e['date_given'][:10]}.",
            entry_id=entry_id,
            iron_man_id=e["iron_man_id"],
            client_id=e["client_id"],
        )
    return to_entry_public(await db.entries.find_one({"_id": entry_id}))


@router.delete("/{entry_id}")
async def delete_entry(entry_id: str, user=Depends(get_current_user)):
    """Hard-delete an entry. Only allowed for iron-man IF the client is not signed up.
    For signed-up clients, the client must request deletion via /delete-request and
    the iron-man must confirm via /delete-confirm."""
    require_iron(user)
    e = await db.entries.find_one({"_id": entry_id, "iron_man_id": user["_id"]})
    if not e:
        raise HTTPException(status_code=404, detail="Entry not found")
    if e.get("linked_user_id"):
        raise HTTPException(
            status_code=403,
            detail="Client is signed up. Ask the client to request deletion.",
        )
    await db.entries.delete_one({"_id": entry_id})
    return {"ok": True}
