"""Локальный mock Keitaro (:8081) — демонстрация UI без реального ключа.

Запуск: python scripts/mock_keitaro.py
В .env: KEITARO_BASE_URL=http://127.0.0.1:8081
"""

import json

from fastapi import FastAPI, Request

app = FastAPI(title="Mock Keitaro")

GOOGLE = "https://google.com"

DOMAINS = [{"id": 1, "name": "in.posdk.xyz", "state": "active"}]
GROUPS = [{"id": 5, "name": "OTHER"}]
SOURCES = [{"id": 7, "name": "FORTESTS"}]
OFFERS = [
    {"id": 3749, "name": "Miaflow [BEAUTY-RO-BE_0009] [pl - spin ro 1] 2. Основной"},
    {"id": 3717, "name": "Miaflow [BEAUTY-RO-BE_0008] [pl - prize ro 1]"},
    {"id": 4000, "name": "New offer"},
]

NEXT_ID = 100
CAMPAIGNS = {
    2: {
        "id": 2,
        "name": "campaign 2",
        "state": "active",
        "created_at": "2026-11-18 12:00:00",
        "group_id": 5,
        "source_id": 7,
        "domain_ids": [1],
        "schema": {
            "type": "condition",
            "flows": [
                {
                    "type": "condition",
                    "name": "Geo AU → Google",
                    "conditions": [{"type": "country", "values": ["AU"]}],
                    "scheme": {"type": "action", "action_type": "redirect", "url": GOOGLE},
                },
                {
                    "type": "default",
                    "name": "Offers",
                    "scheme": {
                        "type": "offers",
                        "items": [
                            {"offer_id": 3749, "weight": 50},
                            {"offer_id": 3717, "weight": 50},
                        ],
                    },
                },
            ],
        },
    }
}


@app.get("/admin/api/v1/domains")
def domains():
    return DOMAINS


@app.get("/admin/api/v1/groups")
def groups():
    return GROUPS


@app.post("/admin/api/v1/groups")
async def create_group(request: Request):
    body = await request.json()
    item = {"id": 6, "name": body.get("name", "")}
    GROUPS.append(item)
    return item


@app.get("/admin/api/v1/sources")
def sources():
    return SOURCES


@app.post("/admin/api/v1/sources")
async def create_source(request: Request):
    body = await request.json()
    item = {"id": 8, "name": body.get("name", "")}
    SOURCES.append(item)
    return item


@app.get("/admin/api/v1/offers")
def offers():
    return OFFERS


@app.get("/admin/api/v1/campaigns")
def campaigns():
    return list(CAMPAIGNS.values())


@app.post("/admin/api/v1/campaigns")
async def create_campaign(request: Request):
    global NEXT_ID
    body = await request.json()
    cid = NEXT_ID
    NEXT_ID += 1
    created = dict(body, id=cid, state="active", created_at="2026-11-18 15:00:00")
    CAMPAIGNS[cid] = created
    return created


@app.get("/admin/api/v1/campaigns/{campaign_id}")
def get_campaign(campaign_id: int):
    if campaign_id not in CAMPAIGNS:
        return {"error": "not found"}
    return CAMPAIGNS[campaign_id]


@app.put("/admin/api/v1/campaigns/{campaign_id}")
async def update_campaign(campaign_id: int, request: Request):
    if campaign_id not in CAMPAIGNS:
        return {"error": "not found"}
    body = await request.json()
    CAMPAIGNS[campaign_id].update(body)
    return CAMPAIGNS[campaign_id]


@app.get("/admin/api/v1/__state")
def __state():
    return {"count": len(CAMPAIGNS), "names": sorted(c["name"] for c in CAMPAIGNS.values())}


if __name__ == "__main__":
    import uvicorn

    print("Mock Keitaro: http://127.0.0.1:8081  (GET /admin/api/v1/__state — осмотр)")
    uvicorn.run(app, host="127.0.0.1", port=8081)
