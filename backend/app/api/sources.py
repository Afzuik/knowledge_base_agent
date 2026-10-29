from fastapi import APIRouter, Request, UploadFile, Response, Query
from app.application.identity import get_local_owner_id
from .schemas import SourceOut, UploadOut, SourceDetail, ChunkPage

router = APIRouter(prefix='/notebooks/{notebook_id}/sources', tags=['sources'])


@router.post('', response_model=UploadOut, status_code=202)
def upload(notebook_id: str, file: UploadFile, request: Request, response: Response):
    try:
        source, duplicate = request.app.state.sources.upload(get_local_owner_id(), notebook_id, file.filename, file.file)
        response.status_code = 200 if duplicate else 202
        return dict(source=source, duplicate=duplicate)
    finally:
        file.file.close()


@router.get('', response_model=list[SourceOut])
def list_sources(notebook_id: str, request: Request):
    return request.app.state.sources.list(get_local_owner_id(), notebook_id)


@router.get('/{source_id}', response_model=SourceDetail)
def detail(notebook_id: str, source_id: str, request: Request):
    source, jobs = request.app.state.sources.detail(get_local_owner_id(), notebook_id, source_id)
    return dict(source=source, jobs=jobs)


@router.get('/{source_id}/chunks', response_model=ChunkPage)
def chunks(notebook_id: str, source_id: str, request: Request,
           offset: int = Query(0, ge=0), limit: int = Query(50, ge=1, le=100)):
    items, total = request.app.state.sources.chunks(get_local_owner_id(), notebook_id, source_id, offset, limit)
    return dict(items=items, total=total, offset=offset, limit=limit)


@router.post('/{source_id}/retry', response_model=SourceOut, status_code=202)
def retry(notebook_id: str, source_id: str, request: Request):
    return request.app.state.sources.retry(get_local_owner_id(), notebook_id, source_id)
