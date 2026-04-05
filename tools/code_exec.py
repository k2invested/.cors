#!/usr/bin/env python3
"""code_exec — execute shell commands sandboxed to workspace.

Input JSON:
  {"command": "<single shell command>"}
  {"commands": ["<step 1>", "<step 2>", ...]}

When commands array is provided, each step runs sequentially.
Stops on first non-zero exit code. Output from all steps is accumulated.

Env: WORKSPACE — sandbox root.
"""
TOOL_DESC = 'execute shell commands sandboxed to workspace.'
TOOL_MODE = 'mutate'
TOOL_SCOPE = 'external'
TOOL_POST_OBSERVE = 'log'

import json, os, subprocess, sys, tempfile, re

MAX_RESULT_CHARS = 32000

def run_one(command: str, workspace: str) -> tuple[str, int]:
    """Run a single command, return (output, exit_code).
    Python one-liners (python3 -c '...') are written to a temp file
    to avoid shell quoting issues with parentheses and braces."""
    # Detect python3 -c '...' or python3 -c "..." and extract the code
    py_match = re.match(r"""^(python3?)\s+-c\s+(['"])(.*)\2\s*$""", command, re.DOTALL)
    if not py_match and command.strip().startswith("python3 -c "):
        # Also handle unquoted or heredoc-style python -c
        py_match = re.match(r"""^(python3?)\s+-c\s+(.)(.*)\2""", command, re.DOTALL)
    if py_match:
        python_bin = py_match.group(1)
        code = py_match.group(3)
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", dir=workspace,
                                          delete=False, prefix="_exec_") as f:
            f.write(code)
            tmp_path = f.name
        try:
            result = subprocess.run(
                [python_bin, tmp_path],
                cwd=workspace, capture_output=True, text=True, timeout=120,
            )
        finally:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
    else:
        result = subprocess.run(
            ["sh", "-c", command],
            cwd=workspace, capture_output=True, text=True, timeout=120,
        )
    output = ""
    if result.stdout:
        output += result.stdout
    if result.stderr:
        if output:
            output += "\n"
        output += f"STDERR:\n{result.stderr}"
    return output, result.returncode

def main():
    params = json.load(sys.stdin)
    workspace = os.environ.get("WORKSPACE", ".")

    commands = params.get("commands", [])
    if not commands:
        cmd = params.get("command", "")
        if cmd:
            commands = [cmd]

    if not commands:
        print("Error: missing 'command' or 'commands' parameter", file=sys.stderr)
        sys.exit(1)

    output_parts = []
    for i, cmd in enumerate(commands):
        step_output, exit_code = run_one(cmd, workspace)
        if len(commands) > 1:
            output_parts.append(f"[step {i+1}/{len(commands)}] {cmd[:80]}")
        if step_output.strip():
            output_parts.append(step_output)
        if exit_code != 0:
            output_parts.append(f"[step {i+1} failed with exit code {exit_code} — stopping]")
            break

    output = "\n".join(output_parts)
    if not output.strip():
        output = f"[{len(commands)} step(s) completed, no output]"

    if len(output) > MAX_RESULT_CHARS:
        output = output[:MAX_RESULT_CHARS] + "\n... [truncated]"

    print(output)

if __name__ == "__main__":
    main()
