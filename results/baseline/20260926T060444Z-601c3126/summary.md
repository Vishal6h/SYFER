# Stock model baseline

Model: `qwen2.5-coder:3b` (ID `f72c60cabf6237b07f6e632b2c48d533cef25eda2efbd34bed21c5e9c01e6225`)
Tasks: 16 | Passed: 6 | Failed: 10 | Runtime: 17.15 s

| Category | Passed | Total |
| --- | ---: | ---: |
| Simple coding | 1 | 2 |
| Bug fixing | 0 | 2 |
| Code explanation | 1 | 2 |
| Patch generation | 0 | 2 |
| Multi-step debugging | 0 | 2 |
| Tool-call formatting | 2 | 2 |
| Test-driven fixing | 1 | 2 |
| Small repository reasoning | 1 | 2 |

## Failed tasks

- `simple_dedupe`: [{'case': 1, 'expected': [3, 1, 2], 'actual': [3, 1, 3, 2, 1]}]
- `bug_count_words`: [{'case': 1, 'expected': 3, 'actual': 2}]
- `bug_last_index`: [{'case': 1, 'expected': 3, 'actual': 0}]
- `explain_mutation`: incorrect JSON fields or extra/missing keys
- `patch_clamp`: hunk line counts do not match
- `patch_slug`: hunk line counts do not match
- `debug_inventory`: [{'case': 1, 'expected': {'pen': 5}, 'actual': {'pen': 3}}]
- `debug_parse_average`: [{'case': 2, 'expected': 2.5, 'actual': 2}]
- `tdd_palindrome`: response must contain only function definitions
- `repo_call_chain`: incorrect JSON fields or extra/missing keys
