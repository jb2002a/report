from __future__ import annotations

import hashlib
from typing import Any

import chromadb
from llama_index.core import Settings as LlamaSettings
from llama_index.core import StorageContext, VectorStoreIndex
from llama_index.core.schema import TextNode
from llama_index.embeddings.openai import OpenAIEmbedding
from llama_index.vector_stores.chroma import ChromaVectorStore

from equity_rag.config import Settings
from equity_rag.schemas import ParsedChunk, SourceInfo


class ChromaStore:
    def __init__(self, settings: Settings):
        self.settings = settings
        self._client = chromadb.PersistentClient(
            path=str(settings.chroma_persist_dir)
        )
        self._collection = self._client.get_or_create_collection(
            name=settings.chroma_collection_name
        )
        self._vector_store = ChromaVectorStore(chroma_collection=self._collection)
        self._configure_llama_settings()
        self._storage_context = StorageContext.from_defaults(
            vector_store=self._vector_store
        )

    def _configure_llama_settings(self) -> None:
        LlamaSettings.embed_model = OpenAIEmbedding(
            model=self.settings.embedding_model,
            api_key=self.settings.openai_api_key or None,
        )

    def upsert_chunks(self, chunks: list[ParsedChunk]) -> None:
        nodes = [
            TextNode(
                text=chunk.text,
                metadata=self._sanitize_metadata(chunk.metadata),
                id_=self._build_chunk_id(chunk),
            )
            for chunk in chunks
        ]
        index = self.get_index()
        index.insert_nodes(nodes)

    def get_index(self) -> VectorStoreIndex:
        return VectorStoreIndex.from_vector_store(
            vector_store=self._vector_store,
            storage_context=self._storage_context,
            embed_model=LlamaSettings.embed_model,
        )

    def count(self) -> int:
        return self._collection.count()

    def list_sources_for_ticker(self, ticker: str) -> list[SourceInfo]:
        """Return distinct broker sources ingested for a ticker."""
        result = self._collection.get(
            where={"ticker": ticker},
            include=["metadatas"],
        )
        metadatas = result.get("metadatas") or []
        by_source: dict[str, SourceInfo] = {}
        for metadata in metadatas:
            if not metadata:
                continue
            source = str(metadata.get("source", "")).strip()
            if not source:
                continue
            if source not in by_source:
                by_source[source] = SourceInfo(
                    source=source,
                    file_name=metadata.get("file_name"),
                    report_date=metadata.get("report_date"),
                )
        return sorted(by_source.values(), key=lambda item: item.source)

    @staticmethod
    def _build_chunk_id(chunk: ParsedChunk) -> str:
        metadata = chunk.metadata
        raw = (
            f"{metadata.get('file_name')}:"
            f"{metadata.get('page')}:"
            f"{metadata.get('chunk_index')}"
        )
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    @staticmethod
    def _sanitize_metadata(metadata: dict[str, Any]) -> dict[str, Any]:
        sanitized: dict[str, Any] = {}
        for key, value in metadata.items():
            if value is None:
                continue
            if isinstance(value, (str, int, float, bool)):
                sanitized[key] = value
            else:
                sanitized[key] = str(value)
        return sanitized
