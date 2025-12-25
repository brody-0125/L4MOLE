
import pytest
from datetime import datetime

from src.domain.entities.file_entity import FileEntity, IndexStatus
from src.domain.entities.chunk_entity import ChunkEntity
from src.domain.entities.folder_entity import FolderEntity, FolderSettings
from src.domain.value_objects.content_hash import ContentHash
from src.domain.value_objects.file_path import FilePath
from src.domain.value_objects.file_type import FileType, FileCategory
from src.domain.ports.text_compressor_port import CompressionType

class TestFileEntity:

    def test_create_factory(self):
        entity = FileEntity.create(
            path="/home/user/test.txt",
            size=1024,
            mtime=1700000000,
        )
        assert entity.path.path == "/home/user/test.txt"
        assert entity.size == 1024
        assert entity.mtime == 1700000000
        assert entity.status == IndexStatus.PENDING
        assert entity.id is None

    def test_filename_property(self):
        entity = FileEntity.create(path="/test/sample.py")
        assert entity.filename == "sample.py"

    def test_directory_property(self):
        entity = FileEntity.create(path="/test/dir/sample.py")
        assert entity.directory == "/test/dir"

    def test_is_indexable_for_text(self):
        entity = FileEntity.create(path="/test/readme.txt")
        assert entity.is_indexable is True

    def test_is_indexable_for_code(self):
        entity = FileEntity.create(path="/test/script.py")
        assert entity.is_indexable is True

    def test_is_indexed_when_pending(self):
        entity = FileEntity.create(path="/test/file.txt")
        assert entity.is_indexed is False

    def test_is_indexed_when_filename_indexed(self):
        entity = FileEntity.create(path="/test/file.txt")
        entity.mark_filename_indexed()
        assert entity.is_indexed is True

    def test_is_content_indexed(self):
        entity = FileEntity.create(path="/test/file.txt")
        assert entity.is_content_indexed is False

        content_hash = ContentHash.from_content("test")
        entity.mark_content_indexed(content_hash, chunk_count=5)
        assert entity.is_content_indexed is True

    def test_has_changed(self):
        entity = FileEntity.create(path="/test/file.txt", mtime=1000)
        assert entity.has_changed(1000) is False
        assert entity.has_changed(2000) is True

    def test_mark_filename_indexed(self):
        entity = FileEntity.create(path="/test/file.txt")
        entity.mark_filename_indexed()
        assert entity.status == IndexStatus.FILENAME_INDEXED

    def test_mark_filename_indexed_no_downgrade(self):
        entity = FileEntity.create(path="/test/file.txt")
        content_hash = ContentHash.from_content("test")
        entity.mark_content_indexed(content_hash, chunk_count=5)
        entity.mark_filename_indexed()
        assert entity.status == IndexStatus.CONTENT_INDEXED

    def test_mark_content_indexed(self):
        entity = FileEntity.create(path="/test/file.txt")
        content_hash = ContentHash.from_content("test content")
        entity.mark_content_indexed(content_hash, chunk_count=10)

        assert entity.status == IndexStatus.CONTENT_INDEXED
        assert entity.content_hash == content_hash
        assert entity.chunk_count == 10

    def test_mark_failed(self):
        entity = FileEntity.create(path="/test/file.txt")
        entity.mark_failed()
        assert entity.status == IndexStatus.FAILED
        assert entity.is_failed is True

    def test_reset_for_reindex(self):
        entity = FileEntity.create(path="/test/file.txt")
        content_hash = ContentHash.from_content("test")
        entity.mark_content_indexed(content_hash, chunk_count=5)
        entity.chunk_ids = [1, 2, 3]

        entity.reset_for_reindex()

        assert entity.status == IndexStatus.PENDING
        assert entity.content_hash is None
        assert entity.chunk_count == 0
        assert entity.chunk_ids == []

    def test_to_dict(self):
        entity = FileEntity.create(path="/test/file.txt", size=100)
        d = entity.to_dict()

        assert d["path"] == "/test/file.txt"
        assert d["filename"] == "file.txt"
        assert d["size"] == 100
        assert d["status"] == "pending"

class TestChunkEntity:

    def test_create_basic(self):
        entity = ChunkEntity(
            file_id=1,
            chunk_index=0,
            vector_id="file:chunk:0",
            content_hash=ContentHash.from_content("chunk content"),
            compressed_content=b"compressed",
            original_size=100,
            compressed_size=50,
            compression_type=CompressionType.ZSTD,
        )

        assert entity.file_id == 1
        assert entity.chunk_index == 0
        assert entity.vector_id == "file:chunk:0"
        assert entity.original_size == 100
        assert entity.compressed_size == 50

    def test_compression_ratio(self):
        entity = ChunkEntity(
            file_id=1,
            chunk_index=0,
            vector_id="test:chunk:0",
            content_hash=ContentHash.from_content("test"),
            compressed_content=b"data",
            original_size=100,
            compressed_size=25,
            compression_type=CompressionType.ZSTD,
        )

        assert entity.compression_ratio == 0.75

    def test_compression_ratio_zero_original(self):
        entity = ChunkEntity(
            file_id=1,
            chunk_index=0,
            vector_id="test:chunk:0",
            content_hash=ContentHash.from_content(""),
            compressed_content=b"",
            original_size=0,
            compressed_size=0,
            compression_type=CompressionType.NONE,
        )

        assert entity.compression_ratio == 0.0

class TestFolderEntity:

    def test_create_basic(self):
        entity = FolderEntity(path="/home/user/documents")
        assert entity.path == "/home/user/documents"
        assert entity.id is None

    def test_with_settings(self):
        settings = FolderSettings(
            include_hidden=True,
            index_content=True,
        )
        entity = FolderEntity.create(path="/test")
        entity.update_settings(settings)

        assert entity.settings.include_hidden is True
        assert entity.settings.index_content is True

    def test_default_settings(self):
        entity = FolderEntity(path="/test")

        assert entity.settings.include_hidden is False
        assert entity.settings.index_content is True

class TestIndexStatus:

    def test_all_values_exist(self):
        assert IndexStatus.PENDING.value == "pending"
        assert IndexStatus.FILENAME_INDEXED.value == "filename_indexed"
        assert IndexStatus.CONTENT_INDEXED.value == "content_indexed"
        assert IndexStatus.FAILED.value == "failed"

    def test_from_string(self):
        status = IndexStatus("pending")
        assert status == IndexStatus.PENDING
