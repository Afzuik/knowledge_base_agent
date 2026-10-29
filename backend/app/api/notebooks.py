from fastapi import APIRouter, Request
from app.application.identity import get_local_owner_id
from .schemas import NotebookCreate, NotebookOut

router = APIRouter(prefix='/notebooks', tags=['notebooks'])


@router.post('', response_model=NotebookOut, status_code=201)
def create_notebook(body: NotebookCreate, request: Request):
    return request.app.state.notebooks.create(get_local_owner_id(), body.name)


@router.get('', response_model=list[NotebookOut])
def list_notebooks(request: Request):
    return request.app.state.notebooks.list(get_local_owner_id())


@router.get('/{notebook_id}', response_model=NotebookOut)
def get_notebook(notebook_id: str, request: Request):
    return request.app.state.notebooks.require(get_local_owner_id(), notebook_id)
