"""SiMonPro REST API (FastAPI).

Run on the edge server:
    uv run uvicorn server.app.main:app --host 0.0.0.0 --port 8000
"""

from __future__ import annotations

import logging
import time
from contextlib import asynccontextmanager

from fastapi import APIRouter, FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from .config import Settings, get_settings
from .db import Database
from .ml.inspector import BaseInspector, PatchCoreInspector, StubInspector
from .routers import auth, batches, dev, inspections, production, products, shipments
from .schemas import HealthOut

API_PREFIX = "/api/v1"
logger = logging.getLogger("simonpro")


def build_inspector(settings: Settings) -> BaseInspector:
    if settings.model_backend == "stub":
        logger.warning("MODEL_BACKEND=stub: score = image brightness (testing only)")
        return StubInspector()
    insp = PatchCoreInspector(settings.model_dir, settings.torch_device)
    insp.load_all()
    return insp


def sync_product_models(db: Database, inspector: BaseInspector) -> None:
    """Record the loaded model version and threshold on each product (AI-05)."""
    models = inspector.models()
    if not models:
        return
    with db.connection() as conn, conn.cursor() as cur:
        for sku, (version, threshold) in models.items():
            cur.execute("UPDATE produk SET versi_model = %s, ambang_batas = %s WHERE sku = %s",
                        (version, threshold, sku))
            if cur.rowcount == 0:
                logger.warning("Model for %s loaded but the product is not in the database", sku)


def create_app(settings: Settings | None = None, inspector: BaseInspector | None = None) -> FastAPI:
    settings = settings or get_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        app.state.settings = settings
        settings.image_dir.mkdir(parents=True, exist_ok=True)
        db = Database(settings)
        db.open()
        app.state.db = db
        app.state.inspector = inspector or build_inspector(settings)
        sync_product_models(db, app.state.inspector)
        logger.info("SiMonPro API ready (backend=%s, device=%s, models=%s)", settings.model_backend,
                    app.state.inspector.device, list(app.state.inspector.models()))
        yield
        db.close()

    app = FastAPI(title="SiMonPro API", version="1.0.0", lifespan=lifespan,
                  description="Layanan pencatatan produksi dan inspeksi kemasan sarden kaleng")

    @app.exception_handler(RequestValidationError)
    async def validation_handler(request: Request, exc: RequestValidationError):
        # D2 specifies 400 Bad Request for invalid input (FastAPI's default is 422).
        errors = [{"field": ".".join(str(p) for p in e["loc"][1:]), "message": e["msg"]} for e in exc.errors()]
        return JSONResponse(status_code=400, content={"detail": "Masukan tidak valid", "errors": errors})

    @app.exception_handler(Exception)
    async def unhandled(request: Request, exc: Exception):
        # NF-03: one failed request never takes the server down; the error goes to the log.
        logger.exception("Unhandled error on %s %s", request.method, request.url.path)
        return JSONResponse(status_code=500, content={"detail": "Terjadi kesalahan pada server"})

    @app.middleware("http")
    async def access_log(request: Request, call_next):
        t0 = time.perf_counter()
        response = await call_next(request)
        logger.info("%s %s -> %d (%.0f ms)", request.method, request.url.path, response.status_code,
                    (time.perf_counter() - t0) * 1000)
        return response

    api = APIRouter(prefix=API_PREFIX)
    for r in (auth.router, products.router, batches.router, production.router,
              inspections.router, shipments.router, dev.router):
        api.include_router(r)

    @api.get("/health", response_model=HealthOut, tags=["meta"])
    def health(request: Request):
        insp: BaseInspector = request.app.state.inspector
        return HealthOut(status="ok", model_backend=settings.model_backend, device=insp.device,
                         models={k: {"version": v, "threshold": t} for k, (v, t) in insp.models().items()})

    app.include_router(api)
    return app


logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
app = create_app()
