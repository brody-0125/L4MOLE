
import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Depends

from ..app_service import ApplicationService, SearchMode
from .models import (
    IndexFileRequest,
    IndexFolderRequest,
    IndexResult,
    SearchModeAPI,
    SearchRequest,
    SearchResponse,
    SearchResultItem,
    StatusResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1", tags=["L4MOLE API"])

_app_service: Optional[ApplicationService] = None


def get_app_service() -> ApplicationService:
    global _app_service
    if _app_service is None:
        _app_service = ApplicationService()
    return _app_service


def _convert_search_mode(mode: SearchModeAPI) -> SearchMode:
    mode_map = {
        SearchModeAPI.FILENAME: SearchMode.FILENAME,
        SearchModeAPI.CONTENT: SearchMode.CONTENT,
        SearchModeAPI.HYBRID: SearchMode.HYBRID,
        SearchModeAPI.COMBINED: SearchMode.COMBINED,
    }
    return mode_map[mode]


@router.get("/status", response_model=StatusResponse)
async def get_status(
    app_service: ApplicationService = Depends(get_app_service),
) -> StatusResponse:
    """Get the current status of the indexing service."""
    try:
        file_count = app_service._container.file_repository.count()
        chunk_count = app_service._container.chunk_repository.count()
        watched = app_service.watch_dirs

        return StatusResponse(
            status="running",
            indexed_files=file_count,
            indexed_chunks=chunk_count,
            watched_folders=watched,
        )
    except Exception as err:
        logger.error("Failed to get status: %s", err)
        raise HTTPException(status_code=500, detail=str(err))


@router.post("/search", response_model=SearchResponse)
async def search(
    request: SearchRequest,
    app_service: ApplicationService = Depends(get_app_service),
) -> SearchResponse:
    """Search indexed files by query."""
    try:
        mode = _convert_search_mode(request.mode)

        results, has_more = app_service.search(
            query=request.query,
            n_results=request.top_k,
            mode=mode,
        )

        items = [
            SearchResultItem(
                file_path=r.file_path,
                similarity_score=r.similarity_score,
                match_type=r.match_type,
                chunk_index=r.chunk_index,
                snippet=r.snippet,
            )
            for r in results
        ]

        return SearchResponse(
            query=request.query,
            mode=request.mode.value,
            results=items,
            total_count=len(items),
        )

    except ValueError as err:
        raise HTTPException(status_code=400, detail=str(err))
    except Exception as err:
        logger.error("Search failed: %s", err)
        raise HTTPException(status_code=500, detail=str(err))


@router.post("/index/file", response_model=IndexResult)
async def index_file(
    request: IndexFileRequest,
    app_service: ApplicationService = Depends(get_app_service),
) -> IndexResult:
    """Index a single file."""
    try:
        success = app_service.index_file(
            file_path=request.file_path,
            index_content=request.index_content,
        )

        return IndexResult(
            success=success,
            path=request.file_path,
            message="File indexed successfully" if success else "Failed to index file",
        )

    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="File not found")
    except Exception as err:
        logger.error("Index file failed: %s", err)
        raise HTTPException(status_code=500, detail=str(err))


@router.post("/index/folder", response_model=IndexResult)
async def index_folder(
    request: IndexFolderRequest,
    app_service: ApplicationService = Depends(get_app_service),
) -> IndexResult:
    """Index all supported files in a folder."""
    try:
        indexed, total = app_service.index_folder(
            folder=request.folder_path,
            include_hidden=request.include_hidden,
            index_content=request.index_content,
        )

        return IndexResult(
            success=indexed > 0,
            path=request.folder_path,
            message=f"Indexed {indexed} of {total} files",
            indexed_count=indexed,
            total_count=total,
        )

    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Folder not found")
    except Exception as err:
        logger.error("Index folder failed: %s", err)
        raise HTTPException(status_code=500, detail=str(err))


@router.delete("/index/file")
async def remove_file(
    file_path: str,
    app_service: ApplicationService = Depends(get_app_service),
) -> dict:
    """Remove a file from the index."""
    try:
        success = app_service.remove_file(file_path)

        return {
            "success": success,
            "path": file_path,
            "message": "File removed from index" if success else "File not found in index",
        }

    except Exception as err:
        logger.error("Remove file failed: %s", err)
        raise HTTPException(status_code=500, detail=str(err))


@router.post("/watch/start")
async def start_watching(
    folder_path: str,
    app_service: ApplicationService = Depends(get_app_service),
) -> dict:
    """Start watching a folder for changes."""
    try:
        app_service.start_watching(folder_path)

        return {
            "success": True,
            "path": folder_path,
            "message": "Started watching folder",
        }

    except Exception as err:
        logger.error("Start watching failed: %s", err)
        raise HTTPException(status_code=500, detail=str(err))


@router.post("/watch/stop")
async def stop_watching(
    app_service: ApplicationService = Depends(get_app_service),
) -> dict:
    """Stop watching all folders."""
    try:
        app_service.stop_watching()

        return {
            "success": True,
            "message": "Stopped watching all folders",
        }

    except Exception as err:
        logger.error("Stop watching failed: %s", err)
        raise HTTPException(status_code=500, detail=str(err))


@router.get("/health")
async def health_check() -> dict:
    """Health check endpoint."""
    return {"status": "healthy"}
