#!/usr/bin/env python3
import sys
from pathlib import Path


def main() -> None:
    src_dir = Path("src")
    output_file = Path("submission.py")

    with open(output_file, "w", encoding="utf-8") as out_f:
        for file in sorted(src_dir.glob("*.py")):
            with open(file, "r", encoding="utf-8") as in_f:
                content = in_f.read()
                # Skip shebang and future imports (except for first file)
                if file != src_dir / "main.py":
                    lines = content.splitlines()
                    filtered = []
                    skip = True
                    for line in lines:
                        if skip and (line.startswith("#!") or line.startswith("from __future__ import")):
                            continue
                        skip = False
                        filtered.append(line)
                    content = "\n".join(filtered)
                out_f.write(f"\n# --- BEGIN {file.name} ---\n")
                out_f.write(content)
                out_f.write(f"\n# --- END {file.name} ---\n")

    print(f"Built single-file submission: {output_file}", file=sys.stderr)


if __name__ == "__main__":
    main()
