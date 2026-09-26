# Stage 1: stock model baseline

This benchmark measures the untouched, locally installed `qwen2.5-coder:3b` model. It has 16 fixed tasks: two each for simple coding, bug fixing, code explanation, patch generation, multi-step debugging, tool-call formatting, test-driven fixing, and small repository reasoning. Prompts, test inputs, and expected outputs are in `tasks.json`.

Run from the project root:

```sh
python3 benchmark/run_baseline.py
```

The runner checks that the exact model name is installed before making requests to Ollama's local `/api/generate` endpoint. It never calls a pull or install command. Sampling uses temperature 0, seed 42, and a 512-token response limit. Ollama/runtime errors are recorded as task failures. Each run gets a UTC timestamp plus a random suffix under `results/baseline/`, so prior runs remain available. A `--limit N` option runs the first N tasks for a smoke check; omit it for the complete baseline.

For coding tasks, the answer must contain Python function definitions. A complete Markdown code fence is extracted if present, so surrounding prose does not prevent testing the code. A separate Python process runs the generated code and fixed test cases from an isolated temporary working directory, with a five-second timeout and a small set of built-in functions. Patch tasks require a unified diff for the named virtual file; the runner checks the hunk context, applies it in memory, and runs the same tests. No task writes its generated solution into the SYFER source tree. The process isolation is for accidental writes and hangs, not a security boundary for hostile code.

Code explanation and repository reasoning tasks require exact JSON fields; a complete JSON code fence is accepted. Explanation tasks also require a nonempty explanation string. Mock tool calls require one exact minified JSON string, including key order and no extra text. The mock tool is never executed or connected to real tools.

Each run stores `run_config.json` with model and file hashes, `tasks_snapshot.json`, the untouched raw response for every task (`<task-id>.txt`), `progress.json`, `summary.json`, and a readable `summary.md`. The score is the number of tasks passing their objective validator divided by 16. A failed format check counts as a failed task even if the intent of the answer looks correct. Runtime is elapsed wall time for the full run, including response generation and validation. Model outputs can vary across Ollama versions and hardware despite fixed sampling settings; the run records the installed model digest for comparison.
