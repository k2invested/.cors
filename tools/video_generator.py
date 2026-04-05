#!/usr/bin/env python3
"""YouTube Shorts video generator with narration, captions, and simple editing.

Requirements:
    pip install moviepy pillow
    ffmpeg available on PATH

Usage:
    python principle/video_generator.py --input job.json

Integration:
    from video_generator import generate_short_video
    generate_short_video(config_dict)

Job schema example:
{
  "output_path": "out/short.mp4",
  "narration_audio": "assets/narration.mp3",
  "clips": [
    {"path": "assets/clip1.mp4", "start": 0, "end": 4.2},
    {"path": "assets/image1.jpg", "duration": 3.0},
    {"path": "assets/clip2.mp4", "duration": 5.0}
  ],
  "captions": [
    {"start": 0.0, "end": 2.5, "text": "First caption"},
    {"start": 2.5, "end": 5.0, "text": "Second caption"}
  ],
  "settings": {
    "width": 1080,
    "height": 1920,
    "fps": 30,
    "font": "Arial-Bold",
    "font_size": 64,
    "caption_color": "white",
    "caption_stroke_color": "black",
    "caption_stroke_width": 3,
    "transition_duration": 0.2,
    "background_color": [0, 0, 0],
    "audio_fade_out": 0.4,
    "music_path": null,
    "music_volume": 0.12,
    "output_codec": "libx264",
    "audio_codec": "aac"
  }
}
"""
from __future__ import annotations
TOOL_DESC = 'YouTube Shorts video generator with narration, captions, and simple editing.'
TOOL_MODE = 'mutate'
TOOL_SCOPE = 'workspace'
TOOL_POST_OBSERVE = 'artifacts'
TOOL_ARTIFACT_PARAMS = ['output_path']

import argparse
import json
import math
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

from moviepy.audio.fx.AudioLoop import AudioLoop
from moviepy.audio.fx.MultiplyVolume import MultiplyVolume
from moviepy.audio.fx.AudioFadeOut import AudioFadeOut
from moviepy.video.VideoClip import ColorClip, ImageClip, TextClip
from moviepy.video.compositing.CompositeVideoClip import CompositeVideoClip
from moviepy.video.compositing.concatenate import concatenate_videoclips
from moviepy.video.io.VideoFileClip import VideoFileClip
from moviepy.audio.io.AudioFileClip import AudioFileClip
from moviepy.audio.AudioClip import CompositeAudioClip


DEFAULT_SETTINGS: Dict[str, Any] = {
    "width": 1080,
    "height": 1920,
    "fps": 30,
    "font": "Arial-Bold",
    "font_size": 64,
    "caption_color": "white",
    "caption_stroke_color": "black",
    "caption_stroke_width": 3,
    "caption_bottom_margin": 180,
    "caption_max_width_ratio": 0.86,
    "transition_duration": 0.2,
    "background_color": [0, 0, 0],
    "audio_fade_out": 0.4,
    "music_path": None,
    "music_volume": 0.12,
    "output_codec": "libx264",
    "audio_codec": "aac",
    "preset": "medium",
    "crf": 18,
    "threads": 4
}

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}
VIDEO_EXTENSIONS = {".mp4", ".mov", ".mkv", ".avi", ".webm", ".m4v"}


class VideoGeneratorError(Exception):
    pass


def _merge_settings(config: Dict[str, Any]) -> Dict[str, Any]:
    settings = dict(DEFAULT_SETTINGS)
    settings.update(config.get("settings", {}))
    return settings


def _ensure_exists(path: str) -> None:
    if not path or not Path(path).exists():
        raise VideoGeneratorError(f"Missing file: {path}")


def _fit_clip_to_vertical(clip, width: int, height: int, bg_color: List[int]):
    scale = max(width / clip.w, height / clip.h)
    resized = clip.resized(scale)
    x1 = max(0, (resized.w - width) / 2)
    y1 = max(0, (resized.h - height) / 2)
    cropped = resized.cropped(x1=x1, y1=y1, width=width, height=height)
    bg = ColorClip(size=(width, height), color=tuple(bg_color), duration=cropped.duration)
    return CompositeVideoClip([bg, cropped.with_position("center")], size=(width, height)).with_duration(cropped.duration)


def _load_visual_clip(item: Dict[str, Any], settings: Dict[str, Any]):
    path = item.get("path")
    _ensure_exists(path)
    ext = Path(path).suffix.lower()

    start = item.get("start", 0)
    end = item.get("end")
    duration = item.get("duration")

    if ext in VIDEO_EXTENSIONS:
        clip = VideoFileClip(path)
        if end is not None:
            clip = clip.subclipped(start_time=start, end_time=end)
        elif duration is not None:
            clip = clip.subclipped(start_time=start, end_time=start + duration)
        elif start:
            clip = clip.subclipped(start_time=start)
    elif ext in IMAGE_EXTENSIONS:
        if duration is None:
            raise VideoGeneratorError(f"Image clip requires duration: {path}")
        clip = ImageClip(path, duration=duration)
    else:
        raise VideoGeneratorError(f"Unsupported media type: {path}")

    fitted = _fit_clip_to_vertical(
        clip,
        settings["width"],
        settings["height"],
        settings["background_color"]
    )
    return fitted.with_fps(settings["fps"])


def _build_timeline(clips_config: List[Dict[str, Any]], settings: Dict[str, Any]):
    if not clips_config:
        raise VideoGeneratorError("No clips provided")

    clips = [_load_visual_clip(item, settings) for item in clips_config]
    transition = max(0.0, float(settings.get("transition_duration", 0)))

    if transition > 0 and len(clips) > 1:
        processed = [clips[0]]
        for clip in clips[1:]:
            processed.append(clip.with_effects([]).with_start(0).crossfadein(transition))
        timeline = concatenate_videoclips(processed, method="compose", padding=-transition)
    else:
        timeline = concatenate_videoclips(clips, method="compose")

    return timeline


def _wrap_caption_text(text: str, max_chars: int = 28) -> str:
    words = text.split()
    if not words:
        return ""
    lines = []
    current = words[0]
    for word in words[1:]:
        if len(current) + 1 + len(word) <= max_chars:
            current += " " + word
        else:
            lines.append(current)
            current = word
    lines.append(current)
    return "\n".join(lines)


def _build_caption_layers(captions: List[Dict[str, Any]], settings: Dict[str, Any]):
    layers = []
    max_width = int(settings["width"] * settings["caption_max_width_ratio"])
    bottom_margin = int(settings["caption_bottom_margin"])

    for cap in captions:
        text = _wrap_caption_text(str(cap.get("text", "")).strip())
        if not text:
            continue
        start = float(cap.get("start", 0))
        end = float(cap.get("end", start + 1.5))
        if end <= start:
            continue

        txt = TextClip(
            text=text,
            font=settings["font"],
            font_size=int(settings["font_size"]),
            color=settings["caption_color"],
            stroke_color=settings["caption_stroke_color"],
            stroke_width=int(settings["caption_stroke_width"]),
            method="caption",
            size=(max_width, None),
            text_align="center"
        )
        txt = txt.with_start(start).with_end(end).with_position(("center", settings["height"] - bottom_margin - txt.h))
        layers.append(txt)
    return layers


def _build_audio(config: Dict[str, Any], video_duration: float, settings: Dict[str, Any]):
    narration_path = config.get("narration_audio")
    if not narration_path:
        raise VideoGeneratorError("narration_audio is required")
    _ensure_exists(narration_path)

    narration = AudioFileClip(narration_path)
    if narration.duration > video_duration:
        video_duration = narration.duration

    tracks = [narration]

    music_path = settings.get("music_path")
    if music_path:
        _ensure_exists(music_path)
        music = AudioFileClip(music_path)
        loops = max(1, math.ceil(video_duration / max(music.duration, 0.1)))
        if loops > 1:
            music = music.with_effects([AudioLoop(duration=video_duration)])
        else:
            music = music.subclipped(0, min(music.duration, video_duration))
        music = music.with_effects([MultiplyVolume(float(settings["music_volume"]))])
        tracks.append(music)

    mixed = CompositeAudioClip(tracks)
    fade = float(settings.get("audio_fade_out", 0))
    if fade > 0:
        mixed = mixed.with_effects([AudioFadeOut(fade)])
    return mixed, video_duration


def generate_short_video(config: Dict[str, Any]) -> str:
    settings = _merge_settings(config)
    output_path = config.get("output_path")
    if not output_path:
        raise VideoGeneratorError("output_path is required")

    Path(output_path).parent.mkdir(parents=True, exist_ok=True)

    base_video = _build_timeline(config.get("clips", []), settings)
    audio, final_duration = _build_audio(config, base_video.duration, settings)

    if base_video.duration < final_duration:
        last_frame = base_video.to_ImageClip(duration=final_duration - base_video.duration)
        last_frame = _fit_clip_to_vertical(last_frame, settings["width"], settings["height"], settings["background_color"])
        base_video = concatenate_videoclips([base_video, last_frame], method="compose")
    elif base_video.duration > final_duration:
        base_video = base_video.subclipped(0, final_duration)

    caption_layers = _build_caption_layers(config.get("captions", []), settings)
    final = CompositeVideoClip([base_video] + caption_layers, size=(settings["width"], settings["height"]))
    final = final.with_audio(audio).with_duration(final_duration).with_fps(int(settings["fps"]))

    final.write_videofile(
        output_path,
        fps=int(settings["fps"]),
        codec=settings["output_codec"],
        audio_codec=settings["audio_codec"],
        preset=settings["preset"],
        ffmpeg_params=["-crf", str(settings["crf"]), "-pix_fmt", "yuv420p"],
        threads=int(settings["threads"])
    )

    final.close()
    base_video.close()
    audio.close()
    return output_path


def _load_job(path: str) -> Dict[str, Any]:
    _ensure_exists(path)
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate YouTube Shorts videos with narration")
    parser.add_argument("--input", required=True, help="Path to job JSON file")
    args = parser.parse_args()

    config = _load_job(args.input)
    result = generate_short_video(config)
    print(f"Generated video: {result}")
    print("Default render settings: MP4 H.264, 1080x1920, 30fps")


if __name__ == "__main__":
    main()
