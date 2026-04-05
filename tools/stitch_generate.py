#!/usr/bin/env python3
"""stitch_generate — Generate UI designs via Google Stitch SDK.

Takes a natural language UI description, generates HTML + Tailwind CSS
via the Stitch SDK, downloads the output.

Input (stdin JSON):
{
  "prompt": "A mobile-first dashboard showing step chains as a tree",
  "device": "MOBILE | DESKTOP | TABLET | AGNOSTIC",
  "project": "project_name (optional, creates new if omitted)",
  "variant_mode": "REFINE | EXPLORE | REIMAGINE (optional, for iterations)"
}

Output: Generated HTML content + screenshot path, or error.

Requires:
  npm install @google/stitch-sdk
  STITCH_API_KEY env var (from stitch.withgoogle.com settings)
"""
TOOL_DESC = 'Generate UI designs via Google Stitch SDK.'
TOOL_MODE = 'mutate'
TOOL_SCOPE = 'external'
TOOL_POST_OBSERVE = 'artifacts'
TOOL_DEFAULT_ARTIFACTS = ['ui_output/']


import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

CORS_ROOT = str(Path(__file__).resolve().parent.parent)
OUTPUT_DIR = os.path.join(CORS_ROOT, "ui_output")


def ensure_sdk():
    """Check if Stitch SDK is available."""
    result = subprocess.run(
        ["node", "-e", "require('@google/stitch-sdk')"],
        capture_output=True, text=True,
    )
    return result.returncode == 0


def generate(prompt: str, device: str = "MOBILE", project: str = None,
             variant_mode: str = None) -> dict:
    """Call Stitch SDK via Node.js subprocess."""

    api_key = os.environ.get("STITCH_API_KEY")
    if not api_key:
        return {"error": "STITCH_API_KEY not set"}

    # Build the Node.js script
    project_line = f'const project = await client.projects.create("{project or "cors_ui"}");'
    variant_line = ""
    if variant_mode:
        variant_line = f"""
    const variants = await screen.variants({{
        creativeRange: "{variant_mode}"
    }});
    const variantHtml = await variants[0].html();
    result.variant_html = variantHtml;
"""

    node_script = f"""
const {{ StitchClient }} = require('@google/stitch-sdk');

async function main() {{
    const client = new StitchClient({{ apiKey: "{api_key}" }});
    {project_line}
    const screen = await project.generate("{prompt}", {{
        deviceType: "{device}"
    }});

    const html = await screen.html();
    const screenshot = await screen.screenshot();

    const result = {{
        html: html,
        screenshot_url: screenshot,
        screen_id: screen.id,
        project_id: project.id,
    }};

    {variant_line}

    console.log(JSON.stringify(result));
}}

main().catch(e => {{
    console.error(JSON.stringify({{ error: e.message }}));
    process.exit(1);
}});
"""

    # Write temp script
    with tempfile.NamedTemporaryFile(mode="w", suffix=".js", delete=False) as f:
        f.write(node_script)
        script_path = f.name

    try:
        result = subprocess.run(
            ["node", script_path],
            capture_output=True, text=True,
            timeout=60,
            cwd=CORS_ROOT,
        )

        if result.returncode != 0:
            error = result.stderr.strip()
            try:
                return json.loads(error)
            except json.JSONDecodeError:
                return {"error": error or "Stitch generation failed"}

        output = json.loads(result.stdout.strip())

        # Save HTML to output directory
        os.makedirs(OUTPUT_DIR, exist_ok=True)
        html_path = os.path.join(OUTPUT_DIR, f"{project or 'cors_ui'}.html")
        with open(html_path, "w") as f:
            f.write(output.get("html", ""))
        output["html_path"] = html_path

        return output

    finally:
        os.unlink(script_path)


def main():
    try:
        params = json.load(sys.stdin)
    except json.JSONDecodeError as e:
        print(f"Error: invalid JSON — {e}")
        sys.exit(1)

    prompt = params.get("prompt", "")
    if not prompt:
        print("Error: missing 'prompt'")
        sys.exit(1)

    device = params.get("device", "MOBILE")
    project = params.get("project")
    variant_mode = params.get("variant_mode")

    if not ensure_sdk():
        print("Error: @google/stitch-sdk not installed. Run: npm install @google/stitch-sdk")
        sys.exit(1)

    result = generate(prompt, device, project, variant_mode)

    if "error" in result:
        print(f"Error: {result['error']}")
        sys.exit(1)

    print(f"Generated: {result.get('html_path', 'unknown')}")
    print(f"Screen: {result.get('screen_id', 'unknown')}")
    print(f"Project: {result.get('project_id', 'unknown')}")
    if result.get("variant_html"):
        print(f"Variant generated ({variant_mode})")

    # Output full HTML for the session to see
    html = result.get("html", "")
    if len(html) > 2000:
        print(f"\nHTML preview ({len(html)} chars):\n{html[:2000]}...")
    else:
        print(f"\nHTML:\n{html}")


if __name__ == "__main__":
    main()
