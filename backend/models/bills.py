from typing import Optional

from pydantic import BaseModel, Field


class BillPublic(BaseModel):
    id: str
    iron_man_id: str
    client_id: str
    client_name: str
    client_phone: str
    month: str
    total_quantity: int
    clothes_amount: float
    carry_in: float = 0.0
    net_due: float
    amount_paid: float = 0.0
    balance: float
    status: str
    total_amount: float  # legacy = net_due
    paid: bool          # legacy = status in (paid, overpaid)
    paid_at: Optional[str] = None
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
