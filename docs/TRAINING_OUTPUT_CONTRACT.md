# SYFER training-output contract, proposed D1

This is the canonical **future Experiment D** response contract. It does not
change earlier datasets, frozen benchmarks, or recorded scores. Each future
JSONL row must declare a `response_mode` in its metadata; the system/user
messages must state that mode's output rules, and the assistant target must
obey them. Keep train and validation task families separate. Never use a
benchmark prompt, fixture, expected answer, or validator as training content.

Across all modes, the assistant emits exactly one requested artifact. Do not
add introductions, explanations outside the artifact, Markdown fences,
example calls, or a second answer. A validator must check the complete raw
response, never silently select the first fenced block. The task prompt must
state every key, type, allowed tool name, reason tag, output container type,
and any whitespace rule that affects scoring.

| `response_mode` | Required output | Validation contract |
| --- | --- | --- |
| `python_code` | Raw Python `def` definitions for every requested function. No prose or fences; no imports unless the task explicitly allows them. | Parse all top-level statements; execute isolated deterministic cases; check declared return types and preservation cases. Publish the available builtins. |
| `exact_json` | One bare JSON value with the task-declared complete schema. For object tasks, no extra/missing keys. | Parse the whole response, reject duplicate keys and trailing content, then recursively check keys, JSON types and required values. JSON object key order is irrelevant. |
| `tool_call_json` | One bare JSON object with exactly `tool` and `arguments`; `tool` is a declared string; `arguments` is the exact per-tool object schema. Compact serialization is preferred in training targets. | Parse and compare types/values/keys; reject duplicate/extra keys, prose and fences. Accept irrelevant JSON whitespace and any object key order. No real tool is invoked by the validator. |
| `unified_diff` | One raw, single-file unified diff with `--- a/<path>`, `+++ b/<path>`, and valid `@@` hunk headers. No prose or fence. | Preserve all bytes/whitespace, verify old-side context and hunk counts, apply to the stated source, then run tests and preservation checks. |
| `explanation_json` | One bare JSON object with exactly `output` and `reason`. `output` has the prompt-declared JSON type; `reason` equals a literal tag stated in the prompt. | Execute the snippet in isolation and compare `output` and tag exactly. Pretty JSON may be parsed, but training targets should be compact and fence-free. |
| `repository_reasoning_json` | One bare JSON object with exactly `output` and `reason`, with typed output and a prompt-stated literal tag. | Execute supplied virtual files in an isolated directory, compare typed output and tag, reject extra keys/prose/fences. |

The canonical training serialization for all JSON modes is compact UTF-8 JSON
with no surrounding text or final newline inside the assistant message. This
reduces format variation. All D JSON scorers, including the tool scorer,
accept insignificant JSON whitespace and object-key reordering. Key order is
a target convention (`tool` before `arguments`, `output` before `reason`), not
a semantic requirement.

The `reason` field is a controlled tag, not free-form prose. If a future task
needs a natural-language explanation instead, define a separately named mode
such as `explanation_prose_json` with exactly `output` and `explanation` and
state it in the prompt and metadata. Do not mix that schema into
`explanation_json` or `repository_reasoning_json`. Experiment C's existing
`output`/`explanation` examples belong to this legacy prose variant and must
not be relabeled as D1 reason-tag examples.

For `tool_call_json`, the task must supply or reference a mock tool registry.
Each tool entry declares its exact argument keys, nested shapes, primitive
types, array element types, nullability, and whether an optional key may be
omitted. `null` and a missing key are distinct. When the prompt requests a
sequence, preserve its order. Unknown tools, invented argument keys, or
substituting YAML are invalid. The validator checks formatting only; it never
connects to shell, file or network tools.

For `unified_diff`, a context line begins with one space, including an empty
context line (` ` followed by newline); deletion/addition lines begin with
`-`/`+`. Hunk counts must match the consumed and produced lines. The parser
must not call whole-diff `.strip()`, because trailing spaces and blank context
are meaningful. It should specify handling of files without a final newline
and of `\\ No newline at end of file`. Tasks should include multiple-hunk,
insertion, deletion, multiline replacement, trailing-whitespace and
unchanged-helper cases. Preserving unrelated code is a checked invariant,
not merely a sentence in the prompt.

For `python_code`, allow harmless ordinary Python builtins such as `iter`,
`next`, `ord`, and `chr` in a future isolated harness, or explicitly disallow
them in the task contract. Keep file/process/network access unavailable.
Check nested result types where the prompt specifies them; if a list of lists
is required, say so rather than relying on examples to exclude tuples.

Before any D training, validate every target against this contract, its
functional or semantic oracle, and family/benchmark contamination checks.
Keep a version identifier with the dataset and evaluator. A future score under
a new validator is a **new series**, never a rewrite of Stock/B/C's frozen
C-development scores.
