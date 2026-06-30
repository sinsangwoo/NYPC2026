#!/usr/bin/env python3
"""Run one match and capture forensic debug output"""

import subprocess
import sys
from pathlib import Path

project_root = Path(__file__).parent.parent
testing_tool = project_root / "tools" / "testing-tool" / "testing-tool.py"
log_file = project_root / "logs" / "forensic_test.log"
stderr_file_left = project_root / "logs" / "forensic_stderr_left.txt"

log_file.parent.mkdir(parents=True, exist_ok=True)

print("Running one forensic test match...")

# Run the match with seed 1
cmd = [
    sys.executable,
    str(testing_tool),
    "--seed", "1",
    "--exec1", f"{sys.executable} {project_root / 'submission.py'}",
    "--exec2", f"{sys.executable} {project_root / 'submission.py'}",
    "--log", str(log_file),
]

# Run with capturing stderr from both players

result = subprocess.run(
    cmd, capture_output=True, text=True, cwd=project_root)

# Save stderr will contain the output from testing tool and both players
with open(stderr_file_left, 'w', encoding='utf-8') as f:
    f.write("=== STDERR from players and tool ===\n")
    f.write(result.stderr)

print(f"Match done!")
print(f"Game log: {log_file}")
print(f"Forensic stderr: {stderr_file_left}")
