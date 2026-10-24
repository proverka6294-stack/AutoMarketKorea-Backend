"""Импорт из локального JSON-файла."""
import json
from pathlib import Path
from typing import Any

from app.importers.base import BaseImporter
from app.importers.errors import SourceFormatError
from app.importers.parsing import extract_items


class LocalFileImporter(BaseImporter):
    key = "local_file"
    name = "Локальный JSON-файл"
    kind = "file"
    description = (
        "Читает объявления из JSON-файла на этом компьютере. "
        "Путь задаётся переменной LOCAL_FEED_PATH."
    )
    license_note = "Используйте только данные, на использование которых у вас есть права."

    def config_problem(self) -> str | None:
        path = self.settings.local_feed_path.strip()
        if not path:
            return "Источник не подключён: не задана переменная LOCAL_FEED_PATH."
        if not Path(path).is_file():
            return f"Источник не подключён: файл не найден ({path})."
        return None

    def fetch_items(self) -> list[Any]:
        path = Path(self.settings.local_feed_path.strip())
        try:
            # utf-8-sig спокойно читает файлы и с BOM, и без него
            payload = json.loads(path.read_text(encoding="utf-8-sig"))
        except (OSError, ValueError) as exc:
            raise SourceFormatError(f"Не удалось прочитать JSON из файла: {exc}") from exc
        return extract_items(payload)