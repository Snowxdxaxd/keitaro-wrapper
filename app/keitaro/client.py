"""Клиент Admin API Keitaro.

Все обращения к трекеру — через этот модуль. Формы payload'ов сверены с
живым инстансом (GET существующей кампании показывает реальную структуру
schema/flows) и с публичной документацией Keitaro.
"""

from typing import Any

import httpx

from ..config import settings


class KeitaroError(RuntimeError):
    """Ошибка API Keitaro (сеть, статус, неожиданный ответ)."""


class KeitaroClient:
    """Асинхронный клиент. Заголовок Api-Key обязателен для всех запросов."""

    def __init__(
        self,
        base_url: str | None = None,
        api_key: str | None = None,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.base_url = (base_url or settings.keitaro_base_url).rstrip("/")
        self.api_key = api_key or settings.keitaro_api_key
        headers = {"Api-Key": self.api_key, "Content-Type": "application/json"}
        self._client = httpx.AsyncClient(
            base_url=self.base_url, headers=headers, timeout=30,
            transport=transport,
        )

    async def aclose(self) -> None:
        await self._client.aclose()

    async def _request(self, method: str, path: str, json: Any | None = None) -> Any:
        resp = await self._client.request(method, path, json=json)
        if resp.status_code >= 400:
            raise KeitaroError(
                f"Keitaro {method} {path} → HTTP {resp.status_code}: {resp.text[:300]}"
            )
        return resp.json()

    # --- справочники -------------------------------------------------------

    async def list_domains(self) -> list[dict[str, Any]]:
        return await self._request("GET", "/admin/api/v1/domains")

    async def list_groups(self) -> list[dict[str, Any]]:
        return await self._request("GET", "/admin/api/v1/groups")

    async def list_sources(self) -> list[dict[str, Any]]:
        return await self._request("GET", "/admin/api/v1/sources")

    async def list_offers(self) -> list[dict[str, Any]]:
        return await self._request("GET", "/admin/api/v1/offers")

    async def list_campaigns(self) -> list[dict[str, Any]]:
        return await self._request("GET", "/admin/api/v1/campaigns")

    async def get_campaign(self, campaign_id: int) -> dict[str, Any]:
        return await self._request("GET", f"/admin/api/v1/campaigns/{campaign_id}")

    # --- создание группы/источника ----------------------------------------

    async def _ensure_named(self, list_path: str, create_path: str, name: str) -> dict[str, Any]:
        """Возвращает запись с нужным name; если нет — создаёт."""
        items = await self._request("GET", list_path)
        for item in items:
            if str(item.get("name", "")).strip().lower() == name.strip().lower():
                return item
        return await self._request("POST", create_path, {"name": name})

    async def ensure_group(self, name: str) -> dict[str, Any]:
        return await self._ensure_named("/admin/api/v1/groups", "/admin/api/v1/groups", name)

    async def ensure_source(self, name: str) -> dict[str, Any]:
        return await self._ensure_named("/admin/api/v1/sources", "/admin/api/v1/sources", name)

    async def ensure_domain(self, domain_id: int | None) -> dict[str, Any]:
        """Возвращает домен: указанный ID или первый активный из списка."""
        domains = await self.list_domains()
        active = [d for d in domains if d.get("state", "active") == "active"]
        if domain_id is not None:
            for d in domains:
                if d.get("id") == domain_id:
                    return d
            raise KeitaroError(f"Домен id={domain_id} не найден в Keitaro")
        if not active:
            raise KeitaroError("В Keitaro нет активных доменов")
        return active[0]

    # --- кампании ----------------------------------------------------------

    async def create_campaign(self, payload: dict[str, Any]) -> dict[str, Any]:
        return await self._request("POST", "/admin/api/v1/campaigns", payload)

    async def update_campaign(self, campaign_id: int, payload: dict[str, Any]) -> dict[str, Any]:
        return await self._request("PUT", f"/admin/api/v1/campaigns/{campaign_id}", payload)

    # --- сборка схемы кампании --------------------------------------------

    def build_create_payload(
        self,
        name: str,
        geo: str,
        offer_id: int,
        domain_id: int,
        group_id: int,
        source_id: int,
    ) -> dict[str, Any]:
        """Кампания из двух потоков: (1) страна == geo → Google, (2) дефолт → оффер.

        Первый поток — условный: фильтр по стране, редирект на Google.
        Второй — дефолтный, без условий, ротация офферов с весами
        (в создаваемой кампании оффер один, поэтому вес 100).
        Порядок потоков важен: условный идёт первым.
        """
        return {
            "name": name,
            "group_id": group_id,
            "source_id": source_id,
            "domain_ids": [domain_id],
            "state": "active",
            "cost_model": "CPC",
            "cost_currency": "USD",
            "cost_value": 0,
            "schema": {
                "type": "condition",
                "flows": [
                    {
                        "type": "condition",
                        "name": f"Geo {geo} → Google",
                        "conditions": [{"type": "country", "values": [geo.upper()]}],
                        "scheme": {
                            "type": "action",
                            "action_type": "redirect",
                            "url": settings.google_redirect_url,
                        },
                    },
                    {
                        "type": "default",
                        "name": "Offers",
                        "scheme": {
                            "type": "offers",
                            "items": [{"offer_id": offer_id, "share": 100}],
                        },
                    },
                ],
            },
        }

    # --- редактор офферов ---------------------------------------------------

    @staticmethod
    def find_offers_flow(campaign: dict[str, Any]) -> dict[str, Any] | None:
        """Ищет поток с ротацией офферов (scheme.type == 'offers')."""
        for flow in campaign.get("schema", {}).get("flows", []):
            if flow.get("scheme", {}).get("type") == "offers":
                return flow
        return None

    @staticmethod
    def equal_weights(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Пересчитывает веса равными долями, сумма строго 100.00.

        Классика: 3 оффера → 33.33 / 33.33 / 33.34 (последний забирает остаток).
        Поле доли в живой схеме Keitaro называется share.
        """
        n = len(items)
        if n == 0:
            return []
        base = round(100 / n, 2)
        weights = [base] * n
        weights[-1] = round(100 - base * (n - 1), 2)
        return [dict(item, share=w) for item, w in zip(items, weights)]

    async def add_offer(self, campaign_id: int, offer_id: int) -> dict[str, Any]:
        campaign = await self.get_campaign(campaign_id)
        flow = self.find_offers_flow(campaign)
        if flow is None:
            raise KeitaroError(
                f"В кампании {campaign_id} нет потока с ротацией офферов"
            )
        items = flow["scheme"].get("items", [])
        if any(int(i.get("offer_id")) == offer_id for i in items):
            raise KeitaroError(f"Оффер {offer_id} уже есть в кампании {campaign_id}")
        items.append({"offer_id": offer_id, "share": 0})
        flow["scheme"]["items"] = self.equal_weights(items)
        return await self.update_campaign(campaign_id, campaign)

    async def remove_offer(self, campaign_id: int, offer_id: int) -> dict[str, Any]:
        campaign = await self.get_campaign(campaign_id)
        flow = self.find_offers_flow(campaign)
        if flow is None:
            raise KeitaroError(
                f"В кампании {campaign_id} нет потока с ротацией офферов"
            )
        items = flow["scheme"].get("items", [])
        rest = [i for i in items if int(i.get("offer_id")) != offer_id]
        if len(rest) == len(items):
            raise KeitaroError(f"Оффера {offer_id} нет в кампании {campaign_id}")
        if not rest:
            raise KeitaroError(
                "Нельзя удалить последний оффер: поток должен вести хотя бы на один оффер"
            )
        flow["scheme"]["items"] = self.equal_weights(rest)
        return await self.update_campaign(campaign_id, campaign)
