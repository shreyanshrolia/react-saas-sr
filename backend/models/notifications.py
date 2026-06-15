from typing import Optional

from pydantic import BaseModel


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
