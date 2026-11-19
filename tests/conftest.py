"""Фикстуры: mock-транспорт Keitaro + тестовая БД.

Секретов здесь нет: транспорт подменяется на httpx.MockTransport,
реальный ключ для тестов не нужен.
"""

import os
import tempfile
from pathlib import Path

# БД тестов — отдельный файл, до импорта app (движок создаётся на импорте).
_tmpdir = tempfile.mkdtemp(prefix="keitaro-wrapper-tests-")
os.environ["DATABASE_URL"] = f"sqlite:///{Path(_tmpdir) / 'test.db'}"
os.environ["KEITARO_GROUP_NAME"] = "FORTESTS"
os.environ["KEITARO_SOURCE_NAME"] = "FORTESTS"
os.environ["CAMPAIGN_NAME_PREFIX"] = "test_mkrtchyan_"

import json  # noqa: E402
from typing import Any  # noqa: E402

import httpx  # noqa: E402
import pytest  # noqa: E402

from app.keitaro.client import KeitaroClient  # noqa: E402
from app.main import app, get_keitaro  # noqa: E402

GOOGLE = "https://google.com"

DOMAINS = [{"id": 1, "name": "in.posdk.xyz", "state": "active"}]
GROUPS = [{"id": 5, "name": "OTHER"}]
SOURCES = [{"id": 7, "name": "FORTESTS"}]
OFFERS = [
    {"id": 3749, "name": "Miaflow [BEAUTY-RO-BE_0009] [pl - spin ro 1] 2. Основной"},
    {"id": 3717, "name": "Miaflow [BEAUTY-RO-BE_0008] [pl - prize ro 1]"},
    {"id": 4000, "name": "New offer"},
]

STATE: dict[str, Any] = {
    "next_id": 100,
    "campaigns": {},
}

INITIAL_CAMPAIGN_2 = {
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
                        {"offer_id": 3749, "share": 50},
                        {"offer_id": 3717, "share": 50},
                    ],
                },
            },
        ],
    },
}

INITIAL_GROUPS = [{"id": 5, "name": "OTHER"}]


@pytest.fixture(autouse=True)
def reset_state():
    """Каждый тест получает чистый mock: кампания 2 как в ТЗ, группы исходные."""
    STATE["next_id"] = 100
    STATE["campaigns"] = {2: json.loads(json.dumps(INITIAL_CAMPAIGN_2))}
    GROUPS[:] = json.loads(json.dumps(INITIAL_GROUPS))
    yield


def handler(request: httpx.Request) -> httpx.Response:
    method, path = request.method, request.url.path
    body = json.loads(request.content or b"{}") if method in ("POST", "PUT") else {}

    if path == "/admin/api/v1/domains" and method == "GET":
        return httpx.Response(200, json=DOMAINS)
    if path == "/admin/api/v1/groups" and method == "GET":
        return httpx.Response(200, json=GROUPS)
    if path == "/admin/api/v1/groups" and method == "POST":
        item = {"id": 6, "name": body.get("name", "")}
        GROUPS.append(item)
        return httpx.Response(200, json=item)
    if path == "/admin/api/v1/sources" and method == "POST":
        item = {"id": 8, "name": body.get("name", "")}
        SOURCES.append(item)
        return httpx.Response(200, json=item)
    if path == "/admin/api/v1/sources" and method == "GET":
        return httpx.Response(200, json=SOURCES)
    if path == "/admin/api/v1/offers" and method == "GET":
        return httpx.Response(200, json=OFFERS)
    if path == "/admin/api/v1/campaigns" and method == "GET":
        return httpx.Response(200, json=list(STATE["campaigns"].values()))
    if path == "/admin/api/v1/campaigns" and method == "POST":
        cid = STATE["next_id"]
        STATE["next_id"] += 1
        created = dict(body, id=cid, state="active", created_at="2026-11-18 15:00:00")
        STATE["campaigns"][cid] = created
        return httpx.Response(200, json=created)
    if path.startswith("/admin/api/v1/campaigns/") and method == "PUT":
        cid = int(path.rsplit("/", 1)[1])
        if cid not in STATE["campaigns"]:
            return httpx.Response(404, json={"error": "not found"})
        STATE["last_put_body"] = body
        STATE["campaigns"][cid].update(body)
        return httpx.Response(200, json=STATE["campaigns"][cid])
    if path.startswith("/admin/api/v1/campaigns/") and method == "GET":
        cid = int(path.rsplit("/", 1)[1])
        if cid not in STATE["campaigns"]:
            return httpx.Response(404, json={"error": "not found"})
        return httpx.Response(200, json=STATE["campaigns"][cid])
    return httpx.Response(404, json={"error": f"no route {method} {path}"})


@pytest.fixture()
def keitaro_client() -> KeitaroClient:
    return KeitaroClient(transport=httpx.MockTransport(handler))


@pytest.fixture()
def api_client(keitaro_client: KeitaroClient):
    app.dependency_overrides[get_keitaro] = lambda: keitaro_client
    from fastapi.testclient import TestClient

    with TestClient(app) as tc:
        yield tc
    app.dependency_overrides.clear()
