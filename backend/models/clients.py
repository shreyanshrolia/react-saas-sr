from typing import Optional

from pydantic import BaseModel, Field


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
    linked_user_id: Optional[str] = None
    delete_requested_at: Optional[str] = None
    created_at: str
    pending_count: int = 0
    current_month_amount: float = 0.0
