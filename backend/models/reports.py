from pydantic import BaseModel


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
