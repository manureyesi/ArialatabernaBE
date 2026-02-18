from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

import os

from app.db import Base, engine
from app.routers.public_api import router as public_router
from app.routers.admin_api import router as admin_router
from app.settings import settings


app = FastAPI(title="Ariala Taberna API", version="1.0.0")

app.mount("/static", StaticFiles(directory="static"), name="static")


@app.on_event("startup")
def _startup():
    os.makedirs("static/events", exist_ok=True)
    Base.metadata.create_all(bind=engine)


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
