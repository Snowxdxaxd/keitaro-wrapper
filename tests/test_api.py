"""API-тесты обёртки: создание кампании, редактор, журнал."""

import unittest

from decimal import Decimal


def test_create_campaign_adds_prefix_and_logs(api_client):
    resp = api_client.post(
        "/api/campaigns",
        json={"name": "campaign1", "geo": "au", "offer_id": 4000},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "test_mkrtchyan_campaign1"
    assert data["id"] >= 100


def test_geo_validation(api_client):
    resp = api_client.post(
        "/api/campaigns", json={"name": "x", "geo": "auu", "offer_id": 4000}
    )
    assert resp.status_code == 422


def test_campaign_detail_returns_normalized_flows(api_client):
    resp = api_client.get("/api/campaigns/2")
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == 2
    first, second = data["flows"]
    assert first["redirect_url"] == "https://google.com"
    assert first["conditions"][0]["values"] == ["AU"]
    assert second["offers"] == [
        {"offer_id": 3749, "share": 50},
        {"offer_id": 3717, "share": 50},
    ]


def test_add_offer_via_api(api_client):
    resp = api_client.post("/api/campaigns/2/offers", json={"offer_id": 4000})
    assert resp.status_code == 200
    detail = api_client.get("/api/campaigns/2").json()
    offers = detail["flows"][1]["offers"]
    assert [o["offer_id"] for o in offers] == [3749, 3717, 4000]
    total = sum(Decimal(str(o["share"])) for o in offers)
    assert total == Decimal("100.00")


def test_add_duplicate_offer_via_api_returns_400(api_client):
    resp = api_client.post("/api/campaigns/2/offers", json={"offer_id": 3749})
    assert resp.status_code == 400
    assert "уже есть" in resp.json()["detail"]


def test_remove_offer_via_api(api_client):
    resp = api_client.delete("/api/campaigns/2/offers/3749")
    assert resp.status_code == 200
    offers = api_client.get("/api/campaigns/2").json()["flows"][1]["offers"]
    assert [o["offer_id"] for o in offers] == [3717]
    assert offers[0]["share"] == 100


def test_cannot_remove_last_offer_via_api(api_client):
    api_client.delete("/api/campaigns/2/offers/3749")
    resp = api_client.delete("/api/campaigns/2/offers/3717")
    assert resp.status_code == 400
    assert "последний оффер" in resp.json()["detail"]


def test_history_written_for_actions(api_client):
    api_client.post("/api/campaigns", json={"name": "campaign1", "geo": "AU", "offer_id": 4000})
    api_client.post("/api/campaigns/2/offers", json={"offer_id": 4000})
    api_client.delete("/api/campaigns/2/offers/3749")
    data = api_client.get("/api/history").json()
    actions = [i["action"] for i in data["items"]]
    assert actions.count("create") >= 1
    assert actions.count("add_offer") >= 1
    assert actions.count("remove_offer") >= 1


class TestReviewFixes:
    """Регрессии по итогам ревью: контракт PUT, 404-маппинг, пустое имя."""

    def test_put_sends_only_editable_fields(self, api_client):
        # add_offer -> PUT не должен содержать read-only поля (id, created_at)
        api_client.post("/api/campaigns/2/offers", json={"offer_id": 4000})
        import conftest
        put = conftest.STATE.get("last_put_body") or {}
        assert put, "PUT не зафиксирован"
        assert "schema" in put and "name" in put
        for read_only in ("id", "created_at"):
            assert read_only not in put, f"read-only поле {read_only} ушло в PUT"

    def test_unknown_campaign_returns_404(self, api_client):
        resp = api_client.get("/api/campaigns/999999")
        assert resp.status_code == 404

    def test_blank_name_after_strip_returns_422(self, api_client):
        resp = api_client.post("/api/campaigns", json={"name": "   ", "geo": "AU", "offer_id": 4000})
        assert resp.status_code == 422

    def test_history_dates_marked_as_utc(self, api_client):
        # SQLite отдаёт наивное UTC время — сериализация должна добавлять Z,
        # иначе new Date() в браузере показывает время со сдвигом пояса
        api_client.post("/api/campaigns", json={"name": "campaign1", "geo": "AU", "offer_id": 4000})
        data = api_client.get("/api/history").json()
        assert data["items"], "журнал пуст"
        assert data["items"][0]["created_at"].endswith("Z")

    def test_name_longer_than_255_with_prefix_returns_422(self, api_client):
        resp = api_client.post("/api/campaigns", json={"name": "x" * 250, "geo": "AU", "offer_id": 4000})
        assert resp.status_code == 422

    def test_put_items_do_not_carry_weight_key(self, api_client):
        # равные доли пишутся в share; старый ключ weight не должен соседствовать
        import conftest
        api_client.post("/api/campaigns/2/offers", json={"offer_id": 4000})
        put = conftest.STATE.get("last_put_body") or {}
        offers_flow = next(
            f for f in put["schema"]["flows"] if f["scheme"]["type"] == "offers"
        )
        for item in offers_flow["scheme"]["items"]:
            assert "share" in item and "weight" not in item

    def test_add_offer_unknown_campaign_returns_404(self, api_client):
        resp = api_client.post("/api/campaigns/999999/offers", json={"offer_id": 4000})
        assert resp.status_code == 404
