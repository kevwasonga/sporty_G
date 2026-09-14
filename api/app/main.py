import logging
from pathlib import Path

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from starlette.staticfiles import StaticFiles

from .auth import require_api_key
from .config import settings
from .database import init_db
from .routers import registrations

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("sporty.lab")

if not settings.encrypt_key:
    logger.warning(
        "ENCRYPT_KEY is not set: passwords and OTP secrets are stored in PLAINTEXT. "
        "Set it for real deployments."
    )

# Resolve the UI dist directory relative to this file:
#   api/app/main.py -> api/app/ -> api/ -> sporty/ -> sporty/ui/dist
_STATIC_DIR = Path(__file__).resolve().parent.parent.parent / "ui" / "dist"


def create_app() -> FastAPI:
    init_db()

    app = FastAPI(
        title=settings.app_name,
        version="1.0.0",
        description="Hackathon lab: Nigeria/Kenya phone numbers -> strong generated passwords -> real SportyBet OTP delivery tracking.",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # --- API routes (must be registered before the static mount) ----------
    app.include_router(registrations.router, dependencies=[Depends(require_api_key)])

    @app.get("/api/health")
    def api_health():
        return {"app": settings.app_name, "provider": settings.provider}

    # --- Static UI files --------------------------------------------------
    # The built React SPA lives in ui/dist/.  Mount it at "/" so the browser
    # loads index.html for the root path and Vite's hashed assets resolve
    # under /assets/.  API routes above take priority over this mount.
    if _STATIC_DIR.is_dir():
        app.mount("/", StaticFiles(directory=str(_STATIC_DIR), html=True), name="static")
        logger.info("Serving UI from %s", _STATIC_DIR)
    else:
        logger.warning("UI dist not found at %s — running as API-only.", _STATIC_DIR)

    return app


app = create_app()
