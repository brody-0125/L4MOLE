
import tempfile
import os
import pytest

from src.infrastructure.persistence.sqlite.connection import SqliteConnectionManager
from src.infrastructure.persistence.sqlite.fts_search_adapter import SqliteFTS5Adapter

class TestSqliteFTS5Adapter:

    @pytest.fixture
    def adapter(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "test.db")
            conn_manager = SqliteConnectionManager(db_path)
            adapter = SqliteFTS5Adapter(conn_manager)
            yield adapter
            conn_manager.close()

    def test_index_and_search_single_document(self, adapter):
        success = adapter.index_content(
            doc_id="doc1",
            content="The quick brown fox jumps over the lazy dog",
            file_path="/path/file.txt",
            chunk_index=0,
        )

        assert success is True

        results = adapter.search("quick brown fox", top_k=10)

        assert len(results) == 1
        assert results[0].id == "doc1"
        assert results[0].file_path == "/path/file.txt"
        assert results[0].chunk_index == 0
        assert results[0].score > 0

    def test_search_returns_ranked_results(self, adapter):
        adapter.index_content("doc1", "apple banana cherry", "/f1.txt", 0)
        adapter.index_content("doc2", "apple apple apple banana", "/f2.txt", 0)
        adapter.index_content("doc3", "cherry date elderberry", "/f3.txt", 0)

        results = adapter.search("apple", top_k=10)

        assert len(results) == 2
        assert results[0].id == "doc2"
        assert results[1].id == "doc1"

    def test_search_with_multiple_terms(self, adapter):
        adapter.index_content("doc1", "machine learning algorithms", "/ml.txt", 0)
        adapter.index_content("doc2", "deep learning neural networks", "/dl.txt", 0)
        adapter.index_content("doc3", "database algorithms", "/db.txt", 0)

        results = adapter.search("learning algorithms", top_k=10)

        assert len(results) >= 1
        assert any(r.id == "doc1" for r in results)

    def test_search_respects_top_k(self, adapter):
        for i in range(10):
            adapter.index_content(f"doc{i}", f"common term document {i}", f"/f{i}.txt", 0)

        results = adapter.search("common", top_k=3)

        assert len(results) == 3

    def test_search_no_results(self, adapter):
        adapter.index_content("doc1", "hello world", "/f1.txt", 0)

        results = adapter.search("xyznotfound", top_k=10)

        assert results == []

    def test_search_empty_query(self, adapter):
        adapter.index_content("doc1", "hello world", "/f1.txt", 0)

        results = adapter.search("", top_k=10)
        assert results == []

        results = adapter.search("   ", top_k=10)
        assert results == []

    def test_search_korean_text(self, adapter):
        adapter.index_content("doc1", "안녕하세요 세계", "/korean.txt", 0)
        adapter.index_content("doc2", "한글 테스트 문서입니다", "/korean2.txt", 0)

        results = adapter.search("한글 테스트", top_k=10)

        assert len(results) >= 1
        assert results[0].id == "doc2"

    def test_search_snippet_generation(self, adapter):
        long_content = "This is a long document. " * 10 + "important keyword here. " + "More text follows. " * 10
        adapter.index_content("doc1", long_content, "/long.txt", 0)

        results = adapter.search("important keyword", top_k=10)

        assert len(results) == 1
        assert "important" in results[0].snippet.lower() or "keyword" in results[0].snippet.lower()

    def test_delete_by_file_path(self, adapter):
        adapter.index_content("doc1", "content one", "/path/file.txt", 0)
        adapter.index_content("doc2", "content two", "/path/file.txt", 1)
        adapter.index_content("doc3", "content three", "/other/file.txt", 0)

        deleted = adapter.delete_by_file_path("/path/file.txt")

        assert deleted == 2
        assert adapter.count() == 1

        results = adapter.search("content", top_k=10)
        assert len(results) == 1
        assert results[0].file_path == "/other/file.txt"

    def test_delete_by_doc_id(self, adapter):
        adapter.index_content("doc1", "content one", "/f1.txt", 0)
        adapter.index_content("doc2", "content two", "/f2.txt", 0)

        success = adapter.delete_by_doc_id("doc1")

        assert success is True
        assert adapter.count() == 1

        results = adapter.search("content", top_k=10)
        assert len(results) == 1
        assert results[0].id == "doc2"

    def test_delete_nonexistent_doc(self, adapter):
        success = adapter.delete_by_doc_id("nonexistent")
        assert success is False

    def test_count(self, adapter):
        assert adapter.count() == 0

        adapter.index_content("doc1", "test", "/f1.txt", 0)
        assert adapter.count() == 1

        adapter.index_content("doc2", "test", "/f2.txt", 0)
        assert adapter.count() == 2

    def test_index_replaces_existing_doc(self, adapter):
        adapter.index_content("doc1", "original content", "/f1.txt", 0)
        adapter.index_content("doc1", "updated content", "/f1.txt", 0)

        assert adapter.count() == 1

        results = adapter.search("updated", top_k=10)
        assert len(results) == 1

        results = adapter.search("original", top_k=10)
        assert len(results) == 0

    def test_index_batch(self, adapter):
        documents = [
            ("doc1", "first document content", "/f1.txt", 0),
            ("doc2", "second document content", "/f2.txt", 1),
            ("doc3", "third document content", "/f3.txt", 2),
        ]

        count = adapter.index_batch(documents)

        assert count == 3
        assert adapter.count() == 3

        results = adapter.search("document", top_k=10)
        assert len(results) == 3

    def test_index_batch_empty(self, adapter):
        count = adapter.index_batch([])
        assert count == 0

    def test_optimize(self, adapter):
        adapter.index_content("doc1", "test content", "/f1.txt", 0)

        success = adapter.optimize()

        assert success is True

    def test_special_characters_in_query(self, adapter):
        adapter.index_content("doc1", "test function() call", "/f1.txt", 0)

        results = adapter.search("function()", top_k=10)
        assert isinstance(results, list)

    def test_prefix_search(self, adapter):
        adapter.index_content("doc1", "programming languages", "/f1.txt", 0)
        adapter.index_content("doc2", "program execution", "/f2.txt", 0)

        results = adapter.search("program", top_k=10)

        assert len(results) >= 1
