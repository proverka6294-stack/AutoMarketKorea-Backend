"""Ошибки импорта. Каждая означает свой статус источника."""


class ImporterError(Exception):
    """Базовая ошибка импорта."""


class SourceUnavailableError(ImporterError):
    """Источник временно недоступен (сеть, таймаут, HTTP 5xx) даже после повторных попыток."""


class SourceRejectedError(ImporterError):
    """Источник отказал в доступе или запрос неверен (HTTP 401/403/404, небезопасный адрес)."""


class SourceFormatError(ImporterError):
    """Источник ответил, но данные не в ожидаемом формате."""