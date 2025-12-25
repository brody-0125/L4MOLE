
import gzip
import logging

from ...domain.ports.text_compressor_port import (
    CompressionResult,
    CompressionType,
    TextCompressorPort,
)

logger = logging.getLogger(__name__)

class ZstdTextCompressor(TextCompressorPort):

    def __init__(
        self,
        default_type: CompressionType = CompressionType.ZSTD,
        compression_level: int = 3,
    ) -> None:
        self._default_type = default_type
        self._compression_level = compression_level
        self._zstd_compressor = None
        self._zstd_decompressor = None
        self._initialize_compressors()

    def _initialize_compressors(self) -> None:
        try:
            import zstandard as zstd

            self._zstd_compressor = zstd.ZstdCompressor(
                level=self._compression_level
            )
            self._zstd_decompressor = zstd.ZstdDecompressor()
            logger.debug("Zstd compression available")
        except ImportError:
            logger.warning("zstandard not installed, Zstd unavailable")

    @property
    def compression_type(self) -> CompressionType:
        if self._default_type == CompressionType.ZSTD and self._zstd_compressor:
            return CompressionType.ZSTD
        return CompressionType.GZIP

    def compress(self, text: str) -> CompressionResult:
        if not text:
            return CompressionResult(
                data=b"",
                original_size=0,
                compressed_size=0,
                compression_type=CompressionType.NONE,
            )

        original_bytes = text.encode("utf-8")
        original_size = len(original_bytes)

        compression_type = self.compression_type

        try:
            if compression_type == CompressionType.ZSTD:
                compressed = self._zstd_compressor.compress(original_bytes)
            else:
                compressed = gzip.compress(original_bytes, compresslevel=6)
                compression_type = CompressionType.GZIP

            compressed_size = len(compressed)

            if compressed_size >= original_size:
                return CompressionResult(
                    data=original_bytes,
                    original_size=original_size,
                    compressed_size=original_size,
                    compression_type=CompressionType.NONE,
                )

            return CompressionResult(
                data=compressed,
                original_size=original_size,
                compressed_size=compressed_size,
                compression_type=compression_type,
            )

        except Exception as err:
            logger.error("Compression failed: %s", err)
            return CompressionResult(
                data=original_bytes,
                original_size=original_size,
                compressed_size=original_size,
                compression_type=CompressionType.NONE,
            )

    def decompress(
        self,
        data: bytes,
        compression_type: CompressionType,
    ) -> str:
        if not data:
            return ""

        if compression_type == CompressionType.NONE:
            return data.decode("utf-8")

        try:
            if compression_type == CompressionType.ZSTD:
                if self._zstd_decompressor is None:
                    raise ValueError("Zstd decompressor not available")
                decompressed = self._zstd_decompressor.decompress(data)

            elif compression_type == CompressionType.GZIP:
                decompressed = gzip.decompress(data)

            else:
                return data.decode("utf-8")

            return decompressed.decode("utf-8")

        except Exception as err:
            logger.error("Decompression failed: %s", err)
            try:
                return data.decode("utf-8")
            except UnicodeDecodeError:
                return ""

    def is_available(self, compression_type: CompressionType) -> bool:
        if compression_type == CompressionType.NONE:
            return True
        if compression_type == CompressionType.GZIP:
            return True
        if compression_type == CompressionType.ZSTD:
            return self._zstd_compressor is not None
        return False
