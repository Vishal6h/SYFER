"""Shared, repeatable setup; no Python packages are required."""
import hashlib
import os
import shutil
import subprocess
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from syfer_chat import ROOT, MODEL, OLLAMA, request, select_backend, server_binary, system_prompt

RELEASE = "https://github.com/Vishal6h/SYFER/releases/download/v1.0/SYFER-v1-Q4_K_M.gguf"


def checksum(path):
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def download_model(url, partial):
    offset = partial.stat().st_size if partial.exists() else 0
    request = Request(url, headers={"Range": f"bytes={offset}-"} if offset else {})
    try:
        response = urlopen(request, timeout=60)
    except HTTPError as exc:
        if not offset or exc.code != 416:
            raise
        # A complete but invalid partial must be replaced by a fresh transfer.
        response = urlopen(url, timeout=60)
        offset = 0
    with response:
        resume = offset and response.status == 206
        if resume and not response.headers.get("Content-Range", "").startswith(f"bytes {offset}-"):
            raise RuntimeError("Download server returned an invalid resume range; partial file preserved.")
        with partial.open("ab" if resume else "wb") as dest:
            shutil.copyfileobj(response, dest, 1024 * 1024)


def verify_model():
    expected = (ROOT / "release" / "checksums.txt").read_text().split()[0]
    if MODEL.is_file():
        if checksum(MODEL) != expected:
            raise RuntimeError("Model checksum failed. Replace model/SYFER-v1-Q4_K_M.gguf with the official v1.0 release asset; the existing file was preserved.")
        return
    print("[SYFER] Downloading official v1.0 model (~1.8 GB)...")
    MODEL.parent.mkdir(parents=True, exist_ok=True)
    partial = MODEL.with_suffix(".gguf.part")
    try:
        download_model(os.environ.get("SYFER_MODEL_URL", RELEASE), partial)
        if checksum(partial) != expected:
            raise RuntimeError("Downloaded model checksum failed.")
        partial.replace(MODEL)
    except Exception as exc:
        raise RuntimeError("Model installation failed. Download SYFER-v1-Q4_K_M.gguf from https://github.com/Vishal6h/SYFER/releases/tag/v1.0 and place it in model/. " + str(exc)) from exc


def run(command, log, debug):
    log.write("Command: " + repr(command) + "\n")
    log.flush()
    # Always drain the pipe, including in quiet mode; never invoke a shell.
    process = subprocess.Popen(command, cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, errors="replace")
    try:
        for line in process.stdout:
            log.write(line)
            if debug:
                print(line, end="")
        if process.wait():
            raise RuntimeError("Backend preparation failed. See logs/setup.log or rerun setup with --debug.")
    finally:
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
        process.stdout.close()


def prepare_llama(log, debug):
    if server_binary():
        return
    if os.name == "nt":
        raise RuntimeError("Install Ollama (recommended), or set SYFER_LLAMA_SERVER to llama-server.exe. Windows setup does not install build tools.")
    for tool in ("git", "cmake", "c++"):
        if not shutil.which(tool):
            raise RuntimeError(f"Install {tool} using your environment's package manager and rerun setup, or use Ollama.")
    source = ROOT / "runtime" / "llama.cpp"
    if not (source / ".git").is_dir():
        run(["git", "clone", "--depth", "1", "https://github.com/ggml-org/llama.cpp.git", str(source)], log, debug)
    cuda = bool(shutil.which("nvcc") and shutil.which("nvidia-smi"))
    if cuda:
        cuda = subprocess.run(["nvidia-smi", "-L"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode == 0
    def build(enabled):
        run(["cmake", "-S", str(source), "-B", str(source / "build"), "-DCMAKE_BUILD_TYPE=Release", "-DGGML_CUDA=" + ("ON" if enabled else "OFF")], log, debug)
        run(["cmake", "--build", str(source / "build"), "--config", "Release", "--target", "llama-server", "-j", "2"], log, debug)
    try:
        build(cuda)
    except RuntimeError:
        if not cuda:
            raise
        print("[SYFER] CUDA build unavailable; preparing CPU runtime...")
        build(False)


def prepare_ollama(log, debug):
    prompt = system_prompt()
    try:
        current = request(OLLAMA + "/api/show", {"model": "syfer:v1"}, timeout=10)
        parameters = current.get("parameters", "").split()
        if current.get("system", "").strip() == prompt and "num_ctx" in parameters and parameters[parameters.index("num_ctx") + 1] == "32768":
            return
    except (OSError, ValueError, KeyError, IndexError):
        pass
    binary = shutil.which("ollama")
    if not binary:
        raise RuntimeError("Ollama API is responding, but the ollama command is missing from PATH. Add the Ollama installation to PATH and rerun setup.")
    modelfile = ROOT / "release" / "Modelfile"
    modelfile.write_text('FROM "' + MODEL.as_posix() + '"\n\nPARAMETER temperature 0\nPARAMETER num_ctx 32768\n\nSYSTEM """\n' + prompt + '\n"""\n', encoding="utf-8")
    # Pin CLI operations to the same loopback service used by the frontend.
    previous = os.environ.get("OLLAMA_HOST")
    os.environ["OLLAMA_HOST"] = OLLAMA
    try:
        run([binary, "create", "syfer:v1", "-f", str(modelfile)], log, debug)
    finally:
        if previous is None:
            os.environ.pop("OLLAMA_HOST", None)
        else:
            os.environ["OLLAMA_HOST"] = previous


def setup(choice="auto", debug=False):
    (ROOT / "logs").mkdir(exist_ok=True)
    with (ROOT / "logs" / "setup.log").open("w", encoding="utf-8") as log:
        print("[SYFER] Checking model...", flush=True)
        verify_model()
        print("[SYFER] Checking runtime...")
        backend = select_backend(choice, setup=True)
        print("[SYFER] Preparing backend...")
        if debug:
            print(f"[SYFER DEBUG] Backend: {backend}")
        if backend == "ollama":
            prepare_ollama(log, debug)
        else:
            prepare_llama(log, debug)
        print("[SYFER] Setup complete.")
