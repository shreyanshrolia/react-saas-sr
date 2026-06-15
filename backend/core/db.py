"""MongoDB connection. Single client/db for the whole app."""
from motor.motor_asyncio import AsyncIOMotorClient

from .config import DB_NAME, MONGO_URL

mongo_client = AsyncIOMotorClient(MONGO_URL)
db = mongo_client[DB_NAME]


async def ensure_indexes() -> None:
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
    await db.notifications.create_index([("user_id", 1), ("read", 1), ("created_at", -1)])
