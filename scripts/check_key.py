"""Проверка API-ключа Keitaro из .env. Ключ не выводится.

Запуск: python scripts/check_key.py
"""

import asyncio
import sys
from pathlib import Path

import httpx


def load_env() -> dict[str, str]:
    cfg = {}
    env = Path(".env")
    if not env.exists():
        sys.exit("Файл .env не найден в этой папке")
    for line in env.read_text(encoding="utf-8").splitlines():
        if "=" in line and not line.strip().startswith("#"):
            k, _, v = line.partition("=")
            cfg[k.strip()] = v.strip()
    return cfg


async def main() -> None:
    cfg = load_env()
    base = cfg.get("KEITARO_BASE_URL", "").rstrip("/")
    key = cfg.get("KEITARO_API_KEY", "")
    if not base:
        sys.exit("В .env нет KEITARO_BASE_URL")
    if not key:
        sys.exit("В .env нет KEITARO_API_KEY — впиши ключ из админки (Профиль → API ключи)")

    print(f"База: {base}")
    print(f"Ключ: длина {len(key)}, hex: {key.isalnum() and all(c in '0123456789abcdefABCDEF' for c in key)}")

    async with httpx.AsyncClient(timeout=30) as ac:
        r = await ac.get(f"{base}/admin/api/v1/campaigns", headers={"Api-Key": key})

    if r.status_code == 200 and "application/json" in r.headers.get("content-type", ""):
        data = r.json()
        print(f"КЛЮЧ РАБОТАЕТ: кампаний в инстансе — {len(data)}")
        for c in data[:10]:
            print(f"  [{c.get('id')}] {c.get('name')}")
        return
    if r.status_code == 403:
        print("КЛЮЧ НЕ РАБОТАЕТ: Keitaro отдаёт страницу логина (403).")
        print("Это значит: в KEITARO_API_KEY записан не API-ключ.")
        print("Порядок действий (см. скриншот в ТЗ):")
        print("  1. Зайди в админку: https://tlgk.host/admin (логин + пароль из задания).")
        print("  2. Профиль → вкладка «API ключи» → «Создать новый ключ».")
        print("  3. Скопируй созданный ключ и вставь в .env: KEITARO_API_KEY=<ключ>")
        sys.exit(1)
    print(f"Неожиданный ответ: HTTP {r.status_code} ({r.headers.get('content-type','-')})")
    sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
