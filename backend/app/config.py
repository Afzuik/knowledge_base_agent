from dataclasses import dataclass
from pathlib import Path
import os


@dataclass(frozen=True)
class Settings:
    project_root: Path = Path(__file__).resolve().parents[2]
    data_root: Path | None = None
    max_upload_bytes: int = 20 * 1024 * 1024
    max_text_chars: int = 2_000_000
    max_pdf_pages: int = 200
    chunk_size: int = 800
    chunk_overlap: int = 100

    @property
    def data_dir(self) -> Path:
        return (self.data_root or self.project_root / "data").resolve()

    @property
    def database_path(self) -> Path:
        return self.data_dir / "app.sqlite3"

    @property
    def uploads_dir(self) -> Path:
        return self.data_dir / "uploads"

    @property
    def vector_dir(self) -> Path:
        return self.data_dir / "chroma"

    @property
    def frontend_dist(self) -> Path:
        return self.project_root / "frontend" / "dist"


# Non-secret local path override, useful for isolated demos/tests. No .env/model loading.
settings = Settings(data_root=Path(os.environ["WORKBENCH_DATA_DIR"]) if os.getenv("WORKBENCH_DATA_DIR") else None)
