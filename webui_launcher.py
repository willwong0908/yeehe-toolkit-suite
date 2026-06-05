from __future__ import annotations

import contextlib
import ctypes
import logging
import os
import socket
import sys
import threading
import time
import webbrowser

import uvicorn

from term_extractor_app.constants import APP_NAME, APP_VERSION
from term_extractor_app.web_app import app


HOST = "127.0.0.1"
PORT = 8765
URL = f"http://{HOST}:{PORT}/"


def _prepare_console() -> None:
    os.environ.setdefault("PYTHONUTF8", "1")
    for stream_name in ("stdout", "stderr"):
        stream = getattr(sys, stream_name, None)
        if hasattr(stream, "reconfigure"):
            with contextlib.suppress(Exception):
                stream.reconfigure(encoding="utf-8", errors="replace")
    if os.name == "nt":
        with contextlib.suppress(Exception):
            ctypes.windll.kernel32.SetConsoleOutputCP(65001)
            ctypes.windll.kernel32.SetConsoleCP(65001)
            ctypes.windll.kernel32.SetConsoleTitleW(f"{APP_NAME} {APP_VERSION}")


def _print_banner() -> None:
    print("\033[96m")
    print("  ██╗   ██╗███████╗███████╗██╗  ██╗███████╗")
    print("  ╚██╗ ██╔╝██╔════╝██╔════╝██║  ██║██╔════╝")
    print("   ╚████╔╝ █████╗  █████╗  ███████║█████╗  ")
    print("    ╚██╔╝  ██╔══╝  ██╔══╝  ██╔══██║██╔══╝  ")
    print("     ██║   ███████╗███████╗██║  ██║███████╗")
    print("     ╚═╝   ╚══════╝╚══════╝╚═╝  ╚═╝╚══════╝")
    print("\033[0m", end="")
    print("  ┌──────────────────────────────────────────────┐")
    print(f"  │ {APP_NAME}  v{APP_VERSION:<27}│")
    print("  │                                              │")
    print(f"  │ 服务地址  {URL:<31}│")
    print("  │ 状态      正在启动，浏览器稍后自动打开        │")
    print("  │ 关闭      输入 q 回车，或按 Ctrl+C            │")
    print("  └──────────────────────────────────────────────┘")
    print("")
    print("  运行日志")
    print("  ────────────────────────────────────────────────")
    sys.stdout.flush()


def _wait_until_ready(timeout_seconds: float = 20.0) -> bool:
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        with contextlib.closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as sock:
            sock.settimeout(0.3)
            if sock.connect_ex((HOST, PORT)) == 0:
                return True
        time.sleep(0.2)
    return False


def _open_browser_when_ready() -> None:
    if _wait_until_ready():
        print(f"  已启动：{URL}")
        print("  浏览器已打开。保持本窗口开启即可使用工具。")
        sys.stdout.flush()
        webbrowser.open(URL)
    else:
        print("  启动超时：请查看下方错误信息，或确认端口是否被占用。")
        sys.stdout.flush()


def _listen_for_quit(server: uvicorn.Server) -> None:
    while not server.should_exit:
        try:
            command = input().strip().lower()
        except EOFError:
            return
        except KeyboardInterrupt:
            server.should_exit = True
            return
        if command in {"q", "quit", "exit"}:
            print("  正在关闭服务...")
            sys.stdout.flush()
            server.should_exit = True
            return


def main() -> int:
    _prepare_console()
    _print_banner()
    logging.getLogger("uvicorn").setLevel(logging.WARNING)
    logging.getLogger("uvicorn.error").setLevel(logging.WARNING)
    logging.getLogger("uvicorn.access").disabled = True

    config = uvicorn.Config(
        app,
        host=HOST,
        port=PORT,
        access_log=False,
        log_level="warning",
    )
    server = uvicorn.Server(config)
    threading.Thread(target=_open_browser_when_ready, daemon=True).start()
    threading.Thread(target=_listen_for_quit, args=(server,), daemon=True).start()
    try:
        server.run()
    except KeyboardInterrupt:
        server.should_exit = True
    finally:
        print("  服务已关闭。")
        sys.stdout.flush()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
