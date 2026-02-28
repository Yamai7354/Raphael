---
name: debug_code
description: Systematic code debugging — error triage, log analysis, stack trace interpretation, root cause analysis, and automated fix generation
---

# Debug Code

Systematically diagnose and fix bugs using a structured diagnostic workflow.

## When to Use

- User reports an **error**, **bug**, **crash**, or **unexpected behavior**
- A build, test, or runtime failure needs investigation
- Stack traces or error logs need interpretation
- Flaky or intermittent issues need root cause analysis

## Environment Context

The user has 4 active workspaces (Corpora) that may contain relevant code:
- `/Users/yamai/ai/Raphael` -> `/Users/yamai/ai/Raphael`
- `/Users/yamai/ai/agent_ecosystem` -> `/Users/yamai/ai/agent_ecosystem`
- `/Users/yamai/ai/network_observatory` -> `Yamai7354/network_observatory`
- `/Users/yamai/ai/portfolio` -> `/Users/yamai/ai/portfolio`

You can search across these using tools like `grep_search` or Semantic Search tools (e.g. `mcp_airweave_search`).
The `agent_ecosystem` is an active workspace relevant for multi-agent or router-based debugging.

## Workflow

### 1. Gather Context (Triage)

Before investigating, collect:

- [ ] **Error message** — exact text, stack trace, error code
- [ ] **Reproduction steps** — what triggers the bug
- [ ] **Environment** — OS, language version, dependency versions
- [ ] **Recent changes** — git log, recent edits, new dependencies
- [ ] **Expected vs actual behavior**

```bash
# Check recent changes
git log --oneline -10
git diff HEAD~3 --stat

# Check language/runtime version
python3 --version
node --version
```

### 2. Classify the Error

| Error Type        | Symptoms                                | First Action                      |
| ----------------- | --------------------------------------- | --------------------------------- |
| **Syntax**        | File won't parse, SyntaxError           | Go to exact line, check syntax    |
| **Import/Module** | ModuleNotFoundError, Cannot find module | Check dependencies, paths         |
| **Type**          | TypeError, AttributeError               | Check variable types, null checks |
| **Runtime**       | Exception during execution              | Read stack trace bottom-up        |
| **Logic**         | Wrong output, no error                  | Add logging, trace data flow      |
| **Concurrency**   | Race conditions, deadlocks              | Check async/await, locks          |
| **Environment**   | Works locally, fails elsewhere          | Check env vars, config, versions  |
| **Performance**   | Slow, high memory, timeouts             | Profile, check loops, queries     |

### 3. Read the Stack Trace

**Read bottom-up** — the root cause is usually at the bottom:

```
Traceback (most recent call last):           ← Start of call chain
  File "main.py", line 42, in run           ← Caller
    result = process(data)
  File "processor.py", line 15, in process   ← Where it crashed
    return data['key']                        ← The failing line
KeyError: 'key'                              ← The actual error
```

**Steps:**
1. Read the **last line** — what error was raised
2. Read the **last file:line** — where it happened
3. Use `view_file` to see surrounding code context
4. Trace the call chain upward to understand data flow

### 4. Investigate

#### Search for the error pattern
```
grep_search(Query="KeyError", SearchPath="/project/src", MatchPerLine=true)
```

#### View the failing code
```
view_file(AbsolutePath="/project/src/processor.py", StartLine=10, EndLine=25)
```

#### Check related code
```
view_code_item(File="/project/src/processor.py", NodePaths=["process"])
```

#### Add diagnostic logging (if needed)
Insert temporary print/log statements to trace data flow:

```python
# Debug: trace the incoming data
print(f"DEBUG: data type={type(data)}, keys={data.keys() if hasattr(data, 'keys') else 'N/A'}")
print(f"DEBUG: data={data}")
```

#### Run with verbose output
```bash
# Python
python3 -v script.py 2>&1 | tail -50

# Node.js
NODE_DEBUG=* node script.js 2>&1 | tail -50

# General — capture stderr
./command 2>&1 | tee debug_output.log
```

### 5. Identify Root Cause

Common root cause patterns:

| Pattern            | Example                                 | Fix                                 |
| ------------------ | --------------------------------------- | ----------------------------------- |
| Missing null check | `data.name` when data is None           | Add `if data:` guard                |
| Wrong data type    | String where int expected               | Add type conversion/validation      |
| Off-by-one         | `array[len]` instead of `array[len-1]`  | Fix index bounds                    |
| Missing dependency | Module not in requirements              | Add to requirements, install        |
| Race condition     | Two threads writing same file           | Add locks or queue                  |
| Stale cache        | Old compiled files                      | Clean build artifacts               |
| Env var missing    | `os.environ['KEY']` not set             | Use `.get()` with default           |
| Path error         | Relative path breaks from different cwd | Use absolute or `__file__` relative |

### 6. Apply the Fix

1. **Make the minimal fix** — change only what's necessary
2. **Add guard clauses** — prevent the same class of bug
3. **Run the failing test/command** to confirm the fix
4. **Run the full test suite** to check for regressions

```bash
# Re-run the failing command
python3 script.py

# Run tests
python3 -m pytest tests/ -v
npm test
```

### 7. Prevent Recurrence

After fixing, consider:
- Add a **test case** that covers the bug
- Add **input validation** at boundary layers
- Add **type hints** (Python) or **TypeScript types** for better static analysis
- Update **error messages** to be more descriptive
- Add **logging** at key decision points

## Advanced Debugging

### Memory Issues
```bash
# Python memory profiling
python3 -c "
import tracemalloc
tracemalloc.start()
# ... run code ...
snapshot = tracemalloc.take_snapshot()
for stat in snapshot.statistics('lineno')[:10]:
    print(stat)
"
```

### Performance Profiling
```bash
# Python
python3 -m cProfile -s cumulative script.py 2>&1 | head -30

# Node.js
node --prof script.js
```

### Binary Search for Bugs (git bisect)
```bash
git bisect start
git bisect bad          # Current version is broken
git bisect good v1.0.0  # This version was working
# Git will checkout commits for you to test
# After testing each:
git bisect good  # or git bisect bad
```

## Error Handling

- **Can't reproduce**: Ask for exact steps, check environment differences
- **Flaky tests**: Run multiple times, check for timing/ordering dependencies
- **No stack trace**: Add `try/except` with `traceback.print_exc()`, check stderr
- **Third-party bug**: Check issue trackers, pin to known-good version, add workaround
