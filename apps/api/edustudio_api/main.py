from fastapi import FastAPI
from sqlalchemy import text

from .db import engine
from .routers import ai, auth, files, projects

app = FastAPI(title="EduStudio AI API", version="0.1.0", docs_url=None, redoc_url=None)
app.include_router(auth.router, prefix="/api")
app.include_router(projects.router, prefix="/api")
app.include_router(files.router, prefix="/api")
app.include_router(ai.router, prefix="/api")


@app.get("/api/health")
def health() -> dict[str, str]:
    with engine.connect() as connection:
        connection.execute(text("SELECT 1"))
    return {"status": "ok"}

