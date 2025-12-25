
import pytest

from src.domain.value_objects.content_hash import ContentHash
from src.domain.value_objects.embedding_vector import EmbeddingVector
from src.domain.value_objects.file_path import FilePath
from src.domain.value_objects.file_type import FileType, FileCategory
from src.domain.value_objects.search_query import SearchQuery, SearchMode
from src.domain.value_objects.search_result import SearchResult, SearchResultTier

class TestFilePath:

    def test_create_from_path(self):
        fp = FilePath("/home/user/documents/test.txt")
        assert fp.path == "/home/user/documents/test.txt"
        assert fp.filename == "test.txt"
        assert fp.directory == "/home/user/documents"
        assert fp.extension == "txt"

    def test_hidden_file_detection(self):
        hidden = FilePath("/home/.hidden_file")
        normal = FilePath("/home/normal_file.txt")
        assert hidden.is_hidden() is True
        assert normal.is_hidden() is False

    def test_empty_extension(self):
        fp = FilePath("/test/Makefile")
        assert fp.extension == ""

    def test_equality(self):
        fp1 = FilePath("/test/file.txt")
        fp2 = FilePath("/test/file.txt")
        fp3 = FilePath("/test/other.txt")
        assert fp1 == fp2
        assert fp1 != fp3

    def test_immutability(self):
        fp = FilePath("/test/file.txt")
        with pytest.raises(AttributeError):
            fp.path = "/other/path.txt"

    def test_is_under(self):
        fp = FilePath("/home/user/documents/test.txt")
        assert fp.is_under("/home/user") is True
        assert fp.is_under("/other/path") is False

    def test_with_suffix(self):
        fp = FilePath("/test/file.txt")
        fp2 = fp.with_suffix(".md")
        assert fp2.extension == "md"

    def test_empty_path_raises(self):
        with pytest.raises(ValueError, match="cannot be empty"):
            FilePath("")

class TestFileType:

    def test_from_extension_text(self):
        ft = FileType.from_extension(".txt")
        assert ft.category == FileCategory.TEXT
        assert ft.is_indexable is True

    def test_from_extension_python(self):
        ft = FileType.from_extension(".py")
        assert ft.category == FileCategory.TEXT
        assert ft.is_indexable is True

    def test_from_extension_image(self):
        ft = FileType.from_extension(".png")
        assert ft.category == FileCategory.IMAGE

    def test_from_extension_pdf(self):
        ft = FileType.from_extension(".pdf")
        assert ft.category == FileCategory.PDF

    def test_from_extension_unknown(self):
        ft = FileType.from_extension(".xyz123")
        assert ft.category == FileCategory.UNKNOWN

    def test_from_path(self):
        ft = FileType.from_path("/home/user/script.py")
        assert ft.category == FileCategory.TEXT

    def test_case_insensitive(self):
        ft1 = FileType.from_extension(".PY")
        ft2 = FileType.from_extension(".py")
        assert ft1.category == ft2.category

    def test_is_text_property(self):
        ft = FileType.from_extension(".txt")
        assert ft.is_text is True

    def test_is_pdf_property(self):
        ft = FileType.from_extension(".pdf")
        assert ft.is_pdf is True

    def test_is_image_property(self):
        ft = FileType.from_extension(".png")
        assert ft.is_image is True

class TestContentHash:

    def test_from_content(self):
        ch = ContentHash.from_content("Hello, World!")
        assert ch.value is not None
        assert len(ch.value) == 16

    def test_same_content_same_hash(self):
        ch1 = ContentHash.from_content("test content")
        ch2 = ContentHash.from_content("test content")
        assert ch1.value == ch2.value

    def test_different_content_different_hash(self):
        ch1 = ContentHash.from_content("content 1")
        ch2 = ContentHash.from_content("content 2")
        assert ch1.value != ch2.value

    def test_equality(self):
        ch1 = ContentHash.from_content("test")
        ch2 = ContentHash.from_content("test")
        assert ch1 == ch2

    def test_immutability(self):
        ch = ContentHash.from_content("test")
        with pytest.raises(AttributeError):
            ch.value = "new_hash"

    def test_from_bytes(self):
        ch = ContentHash.from_bytes(b"binary data")
        assert len(ch.value) == 16

    def test_str_representation(self):
        ch = ContentHash.from_content("test")
        assert str(ch) == ch.value

class TestEmbeddingVector:

    def test_create(self):
        values = [0.1, 0.2, 0.3, 0.4, 0.5]
        ev = EmbeddingVector(values)
        assert ev.dimension == 5
        assert ev.values == tuple(values)

    def test_to_list(self):
        values = [0.1, 0.2, 0.3]
        ev = EmbeddingVector(values)
        assert ev.to_list() == values

    def test_immutability(self):
        ev = EmbeddingVector([0.1, 0.2])
        with pytest.raises(AttributeError):
            ev.values = (0.3, 0.4)

    def test_dimension_property(self):
        ev = EmbeddingVector([0.1] * 768)
        assert ev.dimension == 768

    def test_len(self):
        ev = EmbeddingVector([0.1, 0.2, 0.3])
        assert len(ev) == 3

    def test_getitem(self):
        ev = EmbeddingVector([0.1, 0.2, 0.3])
        assert ev[0] == 0.1
        assert ev[2] == 0.3

    def test_empty_raises(self):
        with pytest.raises(ValueError, match="cannot be empty"):
            EmbeddingVector([])

    def test_cosine_distance(self):
        ev1 = EmbeddingVector([1.0, 0.0])
        ev2 = EmbeddingVector([0.0, 1.0])
        assert ev1.cosine_distance(ev2) == pytest.approx(1.0)

    def test_similarity_percent(self):
        ev1 = EmbeddingVector([1.0, 0.0])
        ev2 = EmbeddingVector([1.0, 0.0])
        assert ev1.similarity_percent(ev2) == pytest.approx(100.0)

class TestSearchQuery:

    def test_create_basic(self):
        sq = SearchQuery(text="test query")
        assert sq.text == "test query"
        assert sq.mode == SearchMode.FILENAME
        assert sq.max_results == 10

    def test_create_with_options(self):
        sq = SearchQuery(
            text="search term",
            mode=SearchMode.CONTENT,
            max_results=20,
            min_similarity=50.0,
        )
        assert sq.mode == SearchMode.CONTENT
        assert sq.max_results == 20
        assert sq.min_similarity == 50.0

    def test_empty_text_raises(self):
        with pytest.raises(ValueError, match="cannot be empty"):
            SearchQuery(text="")

    def test_whitespace_only_raises(self):
        with pytest.raises(ValueError, match="cannot be empty"):
            SearchQuery(text="   ")

    def test_invalid_max_results_raises(self):
        with pytest.raises(ValueError, match="max_results must be at least 1"):
            SearchQuery(text="test", max_results=0)

    def test_invalid_min_similarity_raises(self):
        with pytest.raises(ValueError, match="min_similarity must be between"):
            SearchQuery(text="test", min_similarity=101.0)

    def test_normalized_text(self):
        sq = SearchQuery(text="  test query  ")
        assert sq.normalized_text == "test query"

    def test_with_mode(self):
        sq1 = SearchQuery(text="test", mode=SearchMode.FILENAME)
        sq2 = sq1.with_mode(SearchMode.CONTENT)
        assert sq1.mode == SearchMode.FILENAME
        assert sq2.mode == SearchMode.CONTENT
        assert sq1.text == sq2.text

    def test_with_max_results(self):
        sq1 = SearchQuery(text="test", max_results=10)
        sq2 = sq1.with_max_results(50)
        assert sq1.max_results == 10
        assert sq2.max_results == 50

    def test_immutability(self):
        sq = SearchQuery(text="test")
        with pytest.raises(AttributeError):
            sq.text = "new text"

    def test_combined_mode(self):
        sq = SearchQuery(text="test", mode=SearchMode.COMBINED)
        assert sq.mode == SearchMode.COMBINED

class TestSearchResult:

    def test_create_basic(self):
        sr = SearchResult(
            file_path="/test/file.txt",
            similarity_score=85.0,
            match_type="filename",
        )
        assert sr.file_path == "/test/file.txt"
        assert sr.similarity_score == 85.0
        assert sr.match_type == "filename"

    def test_tier_excellent(self):
        sr = SearchResult(
            file_path="/test.txt",
            similarity_score=95.0,
            match_type="content",
        )
        assert sr.tier == SearchResultTier.EXCELLENT

    def test_tier_good(self):
        sr = SearchResult(
            file_path="/test.txt",
            similarity_score=85.0,
            match_type="content",
        )
        assert sr.tier == SearchResultTier.GOOD

    def test_tier_fair(self):
        sr = SearchResult(
            file_path="/test.txt",
            similarity_score=70.0,
            match_type="content",
        )
        assert sr.tier == SearchResultTier.FAIR

    def test_tier_low(self):
        sr = SearchResult(
            file_path="/test.txt",
            similarity_score=50.0,
            match_type="content",
        )
        assert sr.tier == SearchResultTier.LOW

    def test_matches_threshold(self):
        sr = SearchResult(
            file_path="/test.txt",
            similarity_score=75.0,
            match_type="content",
        )
        assert sr.matches_threshold(70.0) is True
        assert sr.matches_threshold(80.0) is False

    def test_to_dict(self):
        sr = SearchResult(
            file_path="/test.txt",
            similarity_score=85.0,
            match_type="filename",
            chunk_index=0,
            snippet="test snippet",
        )
        d = sr.to_dict()
        assert d["path"] == "/test.txt"
        assert d["similarity"] == 85.0
        assert d["match_type"] == "filename"
        assert d["chunk_index"] == 0
        assert d["snippet"] == "test snippet"
        assert d["tier"] == "good"

    def test_immutability(self):
        sr = SearchResult(
            file_path="/test.txt",
            similarity_score=85.0,
            match_type="filename",
        )
        with pytest.raises(AttributeError):
            sr.similarity_score = 90.0
