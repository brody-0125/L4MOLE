
import logging
from dataclasses import dataclass, field
from typing import Callable, List, Optional

from ...domain.entities.folder_entity import FolderEntity, FolderSettings
from ...domain.ports.file_reader_port import FileReaderPort
from ...domain.ports.folder_repository import FolderRepository
from .index_file import IndexFileResult, IndexFileUseCase

logger = logging.getLogger(__name__)

@dataclass
class IndexFolderResult:

    path: str
    total_files: int
    indexed_files: int
    failed_files: int
    total_chunks: int
    errors: List[str] = field(default_factory=list)

    @property
    def success_rate(self) -> float:
        if self.total_files == 0:
            return 0.0
        return self.indexed_files / self.total_files

ProgressCallback = Callable[[str, int, int], None]

class IndexFolderUseCase:

    def __init__(
        self,
        folder_repository: FolderRepository,
        file_reader: FileReaderPort,
        index_file_use_case: IndexFileUseCase,
    ) -> None:
        self._folder_repo = folder_repository
        self._file_reader = file_reader
        self._index_file = index_file_use_case

    def execute(
        self,
        folder_path: str,
        include_hidden: bool = False,
        index_content: bool = True,
        progress_callback: Optional[ProgressCallback] = None,
    ) -> IndexFolderResult:
        logger.info("Indexing folder: %s", folder_path)

        if not self._file_reader.is_directory(folder_path):
            return IndexFolderResult(
                path=folder_path,
                total_files=0,
                indexed_files=0,
                failed_files=0,
                total_chunks=0,
                errors=["Folder does not exist or is not a directory"],
            )

        folder_settings = FolderSettings(
            include_hidden=include_hidden,
            index_content=index_content,
        )
        folder_entity = FolderEntity(
            path=folder_path,
            settings=folder_settings,
        )
        self._folder_repo.save(folder_entity)

        files = self._file_reader.list_files(
            directory=folder_path,
            recursive=True,
            include_hidden=include_hidden,
        )

        total_files = len(files)
        indexed_files = 0
        failed_files = 0
        total_chunks = 0
        errors: List[str] = []

        logger.info("Found %d files to index", total_files)

        for idx, file_path in enumerate(files):
            if progress_callback:
                progress_callback(file_path.path, idx + 1, total_files)

            result = self._index_file.execute(
                file_path=file_path.path,
                index_content=index_content,
            )

            if result.success:
                indexed_files += 1
                total_chunks += result.chunk_count
            else:
                failed_files += 1
                if result.error:
                    errors.append(f"{file_path.path}: {result.error}")

        logger.info(
            "Folder indexing complete: %d/%d files indexed, %d chunks",
            indexed_files,
            total_files,
            total_chunks,
        )

        return IndexFolderResult(
            path=folder_path,
            total_files=total_files,
            indexed_files=indexed_files,
            failed_files=failed_files,
            total_chunks=total_chunks,
            errors=errors,
        )

    def remove_folder(self, folder_path: str) -> bool:
        return self._folder_repo.delete(folder_path)

    def get_indexed_folders(self) -> List[FolderEntity]:
        return self._folder_repo.find_all()
