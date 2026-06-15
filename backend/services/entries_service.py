"""Entry math + serialization."""
from typing import List, Tuple

from models.entries import EntryItem, EntryPublic


def entry_total(items: List[EntryItem]) -> Tuple[int, float]:
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
