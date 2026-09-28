#!/usr/bin/env python3
"""Small terminal client for the local SYFER backends."""
import argparse
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys
import time
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parent.parent
MODEL = ROOT / "model" / "SYFER-v1-Q4_K_M.gguf"
SYSTEM = ROOT / "assets" / "system-prompt.txt"
BANNER = ROOT / "assets" / "syfer-banner.txt"


def request(url, data=None, timeout=120):
    payload = None if data is None else json.dumps(data).encode("utf-8")
    req = Request(url, data=payload, headers={"Content-Type": "application/json"})
    with urlopen(req, timeout=timeout) as response:
        return json.load(response)


def server_binary():
    configured = os.environ.get("SYFER_LLAMA_SERVER")
    if configured:
        binary = Path(configured).expanduser()
        return binary if binary.is_file() and os.access(binary, os.X_OK) else None
    local = ROOT / "runtime" / "llama.cpp" / "build" / "bin" / "llama-server"
    if local.is_file() and os.access(local, os.X_OK):
        return local
    found = shutil.which("llama-server")
    return Path(found) if found else None


def free_port():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def start_llama(debug):
    context = os.environ.get("SYFER_CONTEXT", "4096")
    try:
        if not context.isascii() or not context.isdecimal() or int(context) < 1:
            raise ValueError
    except ValueError:
        raise RuntimeError("SYFER_CONTEXT must be a positive integer.") from None
    if not MODEL.is_file():
        raise RuntimeError(f"SYFER model missing: {MODEL}\nRun ./setup.sh first.")
    binary = server_binary()
    if binary is None:
        raise RuntimeError("llama-server is unavailable. Run ./setup.sh or set SYFER_LLAMA_SERVER to its executable path.")
    port = free_port()
    output = None if debug else subprocess.DEVNULL
    command = [str(binary), "-m", str(MODEL), "-c", context, "--host", "127.0.0.1", "--port", str(port), "--no-webui"]
    if not debug:
        command.append("--log-disable")
    process = subprocess.Popen(command, stdout=output, stderr=output)
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
        except subprocess.TimeoutExpired:
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
        if prompt in ("/exit", "/quit"):
            break
        if prompt == "/help":
            print("/help  /clear  /exit\n")
            continue
        if prompt == "/clear":
            history = history[:1]
            print("Conversation cleared.\n")
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


def main():
    parser = argparse.ArgumentParser(description="SYFER local chat")
    parser.add_argument("--backend", choices=("llama", "ollama"), required=True)
    parser.add_argument("--debug", action="store_true", help="show backend startup output")
    args = parser.parse_args()
    if not SYSTEM.is_file() or not BANNER.is_file():
        raise RuntimeError("SYFER assets are missing from this repository clone.")
    if args.backend == "ollama" and not shutil.which("ollama"):
        raise RuntimeError("Ollama is unavailable. Install Ollama and run ./scripts/install_syfer.sh.")
    process = None
    try:
        if args.backend == "llama":
            process, base = start_llama(args.debug)
        else:
            base = "http://127.0.0.1:11434"
        banner = BANNER.read_text(encoding="utf-8").splitlines(keepends=True)
        if sys.stdout.isatty():
            print("\033[2J\033[H", end="")
            print("\033[0;36m" + "".join(banner[:6]) + "\033[0m" + "".join(banner[6:]))
        else:
            print("".join(banner), end="\n")
        chat(args.backend, base, SYSTEM.read_text(encoding="utf-8").strip())
    finally:
        if process is not None:
            stop_server(process)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n")
    except (RuntimeError, HTTPError, URLError, OSError, KeyError, ValueError) as exc:
        print(f"SYFER error: {exc}", file=sys.stderr)
        sys.exit(1)
