from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.config import settings
from app.database import Base, engine
from app.api import fields, soil_tests, crops, ranking, recommendations


def create_app() -> FastAPI:
    app = FastAPI(title=settings.APP_NAME, debug=settings.DEBUG)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.on_event("startup")
    def on_startup():
        try:
            Base.metadata.create_all(bind=engine)
        except Exception:
            pass

    app.include_router(fields.router, prefix=settings.API_V1_PREFIX)
    app.include_router(soil_tests.router, prefix=settings.API_V1_PREFIX)
    app.include_router(crops.router, prefix=settings.API_V1_PREFIX)
    app.include_router(ranking.router, prefix=settings.API_V1_PREFIX)
    app.include_router(recommendations.router, prefix=settings.API_V1_PREFIX)

    return app


app = create_app()
