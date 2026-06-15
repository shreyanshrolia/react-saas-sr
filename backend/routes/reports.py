"""Monthly / yearly / per-client reports."""
from typing import List, Optional

from fastapi import APIRouter, Depends

from core.db import db
from core.deps import get_current_user, require_iron
from core.time_utils import now_utc
from models.reports import ClientReportRow, MonthlyReport

router = APIRouter(prefix="/reports", tags=["reports"])


@router.get("/monthly", response_model=List[MonthlyReport])
async def report_monthly(year: Optional[int] = None, user=Depends(get_current_user)):
    yr = year or now_utc().year
    months: dict = {}
    q: dict = {}
    if user["role"] == "iron_man":
        q["iron_man_id"] = user["_id"]
    else:
        q["linked_user_id"] = user["_id"]
    async for e in db.entries.find(q):
        if not e.get("month_key", "").startswith(str(yr)):
            continue
        m = e["month_key"]
        if m not in months:
            months[m] = {"qty": 0, "amt": 0.0, "count": 0}
        months[m]["qty"] += int(e.get("total_quantity", 0))
        months[m]["amt"] += float(e.get("total_amount", 0))
        months[m]["count"] += 1

    bq = dict(q)
    paid_map: dict = {}
    async for b in db.bills.find(bq):
        if not b["month"].startswith(str(yr)):
            continue
        rec = paid_map.setdefault(b["month"], {"paid": 0.0, "unpaid": 0.0})
        if b.get("paid"):
            rec["paid"] += float(b.get("total_amount", 0))
        else:
            rec["unpaid"] += float(b.get("total_amount", 0))

    out = []
    for m in sorted(months.keys(), reverse=True):
        pm = paid_map.get(m, {"paid": 0.0, "unpaid": 0.0})
        out.append(MonthlyReport(
            month=m,
            total_quantity=months[m]["qty"],
            total_amount=round(months[m]["amt"], 2),
            paid_amount=round(pm["paid"], 2),
            unpaid_amount=round(pm["unpaid"], 2),
            entries_count=months[m]["count"],
        ))
    return out


@router.get("/yearly")
async def report_yearly(user=Depends(get_current_user)):
    q: dict = {}
    if user["role"] == "iron_man":
        q["iron_man_id"] = user["_id"]
    else:
        q["linked_user_id"] = user["_id"]
    years: dict = {}
    async for e in db.entries.find(q):
        yr = e.get("month_key", "")[:4]
        if not yr:
            continue
        years.setdefault(yr, {"qty": 0, "amt": 0.0, "count": 0})
        years[yr]["qty"] += int(e.get("total_quantity", 0))
        years[yr]["amt"] += float(e.get("total_amount", 0))
        years[yr]["count"] += 1
    out = []
    for yr in sorted(years.keys(), reverse=True):
        out.append({
            "year": yr,
            "total_quantity": years[yr]["qty"],
            "total_amount": round(years[yr]["amt"], 2),
            "entries_count": years[yr]["count"],
        })
    return out


@router.get("/by-client", response_model=List[ClientReportRow])
async def report_by_client(month: Optional[str] = None, user=Depends(get_current_user)):
    require_iron(user)
    rows: dict = {}
    eq = {"iron_man_id": user["_id"]}
    if month:
        eq["month_key"] = month
    async for e in db.entries.find(eq):
        cid = e["client_id"]
        if cid not in rows:
            rows[cid] = {
                "client_id": cid,
                "client_name": e.get("client_name", ""),
                "client_phone": e.get("client_phone", ""),
                "total_quantity": 0,
                "total_amount": 0.0,
                "paid_amount": 0.0,
                "unpaid_amount": 0.0,
            }
        rows[cid]["total_quantity"] += int(e.get("total_quantity", 0))
        rows[cid]["total_amount"] += float(e.get("total_amount", 0))
    bq = {"iron_man_id": user["_id"]}
    if month:
        bq["month"] = month
    async for b in db.bills.find(bq):
        cid = b["client_id"]
        if cid not in rows:
            continue
        if b.get("paid"):
            rows[cid]["paid_amount"] += float(b.get("total_amount", 0))
        else:
            rows[cid]["unpaid_amount"] += float(b.get("total_amount", 0))
    return [
        ClientReportRow(
            client_id=r["client_id"],
            client_name=r["client_name"],
            client_phone=r["client_phone"],
            total_quantity=r["total_quantity"],
            total_amount=round(r["total_amount"], 2),
            paid_amount=round(r["paid_amount"], 2),
            unpaid_amount=round(r["unpaid_amount"], 2),
        )
        for r in sorted(rows.values(), key=lambda x: -x["total_amount"])
    ]
