# L4MOLE

<p align="center">
  <img src="resources/logo.png" alt="L4MOLE Logo" width="200">
</p>

**Local Semantic Explorer**

A desktop application for semantic search across your local files using AI embeddings. Search by meaning, not just keywords.

![Python](https://img.shields.io/badge/Python-3.10+-blue.svg)
![PyQt6](https://img.shields.io/badge/GUI-PyQt6-green.svg)
![License](https://img.shields.io/badge/License-MIT-yellow.svg)
![Architecture](https://img.shields.io/badge/Architecture-Clean-white.svg)

## Features

- **Semantic Search**: Find files by meaning using AI embeddings (Ollama)
- **Hybrid Search**: Combine vector similarity and keyword search (RRF fusion)
- **Filename Search**: Quick lookup by file names
- **Multi-modal Support**: Index text files, PDFs, and images
- **Real-time Sync**: Automatic index updates when files change
- **REST API**: Programmatic access via FastAPI endpoints
- **Offline-first**: All processing happens locally
- **Privacy-focused**: Your data never leaves your computer

## Supported File Types

| Category | Extensions |
|----------|------------|
| Text | `.txt`, `.md`, `.py`, `.json`, `.csv` |
| Documents | `.pdf` |
| Images | `.png`, `.jpg`, `.jpeg`, `.webp` |

## Requirements

### Software

| Software | Version | Purpose |
|----------|---------|---------|
| Python | 3.10+ | Runtime |
| [Ollama](https://ollama.com) | 0.1.0+ | AI embedding engine |
| OS | macOS 12+ / Ubuntu 20.04+ / Windows 10+ | Platform |

### Hardware

| Resource | Minimum | Recommended |
|----------|---------|-------------|
| RAM | 4 GB | 8 GB+ |
| Disk Space | 2 GB | 5 GB+ |
| GPU | Not required | CPU-only embeddings |

## Quick Start

### 1. Clone and setup

```bash
git clone https://github.com/yourusername/L4MOLE.git
cd L4MOLE
python3 -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Install Ollama and pull model

```bash
# macOS
brew install ollama

# Linux
curl -fsSL https://ollama.com/install.sh | sh

# Windows
winget install Ollama.Ollama
```

```bash
ollama pull nomic-embed-text
```

### 3. Run

```bash
python main.py
```

> Ollama will start automatically if not running.

## Usage

### Run Modes

```bash
python main.py                    # GUI only (default)
python main.py --mode api         # REST API only
python main.py --mode both        # GUI + API
python main.py --mode api --port 9000  # Custom port
```

### Command Line Options

| Option | Default | Description |
|--------|---------|-------------|
| `--mode` | `gui` | `gui`, `api`, or `both` |
| `--host` | `127.0.0.1` | API server host |
| `--port` | `8000` | API server port |
| `--log-level` | `info` | `debug`, `info`, `warning`, `error` |

### Search Modes

| Mode | Description |
|------|-------------|
| Filename | Search by file names |
| Content | Semantic search through file contents |
| Hybrid | Combined vector + keyword search (RRF) |

### Keyboard Shortcuts

| Action | Windows/Linux | macOS |
|--------|---------------|-------|
| Focus search | `Ctrl+F` | `Cmd+F` |
| Reindex | `Ctrl+R` | `Cmd+R` |
| Settings | `Ctrl+,` | `Cmd+,` |
| Clear results | `Esc` | `Esc` |

## Architecture

Clean Architecture with clear separation of concerns.

```
src/
├── domain/           # Core business logic
│   ├── entities/     # File, Chunk, Folder
│   ├── value_objects/# FilePath, SearchQuery, EmbeddingVector
│   ├── ports/        # Repository interfaces
│   └── services/     # Hybrid search combiner, deduplication
├── application/      # Use cases
│   ├── use_cases/    # IndexFile, IndexFolder, Search
│   └── services/     # Transaction management
├── infrastructure/   # External adapters
│   ├── container/    # DI container
│   ├── persistence/  # SQLite, Milvus
│   ├── embedding/    # Ollama adapter
│   ├── file_system/  # File reader
│   ├── compression/  # Zstandard compression
│   └── resilience/   # Circuit breaker
└── presentation/     # UI layer
    ├── api/          # FastAPI endpoints
    └── gui/          # PyQt6 interface
```

### Key Components

| Component | Technology | Purpose |
|-----------|------------|---------|
| Embeddings | Ollama | Generate semantic vectors |
| Vector Store | Milvus Lite | Similarity search |
| Metadata | SQLite (WAL) | File metadata storage |
| Keyword Search | SQLite FTS5 | Full-text search |
| GUI | PyQt6 | Desktop interface |
| REST API | FastAPI | Programmatic access |
| File Watching | Watchdog | Real-time sync |

## Development

### Run Tests

```bash
pytest                    # All tests
pytest --cov=src          # With coverage
pytest tests/unit/ -v     # Unit tests only
```

### Code Quality

```bash
mypy src/                 # Type checking
ruff check src/           # Linting
vulture src/              # Dead code analysis
```

## Data Storage

| File | Purpose |
|------|---------|
| `metadata.db` | SQLite database |
| `milvus_lite.db` | Vector embeddings |

### SQLite Tables

| Table | Purpose |
|-------|---------|
| `files` | File metadata (path, size, mtime, hash, status) |
| `directories` | Directory path dictionary for compression |
| `chunks` | Content chunks with compressed text |
| `indexed_folders` | Folder settings (include hidden, index content) |
| `search_history` | Search query history |
| `content_fts` | FTS5 full-text search index |

### Milvus Collections

| Collection | Purpose |
|------------|---------|
| `filenames` | Filename embedding vectors |
| `contents` | Content chunk embedding vectors |

## Troubleshooting

### Ollama Connection Failed

1. Verify installation: `ollama --version`
2. Check running status: `ollama list`
3. Restart if needed: `ollama serve`

### Slow Indexing

- Large PDFs may take time (1+ min for >10 MB files)
- Start with smaller folders (<100 files)
- Ensure sufficient RAM (4 GB minimum)

### No Search Results

1. Confirm indexing completed (100%)
2. Try different search modes
3. Use shorter, simpler queries
4. Verify supported file types

## License

MIT License - see [LICENSE](LICENSE) for details.

## Acknowledgments

- [Ollama](https://ollama.com) - Local AI runtime
- [Milvus](https://milvus.io) - Vector database
- [PyQt6](https://www.riverbankcomputing.com/software/pyqt/) - GUI framework
- [FastAPI](https://fastapi.tiangolo.com) - REST API framework
