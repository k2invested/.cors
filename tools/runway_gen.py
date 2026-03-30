#!/usr/bin/env python3
"""runway_gen — generate video clips using Runway Gen-4/4.5.

Actions:
  {"action": "scene", "prompt": "...", "motion": "...", "ratio": "720:1280"}
    → Two-step: text→image (gen4_image) then image→video (gen4_turbo)
  {"action": "scene_direct", "prompt": "...", "ratio": "720:1280"}
    → Single-step: text→video (gen4.5) — higher quality, simpler
  {"action": "text_to_image", "prompt": "...", "ratio": "1080:1920"}
  {"action": "image_to_video", "prompt_image": "<url>", "prompt": "...", "ratio": "720:1280"}
  {"action": "text_to_video", "prompt": "...", "ratio": "720:1280", "duration": 8}
    → Direct text-to-video via gen4.5
  {"action": "character", "character_uri": "<image or video url>", "character_type": "image|video",
   "reference_uri": "<video url>", "ratio": "720:1280"}
    → Character performance: animate a character from reference video
  {"action": "world_create", "name": "...", "content": "..."}
    → Create a world-building document for style consistency
  {"action": "world_list"}
    → List existing world documents
  {"action": "status", "id": "<task id>"}

Env: RUNWAYML_API_SECRET or RUNWAY_API_KEY
"""
import json
import os
import sys
import time
from pathlib import Path

from dotenv import load_dotenv
env_path = Path(__file__).resolve().parent.parent.parent.parent / ".env"
if env_path.exists():
    load_dotenv(env_path)


def get_client():
    from runwayml import RunwayML
    api_key = os.environ.get("RUNWAYML_API_SECRET") or os.environ.get("RUNWAY_API_KEY")
    if not api_key:
        print("Error: RUNWAYML_API_SECRET or RUNWAY_API_KEY not set", file=sys.stderr)
        sys.exit(1)
    return RunwayML(api_key=api_key)


def poll_task(client, task_id, max_polls=120, interval=5, label="task"):
    """Poll a Runway task until completion."""
    for _ in range(max_polls):
        time.sleep(interval)
        status = client.tasks.retrieve(task_id)
        if hasattr(status, 'status'):
            if status.status == 'SUCCEEDED':
                output = status.output
                if hasattr(output, 'url'):
                    return {"id": task_id, "status": "done", "url": output.url}
                elif isinstance(output, list) and output:
                    return {"id": task_id, "status": "done", "url": output[0]}
                return {"id": task_id, "status": "done", "output": str(output)}
            elif status.status == 'FAILED':
                failure = str(getattr(status, 'failure', 'unknown'))
                print(f"  [{label}] FAILED: {failure}", file=sys.stderr)
                return {"id": task_id, "status": "failed", "error": failure}
            print(f"  status: {status.status}...", file=sys.stderr)
        else:
            print(f"  polling... {status}", file=sys.stderr)
    return {"id": task_id, "status": "timeout"}


def normalize_video_ratio(ratio: str) -> str:
    """Map ratio to valid gen4_turbo/gen4.5 video ratios."""
    VALID = {"1280:720", "720:1280", "1104:832", "832:1104", "960:960", "1584:672"}
    if ratio in VALID:
        return ratio
    w, h = ratio.split(":")
    return "720:1280" if int(h) > int(w) else "1280:720" if int(w) > int(h) else "960:960"


def text_to_image(prompt: str, ratio: str = "1080:1920") -> dict:
    """Generate an image from a text prompt."""
    client = get_client()
    result = client.text_to_image.create(
        model="gen4_image",
        prompt_text=prompt,
        ratio=ratio,
    )
    task_id = result.id
    print(f"Text-to-image task: {task_id}", file=sys.stderr)
    return poll_task(client, task_id, max_polls=60, label="t2i")


def image_to_video(prompt_image: str, prompt: str = "", ratio: str = "1080:1920") -> dict:
    """Generate a video clip from an image."""
    ratio = normalize_video_ratio(ratio)
    client = get_client()
    result = client.image_to_video.create(
        model="gen4_turbo",
        prompt_image=prompt_image,
        prompt_text=prompt,
        ratio=ratio,
    )
    task_id = result.id
    print(f"Image-to-video task: {task_id}", file=sys.stderr)
    return poll_task(client, task_id, max_polls=120, label="i2v")


def text_to_video(prompt: str, ratio: str = "720:1280", duration: int = 8) -> dict:
    """Direct text-to-video via gen4.5 — single step, higher quality."""
    ratio = normalize_video_ratio(ratio)
    client = get_client()
    result = client.text_to_video.create(
        model="gen4.5",
        prompt_text=prompt,
        ratio=ratio,
        duration=duration,
    )
    task_id = result.id
    print(f"Text-to-video task: {task_id}", file=sys.stderr)
    return poll_task(client, task_id, max_polls=120, label="t2v")


def character_performance(character_uri: str, character_type: str,
                          reference_uri: str, ratio: str = "720:1280") -> dict:
    """Animate a character using reference video performance."""
    ratio = normalize_video_ratio(ratio)
    client = get_client()
    result = client.character_performance.create(
        model="act_two",
        character={"type": character_type, "uri": character_uri},
        reference={"type": "video", "uri": reference_uri},
        ratio=ratio,
    )
    task_id = result.id
    print(f"Character performance task: {task_id}", file=sys.stderr)
    return poll_task(client, task_id, max_polls=120, label="char")


def world_create(name: str, content: str) -> dict:
    """Create a world-building document for style/character consistency."""
    client = get_client()
    result = client.documents.create(name=name, content=content)
    return {"id": result.id, "name": name, "status": "created"}


def world_list() -> dict:
    """List existing world-building documents."""
    client = get_client()
    docs = client.documents.list()
    items = []
    for d in docs:
        items.append({"id": d.id, "name": d.name})
    return {"documents": items}


def generate_scene(prompt: str, motion: str = "", ratio: str = "1080:1920") -> dict:
    """Full scene generation: text → image → video (gen4 pipeline)."""
    print(f"Scene: {prompt[:80]}", file=sys.stderr)
    print("Step 1: generating key frame...", file=sys.stderr)
    img_result = text_to_image(prompt, ratio)
    if img_result.get("status") != "done":
        return {"error": f"image generation failed: {img_result}"}

    image_url = img_result.get("url", "")
    print(f"Step 2: animating ({motion[:60] if motion else 'default motion'})...", file=sys.stderr)
    vid_result = image_to_video(image_url, motion or prompt, ratio)
    return vid_result


def generate_scene_direct(prompt: str, ratio: str = "720:1280", duration: int = 8) -> dict:
    """Single-step scene generation via gen4.5 text-to-video."""
    print(f"Scene (direct): {prompt[:80]}", file=sys.stderr)
    return text_to_video(prompt, ratio, duration)


def main():
    params = json.load(sys.stdin)
    action = params.get("action", "scene")
    ratio = params.get("ratio", "1080:1920")

    if action == "text_to_image":
        result = text_to_image(params.get("prompt", ""), ratio)
    elif action == "image_to_video":
        result = image_to_video(
            params.get("prompt_image", ""),
            params.get("prompt", ""),
            ratio,
        )
    elif action == "text_to_video":
        result = text_to_video(
            params.get("prompt", ""),
            ratio,
            params.get("duration", 8),
        )
    elif action == "scene":
        result = generate_scene(
            params.get("prompt", ""),
            params.get("motion", ""),
            ratio,
        )
    elif action == "scene_direct":
        result = generate_scene_direct(
            params.get("prompt", ""),
            ratio,
            params.get("duration", 8),
        )
    elif action == "character":
        result = character_performance(
            params.get("character_uri", ""),
            params.get("character_type", "image"),
            params.get("reference_uri", ""),
            ratio,
        )
    elif action == "world_create":
        result = world_create(
            params.get("name", ""),
            params.get("content", ""),
        )
    elif action == "world_list":
        result = world_list()
    elif action == "status":
        client = get_client()
        status = client.tasks.retrieve(params.get("id", ""))
        result = {"status": str(getattr(status, 'status', 'unknown'))}
        if hasattr(status, 'output') and hasattr(status.output, 'url'):
            result["url"] = status.output.url
    else:
        print(f"Error: unknown action '{action}'", file=sys.stderr)
        sys.exit(1)

    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
