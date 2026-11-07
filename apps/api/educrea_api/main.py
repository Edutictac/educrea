from fastapi import FastAPI
from sqlalchemy import text

from .db import engine
from .services import history as _history  # noqa: F401  registers the file-history listener
from .routers import admin, ai, assets, audios, auth, capabilities, templates, files, history, illustrations, images, materials, oidc, projects, sources, video_ai, videos

from .services.ai.temporary_credentials import TemporaryCredentialMiddleware

app = FastAPI(title="EduCrea API", version="0.1.0", docs_url=None, redoc_url=None)
app.add_middleware(TemporaryCredentialMiddleware)
app.include_router(admin.router, prefix="/api")
app.include_router(auth.router, prefix="/api")
app.include_router(oidc.router, prefix="/api")
app.include_router(sources.router, prefix="/api")
app.include_router(projects.router, prefix="/api")
app.include_router(files.router, prefix="/api")
app.include_router(ai.router, prefix="/api")
app.include_router(materials.router, prefix="/api")
app.include_router(history.router, prefix="/api")
app.include_router(capabilities.router, prefix="/api")
app.include_router(assets.router, prefix="/api")
app.include_router(images.router, prefix="/api")
app.include_router(illustrations.router, prefix="/api")
app.include_router(videos.router, prefix="/api")
app.include_router(audios.router, prefix="/api")
app.include_router(video_ai.router, prefix="/api")
app.include_router(templates.router, prefix="/api")


@app.get("/api/health")
def health() -> dict[str, str]:
    with engine.connect() as connection:
        connection.execute(text("SELECT 1"))
    return {"status": "ok"}

