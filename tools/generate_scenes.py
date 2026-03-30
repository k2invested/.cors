#!/usr/bin/env python3
"""generate_scenes — batch generate video clips via Runway Gen-4/4.5.

Anchor-frame pipeline for visual continuity:
  1. Generate ONE anchor image from the visual bible (character + environment + style)
  2. For each scene, animate that SAME anchor image with different motion/action prompts

Input JSON:
{
  "anchor_prompt": "canonical frame: 28-year-old man with short dark hair, stubble, grey hoodie,
                     dim apartment bedroom, single monitor glow, cold blue tones, shallow DOF",
  "anchor_ratio": "1080:1920",
  "scenes": [
    {"id": "scene_01", "prompt": "slow zoom into face, expression shifts from neutral to tense", "duration": 8},
    {"id": "scene_02", "prompt": "pulls phone from pocket, screen illuminates face", "duration": 6}
  ],
  "output_dir": "assets"
}

If no anchor_prompt is provided, falls back to independent scene_direct generation.

Env: RUNWAYML_API_SECRET or RUNWAY_API_KEY
"""
import json
import os
import subprocess
import sys
import concurrent.futures
from pathlib import Path

from dotenv import load_dotenv
env_path = Path(__file__).resolve().parent.parent.parent.parent / ".env"
if env_path.exists():
    load_dotenv(env_path)

TOOLS_DIR = os.path.dirname(os.path.abspath(__file__))


def call_runway(payload: dict) -> dict:
    """Call runway_gen.py with a JSON payload, return parsed result."""
    result = subprocess.run(
        [sys.executable, os.path.join(TOOLS_DIR, "runway_gen.py")],
        input=json.dumps(payload),
        text=True,
        capture_output=True,
        timeout=900,
    )
    # Surface errors
    if result.stderr:
        err_lines = [l for l in result.stderr.split('\n') if 'dotenv' not in l and l.strip()]
        if err_lines:
            print(f"  stderr: {' '.join(err_lines)[:500]}", file=sys.stderr)
    if result.returncode != 0:
        print(f"  exit code: {result.returncode}", file=sys.stderr)

    # Parse JSON output
    output = result.stdout.strip()
    try:
        data = json.loads(output[output.rfind("{"):])
        return data
    except (json.JSONDecodeError, ValueError):
        pass

    # Fallback: search for URL
    import re
    url_match = re.search(r'"url":\s*"(https://[^"]+)"', output)
    if url_match:
        return {"url": url_match.group(1), "status": "done"}
    return {"error": f"no parseable output: {output[:200]}"}


def download_clip(url: str, clip_path: str) -> dict:
    """Download a clip from URL to local path."""
    try:
        subprocess.run(["curl", "-s", "-o", clip_path, url], check=True, timeout=120)
        if os.path.isfile(clip_path):
            size = os.path.getsize(clip_path)
            return {"path": clip_path, "size": size}
    except Exception as e:
        return {"error": f"download failed: {e}"}
    return {"error": "download failed"}


def generate_anchor_image(anchor_prompt: str, ratio: str = "1080:1920", output_dir: str = "assets", anchor_id: str = "anchor") -> str:
    """Generate the canonical anchor image. Downloads locally and re-uploads as ephemeral.
    Returns a stable URI that won't expire during scene animation."""
    print(f"[anchor] generating canonical frame...")
    print(f"[anchor] prompt: {anchor_prompt[:120]}")
    result = call_runway({
        "action": "text_to_image",
        "prompt": anchor_prompt,
        "ratio": ratio,
    })
    if result.get("status") != "done" or not result.get("url"):
        error = result.get("error", "unknown")
        print(f"[anchor] FAILED: {error}")
        raise RuntimeError(f"anchor image generation failed: {error}")

    temp_url = result["url"]
    print(f"[anchor] generated — downloading locally...")

    # Download anchor image locally (JWT URLs expire quickly)
    local_path = os.path.join(output_dir, f"{anchor_id}_frame.png")
    dl = download_clip(temp_url, local_path)
    if "error" in dl:
        print(f"[anchor] download failed: {dl['error']}")
        raise RuntimeError(f"anchor download failed: {dl['error']}")
    print(f"[anchor] saved locally: {local_path} ({dl['size']:,} bytes)")

    # Re-upload as ephemeral to get a stable URI for image_to_video
    print(f"[anchor] uploading as ephemeral for animation...")
    try:
        from runwayml import RunwayML
        api_key = os.environ.get("RUNWAYML_API_SECRET") or os.environ.get("RUNWAY_API_KEY")
        client = RunwayML(api_key=api_key)
        with open(local_path, "rb") as f:
            upload = client.uploads.create_ephemeral(file=f)
        stable_uri = getattr(upload, 'uri', None) or getattr(upload, 'url', None) or str(upload)
        print(f"[anchor] ephemeral URI: {stable_uri[:80]}...")
        return stable_uri
    except Exception as e:
        print(f"[anchor] ephemeral upload failed: {e} — falling back to temp URL")
        return temp_url


def generate_scene_from_anchor(scene: dict, anchor_url: str, output_dir: str) -> dict:
    """Animate the anchor image with scene-specific motion/action."""
    scene_id = scene.get("id", "scene")
    prompt = scene.get("prompt", "")
    print(f"[{scene_id}] animating anchor frame...")

    result = call_runway({
        "action": "image_to_video",
        "prompt_image": anchor_url,
        "prompt": prompt,
        "ratio": scene.get("ratio", "720:1280"),
    })

    if result.get("url"):
        clip_path = os.path.join(output_dir, f"{scene_id}.mp4")
        print(f"[{scene_id}] downloading → {clip_path}")
        dl = download_clip(result["url"], clip_path)
        if "path" in dl:
            print(f"[{scene_id}] done ({dl['size']:,} bytes)")
            return {"id": scene_id, "path": dl["path"], "size": dl["size"]}
        else:
            return {"id": scene_id, "error": dl["error"]}
    else:
        error = result.get("error", "no URL returned")
        print(f"[{scene_id}] FAILED: {error}")
        return {"id": scene_id, "error": error}


def generate_scene_direct(scene: dict, output_dir: str) -> dict:
    """Fallback: independent text-to-video per scene (no anchor)."""
    scene_id = scene.get("id", "scene")
    print(f"[{scene_id}] generating (direct, no anchor)...")

    result = call_runway({
        "action": "scene_direct",
        "prompt": scene.get("prompt", ""),
        "ratio": scene.get("ratio", "720:1280"),
        "duration": scene.get("duration", 8),
    })

    if result.get("url"):
        clip_path = os.path.join(output_dir, f"{scene_id}.mp4")
        print(f"[{scene_id}] downloading → {clip_path}")
        dl = download_clip(result["url"], clip_path)
        if "path" in dl:
            print(f"[{scene_id}] done ({dl['size']:,} bytes)")
            return {"id": scene_id, "path": dl["path"], "size": dl["size"]}
        else:
            return {"id": scene_id, "error": dl["error"]}
    else:
        error = result.get("error", "no URL returned")
        print(f"[{scene_id}] FAILED: {error}")
        return {"id": scene_id, "error": error}


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=str, help="JSON config file path")
    args, _ = parser.parse_known_args()

    if args.input:
        params = json.load(open(args.input))
    else:
        params = json.load(sys.stdin)

    scenes = params.get("scenes", [])
    output_dir = params.get("output_dir", "assets")
    anchor_ratio = params.get("anchor_ratio", "1080:1920")

    # Support both single anchor (legacy) and multi-anchor (new)
    anchors = params.get("anchors", [])
    legacy_anchor = params.get("anchor_prompt", "")
    if legacy_anchor and not anchors:
        anchors = [{"id": "anchor_01", "prompt": legacy_anchor}]

    if not scenes:
        print("Error: no scenes provided", file=sys.stderr)
        sys.exit(1)

    os.makedirs(output_dir, exist_ok=True)

    # Generate all anchor images first (sequentially — they're the foundation)
    anchor_urls = {}
    if anchors:
        print(f"[anchors] generating {len(anchors)} anchor image(s)...")
        for anchor in anchors:
            aid = anchor.get("id", "anchor_01")
            prompt = anchor.get("prompt", "")
            try:
                url = generate_anchor_image(prompt, anchor_ratio, output_dir, aid)
                anchor_urls[aid] = url
                print(f"[{aid}] done")
            except RuntimeError as e:
                print(f"[{aid}] FAILED: {e} — scenes using this anchor will fall back to direct")

    print(f"Generating {len(scenes)} scenes → {output_dir}/")
    if anchor_urls:
        print(f"[mode] anchor-frame — {len(anchor_urls)} anchor(s), scenes animate their assigned anchor")
    else:
        print(f"[mode] direct — each clip generated independently")

    # Parallel generation — each scene uses its assigned anchor or falls back to direct
    def generate_one(scene):
        scene_anchor = scene.get("anchor", "anchor_01")
        if scene_anchor in anchor_urls:
            return generate_scene_from_anchor(scene, anchor_urls[scene_anchor], output_dir)
        else:
            return generate_scene_direct(scene, output_dir)

    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
        futures = {executor.submit(generate_one, scene): scene for scene in scenes}
        results = []
        for future in concurrent.futures.as_completed(futures):
            results.append(future.result())

    # Summary
    success = [r for r in results if "path" in r]
    failed = [r for r in results if "error" in r]
    print(f"\nDone: {len(success)} clips generated, {len(failed)} failed")
    for r in success:
        print(f"  ✓ {r['id']}: {r['path']} ({r['size']:,} bytes)")
    for r in failed:
        print(f"  ✗ {r['id']}: {r['error']}")


if __name__ == "__main__":
    main()
