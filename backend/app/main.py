from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .config import CORS_ORIGINS, DATA_DIR
from .database import Base, engine
from .routers import admin_extra, admin_routes, auth_routes, public_routes, student_routes, whatsapp_routes

Base.metadata.create_all(engine)

app = FastAPI(title="EcoByte API", version="2.0.0",
              description="Smart canteen management, food-waste monitoring, demand prediction and NGO donations.")
app.add_middleware(CORSMiddleware, allow_origins=CORS_ORIGINS, allow_credentials=True,
                   allow_methods=["*"], allow_headers=["*"])

app.include_router(auth_routes.router)
app.include_router(student_routes.router)
app.include_router(admin_routes.router)
app.include_router(admin_extra.router)
app.include_router(public_routes.router)
app.include_router(whatsapp_routes.admin)
app.include_router(whatsapp_routes.public)

UPLOADS = DATA_DIR / "uploads"
UPLOADS.mkdir(exist_ok=True)
# Uploaded meal / donation photos (random names, image types validated on upload).
app.mount("/api/uploads", StaticFiles(directory=UPLOADS), name="uploads")


@app.get("/api/health")
def health():
    return {"status": "ok"}


# Serve the built frontend (npm run build) from the same origin when it exists.
DIST = Path(__file__).resolve().parent.parent.parent / "frontend" / "dist"
if DIST.exists():
    app.mount("/assets", StaticFiles(directory=DIST / "assets"), name="assets")

    @app.get("/{path:path}", include_in_schema=False)
    def spa(path: str):
        if path.startswith("api/"):
            raise HTTPException(404, "Not found")
        f = DIST / path
        if path and f.is_file() and DIST in f.resolve().parents:
            return FileResponse(f)
        return FileResponse(DIST / "index.html")
