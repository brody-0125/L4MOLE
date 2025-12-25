
import os
import tempfile
from typing import Generator

import pytest

from src.domain.entities.file_entity import FileEntity, IndexStatus
from src.domain.entities.chunk_entity import ChunkEntity
from src.domain.value_objects.content_hash import ContentHash
from src.domain.value_objects.file_path import FilePath
from src.domain.value_objects.file_type import FileType
from src.domain.ports.text_compressor_port import CompressionType

@pytest.fixture
def temp_dir() -> Generator[str, None, None]:
    with tempfile.TemporaryDirectory() as tmpdir:
        yield tmpdir

@pytest.fixture
def sample_text_file(temp_dir: str) -> str:
    file_path = os.path.join(temp_dir, "sample.txt")
    content = "This is a sample text file for testing purposes.\n" * 10
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(content)
    return file_path

@pytest.fixture
def sample_python_file(temp_dir: str) -> str:
    file_path = os.path.join(temp_dir, "sample.py")
    content = '''"""Sample Python module."""

def hello_world():
    """Print hello world."""
    print("Hello, World!")

class SampleClass:
    """A sample class for testing."""

    def __init__(self, name: str):
        self.name = name

    def greet(self) -> str:
        return f"Hello, {self.name}!"
'''
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(content)
    return file_path

@pytest.fixture
def sample_file_entity() -> FileEntity:
    return FileEntity(
        id=1,
        path=FilePath("/test/sample.txt"),
        file_type=FileType.from_extension(".txt"),
        size=1024,
        mtime=1700000000,
        content_hash=ContentHash.from_content("test content"),
        status=IndexStatus.PENDING,
        chunk_count=0,
    )

@pytest.fixture
def sample_chunk_entity() -> ChunkEntity:
    return ChunkEntity(
        id=1,
        file_id=1,
        chunk_index=0,
        vector_id="test:chunk:0",
        content_hash=ContentHash.from_content("chunk content"),
        compressed_content=b"compressed data",
        original_size=100,
        compressed_size=50,
        compression_type=CompressionType.ZSTD,
    )

@pytest.fixture
def sample_content() -> str:
    return """
    Lorem ipsum dolor sit amet, consectetur adipiscing elit.
    Sed do eiusmod tempor incididunt ut labore et dolore magna aliqua.
    Ut enim ad minim veniam, quis nostrud exercitation ullamco laboris.

    This is a test document with multiple paragraphs.
    It should be used to test text processing functionality.

    The quick brown fox jumps over the lazy dog.
    Pack my box with five dozen liquor jugs.
    """ * 50  # Make it large enough for chunking tests
