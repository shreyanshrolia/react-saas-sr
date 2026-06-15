from typing import List, Optional

from pydantic import BaseModel, Field


class EntryItem(BaseModel):
    cloth_type: str = Field(..., min_length=1, max_length=40)
    quantity: int = Field(..., ge=1, le=999)
    rate: float = Field(..., ge=0)


class EntryCreateReq(BaseModel):
    client_id: str
    date_given: Optional[str] = None
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
    status: str  # pending | return_pending | returned
    linked_user_id: Optional[str] = None
    return_requested_at: Optional[str] = None
    delete_requested_at: Optional[str] = None
    created_at: str
