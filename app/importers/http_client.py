"""HTTP-запрос к внешнему источнику с повторными попытками.

Повторяем только временные сбои: обрыв связи, таймаут, коды 408/425/429/5xx.
Отказ в доступе (401/403) и неверный адрес (404) не повторяем: это не лечится ожиданием.
"""
import logging
from typing import Any
from urllib.parse import urlsplit

import httpx
from tenacity import (
    Retrying,
    before_sleep_log,
    retry_if_exception,
    stop_after_attempt,
    wait_exponential_jitter,
)

from app.importers.errors import (
    SourceFormatError,
    SourceRejectedError,
    SourceUnavailableError,
)

logger = logging.getLogger(__name__)

TRANSIENT_STATUS_CODES = {408, 425, 429, 500, 502, 503, 504}


def safe_url(url: str) -> str:
    """Адрес без параметров и логина: его можно писать в журнал."""
    parts = urlsplit(url)
    return f"{parts.scheme}://{parts.hostname or ''}{parts.path}"


def _is_transient(exc: BaseException) -> bool:
    if isinstance(exc, httpx.HTTPStatusError):
        return exc.response.status_code in TRANSIENT_STATUS_CODES
    if isinstance(exc, httpx.UnsupportedProtocol):
        return False
    return isinstance(exc, httpx.TransportError)


def fetch_json(
    url: str,
    *,
    headers: dict[str, str] | None = None,
    timeout: float = 15.0,
    max_attempts: int = 4,
    backoff_seconds: float = 1.0,
    transport: httpx.BaseTransport | None = None,
) -> Any:
    shown_url = safe_url(url)
    logger.info("Запрос к источнику: %s", shown_url)

    retryer = Retrying(
        stop=stop_after_attempt(max_attempts),
        wait=wait_exponential_jitter(
            initial=backoff_seconds,
            max=30.0,
            jitter=1.0 if backoff_seconds > 0 else 0.0,
        ),
        retry=retry_if_exception(_is_transient),
        before_sleep=before_sleep_log(logger, logging.WARNING),
        reraise=True,
    )

    def attempt() -> httpx.Response:
        with httpx.Client(
            timeout=timeout, transport=transport, follow_redirects=False
        ) as client:
            response = client.get(url, headers=headers)
            response.raise_for_status()
            return response

    try:
        response = retryer(attempt)
    except httpx.HTTPStatusError as exc:
        code = exc.response.status_code
        if code in TRANSIENT_STATUS_CODES:
            raise SourceUnavailableError(
                f"Источник временно недоступен (HTTP {code}), попыток: {max_attempts}."
            ) from exc
        if code in (401, 403):
            raise SourceRejectedError(
                f"Источник отклонил доступ (HTTP {code}). Проверьте ключ API и условия лицензии."
            ) from exc
        raise SourceRejectedError(
            f"Источник вернул HTTP {code}. Проверьте адрес источника."
        ) from exc
    except httpx.TransportError as exc:
        raise SourceUnavailableError(
            f"Не удалось связаться с источником ({type(exc).__name__}), попыток: {max_attempts}."
        ) from exc

    try:
        return response.json()
    except ValueError as exc:
        raise SourceFormatError("Источник вернул ответ, который не является JSON.") from exc