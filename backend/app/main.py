"""Composition root. No runtime DB, file or thread side effects until lifespan starts."""
from contextlib import asynccontextmanager
import logging
from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.exc import SQLAlchemyError

from app.api.router import api_router
from app.config import settings
from app.application.errors import AppError
from app.application.notebooks import Notebooks
from app.application.sources import Sources
from app.application.ingestion import Ingestion
from app.infrastructure.database.connection import build_engine
from app.infrastructure.database.migrate import migrate
from app.infrastructure.database.rag_repository import RagRepository as Repository
from app.infrastructure.models import build_providers
from app.infrastructure.vector.chroma import ChromaVectors
from app.application.indexing import Indexing
from app.application.chat import Chat
from app.application.notes import Notes
from app.infrastructure.database.note_repository import NoteRepository
from app.infrastructure.storage.local_files import LocalFiles
from app.infrastructure.tasks.local_runner import LocalRunner, process_lock

log = logging.getLogger(__name__)


def create_app(config=None, run_worker=True, providers=None, vectors=None):
    config = config or settings

    @asynccontextmanager
    async def lifespan(app):
        with process_lock(config.data_dir):
            engine = build_engine(config)
            runner = None
            try:
                migrate(engine)
                repo = Repository(engine)
                files = LocalFiles(config.uploads_dir)
                notebooks = Notebooks(repo)
                ingestion = Ingestion(repo, files, config)
                repo.recover_research()
                ingestion.recover()
                app.state.config = config
                app.state.repo = repo
                app.state.notes = Notes(NoteRepository(engine))
                app.state.notebooks = notebooks
                app.state.sources = Sources(repo, files, notebooks, config)
                app.state.ingestion = ingestion
                model_services = providers or build_providers(config.project_root)
                vector_store = vectors or ChromaVectors(config.vector_dir)
                indexing = Indexing(repo, app.state.sources, model_services, vector_store)
                app.state.providers = model_services
                app.state.indexing = indexing
                app.state.chat = Chat(repo, notebooks, app.state.sources, model_services, vector_store)
                if run_worker:
                    runner = LocalRunner(lambda: ingestion.run_once() or indexing.run_once())
                    runner.start()
                yield
            finally:
                if runner:
                    runner.stop()
                engine.dispose()

    app = FastAPI(title='Knowledge Workbench', version='0.4.0', lifespan=lifespan)
    app.include_router(api_router, prefix='/api')

    @app.middleware('http')
    async def declared_upload_limit(request: Request, call_next):
        # Early rejection before multipart spool; storage enforces actual file bytes too.
        if request.method == 'POST' and request.url.path.endswith('/sources'):
            length = request.headers.get('content-length')
            if length:
                try:
                    if int(length) > config.max_upload_bytes + 65536:
                        return JSONResponse(status_code=413, content={'code': 'upload_too_large', 'message': '上传请求超过大小限制。'})
                except ValueError:
                    return JSONResponse(status_code=400, content={'code': 'invalid_length', 'message': '无效的请求长度。'})
        return await call_next(request)

    @app.exception_handler(AppError)
    async def app_error(_request, exc):
        return JSONResponse(status_code=exc.status, content={'code': exc.code, 'message': exc.message})

    async def storage_error(_request, exc):
        log.error('Local persistence failure', exc_info=(type(exc), exc, exc.__traceback__))
        return JSONResponse(status_code=503, content={'code': 'storage_error', 'message': '本地存储操作失败，请检查日志和磁盘后重试。'})

    app.add_exception_handler(SQLAlchemyError, storage_error)
    app.add_exception_handler(OSError, storage_error)

    assets = config.frontend_dist / 'assets'
    if assets.is_dir():
        app.mount('/assets', StaticFiles(directory=assets), name='assets')

    @app.get('/', include_in_schema=False)
    def frontend():
        index = config.frontend_dist / 'index.html'
        if index.is_file():
            return FileResponse(index)
        return JSONResponse(status_code=503, content={'detail': 'Frontend not built. Run npm ci && npm run build in frontend/.', 'health_url': '/api/health'})

    return app


app = create_app()
