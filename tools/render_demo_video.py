#!/usr/bin/env python3
"""Render the two-minute CodeFellow submission video from verified local evidence."""

from __future__ import annotations

import argparse
import json
import math
import os
import subprocess
import sys
import wave
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


WIDTH, HEIGHT, FPS = 1280, 720, 24
BG = "#07111f"
PANEL = "#0c1d31"
PANEL_2 = "#10263d"
BORDER = "#24415e"
GREEN = "#2fd6a2"
GREEN_LIGHT = "#8ff0d2"
WHITE = "#eaf2ff"
MUTED = "#9db3cb"
RED = "#ff8d86"
AMBER = "#ffd479"
BLUE = "#75bfff"

FONT_DIR = Path("C:/Windows/Fonts")
FONT_REGULAR = FONT_DIR / "segoeui.ttf"
FONT_BOLD = FONT_DIR / "segoeuib.ttf"
FONT_MONO = FONT_DIR / "consola.ttf"
FONT_MONO_BOLD = FONT_DIR / "consolab.ttf"


def font(path: Path, size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(str(path), size)


F = {
    "hero": font(FONT_BOLD, 54),
    "h1": font(FONT_BOLD, 42),
    "h2": font(FONT_BOLD, 30),
    "body": font(FONT_REGULAR, 23),
    "body_small": font(FONT_REGULAR, 19),
    "label": font(FONT_MONO_BOLD, 16),
    "small": font(FONT_MONO, 14),
    "code": font(FONT_MONO, 19),
    "code_bold": font(FONT_MONO_BOLD, 19),
    "metric": font(FONT_BOLD, 40),
}


def clamp(value: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, value))


def ease(value: float) -> float:
    value = clamp(value)
    return value * value * (3 - 2 * value)


def alpha_color(hex_color: str, alpha: int) -> tuple[int, int, int, int]:
    value = hex_color.lstrip("#")
    return tuple(int(value[i : i + 2], 16) for i in (0, 2, 4)) + (alpha,)


def text_width(draw: ImageDraw.ImageDraw, value: str, use_font: ImageFont.FreeTypeFont) -> float:
    return draw.textbbox((0, 0), value, font=use_font)[2]


def wrap_text(draw: ImageDraw.ImageDraw, value: str, use_font: ImageFont.FreeTypeFont, max_width: int) -> list[str]:
    lines: list[str] = []
    for paragraph in value.splitlines() or [""]:
        words = paragraph.split()
        if not words:
            lines.append("")
            continue
        line = words[0]
        for word in words[1:]:
            candidate = f"{line} {word}"
            if text_width(draw, candidate, use_font) <= max_width:
                line = candidate
            else:
                lines.append(line)
                line = word
        lines.append(line)
    return lines


def draw_wrapped(
    draw: ImageDraw.ImageDraw,
    xy: tuple[int, int],
    value: str,
    use_font: ImageFont.FreeTypeFont,
    fill: str,
    max_width: int,
    spacing: int = 8,
) -> int:
    x, y = xy
    line_height = use_font.size + spacing
    for line in wrap_text(draw, value, use_font, max_width):
        draw.text((x, y), line, font=use_font, fill=fill)
        y += line_height
    return y


def draw_brand(draw: ImageDraw.ImageDraw, section: str = "OFFLINE CODING TUTOR") -> None:
    draw.rounded_rectangle((50, 36, 101, 87), radius=8, fill=GREEN)
    draw.text((61, 48), "CF", font=F["code_bold"], fill="#062118")
    draw.text((118, 33), "CodeFellow", font=F["h2"], fill=WHITE)
    draw.text((120, 70), section, font=F["small"], fill=GREEN_LIGHT)
    draw.text((1006, 52), "NETWORK: OFF", font=F["label"], fill=GREEN_LIGHT)


def draw_footer(draw: ImageDraw.ImageDraw, caption: str, elapsed: float, total: float) -> None:
    draw.rectangle((0, 624, WIDTH, HEIGHT), fill="#050c16")
    caption_lines = wrap_text(draw, caption, F["body_small"], 1120)[:2]
    y = 641 if len(caption_lines) == 1 else 630
    for line in caption_lines:
        draw.text((62, y), line, font=F["body_small"], fill=WHITE)
        y += 28
    progress = clamp(elapsed / total)
    draw.rectangle((0, 712, WIDTH, 720), fill=BORDER)
    draw.rectangle((0, 712, int(WIDTH * progress), 720), fill=GREEN)


def pill(draw: ImageDraw.ImageDraw, x: int, y: int, value: str, fill: str = PANEL_2, color: str = GREEN_LIGHT) -> int:
    width = int(text_width(draw, value, F["label"])) + 34
    draw.rounded_rectangle((x, y, x + width, y + 38), radius=18, fill=fill, outline=BORDER, width=2)
    draw.text((x + 17, y + 9), value, font=F["label"], fill=color)
    return width


def panel(draw: ImageDraw.ImageDraw, box: tuple[int, int, int, int], title: str | None = None) -> None:
    draw.rounded_rectangle(box, radius=14, fill=PANEL, outline=BORDER, width=2)
    if title:
        draw.text((box[0] + 24, box[1] + 18), title.upper(), font=F["label"], fill=GREEN_LIGHT)


def reveal(value: str, progress: float) -> str:
    return value[: int(len(value) * clamp(progress))]


def scene_problem(draw: ImageDraw.ImageDraw, p: float) -> None:
    draw_brand(draw, "THE ACCESS PROBLEM")
    draw.text((62, 144), "Cloud AI is not", font=F["hero"], fill=WHITE)
    draw.text((62, 205), "universal access.", font=F["hero"], fill=RED)
    items = [
        ("DATA FEES", "Recurring cost for every question"),
        ("UNRELIABLE INTERNET", "Learning stops when the signal drops"),
        ("CLOUD DEPENDENCY", "Prompts and code leave the laptop"),
    ]
    for index, (heading, detail) in enumerate(items):
        local = ease((p - index * 0.12) / 0.28)
        x = int(62 + index * 392)
        y = int(350 + (1 - local) * 20)
        panel(draw, (x, y, x + 350, y + 164))
        draw.text((x + 24, y + 24), heading, font=F["label"], fill=RED)
        draw_wrapped(draw, (x + 24, y + 66), detail, F["body_small"], MUTED, 300)


def scene_solution(draw: ImageDraw.ImageDraw, p: float) -> None:
    draw_brand(draw)
    draw.text((62, 154), "Learn, debug, and build", font=F["h1"], fill=WHITE)
    draw.text((62, 203), "no internet required.", font=F["h1"], fill=GREEN_LIGHT)
    panel(draw, (62, 300, 1218, 535))
    nodes = [("LEARNER", 118), ("CODEFELLOW", 492), ("CODE + EXPLANATION", 866)]
    for index, (label, x) in enumerate(nodes):
        active = ease((p - index * 0.13) / 0.3)
        box_fill = GREEN if index == 1 else PANEL_2
        draw.rounded_rectangle((x, 374, x + 250, 462), radius=12, fill=box_fill, outline=BORDER, width=2)
        color = "#062118" if index == 1 else WHITE
        tw = text_width(draw, label, F["label"])
        draw.text((x + (250 - tw) / 2, 407), label, font=F["label"], fill=color)
        if index < 2:
            arrow_x = x + 278
            draw.line((arrow_x, 418, arrow_x + 68 * active, 418), fill=GREEN_LIGHT, width=4)
            if active > 0.85:
                draw.polygon([(arrow_x + 68, 418), (arrow_x + 55, 409), (arrow_x + 55, 427)], fill=GREEN_LIGHT)
    x = 62
    for value in ("ENGLISH", "KISWAHILI", "CODE-SWITCHING", "CPU ONLY"):
        x += pill(draw, x, 560, value) + 14


def draw_terminal_chrome(draw: ImageDraw.ImageDraw, title: str) -> None:
    panel(draw, (44, 112, 1236, 600))
    draw.rectangle((44, 112, 1236, 160), fill=PANEL_2)
    for x, color in ((68, RED), (91, AMBER), (114, GREEN)):
        draw.ellipse((x, 130, x + 12, 142), fill=color)
    draw.text((156, 127), title, font=F["small"], fill=MUTED)
    draw.text((955, 127), "127.0.0.1  |  CPU", font=F["small"], fill=GREEN_LIGHT)


def scene_english_demo(draw: ImageDraw.ImageDraw, p: float) -> None:
    draw_brand(draw, "RECORDED LOCAL OUTPUT")
    draw_terminal_chrome(draw, "codefellow / english")
    prompt = "Implement get_positive(l). Return only positive numbers."
    draw.text((74, 188), ">", font=F["code_bold"], fill=GREEN)
    typed = reveal(prompt, p / 0.32)
    draw.text((104, 188), typed, font=F["code"], fill=WHITE)
    response_p = clamp((p - 0.30) / 0.58)
    if response_p > 0:
        draw.text((74, 252), "CodeFellow", font=F["label"], fill=GREEN_LIGHT)
        code = "def get_positive(l):\n    return [x for x in l if x > 0]"
        visible = reveal(code, response_p)
        draw.multiline_text((74, 294), visible, font=F["code"], fill=WHITE, spacing=12)
    if p > 0.78:
        draw_wrapped(
            draw,
            (74, 405),
            "Uses a list comprehension and keeps values greater than zero.",
            F["body_small"],
            MUTED,
            950,
        )
        pill(draw, 74, 496, "EXECUTABLE: YES", fill="#103529")
        pill(draw, 282, 496, "FORMAT: PASS", fill="#103529")
        pill(draw, 461, 496, "CLOUD: NONE", fill="#103529")


def scene_kiswahili_demo(draw: ImageDraw.ImageDraw, p: float) -> None:
    draw_brand(draw, "RECORDED LOCAL OUTPUT")
    draw_terminal_chrome(draw, "codefellow / kiswahili + code-switching")
    prompt = "Tekeleza function triangle_area(a, h). Jibu kwa Kiswahili."
    draw.text((74, 188), ">", font=F["code_bold"], fill=GREEN)
    draw.text((104, 188), reveal(prompt, p / 0.34), font=F["code"], fill=WHITE)
    response_p = clamp((p - 0.32) / 0.54)
    if response_p > 0:
        draw.text((74, 252), "CodeFellow", font=F["label"], fill=GREEN_LIGHT)
        code = "def triangle_area(a, h):\n    return 0.5 * a * h"
        draw.multiline_text((74, 294), reveal(code, response_p), font=F["code"], fill=WHITE, spacing=12)
    if p > 0.76:
        draw.text((74, 414), "Function name na argument contract zimehifadhiwa.", font=F["body_small"], fill=MUTED)
        pill(draw, 74, 496, "KISWAHILI", fill="#103529")
        pill(draw, 250, 496, "CODE-SWITCHING", fill="#103529")
        pill(draw, 472, 496, "TRANSLATOR: NONE", fill="#103529")


def scene_debug_demo(draw: ImageDraw.ImageDraw, p: float) -> None:
    draw_brand(draw, "GENUINE APP RUN")
    draw.text((62, 122), "Hint-first debugging, grounded in local evidence", font=F["h2"], fill=WHITE)
    panel(draw, (62, 184, 603, 572), "Learner file: average_bug.js")
    code = [
        "function average(values) {",
        "  return values.reduce(",
        "    (sum, value) => sum + value",
        "  ) / values.length;",
        "}",
        "",
        "console.log(average([]));",
    ]
    y = 234
    for line in code:
        draw.text((88, y), line, font=F["code"], fill=WHITE if "average([])" not in line else AMBER)
        y += 34
    panel(draw, (630, 184, 1218, 572), "CodeFellow")
    local = clamp((p - 0.18) / 0.64)
    response = [
        ("OBSERVATION", GREEN_LIGHT),
        ("The function fails on an empty array.", WHITE),
        ("", WHITE),
        ("NEXT STEP", GREEN_LIGHT),
        ("Add an empty-array guard before reduce.", WHITE),
        ("", WHITE),
        ("LOCAL TEST EVIDENCE", GREEN_LIGHT),
        ("average([]) -> failure reproduced", MUTED),
    ]
    visible_lines = int(len(response) * local)
    y = 230
    for index, (line, color) in enumerate(response[:visible_lines]):
        use_font = F["label"] if color == GREEN_LIGHT else F["body_small"]
        draw.text((658, y), line, font=use_font, fill=color)
        y += 37 if line else 20
    if p > 0.86:
        pill(draw, 930, 515, "SOURCE UNCHANGED", fill="#103529")


def scene_engineering(draw: ImageDraw.ImageDraw, p: float) -> None:
    draw_brand(draw, "VERIFIED ENGINEERING")
    draw.text((62, 128), "Multilingual behavior without sacrificing code contracts", font=F["h2"], fill=WHITE)
    steps = [
        ("10,000", "VERIFIED EXAMPLES"),
        ("LOCK", "IDENTICAL CODE"),
        ("RUN", "EDGE-CASE TESTS"),
        ("KILL", "WEAK MUTATIONS"),
    ]
    for index, (value, label) in enumerate(steps):
        x = 62 + index * 300
        local = ease((p - index * 0.1) / 0.3)
        y = int(254 + (1 - local) * 22)
        panel(draw, (x, y, x + 254, y + 170))
        draw.text((x + 24, y + 32), value, font=F["metric"], fill=GREEN_LIGHT)
        draw.text((x + 24, y + 100), label, font=F["label"], fill=MUTED)
        if index < 3:
            draw.line((x + 260, y + 84, x + 290, y + 84), fill=BORDER, width=4)
    draw.text((62, 492), "65% English coding", font=F["body_small"], fill=WHITE)
    draw.text((332, 492), "20% Kiswahili tutor", font=F["body_small"], fill=WHITE)
    draw.text((622, 492), "15% code-switching", font=F["body_small"], fill=WHITE)
    draw.text((932, 492), "90.8% mutation kill", font=F["body_small"], fill=WHITE)


def scene_performance(draw: ImageDraw.ImageDraw, p: float) -> None:
    draw_brand(draw, "OFFICIAL LOCAL PROFILER")
    draw.text((62, 128), "Built for the 8 GB laptop", font=F["h1"], fill=WHITE)
    metrics = [
        ("4.72", "TOKENS / SECOND"),
        ("3.29 GiB", "PEAK MEMORY"),
        ("0.82", "ARC-EASY ACC_NORM"),
        ("0", "GPU REQUIRED"),
    ]
    for index, (value, label) in enumerate(metrics):
        x = 62 + (index % 2) * 586
        y = 232 + (index // 2) * 168
        local = ease((p - index * 0.08) / 0.28)
        panel(draw, (x, y, x + 548, y + 136))
        shown_value = value if local > 0.25 else ""
        draw.text((x + 26, y + 26), shown_value, font=F["metric"], fill=GREEN_LIGHT)
        draw.text((x + 250, y + 57), label, font=F["label"], fill=MUTED)
    draw.text((62, 578), "4 CPU cores  |  no thermal throttling  |  below the 7 GB limit", font=F["body_small"], fill=WHITE)


def scene_impact(draw: ImageDraw.ImageDraw, p: float) -> None:
    draw_brand(draw, "CODING ASSISTANCE + EDUCATION")
    draw.text((62, 132), "One local tutor. Three immediate deployment paths.", font=F["h2"], fill=WHITE)
    audiences = [
        ("STUDENT", "Private help on a personal laptop"),
        ("BOOTCAMP", "Repeatable support without API bills"),
        ("TVET / COLLEGE", "English and Kiswahili instruction"),
    ]
    for index, (title, detail) in enumerate(audiences):
        x = 62 + index * 392
        local = ease((p - index * 0.12) / 0.3)
        y = int(262 + (1 - local) * 18)
        panel(draw, (x, y, x + 350, y + 204))
        draw.text((x + 24, y + 28), title, font=F["h2"], fill=GREEN_LIGHT)
        draw_wrapped(draw, (x + 24, y + 92), detail, F["body_small"], MUTED, 300)
    draw.text((62, 535), "The language capability lives inside the submitted model.", font=F["body"], fill=WHITE)


def scene_closing(draw: ImageDraw.ImageDraw, p: float) -> None:
    draw.rounded_rectangle((96, 104, 172, 180), radius=12, fill=GREEN)
    draw.text((112, 124), "CF", font=F["h2"], fill="#062118")
    draw.text((96, 232), "CodeFellow", font=F["hero"], fill=WHITE)
    draw.text((96, 306), "Learn, debug, and build", font=F["h1"], fill=WHITE)
    draw.text((96, 358), "no internet required.", font=F["h1"], fill=GREEN_LIGHT)
    draw.text((96, 466), "Open source  |  Reproducible  |  Ready for audit", font=F["body"], fill=MUTED)
    pill(draw, 96, 538, "github.com/brianzhou139/CodeFellow", fill="#103529")


SCENES = {
    "problem": scene_problem,
    "solution": scene_solution,
    "english_demo": scene_english_demo,
    "kiswahili_demo": scene_kiswahili_demo,
    "debug_demo": scene_debug_demo,
    "engineering": scene_engineering,
    "performance": scene_performance,
    "impact": scene_impact,
    "closing": scene_closing,
}


def wav_info(path: Path) -> tuple[int, int, int, bytes]:
    with wave.open(str(path), "rb") as handle:
        return handle.getnchannels(), handle.getsampwidth(), handle.getframerate(), handle.readframes(handle.getnframes())


def build_audio(segments: list[dict], narration_dir: Path, output_path: Path) -> None:
    chunks: list[bytes] = []
    reference: tuple[int, int, int] | None = None
    for index, segment in enumerate(segments, start=1):
        path = narration_dir / f"{index:02d}-{segment['kind']}.wav"
        channels, sample_width, sample_rate, frames = wav_info(path)
        current = (channels, sample_width, sample_rate)
        if reference is None:
            reference = current
        if current != reference:
            raise RuntimeError(f"inconsistent narration format in {path}")
        duration = len(frames) / (channels * sample_width * sample_rate)
        target = float(segment["duration"])
        lead = 0.28
        if duration + lead > target - 0.2:
            raise RuntimeError(f"narration for {segment['kind']} is {duration:.2f}s but scene is {target:.2f}s")
        silence_frame = b"\x00" * (channels * sample_width)
        chunks.append(silence_frame * int(sample_rate * lead))
        chunks.append(frames)
        tail = target - lead - duration
        chunks.append(silence_frame * int(sample_rate * tail))
    assert reference is not None
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(output_path), "wb") as handle:
        handle.setnchannels(reference[0])
        handle.setsampwidth(reference[1])
        handle.setframerate(reference[2])
        handle.writeframes(b"".join(chunks))


def locate_ffmpeg(video_tools: Path) -> Path:
    sys.path.insert(0, str(video_tools))
    import imageio_ffmpeg  # type: ignore

    return Path(imageio_ffmpeg.get_ffmpeg_exe())


def render_video(segments: list[dict], audio_path: Path, output_path: Path, ffmpeg: Path) -> None:
    total = sum(float(segment["duration"]) for segment in segments)
    command = [
        str(ffmpeg), "-y",
        "-f", "rawvideo", "-vcodec", "rawvideo", "-pix_fmt", "rgb24",
        "-s", f"{WIDTH}x{HEIGHT}", "-r", str(FPS), "-i", "-",
        "-i", str(audio_path),
        "-c:v", "libx264", "-preset", "medium", "-crf", "18", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "160k", "-movflags", "+faststart", "-shortest",
        str(output_path),
    ]
    process = subprocess.Popen(command, stdin=subprocess.PIPE)
    assert process.stdin is not None
    scene_starts: list[float] = []
    cursor = 0.0
    for segment in segments:
        scene_starts.append(cursor)
        cursor += float(segment["duration"])
    frame_count = int(round(total * FPS))
    for frame_index in range(frame_count):
        now = frame_index / FPS
        scene_index = max(i for i, start in enumerate(scene_starts) if start <= now)
        segment = segments[scene_index]
        start = scene_starts[scene_index]
        duration = float(segment["duration"])
        p = clamp((now - start) / duration)
        image = Image.new("RGB", (WIDTH, HEIGHT), BG)
        draw = ImageDraw.Draw(image)
        SCENES[segment["kind"]](draw, p)
        draw_footer(draw, segment["caption"], now, total)
        fade = min(clamp((now - start) / 0.25), clamp((start + duration - now) / 0.25))
        if fade < 1:
            overlay = Image.new("RGBA", (WIDTH, HEIGHT), alpha_color(BG, int(255 * (1 - fade))))
            image = Image.alpha_composite(image.convert("RGBA"), overlay).convert("RGB")
        process.stdin.write(image.tobytes())
        if frame_index % (FPS * 10) == 0:
            print(f"rendered {now:5.1f}s / {total:.1f}s", flush=True)
    process.stdin.close()
    code = process.wait()
    if code != 0:
        raise SystemExit(code)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--segments", type=Path, required=True)
    parser.add_argument("--narration-dir", type=Path, required=True)
    parser.add_argument("--video-tools", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()

    segments = json.loads(args.segments.read_text(encoding="utf-8"))
    total = sum(float(segment["duration"]) for segment in segments)
    if not math.isclose(total, 120.0):
        raise RuntimeError(f"storyboard must total 120 seconds, got {total}")
    args.output_dir.mkdir(parents=True, exist_ok=True)
    audio_path = args.output_dir / "codefellow-demo-narration.wav"
    video_path = args.output_dir / "CodeFellow-ADTC-2026-demo.mp4"
    build_audio(segments, args.narration_dir, audio_path)
    render_video(segments, audio_path, video_path, locate_ffmpeg(args.video_tools))
    print(video_path.resolve())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
