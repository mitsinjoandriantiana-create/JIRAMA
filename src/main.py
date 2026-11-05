from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from src.api import router
from src.settings import settings

WEB_DIR = Path(__file__).parent / "static"


app = FastAPI(
    title=settings.app_name,
    description="Suivi personnel indépendant des factures JIRAMA saisies manuellement.",
    version="1.0.0",
)
app.include_router(router)
app.mount("/static", StaticFiles(directory=WEB_DIR), name="static")


@app.get("/", include_in_schema=False)
def home() -> FileResponse:
    return FileResponse(WEB_DIR / "index.html")
