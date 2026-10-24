"""Служебные эндпоинты. Защищены ключом ADMIN_API_KEY (заголовок X-Admin-Key)."""
import secrets

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.importers.runner import run_import
from app.schemas import ImportResult

router = APIRouter(prefix="/admin", tags=["admin"])


@router.post("/sources/{source_key}/import", response_model=ImportResult)
def import_from_source(
    source_key: str,
    request: Request,
    db: Session = Depends(get_db),
    x_admin_key: str | None = Header(default=None),
) -> ImportResult:
    settings = request.app.state.settings
    if not settings.admin_api_key:
        raise HTTPException(
            status_code=503,
            detail="Админ-доступ отключён: задайте ADMIN_API_KEY в файле .env.",
        )
    if not x_admin_key or not secrets.compare_digest(
        x_admin_key.encode("utf-8"), settings.admin_api_key.encode("utf-8")
    ):
        raise HTTPException(status_code=401, detail="Неверный или отсутствующий X-Admin-Key.")

    importer = request.app.state.importers.get(source_key)
    if importer is None:
        raise HTTPException(status_code=404, detail="Источник с таким ключом не найден.")

    # Импорт выполняется прямо в запросе. Для больших файлов используйте командную строку.
    return run_import(db, importer, settings)