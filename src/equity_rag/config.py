from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

load_dotenv()


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    openai_api_key: str = Field(default="", alias="OPENAI_API_KEY")
    llama_cloud_api_key: str = Field(default="", alias="LLAMA_CLOUD_API_KEY")
    chroma_persist_dir: Path = Field(
        default=Path("./data/chroma"),
        alias="CHROMA_PERSIST_DIR",
    )
    chroma_collection_name: str = Field(
        default="equity_reports",
        alias="CHROMA_COLLECTION_NAME",
    )
    llm_model: str = Field(default="gpt-4.1-mini", alias="LLM_MODEL")
    embedding_model: str = Field(
        default="text-embedding-3-small",
        alias="EMBEDDING_MODEL",
    )
    langsmith_tracing: bool = Field(default=True, alias="LANGSMITH_TRACING")
    langsmith_api_key: str = Field(default="", alias="LANGSMITH_API_KEY")
    langsmith_project: str = Field(
        default="equity-report-rag-mvp",
        alias="LANGSMITH_PROJECT",
    )
    retrieval_top_k: int = Field(default=6, alias="RETRIEVAL_TOP_K")
    min_context_chunks: int = Field(default=2, alias="MIN_CONTEXT_CHUNKS")
    chunk_size: int = Field(default=1000, alias="CHUNK_SIZE")
    chunk_overlap: int = Field(default=120, alias="CHUNK_OVERLAP")
    chunk_min_text_chars: int = Field(default=150, alias="CHUNK_MIN_TEXT_CHARS")

    export_debug_chunks: bool = Field(default=False, alias="EXPORT_DEBUG_CHUNKS")
    data_dir: Path = Path("./data")
    raw_pdfs_dir: Path = Path("./data/raw_pdfs")
    outputs_dir: Path = Path("./data/outputs")
    debug_chunks_dir: Path = Path("./data/debug_chunks")

    def ensure_dirs(self) -> None:
        self.chroma_persist_dir.mkdir(parents=True, exist_ok=True)
        self.raw_pdfs_dir.mkdir(parents=True, exist_ok=True)
        self.outputs_dir.mkdir(parents=True, exist_ok=True)
        self.debug_chunks_dir.mkdir(parents=True, exist_ok=True)


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    settings.ensure_dirs()
    return settings
