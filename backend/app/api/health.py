from fastapi import APIRouter, Request
from .schemas import HealthResponse

router = APIRouter(tags=['health'])


@router.get('/health', response_model=HealthResponse)
def health(request: Request):
    providers = request.app.state.providers
    configured = providers.settings.llm.configured and providers.settings.embedding.configured
    return HealthResponse(max_upload_bytes=request.app.state.config.max_upload_bytes,
        qa_ready=configured, model_services=providers.settings.public())
