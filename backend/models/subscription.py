from pydantic import BaseModel

from . import Role


class SubscribeReq(BaseModel):
    # Legacy placeholder activation (kept for fallback when Razorpay is not configured).
    plan: Role


class CreateOrderReq(BaseModel):
    plan: Role


class VerifyPaymentReq(BaseModel):
    razorpay_order_id: str
    razorpay_payment_id: str
    razorpay_signature: str
