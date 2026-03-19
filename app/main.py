from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import agri_assistant, crop_profiles, crops, dashboards, fields, ranking, recommendations, soil_tests
from app.config import settings
from app.database import Base, engine
from app.models import (  # noqa: F401
    crop_price,
    crop_profile,
    feedback,
    field,
    field_crop_cycle,
    input_cost,
    recommendation,
    soil_test,
    weather_history,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        Base.metadata.create_all(bind=engine)
    except Exception:
        pass
    yield


def create_app() -> FastAPI:
    app = FastAPI(title=settings.APP_NAME, debug=settings.DEBUG, lifespan=lifespan)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(fields.router, prefix=settings.API_V1_PREFIX)
    app.include_router(soil_tests.router, prefix=settings.API_V1_PREFIX)
    app.include_router(crops.router, prefix=settings.API_V1_PREFIX)
    app.include_router(crop_profiles.router, prefix=settings.API_V1_PREFIX)
    app.include_router(dashboards.router, prefix=settings.API_V1_PREFIX)
    app.include_router(ranking.router, prefix=settings.API_V1_PREFIX)
    app.include_router(recommendations.router, prefix=settings.API_V1_PREFIX)
    app.include_router(agri_assistant.router, prefix=settings.API_V1_PREFIX)

    return app


app = create_app()
