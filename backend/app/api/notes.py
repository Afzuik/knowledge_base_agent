"""Notes protocol only; no model calls or database access here."""
from urllib.parse import quote
from fastapi import APIRouter, Request, Response, Query
from app.application.identity import get_local_owner_id
from .schemas import NoteCreate, NoteUpdate, NoteOut, NoteSummary, NoteCreateOut

router = APIRouter(prefix='/notebooks/{notebook_id}/notes',tags=['notes'])


@router.post('',response_model=NoteCreateOut,status_code=201)
def create(notebook_id: str, body: NoteCreate, request: Request, response: Response):
    note,created = request.app.state.notes.create(get_local_owner_id(),notebook_id,body.origin_message_id,body.title)
    response.status_code = 201 if created else 200
    return {'note':note,'created':created}


@router.get('',response_model=list[NoteSummary])
def list_notes(notebook_id: str, request: Request):
    return request.app.state.notes.list(get_local_owner_id(),notebook_id)


@router.get('/{note_id}',response_model=NoteOut)
def get_note(notebook_id: str, note_id: str, request: Request):
    return request.app.state.notes.get(get_local_owner_id(),notebook_id,note_id)


@router.patch('/{note_id}',response_model=NoteOut)
def update(notebook_id: str, note_id: str, body: NoteUpdate, request: Request):
    return request.app.state.notes.update(get_local_owner_id(),notebook_id,note_id,body.revision,body.title,body.body_markdown)


@router.get('/{note_id}/export')
def export(notebook_id: str, note_id: str, request: Request, revision: int = Query(ge=1)):
    content,filename = request.app.state.notes.export(get_local_owner_id(),notebook_id,note_id,revision)
    return Response(content=content,media_type='text/markdown',headers={
        'Content-Disposition':f'attachment; filename="note-{note_id[:8]}.md"; filename*=UTF-8\'\'' + quote(filename,safe=''),
        'X-Note-Revision':str(revision),'X-Content-Type-Options':'nosniff','Cache-Control':'no-store'})
