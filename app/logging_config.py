"""Журналирование: вывод в консоль и в файл logs/automarket.log."""
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

_MARK = "_automarket_handler"


def setup_logging(level: str = "INFO", log_dir: str = "logs") -> None:
    root = logging.getLogger()
    root.setLevel(level)

    # Убираем только наши старые обработчики, чтобы не дублировать строки.
    for handler in list(root.handlers):
        if getattr(handler, _MARK, False):
            root.removeHandler(handler)
            handler.close()

    formatter = logging.Formatter("%(asctime)s %(levelname)s [%(name)s] %(message)s")
    handlers: list[logging.Handler] = [logging.StreamHandler()]
    try:
        Path(log_dir).mkdir(parents=True, exist_ok=True)
        handlers.append(
            RotatingFileHandler(
                Path(log_dir) / "automarket.log",
                maxBytes=1_000_000,
                backupCount=3,
                encoding="utf-8",
            )
        )
    except OSError:
        logging.getLogger(__name__).warning(
            "Не удалось создать файл журнала, пишем только в консоль."
        )

    for handler in handlers:
        handler.setFormatter(formatter)
        setattr(handler, _MARK, True)
        root.addHandler(handler)