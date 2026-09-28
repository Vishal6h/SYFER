# SYFER v1 cross-platform runtime review

Changes are local for review. No training, conversion, quantization, commits,
pushes, tags, or release publication were performed. The model, licensing,
benchmarks, historical results, datasets, and training artifacts were preserved.
The existing untracked experiment evidence was left in place.

## Architecture and files

All platforms use `scripts/syfer_chat.py` for UI, identity, in-memory history,
commands, backend APIs, context configuration, and owned llama-server lifecycle.
The setup entry point delegates to `scripts/syfer_setup.py` for shared checksum,
download, backend preparation, and logging logic.

- Linux and WSL: `./syfer` and `./setup.sh` are thin Bash wrappers.
- Android: the same Bash/Python implementation, using the environment's compiler
  and libraries when a llama.cpp build is necessary.
- Native Windows: `syfer.ps1` resolves `$PSScriptRoot`, probes `py -3`, `python`,
  then `python3`, and invokes Python with argument arrays. `setup.ps1` forwards
  `--setup` and translates `-Debug`. No WSL or global policy change is involved.

Created: `assets/project-facts.txt`, `scripts/syfer_setup.py`, `setup.ps1`,
`syfer.ps1`, `tests/test_runtime.py`, `tests/runtime_smoke.py`,
`tests/launcher_smoke.py`, and this report.

Modified: `.gitignore`, `README.md`, `README_RELEASE.md`,
`assets/system-prompt.txt`, `release/README.md`, `scripts/install_syfer.sh`,
`scripts/run_syfer.sh`, `scripts/syfer_chat.py`, `setup.sh`, and `syfer`.
The existing banner asset remains the source of the visible branding.

## Behavior

Automatic chat selection uses responsive Ollama with `syfer:v1`, then a discovered
llama-server. Automatic setup can prepare the Ollama model when the service
responds. Linux can build a missing llama-server; Windows asks for Ollama or a
preinstalled llama-server.exe. `--backend` and `SYFER_BACKEND` pin selection.
Explicit selections do not fall back silently. An executable alone does not
establish Ollama readiness.

llama-server discovery checks `SYFER_LLAMA_SERVER`, repository build paths
(including Windows `bin/Release`), then PATH. Relative overrides resolve against
the repository. Model and asset paths use pathlib. Subprocesses use argument
arrays without a shell. The owned server binds to `127.0.0.1` on a free port.
Local API requests bypass HTTP proxy settings. Ollama CLI preparation is also
pinned to the loopback service.

System messages combine the behavior prompt and verified facts centrally in
Python, including release date, creator, Qwen attribution, and memory limits.
Ollama installation uses this same composition. No detailed performance numbers
were added. These are prompt instructions, not a guarantee against every possible
model hallucination; the requested real-model questions passed on both backends.

Exact stripped, case-insensitive exit commands are handled before API calls.
`/clear` resets history while retaining the system message. `/help` lists only
SYFER commands. EOF and Ctrl+C print `SYFER > Goodbye.`; Ctrl+C returns 130.
The owned llama-server is terminated and reaped, with a kill fallback.
Startup cancellation also cleans up. Ollama's independently managed service
is intentionally kept running. Windows Ctrl+Break is handled where Python exposes
SIGBREAK. Forced OS process termination cannot execute Python cleanup.

Setup verifies SHA-256 using hashlib and the unchanged release checksum. It
reuses valid files, preserves corrupt existing files with a clear error, and
continues the project's existing automatic official-release download when absent.
Downloads go to `.part` and are moved only after verification. The shared Python
downloader resumes partial files when the server supports HTTP Range, validates
the returned range, and restarts safely when the server ignores or rejects it. Normal output is concise. Compiler/Ollama preparation output
is written to `logs/setup.log`; debug also displays it. Runtime debug exposes
backend output explicitly. Logs and partial files are ignored by Git.

Requirements on all platforms: Python 3.8+, the verified v1.0 GGUF for setup or
llama-server, and a usable backend. An already installed Ollama model can be used
without retaining the source GGUF for chat. Windows recommends running Ollama;
llama-server.exe with its DLLs is an alternative. Linux builds additionally need
Git, CMake, and a C++ compiler. No NVIDIA GPU is required. llama.cpp context defaults
to 4096 and accepts 1–32768; Ollama setup retains 32768.

## Validation performed on Linux

- Python AST syntax validation of runtime/setup and all test scripts: passed.
- Bash syntax validation of all four wrappers: passed.
- `git diff --check`: passed.
- Runtime/docs path scan: no developer-specific absolute paths introduced.
  The pre-existing ignored `config/llama-cli-path` is unused by this runtime.
- `python3 -B -m unittest discover -s tests -v`: 21 tests passed, covering all exit
  aliases/case/whitespace, no command API requests, non-command exit words,
  help/clear, prompt facts, custom/invalid context, Windows paths containing
  spaces, discovery, free loopback ports, startup/generation cleanup, missing
  model/backend errors, hash checks, setup logging and idempotency.
- `python3 -B tests/runtime_smoke.py`: real local GGUF through both llama-server
  and Ollama answered creator, release date, memory and performance questions
  correctly. The owned llama-server was reaped.
- `python3 -B tests/launcher_smoke.py`: six real launcher checks passed:
  exit, EOF and SIGINT for each backend. No tracebacks. No llama-server process
  remained in the process listing afterward.
- llama setup repeated successfully, including debug. Existing model/runtime reused.
- Ollama setup repeated successfully; combined prompt installed, 32768 retained,
  and second setup skipped recreation.

Representative real answers from both backends:

| Question | Verified answer |
|---|---|
| Creator | VISHAL K |
| Release date | September 27, 2026 |
| Previous chats | No built-in persistent memory across separate sessions |
| Performance percentage | No single universal percentage; performance varies by task |

PowerShell was not installed locally. Windows launcher text and Windows-style
argument/path handling were validated on Linux; no PowerShell parser or native
Windows runtime execution was performed. Android device execution was not
performed. Fresh network model download and a fresh compiler build were not run:
the existing verified model and working runtime were reused. Failure/logging
branches were exercised using controlled subprocesses and mocks.

## Manual native Windows verification

Use a clone path containing spaces, such as `C:\Users\Test User\SYFER`.
Install Python, Git and Ollama, and start the Ollama app. From the clone:

```powershell
.\setup.ps1
.\setup.ps1 -Debug
.\syfer.ps1 --backend ollama
```

If policy blocks scripts, run each through
`powershell -ExecutionPolicy Bypass -File .\setup.ps1` or
`powershell -ExecutionPolicy Bypass -File .\syfer.ps1 --backend ollama`.
No persistent execution-policy change is needed.

Ask creator/date/memory/performance questions. Test `/help`, `/clear`, `EXIT`,
`/bye`, `/q` in separate sessions. Confirm `Explain sys.exit()` remains a question.
Test Ctrl+C at the prompt and during generation, and Ctrl+Z then Enter for EOF.
Repeat with a local llama.cpp distribution:

```powershell
$env:SYFER_LLAMA_SERVER="C:\Tools\llama.cpp\llama-server.exe"
$env:SYFER_CONTEXT="8192"
.\setup.ps1 --backend llama
.\syfer.ps1 --backend llama
Get-Process llama-server -ErrorAction SilentlyContinue
$env:SYFER_CONTEXT="invalid"
.\syfer.ps1 --backend llama
Remove-Item Env:SYFER_CONTEXT
Remove-Item Env:SYFER_LLAMA_SERVER
py -3 -B -m unittest discover -s tests -v
```

Compare server processes before/after to ensure this session's child is gone.
Check cyan output in Windows Terminal and plain redirected output without escape
sequences. Test a machine with only `python` on PATH and one with `py -3`.
Test missing Python/service/model diagnostics without removing valuable model
files: use a separate clean clone or temporary PATH configuration.

PowerShell parser validation on a Windows host:

```powershell
foreach ($file in 'setup.ps1','syfer.ps1') {
    $tokens=$null; $errors=$null
    [System.Management.Automation.Language.Parser]::ParseFile(
        (Join-Path $PWD $file), [ref]$tokens, [ref]$errors) | Out-Null
    if ($errors.Count) { throw ($errors | Out-String) }
}
```

## Manual Android verification

Native Termux:

```bash
pkg install python git cmake clang
git clone https://github.com/Vishal6h/SYFER.git
cd SYFER
./setup.sh --backend llama
./setup.sh --backend llama
./syfer --backend llama
SYFER_CONTEXT=8192 ./syfer --backend llama
python3 -B -m unittest discover -s tests -v
```

For a Linux distribution running on Android, install those dependencies through
its package manager instead. First test the default 4096 context. Increase only
when device memory permits. Check the same self-knowledge questions, `/clear`,
exit aliases, Ctrl+C, EOF, absence of orphan servers, and plain/cyan terminal output.

## Prioritized future improvement audit

These are recommendations, not additional implemented features. Importance is
relative to runtime reliability; effort and risk are estimates. Every item below
requires **no retraining**.

### A. Critical reliability

| Issue | Proposed solution | Importance | Effort | Risk | Model behavior impact | Retraining | Release |
|---|---|---|---|---|---|---|---|
| Conversation history grows without bounds; backend overflow/truncation can lose useful context | Add token-budget-aware trimming, preserving system facts and complete turns, with an explicit notice | High | Medium | Medium | Changes available conversation context | No | v1.1 |
| Fixed 120s startup/600s request timeouts may poorly fit slow phones or large prompts | Add bounded timeout settings and actionable timeout errors | High | Small | Low | None except how long requests may run | No | v1.0 patch |
| Free port is released before llama-server binds; another process can take it | Retry startup on a confirmed port collision | Medium | Small | Low | None | No | v1.0 patch |

### B. UX

| Issue | Proposed solution | Importance | Effort | Risk | Model behavior impact | Retraining | Release |
|---|---|---|---|---|---|---|---|
| Non-streaming responses leave users waiting | Add Ollama NDJSON and llama.cpp SSE streaming under one renderer | High | Medium | Medium | Presentation only if generation parameters stay unchanged | No | v1.1 |
| Ctrl+C exits the session; a pending Ollama request may continue briefly in its service | Add explicit cancel-generation handling and verify backend disconnect behavior | Medium | Medium | Medium | Can truncate an answer | No | v1.1 |
| No version or diagnostics command | Add `--version` and opt-in diagnostics with safe local details | Medium | Small | Low | None | No | v1.0 patch |

### C. Windows support

| Issue | Proposed solution | Importance | Effort | Risk | Model behavior impact | Retraining | Release |
|---|---|---|---|---|---|---|---|
| Native PowerShell execution/console events not tested here | Add Windows CI and real Ollama/llama-server host acceptance checks, including spaces and Unicode | High | Medium | Low | None | No | v1.0 patch |
| A responding Ollama API may coexist with missing CLI PATH; Windows app aliases can interfere with Python probes | Test installation variants and document PATH repair with verified vendor instructions | Medium | Small | Low | None | No | v1.0 patch |
| Downloaded executables can trigger Defender/SmartScreen reputation checks; no false positive was observed here | Prefer official runtime distributions and document publisher/hash verification; never advise disabling protection | Medium | Small | Low | None | No | v1.0 patch |

### D. Linux/Android support

| Issue | Proposed solution | Importance | Effort | Risk | Model behavior impact | Retraining | Release |
|---|---|---|---|---|---|---|---|
| Termux/Android build and memory behavior lacks device validation | Add representative ARM64 device smoke tests and environment-specific dependency notes | High | Medium | Low | None | No | v1.0 patch |
| Unicode glyph availability and console encoding vary | Add terminal/encoding matrix tests; consider an optional ASCII logo fallback | Low | Small | Low | Presentation only | No | v1.0 patch |

### E. Runtime/performance

| Issue | Proposed solution | Importance | Effort | Risk | Model behavior impact | Retraining | Release |
|---|---|---|---|---|---|---|---|
| Existing llama-server discovery does not check supported flags/version; fresh builds follow upstream HEAD | Record a tested revision and probe necessary server capabilities | High | Medium | Low | Pinning runtime may affect inference numerics | No | v1.0 patch |
| CPU/GPU and context settings have hardware-dependent cost | Document measured hardware examples and explicit opt-in tuning; retain portable defaults | Medium | Small | Low | Context choices can affect responses | No | v1.1 |

### F. Installer/update workflow

| Issue | Proposed solution | Importance | Effort | Risk | Model behavior impact | Retraining | Release |
|---|---|---|---|---|---|---|---|
| Shared downloader resumes on rerun but has no automatic retries or progress meter | Add bounded retries and concise progress | High | Medium | Medium | None; checksum remains mandatory | No | v1.0 patch |
| No update check | Add an explicit user-requested update check, without background network requests or automatic replacement | Low | Medium | Low | None until user updates | No | v1.1 |
| Setup can race another setup and hashes ~1.8 GB each run | Add a cross-platform setup lock; retain authoritative checksum validation | Medium | Medium | Low | None | No | v1.0 patch |
| Ollama reuse checks prompt/context but not source-model digest | Record and verify imported source identity before reusing a matching named model | Medium | Medium | Low | Prevents accidentally selecting a different model | No | v1.0 patch |

### G. Maintainability

| Issue | Proposed solution | Importance | Effort | Risk | Model behavior impact | Retraining | Release |
|---|---|---|---|---|---|---|---|
| Core API response parsing assumes expected backend schema | Add small response validators and tested backend fixtures | Medium | Small | Low | None | No | v1.0 patch |
| Platform behavior needs reproducible coverage | Add Linux/Windows CI for syntax, unit contracts and wrappers; keep heavy model tests opt-in | High | Medium | Low | None | No | v1.0 patch |

### H. Security/privacy

| Issue | Proposed solution | Importance | Effort | Risk | Model behavior impact | Retraining | Release |
|---|---|---|---|---|---|---|---|
| Local unauthenticated APIs are accessible to other local processes | Document the local trust boundary and investigate backend-supported API keys where practical | Medium | Medium | Medium | None | No | v1.1 |
| Setup logs overwrite prior diagnostics and may contain local paths; debug backend logs can include sensitive details | Add bounded rotation and redacted diagnostic exports; keep normal chat unlogged | Medium | Small | Low | None | No | v1.0 patch |

### I. Future v1.x ideas

| Issue | Proposed solution | Importance | Effort | Risk | Model behavior impact | Retraining | Release |
|---|---|---|---|---|---|---|---|
| Self-knowledge relies on prompt compliance | Expand offline identity regression questions without adding brittle keyword interception | Medium | Small | Low | Better detection of drift, no direct behavior change | No | v1.0 patch |
| No optional chat export/import | Consider explicit local export/import with clear memory semantics and privacy controls | Low | Medium | Medium | Imported history affects context | No | v1.1 |


## Suggested commit message

`feat: unify SYFER runtime and setup across Linux and native Windows`

No commit or staging was performed.

## Final repository state

`git status --short` (the four `results/` entries predate this task):

```text
 M .gitignore
 M README.md
 M README_RELEASE.md
 M assets/system-prompt.txt
 M release/README.md
 M scripts/install_syfer.sh
 M scripts/run_syfer.sh
 M scripts/syfer_chat.py
 M setup.sh
 M syfer
?? assets/project-facts.txt
?? docs/RUNTIME_REVIEW.md
?? results/experiment_c_analysis/comparison.json
?? results/experiment_c_dev/
?? results/experiment_d_analysis/audit.json
?? results/experiment_d_dev/
?? scripts/syfer_setup.py
?? setup.ps1
?? syfer.ps1
?? tests/
```

`git diff --stat` (Git excludes untracked new files from this statistic):

```text
 .gitignore               |   4 ++
 README.md                | 145 ++++++++++++++++++++++++++++++++---------------
 README_RELEASE.md        |  20 ++++---
 assets/system-prompt.txt |  12 ++--
 release/README.md        |  31 +++-------
 scripts/install_syfer.sh |  49 +---------------
 scripts/run_syfer.sh     |   2 +-
 scripts/syfer_chat.py    | 141 +++++++++++++++++++++++++++++++++++----------
 setup.sh                 |  51 +----------------
 syfer                    |   3 +-
 10 files changed, 242 insertions(+), 216 deletions(-)
```
