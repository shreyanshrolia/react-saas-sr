"""Grihkari Backend - FastAPI + MongoDB
Daily clothes ironing management. Phone+password JWT auth.
Roles: iron_man, client. Auto-link via phone.
"""
import os
import uuid
import hmac
import hashlib
import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import List, Optional, Literal

import bcrypt
import jwt
import razorpay
from dotenv import load_dotenv
from fastapi import FastAPI, APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from motor.motor_asyncio import AsyncIOMotorClient
from pydantic import BaseModel, Field
from starlette.middleware.cors import CORSMiddleware

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / ".env")

MONGO_URL = os.environ["MONGO_URL"]
DB_NAME = os.environ["DB_NAME"]
JWT_SECRET = os.environ.get("JWT_SECRET", "grihkari-dev-secret-change-in-prod")
JWT_ALGO = "HS256"
JWT_EXP_DAYS = 30
TRIAL_DAYS = 45
IRON_PLAN_INR = 49
CLIENT_PLAN_INR = 19
SUBSCRIPTION_DAYS = 30

RAZORPAY_KEY_ID = os.environ.get("RAZORPAY_KEY_ID", "")
RAZORPAY_KEY_SECRET = os.environ.get("RAZORPAY_KEY_SECRET", "")
RAZORPAY_ENABLED = bool(RAZORPAY_KEY_ID and RAZORPAY_KEY_SECRET)
razorpay_client = razorpay.Client(auth=(RAZORPAY_KEY_ID, RAZORPAY_KEY_SECRET)) if RAZORPAY_ENABLED else None

client = AsyncIOMotorClient(MONGO_URL)
db = client[DB_NAME]

app = FastAPI(title="Grihkari API")
api = APIRouter(prefix="/api")

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("grihkari")

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login", auto_error=False)


# ---------- Models ----------
Role = Literal["iron_man", "client"]


class SignupReq(BaseModel):
    name: str = Field(..., min_length=1, max_length=80)
    phone: str = Field(..., min_length=10, max_length=10, pattern=r"^\d{10}$")
    password: str = Field(..., min_length=6, max_length=80)
    role: Role
    address: Optional[str] = Field(None, max_length=300)


class LoginReq(BaseModel):
    phone: str = Field(..., min_length=10, max_length=10, pattern=r"^\d{10}$")
    password: str


class UserPublic(BaseModel):
    id: str
    name: str
    phone: str
    role: Role
    address: Optional[str] = None
    trial_ends_at: Optional[str] = None
    subscription_status: str = "trial"  # trial | active | expired
    subscription_ends_at: Optional[str] = None
    created_at: str


class AuthResp(BaseModel):
    token: str
    user: UserPublic


class ClientAddReq(BaseModel):
    name: str = Field(..., min_length=1, max_length=80)
    phone: str = Field(..., min_length=10, max_length=10, pattern=r"^\d{10}$")
    address: Optional[str] = Field(None, max_length=300)
    default_rate: Optional[float] = Field(10.0, ge=0)


class ClientUpdateReq(BaseModel):
    name: Optional[str] = None
    address: Optional[str] = None
    default_rate: Optional[float] = None


class ClientPublic(BaseModel):
    id: str
    iron_man_id: str
    name: str
    phone: str
    address: Optional[str] = None
    default_rate: float = 10.0
    linked_user_id: Optional[str] = None  # set when client signs up
    delete_requested_at: Optional[str] = None
    created_at: str
    pending_count: int = 0
    current_month_amount: float = 0.0


class EntryItem(BaseModel):
    cloth_type: str = Field(..., min_length=1, max_length=40)
    quantity: int = Field(..., ge=1, le=999)
    rate: float = Field(..., ge=0)


class EntryCreateReq(BaseModel):
    client_id: str
    date_given: Optional[str] = None  # ISO; defaults to now
    items: List[EntryItem] = Field(..., min_length=1)
    notes: Optional[str] = Field(None, max_length=300)


class EntryMarkReturnedReq(BaseModel):
    date_returned: Optional[str] = None


class NotificationPublic(BaseModel):
    id: str
    type: str
    title: str
    message: str
    entry_id: Optional[str] = None
    client_id: Optional[str] = None
    iron_man_id: Optional[str] = None
    read: bool
    created_at: str


class EntryPublic(BaseModel):
    id: str
    iron_man_id: str
    client_id: str
    client_name: str
    client_phone: str
    date_given: str
    date_returned: Optional[str] = None
    items: List[EntryItem]
    total_quantity: int
    total_amount: float
    notes: Optional[str] = None
    status: str  # pending | return_pending | returned
    linked_user_id: Optional[str] = None
    return_requested_at: Optional[str] = None
    delete_requested_at: Optional[str] = None
    created_at: str


class BillPublic(BaseModel):
    id: str
    iron_man_id: str
    client_id: str
    client_name: str
    client_phone: str
    month: str  # YYYY-MM
    total_quantity: int
    clothes_amount: float
    carry_in: float = 0.0
    net_due: float
    amount_paid: float = 0.0
    balance: float
    status: str  # unpaid | partial | paid | overpaid
    total_amount: float  # = net_due (kept for backwards compat)
    paid: bool  # = (status in ['paid', 'overpaid'])
    paid_at: Optional[str] = None  # last payment time
    generated_at: str


class MarkPaidReq(BaseModel):
    paid: bool


class PaymentCreateReq(BaseModel):
    amount: float = Field(..., gt=0)
    notes: Optional[str] = Field(None, max_length=200)


class PaymentPublic(BaseModel):
    id: str
    bill_id: str
    iron_man_id: str
    client_id: str
    client_name: str
    amount: float
    paid_at: str
    notes: Optional[str] = None


class SubscribeReq(BaseModel):
    # Legacy placeholder activation (kept for fallback when RAZORPAY_ENABLED is False).
    plan: Role


class CreateOrderReq(BaseModel):
    plan: Role


class VerifyPaymentReq(BaseModel):
    razorpay_order_id: str
    razorpay_payment_id: str
    razorpay_signature: str


# ---------- Helpers ----------
def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def iso(dt: datetime) -> str:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.isoformat()


def parse_iso(s: str) -> datetime:
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00"))
    except Exception:
        return now_utc()


def hash_pw(pw: str) -> str:
    return bcrypt.hashpw(pw.encode(), bcrypt.gensalt()).decode()


def verify_pw(pw: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(pw.encode(), hashed.encode())
    except Exception:
        return False


def make_token(user_id: str) -> str:
    payload = {
        "sub": user_id,
        "exp": now_utc() + timedelta(days=JWT_EXP_DAYS),
        "iat": now_utc(),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGO)


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


async def get_current_user(token: Optional[str] = Depends(oauth2_scheme)) -> dict:
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGO])
        user_id = payload.get("sub")
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="Invalid token")
    user = await db.users.find_one({"_id": user_id}, {"password_hash": 0})
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    return user


def month_key(dt: datetime) -> str:
    return dt.strftime("%Y-%m")


def current_month_key() -> str:
    return month_key(now_utc())


# ---------- Auth ----------
@api.post("/auth/signup", response_model=AuthResp)
async def signup(req: SignupReq):
    existing = await db.users.find_one({"phone": req.phone})
    if existing:
        raise HTTPException(status_code=400, detail="Phone already registered")
    user_id = str(uuid.uuid4())
    trial_end = now_utc() + timedelta(days=TRIAL_DAYS)
    doc = {
        "_id": user_id,
        "name": req.name.strip(),
        "phone": req.phone,
        "password_hash": hash_pw(req.password),
        "role": req.role,
        "address": req.address,
        "trial_ends_at": iso(trial_end),
        "subscription_status": "trial",
        "subscription_ends_at": iso(trial_end),
        "created_at": iso(now_utc()),
    }
    await db.users.insert_one(doc)

    # Auto-link: if this user is a client, link to all iron_men who added this phone
    # and backfill linked_user_id on existing entries & bills so the client sees historical data
    if req.role == "client":
        await db.clients.update_many(
            {"phone": req.phone, "linked_user_id": None},
            {"$set": {"linked_user_id": user_id}},
        )
        await db.entries.update_many(
            {"client_phone": req.phone, "linked_user_id": None},
            {"$set": {"linked_user_id": user_id}},
        )
        await db.bills.update_many(
            {"client_phone": req.phone, "linked_user_id": None},
            {"$set": {"linked_user_id": user_id}},
        )

    token = make_token(user_id)
    doc.pop("password_hash", None)
    return AuthResp(token=token, user=to_user_public(doc))


@api.post("/auth/login", response_model=AuthResp)
async def login(req: LoginReq):
    user = await db.users.find_one({"phone": req.phone})
    if not user or not verify_pw(req.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid phone or password")
    # refresh subscription status
    await _refresh_subscription(user)
    token = make_token(user["_id"])
    user.pop("password_hash", None)
    return AuthResp(token=token, user=to_user_public(user))


@api.get("/auth/me", response_model=UserPublic)
async def me(user=Depends(get_current_user)):
    await _refresh_subscription(user)
    fresh = await db.users.find_one({"_id": user["_id"]}, {"password_hash": 0})
    return to_user_public(fresh)


async def _refresh_subscription(user: dict):
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


# ---------- Clients (Iron Man only) ----------
def require_iron(user: dict):
    if user["role"] != "iron_man":
        raise HTTPException(status_code=403, detail="Iron Man role required")


def require_client(user: dict):
    if user["role"] != "client":
        raise HTTPException(status_code=403, detail="Client role required")


async def _client_stats(client_doc: dict) -> dict:
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


@api.get("/clients", response_model=List[ClientPublic])
async def list_clients(user=Depends(get_current_user)):
    require_iron(user)
    out: List[ClientPublic] = []
    async for c in db.clients.find({"iron_man_id": user["_id"]}).sort("created_at", -1):
        stats = await _client_stats(c)
        out.append(to_client_public(c, stats))
    return out


@api.post("/clients", response_model=ClientPublic)
async def add_client(req: ClientAddReq, user=Depends(get_current_user)):
    require_iron(user)
    # Avoid duplicate for same iron_man
    dup = await db.clients.find_one(
        {"iron_man_id": user["_id"], "phone": req.phone}
    )
    if dup:
        raise HTTPException(status_code=400, detail="Client with this phone already exists")
    cid = str(uuid.uuid4())
    # Auto-link if a user with that phone+role=client exists
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
    stats = await _client_stats(doc)
    return to_client_public(doc, stats)


@api.get("/clients/{client_id}", response_model=ClientPublic)
async def get_client(client_id: str, user=Depends(get_current_user)):
    require_iron(user)
    c = await db.clients.find_one({"_id": client_id, "iron_man_id": user["_id"]})
    if not c:
        raise HTTPException(status_code=404, detail="Client not found")
    stats = await _client_stats(c)
    return to_client_public(c, stats)


@api.patch("/clients/{client_id}", response_model=ClientPublic)
async def update_client(client_id: str, req: ClientUpdateReq, user=Depends(get_current_user)):
    require_iron(user)
    c = await db.clients.find_one({"_id": client_id, "iron_man_id": user["_id"]})
    if not c:
        raise HTTPException(status_code=404, detail="Client not found")
    updates = {k: v for k, v in req.dict(exclude_unset=True).items() if v is not None}
    if updates:
        await db.clients.update_one({"_id": client_id}, {"$set": updates})
    c2 = await db.clients.find_one({"_id": client_id})
    stats = await _client_stats(c2)
    return to_client_public(c2, stats)


@api.delete("/clients/{client_id}")
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


@api.post("/clients/{client_id}/delete-request", response_model=ClientPublic)
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
    await _create_notification(
        user_id=c["linked_user_id"],
        type_="client_delete_requested",
        title="Your Iron Man wants to remove you",
        message=f"{user['name']} wants to remove you as a client. Confirm to delete your shared records, or deny to keep them.",
        client_id=client_id,
        iron_man_id=user["_id"],
    )
    c2 = await db.clients.find_one({"_id": client_id})
    stats = await _client_stats(c2)
    return to_client_public(c2, stats)


@api.post("/clients/{client_id}/delete-confirm")
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
    await _create_notification(
        user_id=c["iron_man_id"],
        type_="client_delete_confirmed",
        title="Client removed",
        message=f"{c['name']} confirmed removal. Records have been deleted.",
        iron_man_id=c["iron_man_id"],
    )
    return {"ok": True}


@api.post("/clients/{client_id}/delete-deny", response_model=ClientPublic)
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
    await _create_notification(
        user_id=c["iron_man_id"],
        type_="client_delete_denied",
        title="Removal rejected",
        message=f"{c['name']} did not approve removal. The relationship continues.",
        client_id=client_id,
        iron_man_id=c["iron_man_id"],
    )
    c2 = await db.clients.find_one({"_id": client_id})
    stats = await _client_stats(c2)
    return to_client_public(c2, stats)


# ---------- Entries ----------
def entry_total(items: List[EntryItem]) -> tuple[int, float]:
    qty = sum(i.quantity for i in items)
    amt = sum(i.quantity * i.rate for i in items)
    return qty, round(amt, 2)


def to_entry_public(e: dict) -> EntryPublic:
    return EntryPublic(
        id=e["_id"],
        iron_man_id=e["iron_man_id"],
        client_id=e["client_id"],
        client_name=e.get("client_name", ""),
        client_phone=e.get("client_phone", ""),
        date_given=e["date_given"],
        date_returned=e.get("date_returned"),
        items=[EntryItem(**i) for i in e["items"]],
        total_quantity=e["total_quantity"],
        total_amount=e["total_amount"],
        notes=e.get("notes"),
        status=e["status"],
        linked_user_id=e.get("linked_user_id"),
        return_requested_at=e.get("return_requested_at"),
        delete_requested_at=e.get("delete_requested_at"),
        created_at=e["created_at"],
    )


# ---------- Notifications ----------
async def _create_notification(
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


def _items_summary(items: list) -> str:
    parts = []
    for it in items[:3]:
        parts.append(f"{it.get('cloth_type', '')}×{it.get('quantity', 0)}")
    extra = len(items) - 3
    if extra > 0:
        parts.append(f"+{extra} more")
    return ", ".join(parts)


@api.post("/entries", response_model=EntryPublic)
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
    # Notify the client (if signed up)
    if c.get("linked_user_id"):
        await _create_notification(
            user_id=c["linked_user_id"],
            type_="new_entry",
            title="New clothes added",
            message=f"{user['name']} added {qty} pcs ({_items_summary([i.dict() for i in req.items])}) on {iso(given_dt)[:10]}",
            entry_id=eid,
            iron_man_id=user["_id"],
            client_id=c["_id"],
        )
    return to_entry_public(doc)


@api.get("/entries", response_model=List[EntryPublic])
async def list_entries(
    client_id: Optional[str] = None,
    status_filter: Optional[str] = None,
    month: Optional[str] = None,  # YYYY-MM
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


@api.post("/entries/{entry_id}/return", response_model=EntryPublic)
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
        await _create_notification(
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


@api.post("/entries/{entry_id}/return/confirm", response_model=EntryPublic)
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
    await _create_notification(
        user_id=e["iron_man_id"],
        type_="return_confirmed",
        title="Return confirmed",
        message=f"{user['name']} confirmed receipt of {e['total_quantity']} pcs.",
        entry_id=entry_id,
        iron_man_id=e["iron_man_id"],
        client_id=e["client_id"],
    )
    return to_entry_public(await db.entries.find_one({"_id": entry_id}))


@api.post("/entries/{entry_id}/return/deny", response_model=EntryPublic)
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
    await _create_notification(
        user_id=e["iron_man_id"],
        type_="return_denied",
        title="Return rejected",
        message=f"{user['name']} did NOT receive the clothes yet.",
        entry_id=entry_id,
        iron_man_id=e["iron_man_id"],
        client_id=e["client_id"],
    )
    return to_entry_public(await db.entries.find_one({"_id": entry_id}))


@api.post("/entries/{entry_id}/delete-request", response_model=EntryPublic)
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
    await _create_notification(
        user_id=e["iron_man_id"],
        type_="delete_requested",
        title="Client wants to delete an entry",
        message=f"{user['name']} requested deletion of an entry ({e['total_quantity']} pcs on {e['date_given'][:10]}).",
        entry_id=entry_id,
        iron_man_id=e["iron_man_id"],
        client_id=e["client_id"],
    )
    return to_entry_public(await db.entries.find_one({"_id": entry_id}))


@api.post("/entries/{entry_id}/delete-confirm")
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
        await _create_notification(
            user_id=e["linked_user_id"],
            type_="delete_confirmed",
            title="Entry deleted",
            message=f"Your entry for {e['total_quantity']} pcs on {e['date_given'][:10]} was deleted.",
            entry_id=None,
            iron_man_id=e["iron_man_id"],
            client_id=e["client_id"],
        )
    return {"ok": True}


@api.post("/entries/{entry_id}/delete-deny", response_model=EntryPublic)
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
        await _create_notification(
            user_id=e["linked_user_id"],
            type_="delete_denied",
            title="Deletion rejected",
            message=f"{user['name']} did not approve deletion of your entry from {e['date_given'][:10]}.",
            entry_id=entry_id,
            iron_man_id=e["iron_man_id"],
            client_id=e["client_id"],
        )
    return to_entry_public(await db.entries.find_one({"_id": entry_id}))


@api.delete("/entries/{entry_id}")
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


# ---------- Notifications endpoints ----------
def _to_notification(n: dict) -> NotificationPublic:
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


@api.get("/notifications", response_model=List[NotificationPublic])
async def list_notifications(unread_only: bool = False, user=Depends(get_current_user)):
    q: dict = {"user_id": user["_id"]}
    if unread_only:
        q["read"] = False
    out: List[NotificationPublic] = []
    async for n in db.notifications.find(q).sort("created_at", -1).limit(100):
        out.append(_to_notification(n))
    return out


@api.get("/notifications/unread-count")
async def unread_count(user=Depends(get_current_user)):
    n = await db.notifications.count_documents({"user_id": user["_id"], "read": False})
    return {"count": n}


@api.post("/notifications/{notification_id}/read")
async def mark_notification_read(notification_id: str, user=Depends(get_current_user)):
    res = await db.notifications.update_one(
        {"_id": notification_id, "user_id": user["_id"]},
        {"$set": {"read": True}},
    )
    if res.matched_count == 0:
        raise HTTPException(status_code=404, detail="Notification not found")
    return {"ok": True}


@api.post("/notifications/read-all")
async def mark_all_notifications_read(user=Depends(get_current_user)):
    res = await db.notifications.update_many(
        {"user_id": user["_id"], "read": False},
        {"$set": {"read": True}},
    )
    return {"updated": res.modified_count}


# ---------- Bills ----------
def _compute_status(net_due: float, amount_paid: float) -> str:
    if net_due <= 0 and amount_paid <= 0:
        return "paid"
    if amount_paid <= 0:
        return "unpaid"
    if amount_paid >= net_due:
        return "overpaid" if amount_paid > net_due else "paid"
    return "partial"


def to_bill_public(b: dict) -> BillPublic:
    clothes = float(b.get("clothes_amount", b.get("total_amount", 0)))
    carry = float(b.get("carry_in", 0))
    paid = float(b.get("amount_paid", 0))
    net = float(b.get("net_due", clothes + carry))
    bal = net - paid
    bill_status = b.get("status") or _compute_status(net, paid)
    return BillPublic(
        id=b["_id"],
        iron_man_id=b["iron_man_id"],
        client_id=b["client_id"],
        client_name=b.get("client_name", ""),
        client_phone=b.get("client_phone", ""),
        month=b["month"],
        total_quantity=int(b.get("total_quantity", 0)),
        clothes_amount=round(clothes, 2),
        carry_in=round(carry, 2),
        net_due=round(net, 2),
        amount_paid=round(paid, 2),
        balance=round(bal, 2),
        status=bill_status,
        total_amount=round(net, 2),
        paid=bill_status in ("paid", "overpaid"),
        paid_at=b.get("last_paid_at"),
        generated_at=b["generated_at"],
    )


async def _aggregate_bill_for(client_id: str, month: str) -> tuple[int, float]:
    qty = 0
    amt = 0.0
    async for e in db.entries.find({"client_id": client_id, "month_key": month}):
        qty += int(e.get("total_quantity", 0))
        amt += float(e.get("total_amount", 0))
    return qty, round(amt, 2)


async def _get_previous_bill_balance(client_id: str, month: str) -> float:
    """Return the balance (net_due - amount_paid) of the most recent bill before `month`.
    Positive => client still owes; Negative => client overpaid (credit)."""
    prev = await db.bills.find_one(
        {"client_id": client_id, "month": {"$lt": month}},
        sort=[("month", -1)],
    )
    if not prev:
        return 0.0
    net = float(prev.get("net_due", prev.get("total_amount", 0)))
    paid = float(prev.get("amount_paid", 0))
    return round(net - paid, 2)


async def _ensure_bill(iron_man_id: str, client_doc: dict, month: str) -> dict:
    qty, clothes_amount = await _aggregate_bill_for(client_doc["_id"], month)
    carry_in = await _get_previous_bill_balance(client_doc["_id"], month)
    net_due = round(clothes_amount + carry_in, 2)
    existing = await db.bills.find_one({"client_id": client_doc["_id"], "month": month})
    if existing:
        amount_paid = float(existing.get("amount_paid", 0))
        balance = round(net_due - amount_paid, 2)
        status = _compute_status(net_due, amount_paid)
        await db.bills.update_one(
            {"_id": existing["_id"]},
            {"$set": {
                "total_quantity": qty,
                "clothes_amount": clothes_amount,
                "carry_in": carry_in,
                "net_due": net_due,
                "balance": balance,
                "status": status,
                "total_amount": net_due,  # legacy
                "paid": status in ("paid", "overpaid"),  # legacy
            }},
        )
        return await db.bills.find_one({"_id": existing["_id"]})
    bid = str(uuid.uuid4())
    status = _compute_status(net_due, 0.0)
    doc = {
        "_id": bid,
        "iron_man_id": iron_man_id,
        "client_id": client_doc["_id"],
        "client_name": client_doc["name"],
        "client_phone": client_doc["phone"],
        "linked_user_id": client_doc.get("linked_user_id"),
        "month": month,
        "total_quantity": qty,
        "clothes_amount": clothes_amount,
        "carry_in": carry_in,
        "net_due": net_due,
        "amount_paid": 0.0,
        "balance": net_due,
        "status": status,
        "last_paid_at": None,
        # legacy compat
        "total_amount": net_due,
        "paid": False,
        "paid_at": None,
        "generated_at": iso(now_utc()),
    }
    await db.bills.insert_one(doc)
    return doc


@api.post("/bills/generate", response_model=List[BillPublic])
async def generate_bills(month: Optional[str] = None, user=Depends(get_current_user)):
    require_iron(user)
    target_month = month or current_month_key()
    out = []
    async for c in db.clients.find({"iron_man_id": user["_id"]}):
        b = await _ensure_bill(user["_id"], c, target_month)
        # include if has any activity OR carry_in
        if b["net_due"] > 0 or b["total_quantity"] > 0 or b.get("carry_in", 0) != 0 or b.get("amount_paid", 0) > 0:
            out.append(to_bill_public(b))
    return out


@api.get("/bills", response_model=List[BillPublic])
async def list_bills(
    month: Optional[str] = None,
    client_id: Optional[str] = None,
    user=Depends(get_current_user),
):
    q: dict = {}
    if user["role"] == "iron_man":
        q["iron_man_id"] = user["_id"]
        if client_id:
            q["client_id"] = client_id
    else:
        q["linked_user_id"] = user["_id"]
    if month:
        q["month"] = month

    # For iron_man, refresh current-month bills for all clients
    if user["role"] == "iron_man" and (not month or month == current_month_key()):
        async for c in db.clients.find({"iron_man_id": user["_id"]}):
            await _ensure_bill(user["_id"], c, current_month_key())

    out = []
    async for b in db.bills.find(q).sort("month", -1):
        out.append(to_bill_public(b))
    return out


@api.post("/bills/{bill_id}/paid", response_model=BillPublic)
async def mark_bill_paid(bill_id: str, req: MarkPaidReq, user=Depends(get_current_user)):
    """Legacy endpoint: marks the full balance as paid (or unpaid by deleting all payments)."""
    require_iron(user)
    b = await db.bills.find_one({"_id": bill_id, "iron_man_id": user["_id"]})
    if not b:
        raise HTTPException(status_code=404, detail="Bill not found")
    if req.paid:
        # record a payment for the remaining balance
        net_due = float(b.get("net_due", b.get("total_amount", 0)))
        paid = float(b.get("amount_paid", 0))
        remaining = round(net_due - paid, 2)
        if remaining > 0:
            await _create_payment(b, remaining, None)
    else:
        # delete all payments for this bill
        await db.payments.delete_many({"bill_id": bill_id})
        await db.bills.update_one(
            {"_id": bill_id},
            {"$set": {"amount_paid": 0.0, "balance": float(b.get("net_due", 0)),
                      "status": "unpaid", "last_paid_at": None, "paid": False, "paid_at": None}},
        )
    b2 = await db.bills.find_one({"_id": bill_id})
    return to_bill_public(b2)


async def _create_payment(bill: dict, amount: float, notes: Optional[str]) -> dict:
    pid = str(uuid.uuid4())
    now = iso(now_utc())
    pdoc = {
        "_id": pid,
        "iron_man_id": bill["iron_man_id"],
        "client_id": bill["client_id"],
        "client_name": bill.get("client_name", ""),
        "client_phone": bill.get("client_phone", ""),
        "bill_id": bill["_id"],
        "month": bill["month"],
        "amount": float(amount),
        "paid_at": now,
        "notes": notes,
    }
    await db.payments.insert_one(pdoc)
    new_paid = round(float(bill.get("amount_paid", 0)) + float(amount), 2)
    net_due = float(bill.get("net_due", bill.get("total_amount", 0)))
    balance = round(net_due - new_paid, 2)
    bs = _compute_status(net_due, new_paid)
    await db.bills.update_one(
        {"_id": bill["_id"]},
        {"$set": {
            "amount_paid": new_paid,
            "balance": balance,
            "status": bs,
            "last_paid_at": now,
            "paid": bs in ("paid", "overpaid"),
            "paid_at": now if bs in ("paid", "overpaid") else None,
        }},
    )
    return pdoc


@api.post("/bills/{bill_id}/payments", response_model=PaymentPublic)
async def record_payment(bill_id: str, req: PaymentCreateReq, user=Depends(get_current_user)):
    require_iron(user)
    b = await db.bills.find_one({"_id": bill_id, "iron_man_id": user["_id"]})
    if not b:
        raise HTTPException(status_code=404, detail="Bill not found")
    pdoc = await _create_payment(b, req.amount, req.notes)
    return PaymentPublic(
        id=pdoc["_id"],
        bill_id=pdoc["bill_id"],
        iron_man_id=pdoc["iron_man_id"],
        client_id=pdoc["client_id"],
        client_name=pdoc.get("client_name", ""),
        amount=float(pdoc["amount"]),
        paid_at=pdoc["paid_at"],
        notes=pdoc.get("notes"),
    )


@api.get("/bills/{bill_id}/payments", response_model=List[PaymentPublic])
async def list_bill_payments(bill_id: str, user=Depends(get_current_user)):
    b = await db.bills.find_one({"_id": bill_id})
    if not b:
        raise HTTPException(status_code=404, detail="Bill not found")
    if user["role"] == "iron_man" and b["iron_man_id"] != user["_id"]:
        raise HTTPException(status_code=403, detail="Forbidden")
    if user["role"] == "client" and b.get("linked_user_id") != user["_id"]:
        raise HTTPException(status_code=403, detail="Forbidden")
    out = []
    async for p in db.payments.find({"bill_id": bill_id}).sort("paid_at", -1):
        out.append(PaymentPublic(
            id=p["_id"],
            bill_id=p["bill_id"],
            iron_man_id=p["iron_man_id"],
            client_id=p["client_id"],
            client_name=p.get("client_name", ""),
            amount=float(p["amount"]),
            paid_at=p["paid_at"],
            notes=p.get("notes"),
        ))
    return out


@api.delete("/payments/{payment_id}")
async def delete_payment(payment_id: str, user=Depends(get_current_user)):
    require_iron(user)
    p = await db.payments.find_one({"_id": payment_id, "iron_man_id": user["_id"]})
    if not p:
        raise HTTPException(status_code=404, detail="Payment not found")
    await db.payments.delete_one({"_id": payment_id})
    # Recalculate bill totals
    b = await db.bills.find_one({"_id": p["bill_id"]})
    if b:
        total_paid = 0.0
        last_at: Optional[str] = None
        async for pp in db.payments.find({"bill_id": b["_id"]}).sort("paid_at", -1):
            total_paid += float(pp["amount"])
            if last_at is None:
                last_at = pp["paid_at"]
        net_due = float(b.get("net_due", b.get("total_amount", 0)))
        bs = _compute_status(net_due, total_paid)
        await db.bills.update_one(
            {"_id": b["_id"]},
            {"$set": {
                "amount_paid": round(total_paid, 2),
                "balance": round(net_due - total_paid, 2),
                "status": bs,
                "last_paid_at": last_at,
                "paid": bs in ("paid", "overpaid"),
                "paid_at": last_at if bs in ("paid", "overpaid") else None,
            }},
        )
    return {"ok": True}


# ---------- Reports ----------
class MonthlyReport(BaseModel):
    month: str
    total_quantity: int
    total_amount: float
    paid_amount: float
    unpaid_amount: float
    entries_count: int


class ClientReportRow(BaseModel):
    client_id: str
    client_name: str
    client_phone: str
    total_quantity: int
    total_amount: float
    paid_amount: float
    unpaid_amount: float


@api.get("/reports/monthly", response_model=List[MonthlyReport])
async def report_monthly(year: Optional[int] = None, user=Depends(get_current_user)):
    yr = year or now_utc().year
    months: dict = {}
    q: dict = {}
    if user["role"] == "iron_man":
        q["iron_man_id"] = user["_id"]
    else:
        q["linked_user_id"] = user["_id"]
    async for e in db.entries.find(q):
        if not e.get("month_key", "").startswith(str(yr)):
            continue
        m = e["month_key"]
        if m not in months:
            months[m] = {"qty": 0, "amt": 0.0, "count": 0}
        months[m]["qty"] += int(e.get("total_quantity", 0))
        months[m]["amt"] += float(e.get("total_amount", 0))
        months[m]["count"] += 1

    # paid/unpaid from bills
    bq = dict(q)
    paid_map: dict = {}
    async for b in db.bills.find(bq):
        if not b["month"].startswith(str(yr)):
            continue
        rec = paid_map.setdefault(b["month"], {"paid": 0.0, "unpaid": 0.0})
        if b.get("paid"):
            rec["paid"] += float(b.get("total_amount", 0))
        else:
            rec["unpaid"] += float(b.get("total_amount", 0))

    out = []
    for m in sorted(months.keys(), reverse=True):
        pm = paid_map.get(m, {"paid": 0.0, "unpaid": 0.0})
        out.append(MonthlyReport(
            month=m,
            total_quantity=months[m]["qty"],
            total_amount=round(months[m]["amt"], 2),
            paid_amount=round(pm["paid"], 2),
            unpaid_amount=round(pm["unpaid"], 2),
            entries_count=months[m]["count"],
        ))
    return out


@api.get("/reports/yearly")
async def report_yearly(user=Depends(get_current_user)):
    q: dict = {}
    if user["role"] == "iron_man":
        q["iron_man_id"] = user["_id"]
    else:
        q["linked_user_id"] = user["_id"]
    years: dict = {}
    async for e in db.entries.find(q):
        yr = e.get("month_key", "")[:4]
        if not yr:
            continue
        years.setdefault(yr, {"qty": 0, "amt": 0.0, "count": 0})
        years[yr]["qty"] += int(e.get("total_quantity", 0))
        years[yr]["amt"] += float(e.get("total_amount", 0))
        years[yr]["count"] += 1
    out = []
    for yr in sorted(years.keys(), reverse=True):
        out.append({
            "year": yr,
            "total_quantity": years[yr]["qty"],
            "total_amount": round(years[yr]["amt"], 2),
            "entries_count": years[yr]["count"],
        })
    return out


@api.get("/reports/by-client", response_model=List[ClientReportRow])
async def report_by_client(month: Optional[str] = None, user=Depends(get_current_user)):
    require_iron(user)
    rows: dict = {}
    eq = {"iron_man_id": user["_id"]}
    if month:
        eq["month_key"] = month
    async for e in db.entries.find(eq):
        cid = e["client_id"]
        if cid not in rows:
            rows[cid] = {
                "client_id": cid,
                "client_name": e.get("client_name", ""),
                "client_phone": e.get("client_phone", ""),
                "total_quantity": 0,
                "total_amount": 0.0,
                "paid_amount": 0.0,
                "unpaid_amount": 0.0,
            }
        rows[cid]["total_quantity"] += int(e.get("total_quantity", 0))
        rows[cid]["total_amount"] += float(e.get("total_amount", 0))
    bq = {"iron_man_id": user["_id"]}
    if month:
        bq["month"] = month
    async for b in db.bills.find(bq):
        cid = b["client_id"]
        if cid not in rows:
            continue
        if b.get("paid"):
            rows[cid]["paid_amount"] += float(b.get("total_amount", 0))
        else:
            rows[cid]["unpaid_amount"] += float(b.get("total_amount", 0))
    return [
        ClientReportRow(
            client_id=r["client_id"],
            client_name=r["client_name"],
            client_phone=r["client_phone"],
            total_quantity=r["total_quantity"],
            total_amount=round(r["total_amount"], 2),
            paid_amount=round(r["paid_amount"], 2),
            unpaid_amount=round(r["unpaid_amount"], 2),
        )
        for r in sorted(rows.values(), key=lambda x: -x["total_amount"])
    ]


# ---------- Subscription (Razorpay placeholder) ----------
@api.get("/subscription/plans")
async def get_plans():
    return {
        "iron_man": {"amount": IRON_PLAN_INR, "currency": "INR", "interval": "monthly"},
        "client": {"amount": CLIENT_PLAN_INR, "currency": "INR", "interval": "monthly"},
        "trial_days": TRIAL_DAYS,
        "razorpay_enabled": RAZORPAY_ENABLED,
        "razorpay_key_id": RAZORPAY_KEY_ID if RAZORPAY_ENABLED else None,
    }


def _plan_amount(plan: str) -> int:
    if plan == "iron_man":
        return IRON_PLAN_INR
    if plan == "client":
        return CLIENT_PLAN_INR
    raise HTTPException(status_code=400, detail="Invalid plan")


async def _activate_subscription(user_id: str) -> dict:
    # Start from the later of: now, or current subscription_ends_at.
    # This preserves any unused trial days when the user pays mid-trial.
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


@api.post("/subscription/create-order")
async def create_subscription_order(req: CreateOrderReq, user=Depends(get_current_user)):
    """Creates a Razorpay Order for the user's plan. Returns details the client uses to open Checkout."""
    if not RAZORPAY_ENABLED:
        raise HTTPException(status_code=503, detail="Payment gateway not configured")
    if req.plan != user["role"]:
        raise HTTPException(status_code=400, detail="Plan does not match user role")
    amount_inr = _plan_amount(req.plan)
    amount_paise = amount_inr * 100
    # Receipt must be <= 40 chars per Razorpay docs
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

    # Persist order locally for audit
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
        "amount": amount_paise,  # paise
        "amount_inr": amount_inr,
        "currency": "INR",
        "key_id": RAZORPAY_KEY_ID,
        "name": "Grihkari",
        "description": f"{'Iron Man' if req.plan == 'iron_man' else 'Client'} Premium — Monthly",
        "prefill": {
            "name": user["name"],
            "contact": user["phone"],
        },
        "theme_color": "#1E3A8A",
    }


@api.post("/subscription/verify-payment", response_model=UserPublic)
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
        # Only downgrade audit status if not already paid
        await db.subscription_orders.update_one(
            {"_id": req.razorpay_order_id, "status": {"$ne": "paid"}},
            {"$set": {"status": "signature_failed", "verified_at": iso(now_utc())}},
        )
        raise HTTPException(status_code=400, detail="Invalid payment signature")

    # Confirm the order belongs to this user
    order_doc = await db.subscription_orders.find_one({"_id": req.razorpay_order_id})
    if not order_doc:
        raise HTTPException(status_code=404, detail="Order not found")
    if order_doc["user_id"] != user["_id"]:
        raise HTTPException(status_code=403, detail="Order does not belong to user")

    # Idempotent: if already paid, just return current user state without re-extending
    if order_doc.get("status") == "paid":
        fresh = await db.users.find_one({"_id": user["_id"]}, {"password_hash": 0})
        return to_user_public(fresh)

    # Mark order paid + activate
    await db.subscription_orders.update_one(
        {"_id": req.razorpay_order_id},
        {"$set": {
            "status": "paid",
            "razorpay_payment_id": req.razorpay_payment_id,
            "verified_at": iso(now_utc()),
        }},
    )
    fresh = await _activate_subscription(user["_id"])
    await _refresh_subscription(fresh)
    return to_user_public(fresh)


@api.post("/subscription/activate", response_model=UserPublic)
async def activate_subscription(req: SubscribeReq, user=Depends(get_current_user)):
    """Legacy placeholder activation. Only allowed when Razorpay is NOT configured."""
    if RAZORPAY_ENABLED:
        raise HTTPException(status_code=400, detail="Use /subscription/create-order + /subscription/verify-payment")
    if req.plan != user["role"]:
        raise HTTPException(status_code=400, detail="Plan does not match user role")
    fresh = await _activate_subscription(user["_id"])
    await _refresh_subscription(fresh)
    return to_user_public(fresh)


# ---------- Client-side endpoints ----------
@api.get("/my/iron-men")
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


@api.get("/")
async def root():
    return {"app": "Grihkari", "status": "ok"}


app.include_router(api)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def startup():
    await db.users.create_index("phone", unique=True)
    await db.clients.create_index([("iron_man_id", 1), ("phone", 1)], unique=True)
    await db.clients.create_index("phone")
    await db.entries.create_index([("iron_man_id", 1), ("month_key", 1)])
    await db.entries.create_index("client_id")
    await db.entries.create_index("linked_user_id")
    await db.bills.create_index([("client_id", 1), ("month", 1)], unique=True)
    await db.bills.create_index("linked_user_id")
    await db.payments.create_index("bill_id")
    await db.payments.create_index("iron_man_id")
    await db.notifications.create_index([("user_id", 1), ("read", 1), ("created_at", -1)])
    log.info("Grihkari API started")


@app.on_event("shutdown")
async def shutdown():
    client.close()
