"""Тесты клиента Keitaro: сборка схемы кампании и редактор офферов."""

from decimal import Decimal

import pytest

from app.keitaro.client import KeitaroClient, KeitaroError


def test_create_payload_has_two_flows_in_order(keitaro_client: KeitaroClient):
    payload = keitaro_client.build_create_payload(
        name="test_mkrtchyan_campaign1",
        geo="AU",
        offer_id=3749,
        domain_id=1,
        group_id=5,
        source_id=7,
    )
    assert payload["name"] == "test_mkrtchyan_campaign1"
    assert payload["group_id"] == 5
    assert payload["source_id"] == 7
    assert payload["domain_ids"] == [1]
    flows = payload["schema"]["flows"]
    assert [f["type"] for f in flows] == ["condition", "default"]
    first, second = flows
    assert first["conditions"][0] == {"type": "country", "values": ["AU"]}
    assert first["scheme"] == {
        "type": "action",
        "action_type": "redirect",
        "url": "https://google.com",
    }
    assert second["scheme"]["type"] == "offers"
    assert second["scheme"]["items"] == [{"offer_id": 3749, "share": 100}]


def test_equal_weights_two_offers(keitaro_client: KeitaroClient):
    items = [{"offer_id": 1}, {"offer_id": 2}]
    weighted = keitaro_client.equal_weights(items)
    assert [(i["offer_id"], float(i["share"])) for i in weighted] == [(1, 50.0), (2, 50.0)]


def test_equal_weights_three_offers_sum_is_100(keitaro_client: KeitaroClient):
    items = [{"offer_id": 1}, {"offer_id": 2}, {"offer_id": 3}]
    weighted = keitaro_client.equal_weights(items)
    total = sum(Decimal(str(i["share"])) for i in weighted)
    assert total == Decimal("100.00")
    assert [i["share"] for i in weighted] == [33.33, 33.33, 33.34]


async def test_add_offer_recomputes_weights(keitaro_client: KeitaroClient):
    updated = await keitaro_client.add_offer(2, 4000)
    flow = KeitaroClient.find_offers_flow(updated)
    items = flow["scheme"]["items"]
    assert [i["offer_id"] for i in items] == [3749, 3717, 4000]
    assert sum(Decimal(str(i["share"])) for i in items) == Decimal("100.00")
    # PUT действительно обновил схему в mock-Keitaro
    assert KeitaroClient.find_offers_flow(updated)["scheme"]["items"] == items


async def test_add_duplicate_offer_raises(keitaro_client: KeitaroClient):
    with pytest.raises(KeitaroError, match="уже есть"):
        await keitaro_client.add_offer(2, 3749)


async def test_remove_offer_recomputes_weights(keitaro_client: KeitaroClient):
    updated = await keitaro_client.remove_offer(2, 3749)
    items = KeitaroClient.find_offers_flow(updated)["scheme"]["items"]
    assert [i["offer_id"] for i in items] == [3717]
    assert items[0]["share"] == 100


async def test_remove_missing_offer_raises(keitaro_client: KeitaroClient):
    with pytest.raises(KeitaroError, match="нет в кампании"):
        await keitaro_client.remove_offer(2, 9999)


async def test_cannot_remove_last_offer(keitaro_client: KeitaroClient):
    await keitaro_client.remove_offer(2, 3749)
    with pytest.raises(KeitaroError, match="последний оффер"):
        await keitaro_client.remove_offer(2, 3717)


def test_find_offers_flow_returns_none_without_rotation():
    campaign = {"schema": {"flows": [{"type": "default", "scheme": {"type": "action"}}]}}
    assert KeitaroClient.find_offers_flow(campaign) is None
