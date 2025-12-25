
from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field


class SearchModeAPI(str, Enum):
    FILENAME = "filename"
    CONTENT = "content"
    HYBRID = "hybrid"
    COMBINED = "combined"


class SearchRequest(BaseModel):
    query: str = Field(..., min_length=1, description="Search query text")
    mode: SearchModeAPI = Field(
        default=SearchModeAPI.FILENAME,
        description="Search mode: filename, content, hybrid, or combined"
    )
    top_k: int = Field(
        default=10,
        ge=1,
        le=100,
        description="Maximum number of results to return"
    )


class SearchResultItem(BaseModel):
    file_path: str
    similarity_score: float = Field(ge=0.0, le=100.0)
    match_type: str
    chunk_index: Optional[int] = None
    snippet: str = ""


class SearchResponse(BaseModel):
    query: str
    mode: str
    results: List[SearchResultItem]
    total_count: int


class IndexFileRequest(BaseModel):
    file_path: str = Field(..., description="Absolute path to the file to index")
    index_content: bool = Field(
        default=True,
        description="Whether to index file content (not just filename)"
    )


class IndexFolderRequest(BaseModel):
    folder_path: str = Field(..., description="Absolute path to the folder to index")
    include_hidden: bool = Field(
        default=False,
        description="Whether to include hidden files"
    )
    index_content: bool = Field(
        default=True,
        description="Whether to index file content"
    )


class IndexResult(BaseModel):
    success: bool
    path: str
    message: str
    indexed_count: Optional[int] = None
    total_count: Optional[int] = None


class StatusResponse(BaseModel):
    status: str
    indexed_files: int
    indexed_chunks: int
    watched_folders: List[str]


class ErrorResponse(BaseModel):
    error: str
    detail: Optional[str] = None
