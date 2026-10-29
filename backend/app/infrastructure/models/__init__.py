from dataclasses import dataclass
from .settings import load_settings
from .llm import LLM
from .embedding import Embedding
from .reranker import Reranker


@dataclass
class Providers:
    settings: object
    llm: object
    embedding: object
    reranker: object


def build_providers(project_root):
    settings = load_settings(project_root)
    return Providers(settings, LLM(settings), Embedding(settings), Reranker(settings))
