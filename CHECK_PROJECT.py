from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parent
python_files = sorted(ROOT.rglob("*.py"))
total_lines = 0
errors = []

for path in python_files:
    if "__pycache__" in path.parts:
        continue
    text = path.read_text(encoding="utf-8")
    total_lines += len(text.splitlines())
    try:
        ast.parse(text, filename=str(path))
    except SyntaxError as exc:
        errors.append(f"{path.relative_to(ROOT)}:{exc.lineno}: {exc.msg}")

print(f"Python files: {len(python_files)}")
print(f"Total Python lines: {total_lines:,}")
if errors:
    print("Syntax errors:")
    for error in errors:
        print(" -", error)
    raise SystemExit(1)
print("Syntax check: PASS")
