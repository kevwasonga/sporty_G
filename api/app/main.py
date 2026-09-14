import logging

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware

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

    app.include_router(registrations.router, dependencies=[Depends(require_api_key)])

    @app.get("/")
    def root():
        return {"app": settings.app_name, "provider": settings.provider}

    return app


app = create_app()