from datetime import datetime, timezone
import shutil
from pathlib import Path

from fastapi import APIRouter

from app.config import settings

router = APIRouter(tags=["health"])


@router.get("/health")
async def health() -> dict[str, str]:
    matiec_path = str(settings.matiec_bin)
    matiec_available = shutil.which(matiec_path) is not None or Path(matiec_path).exists()

    return {
        "status": "ok",
        "matiec": "available" if matiec_available else "unavailable",
        "matiec_path": matiec_path,
        "llm_provider": settings.llm_provider,
        "database": "sqlite",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

