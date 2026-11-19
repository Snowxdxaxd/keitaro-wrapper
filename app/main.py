"""FastAPI-приложение: обёртка над Keitaro.

Создание кампаний и редактирование офферов. Все обращения к Keitaro —
через app.keitaro.client. Каждое действие пишется в локальную БД (журнал).
"""

import json
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .config import settings
from .db import Base, SessionLocal, engine
from .keitaro import KeitaroClient, KeitaroError
from .models import CampaignAction
from .schemas import CreateCampaignRequest, OfferRequest

STATIC_DIR = Path(__file__).resolve().parent / "static"


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(engine)  # fallback; для прод-пути — alembic upgrade head
    yield


app = FastAPI(title="Keitaro wrapper", lifespan=lifespan)


def get_keitaro() -> KeitaroClient:
    return KeitaroClient()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _log(db, action: str, campaign_id: int | None, name: str, **details) -> None:
    db.add(
        CampaignAction(
            action=action,
            campaign_id=campaign_id,
            campaign_name=name,
            details=json.dumps(details, ensure_ascii=False),
        )
    )
    db.commit()


@app.get("/")
def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/api/reference")
async def reference(keitaro: KeitaroClient = Depends(get_keitaro)) -> dict:
    """Справочники для UI: домены, группы, источники, офферы."""
    domains, groups, sources, offers = await keitaro.list_domains(), await keitaro.list_groups(), await keitaro.list_sources(), await keitaro.list_offers()
    return {
        "domains": [{"id": d.get("id"), "name": d.get("name")} for d in domains],
        "groups": [{"id": g.get("id"), "name": g.get("name")} for g in groups],
        "sources": [{"id": s.get("id"), "name": s.get("name")} for s in sources],
        "offers": [{"id": o.get("id"), "name": o.get("name")} for o in offers],
        "group_name": settings.keitaro_group_name,
        "source_name": settings.keitaro_source_name,
    }


@app.get("/api/campaigns")
async def campaigns(keitaro: KeitaroClient = Depends(get_keitaro)) -> dict:
    items = await keitaro.list_campaigns()
    prefix = settings.campaign_name_prefix
    return {
        "prefix": prefix,
        "items": [
            {
                "id": c.get("id"),
                "name": c.get("name"),
                "state": c.get("state"),
                "created_at": c.get("created_at"),
            }
            for c in items
        ],
    }


@app.get("/api/campaigns/{campaign_id}")
async def campaign_detail(campaign_id: int, keitaro: KeitaroClient = Depends(get_keitaro)) -> dict:
    try:
        c = await keitaro.get_campaign(campaign_id)
    except KeitaroError as exc:
        raise HTTPException(502, str(exc)) from exc
    flows = []
    for flow in c.get("schema", {}).get("flows", []):
        scheme = flow.get("scheme", {})
        entry: dict = {
            "type": flow.get("type"),
            "name": flow.get("name"),
            "conditions": flow.get("conditions", []),
        }
        if scheme.get("type") == "offers":
            entry["offers"] = [
                {"offer_id": i.get("offer_id"), "share": i.get("share", i.get("weight"))}
                for i in scheme.get("items", [])
            ]
        elif scheme.get("type") == "action":
            entry["redirect_url"] = scheme.get("url")
        flows.append(entry)
    return {"id": c.get("id"), "name": c.get("name"), "state": c.get("state"), "flows": flows}


@app.post("/api/campaigns", status_code=201)
async def create_campaign(
    req: CreateCampaignRequest,
    keitaro: KeitaroClient = Depends(get_keitaro),
    db=Depends(get_db),
) -> dict:
    try:
        group = await keitaro.ensure_group(settings.keitaro_group_name)
        source = await keitaro.ensure_source(settings.keitaro_source_name)
        domain = await keitaro.ensure_domain(req.domain_id)
        name = req.name.strip()
        if not name.startswith(settings.campaign_name_prefix):
            name = settings.campaign_name_prefix + name
        payload = keitaro.build_create_payload(
            name=name,
            geo=req.geo,
            offer_id=req.offer_id,
            domain_id=domain["id"],
            group_id=group["id"],
            source_id=source["id"],
        )
        created = await keitaro.create_campaign(payload)
    except KeitaroError as exc:
        raise HTTPException(502, str(exc)) from exc

    campaign_id = created.get("id")
    _log(db, "create", campaign_id, name, geo=req.geo, offer_id=req.offer_id, domain=domain.get("name"))
    return {"id": campaign_id, "name": name, "url": f"{settings.keitaro_base_url}/admin/campaigns/{campaign_id}"}


@app.post("/api/campaigns/{campaign_id}/offers")
async def add_offer(
    campaign_id: int,
    req: OfferRequest,
    keitaro: KeitaroClient = Depends(get_keitaro),
    db=Depends(get_db),
) -> dict:
    try:
        updated = await keitaro.add_offer(campaign_id, req.offer_id)
    except KeitaroError as exc:
        status = 400 if "уже есть" in str(exc) or "нет потока" in str(exc) else 502
        raise HTTPException(status, str(exc)) from exc
    _log(db, "add_offer", campaign_id, updated.get("name", ""), offer_id=req.offer_id)
    return {"ok": True, "campaign_id": campaign_id, "offer_id": req.offer_id}


@app.delete("/api/campaigns/{campaign_id}/offers/{offer_id}")
async def remove_offer(
    campaign_id: int,
    offer_id: int,
    keitaro: KeitaroClient = Depends(get_keitaro),
    db=Depends(get_db),
) -> dict:
    try:
        updated = await keitaro.remove_offer(campaign_id, offer_id)
    except KeitaroError as exc:
        status = 400 if "нет в кампании" in str(exc) or "последний оффер" in str(exc) or "нет потока" in str(exc) else 502
        raise HTTPException(status, str(exc)) from exc
    _log(db, "remove_offer", campaign_id, updated.get("name", ""), offer_id=offer_id)
    return {"ok": True, "campaign_id": campaign_id, "offer_id": offer_id}


@app.get("/api/history")
def history(db=Depends(get_db)) -> dict:
    rows = db.query(CampaignAction).order_by(CampaignAction.id.desc()).limit(50).all()
    return {
        "items": [
            {
                "id": r.id,
                "created_at": r.created_at.isoformat(),
                "action": r.action,
                "campaign_id": r.campaign_id,
                "campaign_name": r.campaign_name,
                "details": json.loads(r.details) if r.details else {},
            }
            for r in rows
        ]
    }


app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
