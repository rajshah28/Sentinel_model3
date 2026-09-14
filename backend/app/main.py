import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.api.routes_alerts import router as alerts_router
from app.api.routes_auth import router as auth_router
from app.api.routes_cameras import router as cameras_router
from app.api.routes_ingestion import router as ingestion_router
from app.api.routes_trace import router as trace_router
from app.api.routes_ws import router as ws_router
from app.config import FRAMES_DIR
from app.correlation.engine import engine

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

app = FastAPI(title="Sentinel VMS Federation API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(cameras_router)
app.include_router(alerts_router)
app.include_router(trace_router)
app.include_router(ingestion_router)
app.include_router(ws_router)

app.mount("/frames", StaticFiles(directory=FRAMES_DIR, check_dir=False), name="frames")


@app.on_event("startup")
async def on_startup():
    engine.start()
    logging.getLogger("sentinel.main").info("Correlation engine started on API startup")


@app.get("/api/health")
def health():
    return {"status": "ok"}
