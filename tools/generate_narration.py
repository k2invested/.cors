#!/usr/bin/env python3
"""generate_narration — generate TTS narration audio via OpenAI.

Input JSON:
{
  "text": "<full narration text>",
  "output": "assets/narration.mp3",
  "voice": "onyx",
  "model": "tts-1-hd"
}

Env: OPENAI_API_KEY
"""
TOOL_DESC = 'generate TTS narration audio via OpenAI.'
TOOL_MODE = 'mutate'
TOOL_SCOPE = 'external'
TOOL_POST_OBSERVE = 'artifacts'
TOOL_ARTIFACT_PARAMS = ['output']

import json
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
env_path = Path(__file__).resolve().parent.parent.parent.parent / ".env"
if env_path.exists():
    load_dotenv(env_path)


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=str, help="JSON config file path")
    args, _ = parser.parse_known_args()

    if args.input:
        params = json.load(open(args.input))
    else:
        params = json.load(sys.stdin)
    text = params.get("text", "")
    output = params.get("output", "assets/narration.mp3")
    voice = params.get("voice", "onyx")
    model = params.get("model", "tts-1-hd")

    if not text:
        print("Error: missing 'text' parameter", file=sys.stderr)
        sys.exit(1)

    os.makedirs(os.path.dirname(output) or ".", exist_ok=True)

    from openai import OpenAI
    client = OpenAI()
    response = client.audio.speech.create(
        model=model,
        voice=voice,
        input=text,
    )
    response.write_to_file(output)

    size = os.path.getsize(output)
    print(f"Narration saved: {output} ({size:,} bytes, {len(text)} chars, voice={voice})")


if __name__ == "__main__":
    main()
