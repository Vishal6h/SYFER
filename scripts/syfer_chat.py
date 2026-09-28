#!/usr/bin/env python3
"""Small terminal client for the local SYFER backends."""
import argparse
import json
import os
from pathlib import Path
import shutil
import signal
import socket
import subprocess
import sys
import time
from urllib.error import HTTPError, URLError
from urllib.request import Request, build_opener, ProxyHandler

ROOT = Path(__file__).resolve().parent.parent
MODEL = ROOT / "model" / "SYFER-v1-Q4_K_M.gguf"
SYSTEM = ROOT / "assets" / "system-prompt.txt"
FACTS = ROOT / "assets" / "project-facts.txt"
OLLAMA = "http://127.0.0.1:11434"
EXIT_COMMANDS = {"/exit", "/quit", "/bye", "/q", "exit", "quit", "bye"}
BANNER = ROOT / "assets" / "syfer-banner.txt"


def request(url, data=None, timeout=120):
    payload = None if data is None else json.dumps(data).encode("utf-8")
    req = Request(url, data=payload, headers={"Content-Type": "application/json"})
    with build_opener(ProxyHandler({})).open(req, timeout=timeout) as response:
        return json.load(response)


def system_prompt():
    return SYSTEM.read_text(encoding="utf-8").strip() + "\n\nVerified project facts:\n" + FACTS.read_text(encoding="utf-8").strip()


def server_binary():
    configured = os.environ.get("SYFER_LLAMA_SERVER")
    if configured:
        binary = Path(configured).expanduser()
        if not binary.is_absolute():
            binary = ROOT / binary
        if binary.is_file() and os.access(binary, os.X_OK):
            return binary
        raise RuntimeError("SYFER_LLAMA_SERVER must name an existing executable.")
    folder = ROOT / "runtime" / "llama.cpp" / "build" / "bin"
    candidates = [folder / "Release" / "llama-server.exe", folder / "llama-server.exe"]
    candidates = candidates + [folder / "llama-server"] if os.name == "nt" else [folder / "llama-server"] + candidates
    for binary in candidates:
        if binary.is_file() and os.access(binary, os.X_OK):
            return binary
    names = ("llama-server.exe", "llama-server") if os.name == "nt" else ("llama-server", "llama-server.exe")
    for name in names:
        found = shutil.which(name)
        if found:
            return Path(found)
    return None


def ollama_models():
    try:
        return {m.get("name", m.get("model")) for m in request(OLLAMA + "/api/tags", timeout=3)["models"]}
    except (URLError, OSError, ValueError, KeyError):
        return None


def select_backend(choice, setup=False):
    if choice == "llama":
        return choice
    models = ollama_models()
    if models is not None and (setup or "syfer:v1" in models):
        return "ollama"
    if choice == "auto" and server_binary():
        return "llama"
    if models is not None:
        raise RuntimeError("Ollama is responding but syfer:v1 is missing. Run setup with --backend ollama.")
    if choice == "ollama" or shutil.which("ollama"):
        raise RuntimeError("Ollama is installed or selected but its local service is not responding. Start Ollama and rerun setup.")
    if setup and os.name != "nt":
        return "llama"
    raise RuntimeError("No ready backend found. Install and start Ollama, or provide llama-server via SYFER_LLAMA_SERVER, then run setup.")


def free_port():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def start_llama(debug):
    context = os.environ.get("SYFER_CONTEXT", "4096")
    try:
        if not context.isascii() or not context.isdecimal() or not 1 <= int(context) <= 32768:
            raise ValueError
    except ValueError:
        raise RuntimeError("SYFER_CONTEXT must be a positive integer between 1 and 32768.") from None
    if not MODEL.is_file():
        raise RuntimeError(f"SYFER model missing: {MODEL}\nRun setup.sh (Linux) or setup.ps1 (Windows) first.")
    binary = server_binary()
    if binary is None:
        raise RuntimeError("llama-server is unavailable. Run setup.sh / setup.ps1 or set SYFER_LLAMA_SERVER to its executable path.")
    port = free_port()
    output = None if debug else subprocess.DEVNULL
    command = [str(binary), "-m", str(MODEL), "-c", context, "--host", "127.0.0.1", "--port", str(port), "--no-webui"]
    if not debug:
        command.append("--log-disable")
    process = subprocess.Popen(command, stdout=output, stderr=output,
                               **({"creationflags": subprocess.CREATE_NEW_PROCESS_GROUP} if os.name == "nt" else {"start_new_session": True}))
    base = f"http://127.0.0.1:{port}"
    try:
        deadline = time.monotonic() + 120
        while time.monotonic() < deadline:
            if process.poll() is not None:
                raise RuntimeError(f"llama-server exited during startup (code {process.returncode}). Try --debug for details.")
            try:
                health = request(base + "/health", timeout=2)
                if health.get("status") == "ok":
                    return process, base
            except (URLError, TimeoutError, OSError, ValueError):
                pass
            time.sleep(0.2)
        raise RuntimeError("llama-server did not become ready within 120 seconds. Try --debug for details.")
    except BaseException:
        stop_server(process)
        raise


def stop_server(process):
    if process.poll() is None:
        process.terminate()
        try:
            process.wait(timeout=5)
        except (subprocess.TimeoutExpired, KeyboardInterrupt):
            process.kill()
            process.wait()


def chat(backend, base, system):
    history = [{"role": "system", "content": system}]
    print("Starting SYFER...\n")
    while True:
        try:
            prompt = input("You > ").strip()
        except EOFError:
            print()
            break
        if prompt.lower() in EXIT_COMMANDS:
            break
        if prompt == "/help":
            print("SYFER Commands\n\n/help   Show commands\n/clear  Clear current conversation\n/exit   Exit SYFER\n\nAliases: quit, bye, /quit, /bye, /q\n")
            continue
        if prompt == "/clear":
            history = history[:1]
            print("SYFER > Conversation cleared.\n")
            continue
        if not prompt:
            continue
        messages = history + [{"role": "user", "content": prompt}]
        if backend == "ollama":
            result = request(base + "/api/chat", {"model": "syfer:v1", "messages": messages, "stream": False}, timeout=600)
            answer = result["message"]["content"]
        else:
            result = request(base + "/v1/chat/completions", {"messages": messages, "temperature": 0, "max_tokens": 1024, "stream": False}, timeout=600)
            answer = result["choices"][0]["message"]["content"]
        print(f"\nSYFER > {answer.strip()}\n")
        history = messages + [{"role": "assistant", "content": answer}]


def color_supported():
    if not sys.stdout.isatty() or os.environ.get("NO_COLOR") is not None or os.environ.get("TERM") == "dumb":
        return False
    if os.name != "nt":
        return True
    import ctypes
    from ctypes import wintypes
    kernel = ctypes.windll.kernel32
    kernel.GetStdHandle.argtypes = [wintypes.DWORD]
    kernel.GetStdHandle.restype = wintypes.HANDLE
    kernel.GetConsoleMode.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD)]
    kernel.SetConsoleMode.argtypes = [wintypes.HANDLE, wintypes.DWORD]
    handle = kernel.GetStdHandle(-11)
    mode = wintypes.DWORD()
    return bool(kernel.GetConsoleMode(handle, ctypes.byref(mode)) and kernel.SetConsoleMode(handle, mode.value | 4))


def main():
    parser = argparse.ArgumentParser(description="SYFER local chat")
    parser.add_argument("--backend", choices=("auto", "llama", "ollama"), default=os.environ.get("SYFER_BACKEND", "auto"))
    parser.add_argument("--debug", action="store_true", help="show backend and setup output")
    parser.add_argument("--setup", action="store_true", help="verify model and prepare runtime")
    args = parser.parse_args()
    if args.backend not in ("auto", "llama", "ollama"):
        raise RuntimeError("SYFER_BACKEND must be auto, llama, or ollama.")
    if args.setup:
        from syfer_setup import setup
        setup(args.backend, args.debug)
        return
    system = system_prompt()
    backend = select_backend(args.backend)
    process = None
    try:
        if args.debug:
            print(f"[SYFER DEBUG] Backend: {backend}")
        if backend == "llama":
            process, base = start_llama(args.debug)
        else:
            base = OLLAMA
        banner = BANNER.read_text(encoding="utf-8").splitlines(keepends=True)
        if color_supported():
            print("\033[0;36m" + "".join(banner[:6]) + "\033[0m" + "".join(banner[6:]))
        else:
            print("".join(banner), end="\n")
        chat(backend, base, system)
        print("SYFER > Goodbye.")
    finally:
        if process is not None:
            stop_server(process)


def cancelled(signum, frame):
    raise KeyboardInterrupt


if __name__ == "__main__":
    signal.signal(signal.SIGTERM, cancelled)
    if hasattr(signal, "SIGBREAK"):
        signal.signal(signal.SIGBREAK, cancelled)
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(errors="replace")
    try:
        main()
    except KeyboardInterrupt:
        print("\nSYFER > Goodbye.")
        sys.exit(130)
    except (RuntimeError, HTTPError, URLError, OSError, KeyError, IndexError, TypeError, ValueError) as exc:
        print(f"[SYFER] Error: {exc}", file=sys.stderr)
        sys.exit(1)
