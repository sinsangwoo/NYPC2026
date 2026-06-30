#!/usr/bin/env python3
import sys
from pathlib import Path


def strip_internal_imports(content: str) -> str:
    modules = ["main", "candidate_generator", "evaluation_function", "action_selector", "feature_calculator"]
    lines = content.splitlines()
    filtered = []
    skip_multiline = False

    for line in lines:
        stripped = line.strip()
        # Detect start of internal import (both from-style and import-style)
        is_internal_from = any(stripped.startswith(f"from {m} import") for m in modules)
        is_internal_import = any(stripped.startswith(f"import {m}") for m in modules)

        if is_internal_from or is_internal_import:
            if "(" in stripped and ")" not in stripped:
                skip_multiline = True
            continue

        if skip_multiline:
            if ")" in stripped:
                skip_multiline = False
            continue

        filtered.append(line)

    return "\n".join(filtered)


def main() -> None:
    src_dir = Path("src")
    output_file = Path("submission.py")

    with open(output_file, "w", encoding="utf-8") as out_f:
        # Prepend unified shebang and future imports at the very beginning of the merged file
        out_f.write("#!/usr/bin/env python3\n")
        out_f.write("from __future__ import annotations\n\n")

        for file in sorted(src_dir.glob("*.py")):
            with open(file, "r", encoding="utf-8") as in_f:
                content = in_f.read()
                # Unconditionally strip shebang and future imports from all source files
                lines = content.splitlines()
                filtered = []
                for line in lines:
                    if line.startswith("#!") or line.startswith("from __future__ import"):
                        continue
                    filtered.append(line)
                content = "\n".join(filtered)
                content = strip_internal_imports(content)
                out_f.write(f"\n# --- BEGIN {file.name} ---\n")
                out_f.write(content)
                out_f.write(f"\n# --- END {file.name} ---\n")

    print(f"Built single-file submission: {output_file}", file=sys.stderr)


if __name__ == "__main__":
    main()
