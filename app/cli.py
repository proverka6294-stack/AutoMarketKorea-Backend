"""Командная строка.

Примеры:
    python -m app.cli init-db
    python -m app.cli sources
    python -m app.cli import local_file
    python -m app.cli import --all
"""
import argparse
import sys

import app.models  # noqa: F401  (регистрирует таблицы)
from app.config import get_settings
from app.database import Base, make_engine, make_session_factory
from app.importers.registry import build_importers
from app.importers.runner import run_import, sync_sources
from app.logging_config import setup_logging


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m app.cli")
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("init-db", help="создать таблицы и записать список источников")
    subparsers.add_parser("sources", help="показать источники и их состояние")
    import_parser = subparsers.add_parser("import", help="запустить импорт")
    import_parser.add_argument("source", nargs="?", help="ключ источника, например local_file")
    import_parser.add_argument("--all", action="store_true", help="импорт из всех источников")
    args = parser.parse_args(argv)

    settings = get_settings()
    setup_logging(settings.log_level)
    engine = make_engine(settings.sqlalchemy_url)
    Base.metadata.create_all(engine)
    session_factory = make_session_factory(engine)
    importers = build_importers(settings)

    with session_factory() as db:
        sync_sources(db, importers)

        if args.command == "init-db":
            print("Готово: таблицы созданы, источники зарегистрированы.")
            return 0

        if args.command == "sources":
            for importer in importers.values():
                problem = importer.config_problem()
                state = "НЕ ПОДКЛЮЧЁН" if problem else "настроен"
                print(f"{importer.key:20} {state:14} {problem or ''}")
            return 0

        if args.all:
            keys = list(importers)
        elif args.source:
            if args.source not in importers:
                print(f"Неизвестный источник: {args.source}. Доступны: {', '.join(importers)}")
                return 2
            keys = [args.source]
        else:
            parser.error("Укажите ключ источника или флаг --all")

        exit_code = 0
        for key in keys:
            result = run_import(db, importers[key], settings)
            print(
                f"[{result.source_key}] {result.outcome}: {result.message} "
                f"(получено {result.fetched}, создано {result.created}, "
                f"обновлено {result.updated}, без изменений {result.unchanged}, "
                f"некорректных {result.invalid})"
            )
            for line in result.errors_sample:
                print(f"    - {line}")
            if result.outcome in ("unavailable", "error"):
                exit_code = 1
        return exit_code


if __name__ == "__main__":
    sys.exit(main())