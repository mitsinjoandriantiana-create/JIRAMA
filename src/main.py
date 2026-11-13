from fastapi import FastAPI
from fastapi.responses import RedirectResponse

from src.api import router
from src.settings import settings

app = FastAPI(
    title=settings.app_name,
    description="Gestion des factures JIRAMA.",
    version="1.0.0",
)
app.include_router(router)


@app.get("/", include_in_schema=False)
def home() -> RedirectResponse:
    return RedirectResponse(settings.streamlit_url)
