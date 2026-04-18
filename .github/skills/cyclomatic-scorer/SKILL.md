---
name: cyclomatic-scorer
description: Computes McCabe Cyclomatic Complexity per function/method. Fails if any function exceeds complexity boundary of 10. Used by Refactoring-Specialist.
---

# cyclomatic-scorer

Enforces the hard cyclomatic complexity limit of `10` across the codebase.

## When to use

- **Refactoring-Specialist**: Run this against any file you are modifying to determine precisely which functions are over the complexity threshold and legally must be strangled/extracted.

## Run

```bash
bash .github/skills/cyclomatic-scorer/scripts/score.sh "src/domain/"
# or a specific file
bash .github/skills/cyclomatic-scorer/scripts/score.sh "src/services/device_service.py"
```

## How it works
Uses the `radon` python analyzer in the background. It evaluates all functions, methods, and classes in the target path. 

- Normal functions (score 1-5): `A`
- Warning range (score 6-10): `B`
- **FAIL boundary (score > 10)**: Exits with non-zero code. You must fix this. Any function `C` or worse must be simplified.
