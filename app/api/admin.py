"""Служебные эндпоинты. Защищены ключом ADMIN_API_KEY (заголовок X-Admin-Key)."""
import secrets

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.importers.parsing import parse_items
from app.importers.runner import _upsert_records, run_import
from app.models import Source, utcnow
from app.schemas import ImportResult

router = APIRouter(prefix="/admin", tags=["admin"])


def verify_admin_key(request: Request, x_admin_key: str | None):
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


@router.post("/sources/{source_key}/import", response_model=ImportResult)
def import_from_source(
    source_key: str,
    request: Request,
    db: Session = Depends(get_db),
    x_admin_key: str | None = Header(default=None),
) -> ImportResult:
    verify_admin_key(request, x_admin_key)

    importer = request.app.state.importers.get(source_key)
    if importer is None:
        raise HTTPException(status_code=404, detail="Источник с таким ключом не найден.")

    return run_import(db, importer, request.app.state.settings)


class JsonImportPayload(BaseModel):
    items: list[dict]


@router.post("/sources/{source_key}/import-json", response_model=ImportResult)
def import_json_from_payload(
    source_key: str,
    payload: JsonImportPayload,
    request: Request,
    db: Session = Depends(get_db),
    x_admin_key: str | None = Header(default=None),
) -> ImportResult:
    verify_admin_key(request, x_admin_key)

    source = db.scalar(select(Source).where(Source.key == source_key))
    if not source:
        raise HTTPException(404, "Источник не найден")

    parsed = parse_items(payload.items)
    now = utcnow()
    settings = request.app.state.settings
    
    created, updated, unchanged, removed, total = _upsert_records(db, source, parsed.records, settings, now)
    
    source.status = "ok"
    source.status_message = "Импорт из JSON успешен"
    source.last_attempt_at = now
    source.last_success_at = now
    source.last_imported_count = total
    
    db.commit()

    return ImportResult(
        source_key=source_key,
        outcome="success",
        message="Импорт из JSON успешен",
        fetched=len(payload.items),
        created=created,
        updated=updated,
        unchanged=unchanged,
        invalid=parsed.invalid_count
    )