
import logging
from dataclasses import dataclass
from typing import List, Optional

from ...domain.entities.chunk_entity import ChunkEntity
from ...domain.entities.file_entity import FileEntity, IndexStatus
from ...domain.ports.chunk_repository import ChunkRepository
from ...domain.ports.embedding_port import EmbeddingPort
from ...domain.ports.file_reader_port import FileReaderPort
from ...domain.ports.file_repository import FileRepository
from ...domain.ports.keyword_search_port import KeywordSearchPort
from ...domain.ports.text_compressor_port import TextCompressorPort
from ...domain.ports.vector_store_port import VectorStorePort
from ...domain.constants import (
    CONTENT_COLLECTION,
    DEFAULT_CHUNK_OVERLAP,
    DEFAULT_CHUNK_SIZE,
    FILENAME_COLLECTION,
)
from ...domain.services.content_deduplication import ContentDeduplicationService
from ...domain.value_objects.content_hash import ContentHash
from ...domain.value_objects.file_path import FilePath
from ...domain.value_objects.file_type import FileType
from ..services.indexing_transaction import IndexingTransaction

logger = logging.getLogger(__name__)

@dataclass
class IndexFileResult:

    path: str
    success: bool
    filename_indexed: bool
    content_indexed: bool
    chunk_count: int
    error: Optional[str] = None
    deduplicated_count: int = 0
    embeddings_generated: int = 0

    @property
    def dedup_ratio(self) -> float:
        if self.chunk_count == 0:
            return 0.0
        return self.deduplicated_count / self.chunk_count

class IndexFileUseCase:

    def __init__(
        self,
        file_repository: FileRepository,
        chunk_repository: ChunkRepository,
        vector_store: VectorStorePort,
        embedding_service: EmbeddingPort,
        file_reader: FileReaderPort,
        compressor: TextCompressorPort,
        enable_change_detection: bool = True,
        keyword_search: Optional[KeywordSearchPort] = None,
        deduplication_service: Optional[ContentDeduplicationService] = None,
    ) -> None:
        self._file_repo = file_repository
        self._chunk_repo = chunk_repository
        self._vector_store = vector_store
        self._embedding = embedding_service
        self._file_reader = file_reader
        self._compressor = compressor
        self._enable_change_detection = enable_change_detection
        self._keyword_search = keyword_search
        self._dedup_service = deduplication_service

    def execute(
        self,
        file_path: str,
        index_content: bool = True,
    ) -> IndexFileResult:
        logger.info("Indexing file: %s", file_path)

        file_info = self._file_reader.get_info(file_path)

        if not file_info.exists:
            return IndexFileResult(
                path=file_path,
                success=False,
                filename_indexed=False,
                content_indexed=False,
                chunk_count=0,
                error="File does not exist",
            )

        if self._enable_change_detection:
            existing = self._file_repo.find_by_path(file_path)
            if existing and not existing.has_changed(file_info.mtime):
                logger.debug("File unchanged, skipping: %s", file_path)
                return IndexFileResult(
                    path=file_path,
                    success=True,
                    filename_indexed=True,
                    content_indexed=existing.status == IndexStatus.CONTENT_INDEXED,
                    chunk_count=existing.chunk_count,
                )

        file_entity = self._create_file_entity(file_info)

        filename_indexed = self._index_filename(file_entity)

        if not filename_indexed:
            return IndexFileResult(
                path=file_path,
                success=False,
                filename_indexed=False,
                content_indexed=False,
                chunk_count=0,
                error="Failed to index filename",
            )

        content_indexed = False
        chunk_count = 0
        deduplicated_count = 0
        embeddings_generated = 0

        if index_content:
            content_indexed, chunk_count, deduplicated_count, embeddings_generated = (
                self._index_content(file_entity)
            )

        return IndexFileResult(
            path=file_path,
            success=True,
            filename_indexed=filename_indexed,
            content_indexed=content_indexed,
            chunk_count=chunk_count,
            deduplicated_count=deduplicated_count,
            embeddings_generated=embeddings_generated,
        )

    def _create_file_entity(self, file_info) -> FileEntity:
        existing = self._file_repo.find_by_path(file_info.path.path)

        if existing:
            existing.mtime = file_info.mtime
            existing.size = file_info.size
            existing.status = IndexStatus.PENDING
            return self._file_repo.save(existing)

        file_entity = FileEntity(
            path=file_info.path,
            file_type=FileType.from_path(file_info.path.path),
            size=file_info.size,
            mtime=file_info.mtime,
            content_hash=None,
            chunk_count=0,
            status=IndexStatus.PENDING,
        )

        return self._file_repo.save(file_entity)

    def _index_filename(self, file_entity: FileEntity) -> bool:
        try:
            filename = file_entity.path.filename

            embedding = self._embedding.embed(filename)

            if embedding is None:
                logger.error("Failed to generate embedding for filename")
                return False

            metadata = {
                "path": file_entity.path.path,
                "type": file_entity.file_type.category.value,
                "filename": filename,
                "dir": file_entity.path.directory,
            }

            success = self._vector_store.insert(
                collection=FILENAME_COLLECTION,
                id=file_entity.path.path,
                vector=embedding,
                metadata=metadata,
            )

            if success:
                file_entity.mark_filename_indexed()
                self._file_repo.save(file_entity)
                logger.debug("Indexed filename: %s", filename)

            return success

        except Exception as err:
            logger.error("Failed to index filename: %s", err)
            return False

    def _index_content(self, file_entity: FileEntity) -> tuple:
        try:
            content_result = self._file_reader.read_content(
                file_entity.path.path
            )

            if not content_result.success or not content_result.text:
                logger.warning(
                    "No content extracted from %s: %s",
                    file_entity.path.path,
                    content_result.error,
                )
                return False, 0, 0, 0

            content_hash = ContentHash.from_content(content_result.text)

            existing = self._file_repo.find_by_path(file_entity.path.path)
            if (
                existing
                and existing.content_hash
                and existing.content_hash.value == content_hash.value
            ):
                logger.debug("Content unchanged, skipping: %s", file_entity.path.path)
                return True, existing.chunk_count, 0, 0

            if file_entity.id is not None:
                old_vector_ids = self._chunk_repo.get_vector_ids_for_file(
                    file_entity.id
                )
                if old_vector_ids:
                    self._vector_store.delete(CONTENT_COLLECTION, old_vector_ids)
                    self._chunk_repo.delete_by_file_id(file_entity.id)

            chunks = self._split_into_chunks(content_result.text)

            if not chunks:
                return False, 0, 0, 0

            dedup_result = None
            if self._dedup_service is not None:
                dedup_result = self._dedup_service.analyze_chunks(chunks)
                logger.debug(
                    "Deduplication analysis: %d new, %d deduplicated",
                    len(dedup_result.new_chunks),
                    len(dedup_result.deduplicated_chunks),
                )

            chunk_entities = []
            new_vector_ids = []
            new_embeddings = []
            new_metadatas = []
            chunk_texts_for_fts = []
            all_vector_ids = []

            if dedup_result is not None:
                new_chunk_texts = [chunk_text for _, chunk_text, _ in dedup_result.new_chunks]
                if new_chunk_texts:
                    batch_embeddings = self._embedding.embed_batch(new_chunk_texts)
                else:
                    batch_embeddings = []

                for i, (idx, chunk_text, chunk_hash) in enumerate(dedup_result.new_chunks):
                    embedding = batch_embeddings[i] if i < len(batch_embeddings) else None

                    if embedding is None:
                        continue

                    compression_result = self._compressor.compress(chunk_text)
                    vector_id = f"{file_entity.path.path}:chunk:{idx}"

                    chunk_entity = ChunkEntity(
                        file_id=file_entity.id,
                        chunk_index=idx,
                        vector_id=vector_id,
                        content_hash=chunk_hash,
                        compressed_content=compression_result.data,
                        original_size=compression_result.original_size,
                        compressed_size=compression_result.compressed_size,
                        compression_type=compression_result.compression_type,
                    )

                    chunk_entities.append(chunk_entity)
                    new_vector_ids.append(vector_id)
                    new_embeddings.append(embedding)
                    new_metadatas.append({
                        "path": file_entity.path.path,
                        "type": file_entity.file_type.category.value,
                        "chunk_index": idx,
                    })
                    chunk_texts_for_fts.append((vector_id, chunk_text, idx))
                    all_vector_ids.append(vector_id)

                for idx, existing_chunk in dedup_result.deduplicated_chunks:
                    chunk_text = chunks[idx]
                    compression_result = self._compressor.compress(chunk_text)

                    chunk_entity = ChunkEntity(
                        file_id=file_entity.id,
                        chunk_index=idx,
                        vector_id=existing_chunk.vector_id,
                        content_hash=existing_chunk.content_hash,
                        compressed_content=compression_result.data,
                        original_size=compression_result.original_size,
                        compressed_size=compression_result.compressed_size,
                        compression_type=compression_result.compression_type,
                    )

                    chunk_entities.append(chunk_entity)
                    chunk_texts_for_fts.append((existing_chunk.vector_id, chunk_text, idx))
                    all_vector_ids.append(existing_chunk.vector_id)

                chunk_entities.sort(key=lambda c: c.chunk_index)

            else:
                batch_embeddings = self._embedding.embed_batch(chunks)

                for idx, chunk_text in enumerate(chunks):
                    embedding = batch_embeddings[idx] if idx < len(batch_embeddings) else None

                    if embedding is None:
                        continue

                    compression_result = self._compressor.compress(chunk_text)
                    vector_id = f"{file_entity.path.path}:chunk:{idx}"

                    chunk_entity = ChunkEntity(
                        file_id=file_entity.id,
                        chunk_index=idx,
                        vector_id=vector_id,
                        content_hash=ContentHash.from_content(chunk_text),
                        compressed_content=compression_result.data,
                        original_size=compression_result.original_size,
                        compressed_size=compression_result.compressed_size,
                        compression_type=compression_result.compression_type,
                    )

                    chunk_entities.append(chunk_entity)
                    new_vector_ids.append(vector_id)
                    new_embeddings.append(embedding)
                    new_metadatas.append({
                        "path": file_entity.path.path,
                        "type": file_entity.file_type.category.value,
                        "chunk_index": idx,
                    })
                    chunk_texts_for_fts.append((vector_id, chunk_text, idx))
                    all_vector_ids.append(vector_id)

            if not chunk_entities:
                return False, 0, 0, 0

            deduplicated_count = dedup_result.dedup_count if dedup_result else 0
            embeddings_generated = len(new_embeddings)

            original_status = file_entity.status
            original_hash = file_entity.content_hash
            original_chunk_count = file_entity.chunk_count

            transaction = IndexingTransaction(
                f"Index content: {file_entity.path.filename}"
            )

            if new_vector_ids:
                transaction.add_step(
                    name=f"Insert {len(new_vector_ids)} vectors",
                    execute=lambda: self._vector_store.insert_batch(
                        collection=CONTENT_COLLECTION,
                        ids=new_vector_ids,
                        vectors=new_embeddings,
                        metadatas=new_metadatas,
                    ),
                    compensate=lambda: self._vector_store.delete(
                        CONTENT_COLLECTION, new_vector_ids
                    ),
                )

            if self._keyword_search is not None and chunk_texts_for_fts:
                fts_docs = [
                    (vid, text, file_entity.path.path, idx)
                    for vid, text, idx in chunk_texts_for_fts
                ]
                transaction.add_step(
                    name=f"Index {len(fts_docs)} chunks in FTS",
                    execute=lambda: self._keyword_search.index_batch(fts_docs) if hasattr(self._keyword_search, 'index_batch') else all(
                        self._keyword_search.index_content(d[0], d[1], d[2], d[3])
                        for d in fts_docs
                    ),
                    compensate=lambda: self._keyword_search.delete_by_file_path(
                        file_entity.path.path
                    ),
                )

            transaction.add_step(
                name=f"Save {len(chunk_entities)} chunks to database",
                execute=lambda: self._chunk_repo.save_batch(chunk_entities),
                compensate=lambda: self._chunk_repo.delete_by_file_id(file_entity.id)
                if file_entity.id
                else None,
            )

            def update_file_status():
                file_entity.mark_content_indexed(
                    content_hash=content_hash,
                    chunk_count=len(chunk_entities),
                )
                self._file_repo.save(file_entity)

            def revert_file_status():
                file_entity.status = original_status
                file_entity.content_hash = original_hash
                file_entity.chunk_count = original_chunk_count
                self._file_repo.save(file_entity)

            transaction.add_step(
                name="Update file entity status",
                execute=update_file_status,
                compensate=revert_file_status,
            )

            result = transaction.execute()

            if result.success:
                if deduplicated_count > 0:
                    logger.info(
                        "Indexed %d chunks for %s (%d new embeddings, %d deduplicated)",
                        len(chunk_entities),
                        file_entity.path.path,
                        embeddings_generated,
                        deduplicated_count,
                    )
                else:
                    logger.info(
                        "Indexed %d chunks for %s (transaction committed)",
                        len(chunk_entities),
                        file_entity.path.path,
                    )
                return True, len(chunk_entities), deduplicated_count, embeddings_generated
            else:
                logger.error(
                    "Content indexing transaction failed for %s: %s",
                    file_entity.path.path,
                    result.error,
                )
                return False, 0, 0, 0

        except Exception as err:
            logger.error(
                "Failed to index content for %s: %s",
                file_entity.path.path,
                err,
            )
            return False, 0, 0, 0

    def _split_into_chunks(self, text: str) -> List[str]:
        if not text:
            return []

        chunks = []
        start = 0

        while start < len(text):
            end = start + DEFAULT_CHUNK_SIZE

            if end < len(text):
                break_point = text.rfind("\n\n", start, end)
                if break_point == -1:
                    break_point = text.rfind(". ", start, end)
                if break_point == -1:
                    break_point = text.rfind(" ", start, end)
                if break_point > start:
                    end = break_point + 1

            chunk = text[start:end].strip()
            if chunk:
                chunks.append(chunk)

            start = end - DEFAULT_CHUNK_OVERLAP
            if start < 0:
                start = end

        return chunks
