#!/usr/bin/env python3
"""Frozen v1 scorer: strict artifacts plus a separately labelled fence diagnostic."""
import ast
import collections
import hashlib
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
TASKS = HERE / 'tasks.json'
CATEGORIES = ('Simple coding', 'Bug fixing', 'Code explanation', 'Patch generation',
              'Multi-step debugging', 'Tool-call formatting', 'Test-driven fixing',
              'Small repository reasoning')
SAFE_BUILTINS = ('abs all any ascii bin bool chr dict divmod enumerate filter float format '
                 'frozenset hex int isinstance issubclass iter len list map max min next oct ord '
                 'pow range repr reversed round set slice sorted str sum tuple type zip '
                 'Exception ValueError TypeError KeyError IndexError StopIteration ZeroDivisionError').split()
# One standard complete fence, optionally labelled. Matching delimiter required.
FENCE = re.compile(r'\A[ \t\r\n]*(?P<fence>`{3,}|~{3,})[^`~\r\n]*\r?\n(?P<body>.*?)\r?\n(?P=fence)[ \t\r\n]*\Z', re.S)

def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def equal(actual, expected):
    if type(actual) is not type(expected):
        return False
    if isinstance(expected, dict):
        return actual.keys() == expected.keys() and all(equal(actual[k], v) for k,v in expected.items())
    if isinstance(expected, list):
        return len(actual) == len(expected) and all(equal(a,b) for a,b in zip(actual,expected))
    return actual == expected

def unique_object(pairs):
    result = {}
    for key,value in pairs:
        if key in result:
            raise ValueError('duplicate JSON key: ' + key)
        result[key] = value
    return result

def reject_constant(value):
    raise ValueError('non-JSON numeric constant: ' + value)

def parse_json(raw):
    return json.loads(raw, object_pairs_hook=unique_object, parse_constant=reject_constant)

def check_code(raw):
    tree = ast.parse(raw)
    if not tree.body or any(not isinstance(node, ast.FunctionDef) for node in tree.body):
        raise ValueError('return only function definitions, no example calls or prose')
    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom, ast.Global, ast.Nonlocal)):
            raise ValueError('imports and global/nonlocal declarations are forbidden')
        if isinstance(node, ast.Attribute) and node.attr.startswith('__'):
            raise ValueError('dunder attribute access is forbidden')
        if isinstance(node, ast.Name) and (node.id.startswith('__') or node.id in
                {'open','eval','exec','compile','input','breakpoint','getattr','setattr','globals','locals','vars'}):
            raise ValueError('file/process/reflection access is forbidden')
    return tree

HARNESS = r'''
import builtins, copy, json, resource, sys
resource.setrlimit(resource.RLIMIT_CPU, (3,3))
resource.setrlimit(resource.RLIMIT_AS, (384*1024**2,384*1024**2))
payload=json.load(sys.stdin)
scope={'__builtins__':{n:getattr(builtins,n) for n in payload['builtins']}}
exec(compile(payload['code'],'<answer>','exec'),scope)
def eq(a,b):
    if type(a) is not type(b): return False
    if isinstance(b,dict): return a.keys()==b.keys() and all(eq(a[k],v) for k,v in b.items())
    if isinstance(b,list): return len(a)==len(b) and all(eq(x,y) for x,y in zip(a,b))
    return a==b
errors=[]
for i,case in enumerate(payload['cases'],1):
    args=copy.deepcopy(case['args']); before=copy.deepcopy(args)
    try:
        value=scope[case['function']](*args)
        if 'raises' in case: errors.append({'case':i,'error':'expected '+case['raises']})
        elif not eq(value,case['expected']): errors.append({'case':i,'expected':case['expected'],'actual':value})
        if case.get('unchanged_args') and not eq(args,before): errors.append({'case':i,'error':'input mutated'})
        if 'after_args' in case and not eq(args,case['after_args']): errors.append({'case':i,'error':'incorrect final argument state'})
    except Exception as e:
        if type(e).__name__ != case.get('raises'): errors.append({'case':i,'error':type(e).__name__+': '+str(e)})
print(json.dumps({'passed':not errors,'detail':errors},default=repr))
'''

def validate_python(raw, cases):
    check_code(raw)
    with tempfile.TemporaryDirectory(prefix='syfer-v1-answer-') as directory:
        result = subprocess.run([sys.executable,'-I','-B','-c',HARNESS],
            input=json.dumps({'code':raw,'cases':cases,'builtins':SAFE_BUILTINS}),
            text=True,capture_output=True,cwd=directory,timeout=5)
    if result.returncode:
        return False, 'answer process failed: ' + result.stderr[-800:]
    report=parse_json(result.stdout)
    return report['passed'],report['detail']

# The unified-diff parser below preserves content whitespace, accepts CRLF transport,
# one terminal transport blank line, zero-length hunks and no-final-newline markers.
# It is vendored from the audited D validator; earlier frozen files are not imported.

HUNK = re.compile(r"@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@(?:.*)")


def apply_unified_diff(source, raw, path):
    """Apply one-file unified diff while preserving content whitespace.

    CRLF transport and one extra terminal empty line are tolerated. Whitespace
    *inside* context, deletion and addition lines is never stripped.
    """
    if "```" in raw:
        raise ValueError("diff response must be raw, without Markdown fences")
    if "\r\n" in raw:
        raw = raw.replace("\r\n", "\n")
    if raw.endswith("\n\n"):
        raw = raw[:-1]
    lines = raw.splitlines(keepends=True)
    if len(lines) < 4 or lines[0] != f"--- a/{path}\n" or lines[1] != f"+++ b/{path}\n":
        raise ValueError("diff needs exact single-file ---/+++ headers")
    # Standard no-final-newline markers apply to the preceding hunk line.
    prepared = lines[:2]
    for line in lines[2:]:
        if line.rstrip("\n") == "\\ No newline at end of file":
            if len(prepared) <= 2 or not prepared[-1].startswith((" ", "-", "+")):
                raise ValueError("orphan no-final-newline marker")
            prepared[-1] = prepared[-1].removesuffix("\n")
        else:
            prepared.append(line)
    old = source.splitlines(keepends=True)
    new = []
    old_pos = 0
    index = 2
    hunks = 0
    while index < len(prepared):
        header = HUNK.fullmatch(prepared[index].rstrip("\n"))
        if not header:
            raise ValueError("invalid hunk header")
        old_start = int(header.group(1))
        old_count = int(header.group(2) or "1")
        new_start = int(header.group(3))
        new_count = int(header.group(4) or "1")
        old_target = old_start if old_count == 0 else old_start - 1
        if old_start < 0 or (old_start == 0 and old_count != 0) or old_target < old_pos or old_target > len(old):
            raise ValueError("old hunk position does not match source")
        new.extend(old[old_pos:old_target])
        old_pos = old_target
        expected_new_start = len(new) if new_count == 0 else len(new) + 1
        if new_start != expected_new_start:
            raise ValueError("new hunk position does not match output")
        index += 1
        consumed = produced = 0
        while index < len(prepared) and not prepared[index].startswith("@@ "):
            line = prepared[index]
            if not line or line[0] not in " +-":
                raise ValueError("invalid diff line")
            content = line[1:]
            if line[0] in " -":
                if old_pos >= len(old) or old[old_pos] != content:
                    raise ValueError("diff context/deletion does not match source")
                old_pos += 1
                consumed += 1
            if line[0] in " +":
                new.append(content)
                produced += 1
            index += 1
        if (consumed, produced) != (old_count, new_count):
            raise ValueError("hunk line counts do not match")
        hunks += 1
    if not hunks:
        raise ValueError("diff has no hunks")
    new.extend(old[old_pos:])
    return "".join(new)


def function_source(source, name):
    tree = ast.parse(source)
    matches = [node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == name]
    if len(matches) != 1:
        raise ValueError(f"preserved function missing or ambiguous: {name}")
    return ast.get_source_segment(source, matches[0])


def run_oracle(task):
    """Execute trusted authored examples, not generated model code."""
    with tempfile.TemporaryDirectory(prefix="syfer-d-oracle-") as temporary:
        directory = Path(temporary)
        if task["response_mode"] == "explanation_json":
            (directory / "snippet.py").write_text(task["snippet"] + "\n", encoding="utf-8")
            command = [sys.executable, "-I", "-B", "snippet.py"]
        else:
            for name, content in task["files"].items():
                if Path(name).name != name or not name.endswith(".py"):
                    raise ValueError("unsafe virtual file name")
                (directory / name).write_text(content, encoding="utf-8")
            command = [sys.executable, "-B", task["entry"]]
        result = subprocess.run(command, cwd=directory, text=True, capture_output=True,
                                timeout=5, check=False)
    if result.returncode:
        raise ValueError(f"oracle failed: {result.stderr.strip()[-300:]}")
    output = json.loads(result.stdout.strip())
    return output

def strict(task, raw):
    try:
        if re.search(r'(?m)^[ \t]*(?:`{3,}|~{3,})',raw):
            raise ValueError('Markdown fences are forbidden by the explicit response contract')
        mode=task['response_mode']
        if mode=='python_code':
            passed,detail=validate_python(raw,task['cases'])
        elif mode=='unified_diff':
            patched=apply_unified_diff(task['source'],raw,task['path'])
            for name in task.get('preserve_functions',[]):
                if function_source(task['source'],name)!=function_source(patched,name):
                    raise ValueError('unrelated helper modified: '+name)
            passed,detail=validate_python(patched,task['cases'])
        else:
            value=parse_json(raw)
            passed=equal(value,task['expected'])
            detail='parsed JSON matches exact schema/types/values' if passed else 'JSON schema/type/value mismatch'
        return {'passed':bool(passed),'detail':detail,'error_type':None}
    except Exception as error:
        return {'passed':False,'detail':str(error),'error_type':type(error).__name__}

def score(task, raw):
    official=strict(task,raw)
    diagnostic=dict(official)
    normalization='none'
    match=FENCE.fullmatch(raw)
    if not official['passed'] and match and not re.search(r'(?m)^[ \t]*(?:`{3,}|~{3,})',match.group('body')):
        # Only the delimiter lines are removed. Code/JSON/diff content is not repaired.
        # Preserve the newline before the closing delimiter (important for diffs).
        inner=match.group('body')+'\n'
        diagnostic=strict(task,inner)
        normalization='single_complete_outer_fence'
    return {'strict':official,'semantic_diagnostic':diagnostic,
            'diagnostic_normalization':normalization,
            'formatting_only_failure':not official['passed'] and diagnostic['passed']}

def validate_references():
    tasks=json.loads(TASKS.read_text())
    errors=[]; passed=0
    counts=collections.Counter(t['category'] for t in tasks)
    if len(tasks)!=48 or counts!=dict.fromkeys(CATEGORIES,6): errors.append('need 48 tasks, six per category')
    if len({t['id'] for t in tasks})!=48: errors.append('duplicate IDs')
    for task in tasks:
        result=score(task,task['reference'])
        if not result['strict']['passed']: errors.append(task['id']+': '+str(result['strict']['detail']))
        else: passed+=1
        if task['response_mode'] in ('explanation_json','repository_reasoning_json'):
            if task['expected']['reason'] not in task['prompt']: errors.append(task['id']+': hidden reason tag')
            if not equal(run_oracle(task),task['expected']['output']): errors.append(task['id']+': oracle mismatch')
    return {'task_count':len(tasks),'category_counts':dict(counts),'references_passed':passed,'errors':errors}

def main():
    report=validate_references()
    print(json.dumps(report,indent=2))
    return bool(report['errors'])

if __name__=='__main__':
    raise SystemExit(main())
