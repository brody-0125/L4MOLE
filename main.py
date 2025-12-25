import argparse
import logging
import sys
import threading
import warnings

warnings.filterwarnings("ignore", message="pkg_resources is deprecated")


def run_gui():
    """Run the GUI application."""
    from PyQt6.QtWidgets import QApplication, QMessageBox

    from src.presentation.gui import MainWindow
    from src.infrastructure.ollama_utils import ensure_ollama_running, is_ollama_running
    from src.infrastructure.process_manager import (
        cleanup_all,
        register_cleanup,
        set_started_ollama,
    )

    register_cleanup()

    app = QApplication(sys.argv)

    ollama_was_running = is_ollama_running()

    if not ensure_ollama_running():
        QMessageBox.critical(
            None,
            "Ollama Error",
            "Cannot connect to Ollama.\n"
            "Please check if Ollama is installed and running.\n\n"
            "Download: https://ollama.com"
        )
        sys.exit(1)

    if not ollama_was_running:
        set_started_ollama(True)

    window = MainWindow()
    window.show()

    exit_code = app.exec()

    cleanup_all()

    return exit_code


def run_api(host: str = "127.0.0.1", port: int = 8000, log_level: str = "info"):
    """Run the REST API server."""
    from src.presentation.api import APIServer
    from src.infrastructure.ollama_utils import ensure_ollama_running

    if not ensure_ollama_running():
        logging.error(
            "Cannot connect to Ollama. "
            "Please check if Ollama is installed and running."
        )
        sys.exit(1)

    server = APIServer(host=host, port=port, log_level=log_level)
    server.run()


def run_both(host: str = "127.0.0.1", port: int = 8000, log_level: str = "info"):
    """Run both GUI and API server simultaneously."""
    from PyQt6.QtWidgets import QApplication, QMessageBox

    from src.presentation.gui import MainWindow
    from src.presentation.api import APIServer
    from src.infrastructure.ollama_utils import ensure_ollama_running, is_ollama_running
    from src.infrastructure.process_manager import (
        cleanup_all,
        register_cleanup,
        set_started_ollama,
    )

    register_cleanup()

    app = QApplication(sys.argv)

    ollama_was_running = is_ollama_running()

    if not ensure_ollama_running():
        QMessageBox.critical(
            None,
            "Ollama Error",
            "Cannot connect to Ollama.\n"
            "Please check if Ollama is installed and running.\n\n"
            "Download: https://ollama.com"
        )
        sys.exit(1)

    if not ollama_was_running:
        set_started_ollama(True)

    # Start API server in a background thread
    server = APIServer(host=host, port=port, log_level=log_level)

    def run_server():
        import uvicorn
        uvicorn.run(
            server.app,
            host=host,
            port=port,
            log_level=log_level,
        )

    api_thread = threading.Thread(target=run_server, daemon=True)
    api_thread.start()

    logging.info(f"API server started at http://{host}:{port}")

    window = MainWindow()
    window.show()

    exit_code = app.exec()

    cleanup_all()

    return exit_code


def main():
    parser = argparse.ArgumentParser(
        description="L4MOLE - Local Semantic Explorer",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python main.py                    # Start GUI (default)
  python main.py --mode gui         # Start GUI only
  python main.py --mode api         # Start REST API server only
  python main.py --mode both        # Start both GUI and API server
  python main.py --mode api --port 9000  # Start API on custom port
        """
    )

    parser.add_argument(
        "--mode",
        type=str,
        choices=["gui", "api", "both"],
        default="gui",
        help="Run mode: 'gui' for GUI only, 'api' for REST API only, 'both' for both (default: gui)"
    )

    parser.add_argument(
        "--host",
        type=str,
        default="127.0.0.1",
        help="API server host (default: 127.0.0.1)"
    )

    parser.add_argument(
        "--port",
        type=int,
        default=8000,
        help="API server port (default: 8000)"
    )

    parser.add_argument(
        "--log-level",
        type=str,
        choices=["debug", "info", "warning", "error"],
        default="info",
        help="Log level for API server (default: info)"
    )

    args = parser.parse_args()

    logging.basicConfig(
        level=getattr(logging, args.log_level.upper()),
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )

    if args.mode == "gui":
        exit_code = run_gui()
    elif args.mode == "api":
        run_api(host=args.host, port=args.port, log_level=args.log_level)
        exit_code = 0
    elif args.mode == "both":
        exit_code = run_both(host=args.host, port=args.port, log_level=args.log_level)
    else:
        parser.print_help()
        exit_code = 1

    sys.exit(exit_code)


if __name__ == "__main__":
    main()
