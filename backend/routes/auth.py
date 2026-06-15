"""Auth routes: signup, login, me, forgot/reset password, security questions."""
import uuid
from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException

from core.config import HELPLINE_PHONE, SECURITY_QUESTIONS, TRIAL_DAYS
from core.db import db
from core.deps import get_current_user
from core.security import hash_pw, make_token, verify_pw
from core.time_utils import iso, now_utc
from models.auth import (
    AuthResp,
    ForgotPasswordReq,
    LoginReq,
    ResetPasswordReq,
    SignupReq,
    UserPublic,
)
from services.users_service import refresh_subscription, to_user_public

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/signup", response_model=AuthResp)
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
        "security_question": req.security_question.strip(),
        "security_answer_hash": hash_pw(req.security_answer.strip().lower()),
        "trial_ends_at": iso(trial_end),
        "subscription_status": "trial",
        "subscription_ends_at": iso(trial_end),
        "created_at": iso(now_utc()),
    }
    await db.users.insert_one(doc)

    # Auto-link: if this user is a client, link to all iron_men who added this phone
    # and backfill linked_user_id on existing entries & bills so the client sees historical data.
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


@router.post("/login", response_model=AuthResp)
async def login(req: LoginReq):
    user = await db.users.find_one({"phone": req.phone})
    if not user or not verify_pw(req.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid phone or password")
    await refresh_subscription(user)
    token = make_token(user["_id"])
    user.pop("password_hash", None)
    return AuthResp(token=token, user=to_user_public(user))


@router.get("/me", response_model=UserPublic)
async def me(user=Depends(get_current_user)):
    await refresh_subscription(user)
    fresh = await db.users.find_one({"_id": user["_id"]}, {"password_hash": 0})
    return to_user_public(fresh)


@router.get("/security-questions")
async def security_questions():
    return {"questions": SECURITY_QUESTIONS}


@router.post("/forgot-password")
async def forgot_password(req: ForgotPasswordReq):
    """Return the user's security question. Returns 404 if phone not found."""
    user = await db.users.find_one({"phone": req.phone})
    if not user or not user.get("security_question"):
        raise HTTPException(status_code=404, detail="No account or no security question set")
    return {
        "phone": user["phone"],
        "name": user["name"],
        "security_question": user["security_question"],
        "helpline": HELPLINE_PHONE,
    }


@router.post("/reset-password", response_model=AuthResp)
async def reset_password(req: ResetPasswordReq):
    user = await db.users.find_one({"phone": req.phone})
    if not user or not user.get("security_answer_hash"):
        raise HTTPException(status_code=404, detail="Account not found")
    if not verify_pw(req.security_answer.strip().lower(), user["security_answer_hash"]):
        raise HTTPException(
            status_code=401,
            detail=f"Wrong answer. Call helpline {HELPLINE_PHONE} if stuck.",
        )
    await db.users.update_one(
        {"_id": user["_id"]}, {"$set": {"password_hash": hash_pw(req.new_password)}}
    )
    await refresh_subscription(user)
    token = make_token(user["_id"])
    fresh = await db.users.find_one({"_id": user["_id"]}, {"password_hash": 0})
    return AuthResp(token=token, user=to_user_public(fresh))
