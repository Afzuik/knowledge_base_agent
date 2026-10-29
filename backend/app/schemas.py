"""API DTOs. Add feature schemas only as each real endpoint is implemented."""
from typing import Literal

from pydantic import BaseModel


class HealthResponse(BaseModel):
    status: Literal["ok"] = "ok"
    stage: Literal["scaffold"] = "scaffold"
    mode: Literal["local-single-user"] = "local-single-user"
    business_ready: bool = False
