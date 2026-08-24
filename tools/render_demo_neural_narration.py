#!/usr/bin/env python3
"""Render scene narration with a selected Microsoft neural voice.

This optional production helper uses the online Edge speech endpoint. The
submitted CodeFellow model and its measured inference path remain fully local.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import subprocess
from pathlib import Path

import edge_tts


async def render_segment(
    text: str,
    voice: str,
    rate: str,
    volume: str,
    pitch: str,
    mp3_path: Path,
) -> None:
    speech = edge_tts.Communicate(
        text=text,
        voice=voice,
        rate=rate,
        volume=volume,
        pitch=pitch,
    )
    await speech.save(str(mp3_path))


async def main_async(args: argparse.Namespace) -> int:
    segments = json.loads(args.segments.read_text(encoding="utf-8"))
    args.output_directory.mkdir(parents=True, exist_ok=True)

    for index, segment in enumerate(segments, start=1):
        stem = f"{index:02d}-{segment['kind']}"
        mp3_path = args.output_directory / f"{stem}.mp3"
        wav_path = args.output_directory / f"{stem}.wav"
        await render_segment(
            segment["narration"],
            args.voice,
            args.rate,
            args.volume,
            args.pitch,
            mp3_path,
        )
        subprocess.run(
            [
                str(args.ffmpeg),
                "-y",
                "-hide_banner",
                "-loglevel",
                "error",
                "-i",
                str(mp3_path),
                "-ac",
                "1",
                "-ar",
                "24000",
                "-c:a",
                "pcm_s16le",
                str(wav_path),
            ],
            check=True,
        )
        print(f"rendered {stem} with {args.voice}", flush=True)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--segments", type=Path, required=True)
    parser.add_argument("--output-directory", type=Path, required=True)
    parser.add_argument("--ffmpeg", type=Path, required=True)
    parser.add_argument("--voice", default="en-ZA-LeahNeural")
    parser.add_argument("--rate", default="+5%")
    parser.add_argument("--volume", default="+0%")
    parser.add_argument("--pitch", default="+0Hz")
    return asyncio.run(main_async(parser.parse_args()))


if __name__ == "__main__":
    raise SystemExit(main())
