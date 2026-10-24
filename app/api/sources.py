"""GET /sources — подключённые источники и их честное состояние."""
from fastapi import APIRouter, Depends, Request
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.enums import SourceStatus
from app.models import Car, Source
from app.schemas import SourceListResponse, SourceOut

router = APIRouter(tags=["sources"])


@router.get("/sources", response_model=SourceListResponse)
def list_sources(request: Request, db: Session = Depends(get_db)) -> SourceListResponse:
    importers = request.app.state.importers
    rows = db.execute(
        select(Source, func.count(Car.id))
        .outerjoin(Car, Car.source_id == Source.id)
        .group_by(Source.id)
        .order_by(Source.key)
    ).all()

    items: list[SourceOut] = []
    for source, cars_count in rows:
        importer = importers.get(source.key)
        if importer is None:
            problem = "Импортёр для этого источника отсутствует в коде."
        else:
            problem = importer.config_problem()

        # Настройки проверяются в момент запроса: если источник не настроен,
        # мы так и говорим, независимо от старого статуса в базе.
        if problem:
            status = SourceStatus.NOT_CONFIGURED.value
            message = problem
        else:
            status = source.status
            message = source.status_message

        items.append(
            SourceOut(
                key=source.key,
                name=source.name,
                kind=source.kind,
                description=source.description,
                license_note=source.license_note,
                configured=problem is None,
                status=status,
                status_message=message,
                last_attempt_at=source.last_attempt_at,
                last_success_at=source.last_success_at,
                last_imported_count=source.last_imported_count,
                cars_count=cars_count,
            )
        )
    return SourceListResponse(items=items)