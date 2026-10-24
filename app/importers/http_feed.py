"""Импорт из лицензированного JSON API.

Работает только с API, который отдаёт данные в формате из app/importers/records.py.
Если у провайдера другой формат, нужен отдельный адаптер (см. README, раздел
«Как подключить настоящий источник»).
"""
from typing import Any
from urllib.parse import urlparse

import httpx

from app.config import Settings
from app.importers.base import BaseImporter
from app.importers.http_client import fetch_json
from app.importers.parsing import extract_items

_LOCAL_HOSTS = {"localhost", "127.0.0.1"}


class HttpJsonFeedImporter(BaseImporter):
    key = "licensed_json_api"
    name = "Лицензированный JSON API"
    kind = "api"
    description = (
        "Загружает объявления из API провайдера по адресу LICENSED_FEED_URL. "
        "Ключ передаётся в заголовке на сервере и никогда не попадает в клиентское приложение."
    )
    license_note = (
        "Подключайте только API, условия которого (договор или лицензия) "
        "разрешают такое использование данных."
    )

    def __init__(
        self, settings: Settings, transport: httpx.BaseTransport | None = None
    ) -> None:
        super().__init__(settings)
        self._transport = transport  # нужен тестам: подмена сети без реальных запросов

    def config_problem(self) -> str | None:
        url = self.settings.licensed_feed_url.strip()
        if not url:
            return (
                "Источник не подключён: не задан LICENSED_FEED_URL. "
                "Нужен API провайдера, лицензия которого разрешает использование данных."
            )
        parts = urlparse(url)
        if parts.scheme == "https" and parts.hostname:
            return None
        if parts.scheme == "http" and parts.hostname in _LOCAL_HOSTS:
            return None
        return "LICENSED_FEED_URL должен начинаться с https:// (http разрешён только для localhost)."

    def fetch_items(self) -> list[Any]:
        headers = {"Accept": "application/json"}
        api_key = self.settings.licensed_feed_api_key.strip()
        if api_key:
            header_name = self.settings.licensed_feed_auth_header.strip() or "Authorization"
            scheme = self.settings.licensed_feed_auth_scheme.strip()
            headers[header_name] = f"{scheme} {api_key}" if scheme else api_key

        payload = fetch_json(
            self.settings.licensed_feed_url.strip(),
            headers=headers,
            timeout=self.settings.http_timeout_seconds,
            max_attempts=self.settings.http_max_attempts,
            backoff_seconds=self.settings.http_backoff_seconds,
            transport=self._transport,
        )
        return extract_items(payload)