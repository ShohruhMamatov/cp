from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.routes import auth, documents, projects
from app.core.config import settings


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings.storage_path.mkdir(parents=True, exist_ok=True)
    yield


app = FastAPI(title=settings.app_name, version="0.1.0", lifespan=lifespan)

app.include_router(auth.router)
app.include_router(projects.router)
app.include_router(documents.router)


@app.get("/health", tags=["system"])
async def health():
    return {"status": "ok"}
