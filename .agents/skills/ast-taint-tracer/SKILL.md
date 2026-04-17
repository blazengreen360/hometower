---
name: ast-taint-tracer
description: Uses the Python AST (Abstract Syntax Tree) to map the Call Graph and trace the flow of unvalidated variables from external inputs through the layers into dangerous sinks like `session.execute` or `eval()`.
---

# ast-taint-tracer

Provides the `Security-Auditor` and `Bug-Finder` with mechanical Data Flow Analysis. They no longer rely on fragile text `grep` to trace where unvalidated variables end up.

## When to use

- **Security-Auditor**: When you identify a fastAPI route parameter that you suspect is vulnerable to SQL injection, IDOR, or XSS.
- **QA-Bug-Finder**: When tracking down a weird data mutation logic glitch.

## Run

```bash
bash .agents/skills/ast-taint-tracer/scripts/run.sh --file "src/api/routers/devices.py" --sink "session.execute"
```

## How it works
This executes a local Python AST sweep. It parses the file into a structural tree, maps all `Call` and `Attribute` nodes, and flags wherever the requested `sink` method is invoked. It then attempts to trace the parameters passed into that sink upstream to the function signature (the `source`).
