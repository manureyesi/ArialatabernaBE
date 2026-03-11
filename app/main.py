import logging
import os
import sys

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.db import Base, engine
from app.db import SessionLocal
from app.models import AppConfig
from app.routers.admin_api import router as admin_router
from app.routers.public_api import router as public_router
from app.settings import settings


def _configure_logging() -> None:
    level_name = os.getenv("LOG_LEVEL", "INFO").upper()
    level = getattr(logging, level_name, logging.INFO)

    root = logging.getLogger()
    root.setLevel(level)

    if not root.handlers:
        handler = logging.StreamHandler(sys.stdout)
        formatter = logging.Formatter(
            fmt="%(asctime)s %(levelname)s %(name)s: %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        handler.setFormatter(formatter)
        root.addHandler(handler)

    logging.getLogger("app").setLevel(level)


_configure_logging()

app = FastAPI(title="Ariala Taberna API", version="1.0.0")

@app.on_event("startup")
def _startup():
    Base.metadata.create_all(bind=engine)

    db = SessionLocal()
    try:
        existing = db.get(AppConfig, "reserva-activa")
        if not existing:
            db.add(AppConfig(key="reserva-activa", value="false"))
            db.commit()

        existing = db.get(AppConfig, "telefono-contacto")
        if not existing:
            db.add(AppConfig(key="telefono-contacto", value=""))
            db.commit()

        existing = db.get(AppConfig, "mail-contacto")
        if not existing:
            db.add(AppConfig(key="mail-contacto", value="@"))
            db.commit()

        existing = db.get(AppConfig, "horario")
        if not existing:
            db.add(AppConfig(key="horario", value=""))
            db.commit()

        existing = db.get(AppConfig, "url-img-hone")
        if not existing:
            db.add(AppConfig(key="url-img-hone", value=""))
            db.commit()

        existing = db.get(AppConfig, "url-hone")
        if not existing:
            db.add(AppConfig(key="url-hone", value=""))
            db.commit()

    finally:
        db.close()


origins = [o.strip() for o in settings.cors_origins.split(",") if o.strip()]
if origins:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["*"] ,
        allow_headers=["*"] ,
    )


@app.get("/healthz")
def healthz():
    return {"status": "ok"}


@app.get("/readyz")
def readyz():
    return {"status": "ok"}


app.include_router(public_router)
app.include_router(admin_router)
