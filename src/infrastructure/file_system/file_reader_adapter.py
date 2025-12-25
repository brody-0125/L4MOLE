
import logging
import os
import platform
from typing import List, Optional

from ...domain.ports.file_reader_port import (
    FileContent,
    FileInfo,
    FileReaderPort,
)
from ...domain.value_objects.file_path import FilePath
from ...domain.value_objects.file_type import FileCategory, FileType

logger = logging.getLogger(__name__)

SUPPORTED_TEXT_EXTENSIONS = (".txt", ".md", ".py", ".json", ".csv", ".xml", ".yaml", ".yml")
SUPPORTED_IMAGE_EXTENSIONS = (".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp")
SUPPORTED_PDF_EXTENSIONS = (".pdf",)

class LocalFileReader(FileReaderPort):

    def __init__(
        self,
        image_caption_model: str = "llava",
    ) -> None:
        self._image_caption_model = image_caption_model
        self._ollama = None
        self._pypdf = None
        self._initialize_dependencies()

    def _initialize_dependencies(self) -> None:
        try:
            import ollama

            self._ollama = ollama
        except ImportError:
            logger.warning("ollama not installed, image captioning unavailable")

        try:
            from pypdf import PdfReader

            self._pypdf = PdfReader
        except ImportError:
            logger.warning("pypdf not installed, PDF reading unavailable")

    def get_info(self, path: str) -> FileInfo:
        try:
            stat = os.stat(path)
            return FileInfo(
                path=FilePath(path=path),
                size=stat.st_size,
                mtime=int(stat.st_mtime),
                exists=True,
            )
        except OSError:
            return FileInfo(
                path=FilePath(path=path),
                size=0,
                mtime=0,
                exists=False,
            )

    def exists(self, path: str) -> bool:
        return os.path.exists(path) and os.path.isfile(path)

    def read_text(self, path: str) -> FileContent:
        file_type = FileType.from_path(path)

        try:
            with open(path, "r", encoding="utf-8", errors="ignore") as f:
                text = f.read()

            return FileContent(
                text=text,
                file_type=file_type,
                success=True,
            )

        except Exception as err:
            logger.error("Failed to read text file %s: %s", path, err)
            return FileContent(
                text="",
                file_type=file_type,
                success=False,
                error=str(err),
            )

    def read_pdf(self, path: str) -> FileContent:
        file_type = FileType.from_path(path)

        if self._pypdf is None:
            return FileContent(
                text="",
                file_type=file_type,
                success=False,
                error="pypdf not installed",
            )

        reader = None
        try:
            reader = self._pypdf(path)
            pages_text = []

            for page in reader.pages:
                text = page.extract_text()
                if text:
                    pages_text.append(text)

            return FileContent(
                text="\n".join(pages_text),
                file_type=file_type,
                success=True,
            )

        except Exception as err:
            logger.error("Failed to read PDF %s: %s", path, err)
            return FileContent(
                text="",
                file_type=file_type,
                success=False,
                error=str(err),
            )
        finally:
            if reader is not None:
                try:
                    reader.close()
                except (AttributeError, Exception):
                    pass

    def describe_image(self, path: str) -> FileContent:
        file_type = FileType.from_path(path)

        if self._ollama is None:
            return FileContent(
                text="",
                file_type=file_type,
                success=False,
                error="ollama not installed",
            )

        try:
            response = self._ollama.generate(
                model=self._image_caption_model,
                prompt="Describe this image in detail.",
                images=[path],
            )

            description = response.get("response", "")
            return FileContent(
                text=description,
                file_type=file_type,
                success=True,
            )

        except Exception as err:
            logger.error("Failed to describe image %s: %s", path, err)
            return FileContent(
                text="",
                file_type=file_type,
                success=False,
                error=str(err),
            )

    def read_content(self, path: str) -> FileContent:
        file_type = FileType.from_path(path)

        if file_type.category == FileCategory.PDF:
            return self.read_pdf(path)

        if file_type.category == FileCategory.IMAGE:
            return self.describe_image(path)

        if file_type.category == FileCategory.TEXT:
            return self.read_text(path)

        return self.read_text(path)

    def list_files(
        self,
        directory: str,
        recursive: bool = True,
        include_hidden: bool = False,
    ) -> List[FilePath]:
        files = []

        try:
            if recursive:
                for root, dirs, filenames in os.walk(directory):
                    if not include_hidden:
                        dirs[:] = [
                            d for d in dirs
                            if not self._is_hidden(os.path.join(root, d))
                        ]

                    for filename in filenames:
                        file_path = os.path.join(root, filename)

                        if not include_hidden and self._is_hidden(file_path):
                            continue

                        if self._is_supported_file(file_path):
                            files.append(FilePath(path=file_path))
            else:
                for item in os.listdir(directory):
                    file_path = os.path.join(directory, item)

                    if not os.path.isfile(file_path):
                        continue

                    if not include_hidden and self._is_hidden(file_path):
                        continue

                    if self._is_supported_file(file_path):
                        files.append(FilePath(path=file_path))

        except Exception as err:
            logger.error("Failed to list directory %s: %s", directory, err)

        return files

    def is_directory(self, path: str) -> bool:
        return os.path.isdir(path)

    def _is_hidden(self, path: str) -> bool:
        path = os.path.abspath(path)
        is_windows = platform.system() == "Windows"

        if is_windows:
            try:
                import ctypes

                attrs = ctypes.windll.kernel32.GetFileAttributesW(path)
                if attrs != 0xFFFFFFFF and attrs & 2:
                    return True
            except Exception:
                pass

        while path and path != os.path.dirname(path):
            basename = os.path.basename(path)

            if basename.startswith("."):
                return True

            path = os.path.dirname(path)

        return False

    def _is_supported_file(self, path: str) -> bool:
        path_lower = path.lower()

        supported = (
            SUPPORTED_TEXT_EXTENSIONS
            + SUPPORTED_IMAGE_EXTENSIONS
            + SUPPORTED_PDF_EXTENSIONS
        )

        return any(path_lower.endswith(ext) for ext in supported)
