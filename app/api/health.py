"""GET /health — состояние сервера."""
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app import __version__
from app.api.deps import get_db
from app.schemas import HealthResponse

logger = logging.getLogger(__name__)
router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
def health(
    request: Request, response: Response, db: Session = Depends(get_db)
) -> HealthResponse:
    database_ok = True
    try:
        db.execute(text("SELECT 1"))
    except SQLAlchemyError:
        logger.exception("Проверка базы данных не пройдена")
        database_ok = False
        response.status_code = 503

    settings = request.app.state.settings
    return HealthResponse(
        status="ok" if database_ok else "degraded",
        app=settings.app_name,
        version=__version__,
        environment=settings.environment,
        time=datetime.now(timezone.utc),
        database="ok" if database_ok else "error",
        database_dialect=request.app.state.engine.dialect.name,
    )