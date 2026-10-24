"""Список подключаемых импортёров."""
from app.config import Settings
from app.importers.base import BaseImporter
from app.importers.http_feed import HttpJsonFeedImporter
from app.importers.local_file import LocalFileImporter


def build_importers(settings: Settings) -> dict[str, BaseImporter]:
    importers: list[BaseImporter] = [
        LocalFileImporter(settings),
        HttpJsonFeedImporter(settings),
    ]
    return {importer.key: importer for importer in importers}