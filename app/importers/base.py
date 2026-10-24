"""Базовый класс импортёра. Новый источник = новый наследник этого класса."""
from abc import ABC, abstractmethod
from typing import Any

from app.config import Settings


class BaseImporter(ABC):
    key: str
    name: str
    kind: str
    description: str
    license_note: str

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    @abstractmethod
    def config_problem(self) -> str | None:
        """None, если источник подключён. Иначе понятное сообщение, чего не хватает."""

    @abstractmethod
    def fetch_items(self) -> list[Any]:
        """Возвращает «сырые» записи. Бросает ошибки из app.importers.errors."""