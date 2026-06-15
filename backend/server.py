"""Grihkari Backend - FastAPI entrypoint.

Daily clothes ironing management. Phone+password JWT auth.
Roles: iron_man, client. Auto-link via phone.

The app is split into:
  core/      - config, db, security, time, deps
  models/    - Pydantic request/response schemas
  services/  - business logic (no FastAPI imports)
  routes/    - HTTP endpoints grouped by domain
"""
import logging

from fastapi import APIRouter, FastAPI
from starlette.middleware.cors import CORSMiddleware

from core.db import ensure_indexes, mongo_client
from routes import (
    admin,
    auth,
    bills,
    clients,
    entries,
    misc,
    notifications,
    reports,
    subscription,
)

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("grihkari")

app = FastAPI(title="Grihkari API")

# All endpoints sit under /api so the Kubernetes ingress routes them correctly.
api = APIRouter(prefix="/api")
api.include_router(auth.router)
api.include_router(admin.router)
api.include_router(clients.router)
api.include_router(entries.router)
api.include_router(notifications.router)
api.include_router(bills.router)
api.include_router(reports.router)
api.include_router(subscription.router)
api.include_router(misc.router)

app.include_router(api)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def startup() -> None:
    await ensure_indexes()
    log.info("Grihkari API started")


@app.on_event("shutdown")
async def shutdown() -> None:
    mongo_client.close()
