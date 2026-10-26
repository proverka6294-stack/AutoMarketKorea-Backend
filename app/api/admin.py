from pydantic import BaseModel

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
    settings = request.app.state.settings
    if not settings.admin_api_key or x_admin_key != settings.admin_api_key:
        raise HTTPException(status_code=401, detail="Неверный X-Admin-Key.")
    
    from sqlalchemy import select
    from app.models import Source, utcnow
    from app.importers.parsing import parse_items
    from app.importers.runner import _upsert_records

    source = db.scalar(select(Source).where(Source.key == source_key))
    if not source:
        raise HTTPException(404, "Источник не найден")

    parsed = parse_items(payload.items)
    now = utcnow()
    created, updated, unchanged, removed, total = _upsert_records(db, source, parsed.records, settings, now)
    db.commit()

    return ImportResult(
        source_key=source_key, outcome="success", message="Импорт из JSON успешен",
        fetched=len(payload.items), created=created, updated=updated, unchanged=unchanged, invalid=parsed.invalid_count
    )