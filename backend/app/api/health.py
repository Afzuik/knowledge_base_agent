from fastapi import APIRouter, Request
from .schemas import HealthResponse

router = APIRouter(tags=['health'])


@router.get('/health', response_model=HealthResponse)
def health(request: Request):
    return HealthResponse(max_upload_bytes=request.app.state.config.max_upload_bytes)
