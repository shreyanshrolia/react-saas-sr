"""FastAPI dependencies + role guards."""
from typing import Optional

import jwt
from fastapi import Depends, HTTPException
from fastapi.security import OAuth2PasswordBearer

from .config import ADMIN_PASSWORD
from .db import db
from .security import decode_token

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login", auto_error=False)


async def get_current_user(token: Optional[str] = Depends(oauth2_scheme)) -> dict:
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    try:
        payload = decode_token(token)
        user_id = payload.get("sub")
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="Invalid token")
    user = await db.users.find_one({"_id": user_id}, {"password_hash": 0})
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    return user


def require_iron(user: dict) -> None:
    if user["role"] != "iron_man":
        raise HTTPException(status_code=403, detail="Iron Man role required")


def require_client(user: dict) -> None:
    if user["role"] != "client":
        raise HTTPException(status_code=403, detail="Client role required")


def check_admin(token: str) -> None:
    if not ADMIN_PASSWORD or token != f"admin:{ADMIN_PASSWORD}":
        raise HTTPException(status_code=401, detail="Admin auth required")
