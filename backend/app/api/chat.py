"""HTTP/SSE adapter; all research decisions live in application.chat."""
import json
import anyio
from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse
from app.application.identity import get_local_owner_id
from .schemas import ConversationCreate, Question

router = APIRouter(prefix='/notebooks/{notebook_id}/conversations', tags=['research'])


def public_message(row):
    return {k:v for k,v in row.items() if k not in ('request_key','request_fingerprint')}


@router.get('')
def conversations(notebook_id: str, request: Request):
    return request.app.state.chat.conversations(get_local_owner_id(), notebook_id)


@router.post('', status_code=201)
def create(notebook_id: str, body: ConversationCreate, request: Request):
    return request.app.state.chat.create(get_local_owner_id(), notebook_id, body.title)


@router.get('/{conversation_id}/messages')
def messages(notebook_id: str, conversation_id: str, request: Request):
    return [public_message(m) for m in request.app.state.chat.messages(get_local_owner_id(), notebook_id, conversation_id)]


@router.post('/{conversation_id}/messages')
async def ask(notebook_id: str, conversation_id: str, body: Question, request: Request):
    service = request.app.state.chat
    owner = get_local_owner_id()
    row, prepared, replay = await anyio.to_thread.run_sync(lambda: service.prepare(owner, notebook_id, conversation_id,
        body.question, body.source_ids, body.request_key))
    iterator = service.events(row, prepared, replay, owner, notebook_id, body.question)

    async def stream():
        try:
            while True:
                if await request.is_disconnected(): break
                item = await anyio.to_thread.run_sync(lambda: next(iterator, None))
                if item is None: break
                if 'message' in item['data'] and item['data']['message']:
                    item['data']['message'] = public_message(item['data']['message'])
                yield 'event: ' + item['event'] + '\ndata: ' + json.dumps(item['data'],ensure_ascii=False) + '\n\n'
        finally:
            with anyio.CancelScope(shield=True):
                await anyio.to_thread.run_sync(iterator.close)
                if not replay:
                    await anyio.to_thread.run_sync(lambda: service.repo.fail_message(row['id']))

    return StreamingResponse(stream(), media_type='text/event-stream', headers={'Cache-Control':'no-cache','X-Accel-Buffering':'no'})
