"""Grihkari Backend - FastAPI + MongoDB
Daily clothes ironing management. Phone+password JWT auth.
Roles: iron_man, client. Auto-link via phone.
"""
import os
import uuid
import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import List, Optional, Literal

import bcrypt
import jwt
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
    status: str  # pending | returned
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
    # Razorpay placeholder. In production this would verify payment signature.
    plan: Role


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
    ends = user.get("subscription_ends_at")
    if not ends:
        return
    if parse_iso(ends) < now_utc() and user.get("subscription_status") in ("trial", "active"):
        await db.users.update_one(
            {"_id": user["_id"]}, {"$set": {"subscription_status": "expired"}}
        )
        user["subscription_status"] = "expired"


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
    require_iron(user)
    res = await db.clients.delete_one({"_id": client_id, "iron_man_id": user["_id"]})
    if res.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Client not found")
    await db.entries.delete_many({"client_id": client_id})
    await db.bills.delete_many({"client_id": client_id})
    return {"ok": True}


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
        created_at=e["created_at"],
    )


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
        "month_key": month_key(given_dt),
        "created_at": iso(now_utc()),
    }
    await db.entries.insert_one(doc)
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
        # client sees only their own entries (linked)
        q["linked_user_id"] = user["_id"]
    if status_filter in ("pending", "returned"):
        q["status"] = status_filter
    if month:
        q["month_key"] = month
    out = []
    async for e in db.entries.find(q).sort("date_given", -1):
        out.append(to_entry_public(e))
    return out


@api.post("/entries/{entry_id}/return", response_model=EntryPublic)
async def mark_returned(entry_id: str, req: EntryMarkReturnedReq, user=Depends(get_current_user)):
    require_iron(user)
    e = await db.entries.find_one({"_id": entry_id, "iron_man_id": user["_id"]})
    if not e:
        raise HTTPException(status_code=404, detail="Entry not found")
    ret_dt = parse_iso(req.date_returned) if req.date_returned else now_utc()
    await db.entries.update_one(
        {"_id": entry_id},
        {"$set": {"status": "returned", "date_returned": iso(ret_dt)}},
    )
    e2 = await db.entries.find_one({"_id": entry_id})
    return to_entry_public(e2)


@api.delete("/entries/{entry_id}")
async def delete_entry(entry_id: str, user=Depends(get_current_user)):
    require_iron(user)
    res = await db.entries.delete_one({"_id": entry_id, "iron_man_id": user["_id"]})
    if res.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Entry not found")
    return {"ok": True}


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
    }


@api.post("/subscription/activate", response_model=UserPublic)
async def activate_subscription(req: SubscribeReq, user=Depends(get_current_user)):
    """Placeholder activation. In production this verifies Razorpay payment signature.
    For now, marks the user as active for 30 days.
    """
    if req.plan != user["role"]:
        raise HTTPException(status_code=400, detail="Plan does not match user role")
    new_end = now_utc() + timedelta(days=30)
    await db.users.update_one(
        {"_id": user["_id"]},
        {"$set": {
            "subscription_status": "active",
            "subscription_ends_at": iso(new_end),
        }},
    )
    fresh = await db.users.find_one({"_id": user["_id"]}, {"password_hash": 0})
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
    log.info("Grihkari API started")


@app.on_event("shutdown")
async def shutdown():
    client.close()
