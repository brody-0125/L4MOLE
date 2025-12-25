
import gzip
from unittest.mock import patch, MagicMock

import pytest

from src.domain.ports.text_compressor_port import CompressionResult, CompressionType
from src.infrastructure.compression.zstd_compressor import ZstdTextCompressor


class TestZstdTextCompressorInitialization:

    def test_default_initialization(self):
        compressor = ZstdTextCompressor()

        assert compressor._default_type == CompressionType.ZSTD
        assert compressor._compression_level == 3

    def test_custom_compression_level(self):
        compressor = ZstdTextCompressor(compression_level=9)

        assert compressor._compression_level == 9

    def test_gzip_default_type(self):
        compressor = ZstdTextCompressor(default_type=CompressionType.GZIP)

        assert compressor._default_type == CompressionType.GZIP

    def test_zstd_compressor_initialized_when_available(self):
        compressor = ZstdTextCompressor()

        assert compressor._zstd_compressor is not None
        assert compressor._zstd_decompressor is not None

    def test_zstd_unavailable_fallback(self):
        with patch.dict("sys.modules", {"zstandard": None}):
            with patch(
                "src.infrastructure.compression.zstd_compressor.ZstdTextCompressor._initialize_compressors"
            ) as mock_init:
                compressor = ZstdTextCompressor()

                mock_init.assert_called_once()


class TestCompressionType:

    def test_compression_type_zstd_when_available(self):
        compressor = ZstdTextCompressor(default_type=CompressionType.ZSTD)

        assert compressor.compression_type == CompressionType.ZSTD

    def test_compression_type_gzip_when_zstd_unavailable(self):
        compressor = ZstdTextCompressor(default_type=CompressionType.ZSTD)
        compressor._zstd_compressor = None

        assert compressor.compression_type == CompressionType.GZIP

    def test_compression_type_gzip_when_default(self):
        compressor = ZstdTextCompressor(default_type=CompressionType.GZIP)

        assert compressor.compression_type == CompressionType.GZIP


class TestCompress:

    def test_compress_empty_string(self):
        compressor = ZstdTextCompressor()

        result = compressor.compress("")

        assert result.data == b""
        assert result.original_size == 0
        assert result.compressed_size == 0
        assert result.compression_type == CompressionType.NONE

    def test_compress_with_zstd(self):
        compressor = ZstdTextCompressor()
        text = "This is a test string that should be compressed. " * 10

        result = compressor.compress(text)

        assert isinstance(result, CompressionResult)
        assert result.original_size == len(text.encode("utf-8"))
        assert result.compressed_size < result.original_size
        assert result.compression_type == CompressionType.ZSTD

    def test_compress_with_gzip_fallback(self):
        compressor = ZstdTextCompressor()
        compressor._zstd_compressor = None
        text = "This is a test string that should be compressed. " * 10

        result = compressor.compress(text)

        assert result.compression_type == CompressionType.GZIP
        assert result.compressed_size < result.original_size

    def test_compress_small_text_no_compression(self):
        compressor = ZstdTextCompressor()
        text = "Hi"

        result = compressor.compress(text)

        assert result.compression_type == CompressionType.NONE
        assert result.data == text.encode("utf-8")
        assert result.compressed_size == result.original_size

    def test_compress_handles_unicode(self):
        compressor = ZstdTextCompressor()
        text = "한글 테스트 문자열입니다. 유니코드를 잘 처리해야 합니다. " * 10

        result = compressor.compress(text)

        assert result.original_size == len(text.encode("utf-8"))
        assert result.compressed_size <= result.original_size

    def test_compress_handles_exception(self):
        compressor = ZstdTextCompressor()
        compressor._zstd_compressor = MagicMock()
        compressor._zstd_compressor.compress.side_effect = Exception("Compression error")
        text = "Test text"

        result = compressor.compress(text)

        assert result.compression_type == CompressionType.NONE
        assert result.data == text.encode("utf-8")


class TestDecompress:

    def test_decompress_empty_data(self):
        compressor = ZstdTextCompressor()

        result = compressor.decompress(b"", CompressionType.NONE)

        assert result == ""

    def test_decompress_none_type(self):
        compressor = ZstdTextCompressor()
        data = "Hello, World!".encode("utf-8")

        result = compressor.decompress(data, CompressionType.NONE)

        assert result == "Hello, World!"

    def test_decompress_zstd(self):
        compressor = ZstdTextCompressor()
        original = "This is a test string that should be compressed. " * 10

        compressed = compressor.compress(original)
        decompressed = compressor.decompress(
            compressed.data, compressed.compression_type
        )

        assert decompressed == original

    def test_decompress_gzip(self):
        compressor = ZstdTextCompressor()
        original = "This is a gzip test string. " * 10
        compressed_data = gzip.compress(original.encode("utf-8"))

        result = compressor.decompress(compressed_data, CompressionType.GZIP)

        assert result == original

    def test_decompress_zstd_unavailable_falls_back_to_decode(self):
        compressor = ZstdTextCompressor()
        compressor._zstd_decompressor = None
        data = b"fallback text"

        result = compressor.decompress(data, CompressionType.ZSTD)

        assert result == "fallback text"

    def test_decompress_unknown_type_returns_decoded(self):
        compressor = ZstdTextCompressor()
        data = "test".encode("utf-8")

        result = compressor.decompress(data, CompressionType.NONE)

        assert result == "test"

    def test_decompress_zstd_exception_falls_back_to_decode(self):
        compressor = ZstdTextCompressor()

        result = compressor.decompress(b"invalid zstd data", CompressionType.ZSTD)

        assert result == "invalid zstd data"

    def test_decompress_gzip_exception_falls_back_to_decode(self):
        compressor = ZstdTextCompressor()

        result = compressor.decompress(b"invalid gzip data", CompressionType.GZIP)

        assert result == "invalid gzip data"

    def test_decompress_fallback_with_invalid_unicode_returns_empty(self):
        compressor = ZstdTextCompressor()

        result = compressor.decompress(b"\xff\xfe\x00\x01", CompressionType.GZIP)

        assert result == ""

    def test_decompress_handles_unicode(self):
        compressor = ZstdTextCompressor()
        original = "한글 유니코드 테스트 " * 10

        compressed = compressor.compress(original)
        decompressed = compressor.decompress(
            compressed.data, compressed.compression_type
        )

        assert decompressed == original


class TestIsAvailable:

    def test_none_always_available(self):
        compressor = ZstdTextCompressor()

        assert compressor.is_available(CompressionType.NONE) is True

    def test_gzip_always_available(self):
        compressor = ZstdTextCompressor()

        assert compressor.is_available(CompressionType.GZIP) is True

    def test_zstd_available_when_initialized(self):
        compressor = ZstdTextCompressor()

        assert compressor.is_available(CompressionType.ZSTD) is True

    def test_zstd_unavailable_when_not_initialized(self):
        compressor = ZstdTextCompressor()
        compressor._zstd_compressor = None

        assert compressor.is_available(CompressionType.ZSTD) is False

    def test_unknown_type_not_available(self):
        compressor = ZstdTextCompressor()

        unknown_type = MagicMock()
        unknown_type.__eq__ = lambda self, other: False

        result = compressor.is_available(unknown_type)

        assert result is False


class TestRoundTrip:

    @pytest.mark.parametrize(
        "text",
        [
            "Simple ASCII text",
            "한글 텍스트",
            "Mixed 혼합 text テキスト",
            "Special chars: @#$%^&*()",
            "\n".join(["Line " + str(i) for i in range(100)]),
            "A" * 10000,
        ],
    )
    def test_roundtrip_various_texts(self, text):
        compressor = ZstdTextCompressor()

        compressed = compressor.compress(text)
        decompressed = compressor.decompress(
            compressed.data, compressed.compression_type
        )

        assert decompressed == text

    def test_roundtrip_with_gzip(self):
        compressor = ZstdTextCompressor(default_type=CompressionType.GZIP)
        text = "Test text for gzip compression. " * 20

        compressed = compressor.compress(text)
        assert compressed.compression_type == CompressionType.GZIP

        decompressed = compressor.decompress(
            compressed.data, compressed.compression_type
        )
        assert decompressed == text
