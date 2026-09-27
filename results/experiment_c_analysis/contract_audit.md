# Experiment C training / C-development contract audit

This is a read-only postmortem of the 120 Experiment C JSONL examples (88 train,
32 validation), the 32 frozen C-development tasks, their imported scoring
functions, and the three completed run reports. Stock and C both scored 10/32
on exactly the same tasks; B scored 8/32. These are recorded development
results and are not changed here. No model was queried for this audit.

The C training examples have 30 families with four closely related variants
per family. The category counts are patch 32, tool 24, repository 24, and
eight each for simple coding, bug fixing, code explanation, multi-step
debugging, and TDD. The C-development set has four tasks in each category.

## Category-by-category contract

| Category | C training prompt and target | C-development prompt and validator | Alignment / observed C result |
| --- | --- | --- | --- |
| Simple coding | System asks for code only; assistant targets start with raw `def`. No prose or fences. | Prompts ask for Python function definitions without imports or example calls. The scorer extracts the first fenced block if present, checks top-level functions, and runs cases. | Output mode aligns. C passes 3/4; `border_sum` double-counts a single-row grid. Scorer tolerates prose/fences despite prompt wording. |
| Bug fixing | Correct the function while preserving other behavior; raw `def` answer. | Same code-only intent, case-based scoring; some tasks specify not mutating inputs. | Output mode aligns. C passes 3/4; `decode_percent` fails lowercase `%2f`. |
| Code explanation | All 8 training answers are bare JSON with exactly `output` and a free-form nonempty `explanation` string. Prompts explicitly request those keys. | All four tasks request JSON with exactly `output` and `reason`; each states a literal reason tag. `json.loads(raw.strip())` and recursive exact-type/value comparison are used. | **Direct schema mismatch:** `explanation` vs `reason`, prose vs literal tag. C answers all four with fenced JSON; two inner values are also wrong. 0/4. |
| Patch generation | All 32 answers are raw unified diffs with `--- a/path`, `+++ b/path`, correct hunks and space-prefixed context, including blank context lines. Training asks to preserve unrelated lines. | Prompts request a raw single-file unified diff and preservation of unrelated functions. The scorer extracts a fence if present, applies the custom parser, then runs Python cases. | Intended format aligns, but C's four outputs have bare blank context lines and are rejected before code runs. Several also change unrelated code or leave the bug. 0/4. Training has only eight patch families repeated four times each. |
| Multi-step debugging | All 8 training targets are raw definitions that fix multiple stated issues. | Same output intent, tested through the restricted Python harness. | Mode aligns. C passes 1/4. `debug_money` uses two separate code fences; the scorer extracts only the first, so `total_cents` is missing. `debug_ranges` has a tuple/list type mismatch and an inclusive-length error. `word_score` uses an unavailable builtin and wrong arithmetic. |
| Tool-call formatting | All 24 training answers are bare, minified JSON with root keys `tool` and `arguments`; six tool families cover flat, array, nullable, nested target, and two-step arguments. No prose/fences. | Four prompts also demand one minified JSON object, root `tool`/`arguments`, task-specific nested argument keys and values, no extra keys. Scorer compares the raw bytes with one canonical `json.dumps` string. | Schema *shape* aligns, but the tool names and nested schemas are unseen; C emits wrong root/argument structures, fences or YAML. 0/4. The scorer also rejects otherwise equivalent key orders. |
| Test-driven fixing | All 8 examples present cases and return raw Python definitions. | Prompts present cases and request only definitions; Python harness executes them. | Mode aligns. C passes 3/4. The remaining subsequence solution is valid standard Python on all five cases but `iter` is absent from the sandbox allowlist. |
| Small repository reasoning | All 24 examples show virtual files and give bare JSON with `output` plus free-form `explanation`. | All four tasks show virtual files and explicitly require `output` plus an exact `reason` tag. The scorer parses raw JSON, then compares exact keys, types and values. | **Direct schema mismatch** as with code explanation. C has the correct `output` in three of four, but fences and/or prose reason cause rejection. It also misreads the import-cache task. 0/4. |

No C training assistant target contains a Markdown fence. All 24 tool targets
are minified JSON, and all 32 patch targets begin with a diff header. Thus the
observed C fences, YAML, and malformed diffs are failures to generalize the
training format, not examples of those errors deliberately taught by C data.
The critical *content* mismatch is that C's 32 explanation/repository examples
teach `output`/`explanation`, while all eight corresponding development tasks
require `output`/`reason` with exact tags. Future data should teach the
declared response contract using new task families; no frozen prompt or answer
should be copied into training.

## Validator audit

The C-development validator delegates response scoring to
`benchmark/final_holdout/validate_holdout.py`, which delegates code and patch
handling to the frozen `benchmark/run_baseline.py`. The reference answers all
pass, and re-scoring the 96 saved raw responses reproduced every recorded
pass/fail. The issues below concern contract quality for **future versioned**
evaluation, not a re-score of C.

| Check | Finding | Evidence and impact | Future treatment |
| --- | --- | --- | --- |
| Python sandbox | **Genuine valid-answer rejection:** `iter` is not in the allowed builtins, despite no prompt prohibition. | C's `is_subsequence` passes all five cases with only `iter` added to a temporary copy of the harness; frozen scoring raises `NameError` five times. | Publish the allowed language subset or add safe common builtins in a new scorer. Preserve C's historical failure. |
| Python sandbox | `ord` is also absent, but it is not the primary cause of C's `word_score` failure. | With only `ord` added temporarily, C still returns 294 instead of alphabet-position score 6 for `cab`. | Do not reclassify this as a valid solution. Specify supported builtins for future tasks. |
| Python value types | Top-level result type is checked, but nested types are not. | A temporary `f()` returning `[True]` passes a case expecting `[1]` because Python compares `True == 1`. Conversely, `debug_ranges` tuples fail list-of-lists cases even though the JSON-rendered details look identical. | Decide and state whether nested exact types matter; use recursive checks or explicitly accept equivalent range pairs. |
| Code-only parser | `code_only` accepts prose and fences, silently selects only the **first** fenced block, and ignores later code. | A prose-wrapped fenced reference still passes `cdev_interleave` despite its raw-code prompt. C's `debug_money` contains both functions in separate fences, but only the first is executed. | Future raw-code mode should reject prose/fences (or document normalization); never silently drop a second block. |
| JSON response | Surrounding whitespace and key order are tolerated; exact `reason` tags and types are enforced. | An object with keys reordered and surrounding whitespace passes. All C explanation/repository prompts explicitly state the required reason tag; prose is noncompliant. | Keep exact tags where the prompt states them. Document the whitespace policy consistently. |
| Tool call | **Unnecessary exact-string matching:** byte equality imposes JSON key order and serialization beyond the stated schema. | Reversing only the root key order in an otherwise identical minified `cdev_tool_edit_plan` call is rejected as `mock call differs`. This did **not** explain C's failures; C's fields/format were actually wrong. | Parse JSON, reject duplicate/extra keys, check exact types/values, and enforce minification separately without requiring key order. |
| Unified diff | **Genuine parser defect:** whole-diff `.strip()` destroys significant trailing whitespace. | A standard `difflib.unified_diff` ending with a blank context line is rejected with `hunk line counts do not match`. An added line ending in two spaces is silently changed to no spaces. A no-final-newline edit is likewise not preserved. | In a new parser, remove at most the transport newline, retain line bytes, support/document `\\ No newline at end of file`, and verify exact resulting source. |
| Unified diff | Current C patch failures are genuine malformed outputs. | All four C diffs contain an empty line without the required context prefix. Their parser error is `invalid diff line`, independent of the trailing-whitespace defect above. | Keep this requirement; add clear diagnostics and raw-diff negative cases to future tests. |
| Patch behavior | Case tests do not prove preservation of unrelated code. | A valid diff that changes `label(value)` to `f"{value}"` while correctly fixing `escape_markup` passes the frozen `cdev_patch_escape` cases; `label(3)` would change from integer `3` to string `"3"`. | Future patch tasks should check untouched source/AST regions or add sentinel cases, along with functional tests. |
| Repository/explanation oracle | The reference snippets run in temporary directories; response scoring compares to fixed expected JSON. | All authored references pass. Prompt-specified `output` type and reason tag are enforced. No evidence of an unstated reason field on these eight tasks. | Retain isolated oracles and explicitly print exact schema in every future prompt. |

`cdev_debug_ranges` does not expressly say “return a list of lists,” although
its notation and examples use `[start,end]`. The tuple rejection is therefore
an avoidable type ambiguity. Its `covered_length` answer is wrong regardless,
so the current overall failure does not depend solely on that ambiguity.
The four tool prompts state the root and nested fields, but do not state that
JSON object key order is semantically significant. Exact raw-byte comparison
adds this unstated restriction.

## Decision implications

Experiment C did not improve patch, tool, explanation or repository category
scores. Twenty of its 32 raw responses are byte-for-byte identical to Stock.
The next training design should align prompts and targets to one explicit
versioned contract, use varied non-benchmark families, test raw formatting
before training, and retain basic-code rehearsal. Validator defects should be
fixed only in a new versioned future benchmark and scored independently;
the frozen C-development tasks, validator, and recorded results remain intact.
