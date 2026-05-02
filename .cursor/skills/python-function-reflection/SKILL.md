---
name: python-function-reflection
description: Explains why a Python function implementation failed tests and provides concise reflection-only guidance. Use when the user shares failing unit test output and asks for analysis of what is wrong without requesting a code rewrite.
---

# Python Function Reflection

## When to use

Use this skill when the user provides:
- a Python function implementation,
- unit test results (especially failures),
- a request to explain what is wrong in a few sentences.

## Required response style

- Return only a brief reflection (few sentences).
- Do not provide a replacement implementation unless explicitly requested.
- Focus on why tests failed and what behavior is incorrect.
- Tie the explanation to concrete failing assertions or observed outputs.
- Prefer explicit Python typing language; avoid suggesting `Any` unless unavoidable.

## Reflection checklist

1. Identify expected behavior from test assertions.
2. Compare expected behavior to actual output.
3. Point out the exact logic mismatch in the implementation.
4. Describe the correction direction at a high level (no full code by default).

## Example pattern

Given:
- expected `add(1, 2) == 3`,
- actual output `-1`,
- implementation uses subtraction.

Good reflection:
"The function fails because it subtracts `b` from `a` instead of adding them. This causes incorrect output for positive inputs like `(1, 2)`. Update the arithmetic logic so the return value reflects addition, which aligns with the tests."
