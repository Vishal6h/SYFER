# Stock model baseline

Model: `qwen2.5-coder:3b` (ID `f72c60cabf6237b07f6e632b2c48d533cef25eda2efbd34bed21c5e9c01e6225`)
Tasks: 16 | Passed: 4 | Failed: 12 | Runtime: 38.41 s

| Category | Passed | Total |
| --- | ---: | ---: |
| Simple coding | 1 | 2 |
| Bug fixing | 0 | 2 |
| Code explanation | 0 | 2 |
| Patch generation | 0 | 2 |
| Multi-step debugging | 0 | 2 |
| Tool-call formatting | 2 | 2 |
| Test-driven fixing | 0 | 2 |
| Small repository reasoning | 1 | 2 |

## Failed tasks

- `simple_dedupe`: [{'case': 1, 'expected': [3, 1, 2], 'actual': [3, 1, 3, 2, 1]}]
- `bug_count_words`: unterminated string literal (detected at line 3) (<unknown>, line 3)
- `bug_last_index`: invalid syntax (<unknown>, line 1)
- `explain_slice`: Expecting value: line 1 column 1 (char 0)
- `explain_mutation`: Expecting value: line 1 column 1 (char 0)
- `patch_clamp`: hunk line counts do not match
- `patch_slug`: hunk line counts do not match
- `debug_inventory`: invalid syntax (<unknown>, line 1)
- `debug_parse_average`: [{'case': 2, 'expected': 2.5, 'actual': 2}]
- `tdd_palindrome`: unterminated string literal (detected at line 1) (<unknown>, line 1)
- `tdd_chunk`: unterminated string literal (detected at line 1) (<unknown>, line 1)
- `repo_call_chain`: Expecting value: line 1 column 1 (char 0)
