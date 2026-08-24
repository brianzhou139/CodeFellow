#!/usr/bin/env python3
"""Resumably download and unpack the pinned ImageIO FFmpeg wheel."""

from __future__ import annotations

import hashlib
import time
import urllib.request
import zipfile
from pathlib import Path


URL = "https://files.pythonhosted.org/packages/2c/c6/fa760e12a2483469e2bf5058c5faff664acf66cadb4df2ad6205b016a73d/imageio_ffmpeg-0.6.0-py3-none-win_amd64.whl"
EXPECTED_SIZE = 31_246_824
EXPECTED_SHA256 = "02fa47c83703c37df6bfe4896aab339013f62bf02c5ebf2dce6da56af04ffc0a"


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    cache = root / "video" / "rendered" / "cache"
    target = cache / "imageio_ffmpeg-0.6.0-py3-none-win_amd64.whl"
    partial = target.with_suffix(target.suffix + ".partial")
    install_dir = root / "video" / "rendered" / "video-tools"
    cache.mkdir(parents=True, exist_ok=True)

    if target.exists() and target.stat().st_size == EXPECTED_SIZE:
        digest = hashlib.sha256(target.read_bytes()).hexdigest()
        if digest == EXPECTED_SHA256:
            install_dir.mkdir(parents=True, exist_ok=True)
            with zipfile.ZipFile(target) as archive:
                archive.extractall(install_dir)
            print(f"installed encoder dependency in {install_dir}")
            return 0

    attempts = 0
    while True:
        current = partial.stat().st_size if partial.exists() else 0
        if current == EXPECTED_SIZE:
            break
        if current > EXPECTED_SIZE:
            partial.unlink()
            current = 0
        attempts += 1
        if attempts > 40:
            raise RuntimeError("encoder download did not complete after 40 resumable attempts")
        request = urllib.request.Request(URL, headers={"Range": f"bytes={current}-"} if current else {})
        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                resumed = current > 0 and response.status == 206
                mode = "ab" if resumed else "wb"
                if current and not resumed:
                    current = 0
                with partial.open(mode) as handle:
                    while True:
                        chunk = response.read(1024 * 1024)
                        if not chunk:
                            break
                        handle.write(chunk)
                        current += len(chunk)
                        print(f"downloaded {current / EXPECTED_SIZE:6.1%}", flush=True)
        except Exception as error:  # network interruptions are expected on the target connection
            print(f"download interrupted: {error}; resuming", flush=True)
            time.sleep(2)

    if partial.stat().st_size != EXPECTED_SIZE:
        raise RuntimeError(f"unexpected wheel size: {partial.stat().st_size}")
    digest = hashlib.sha256(partial.read_bytes()).hexdigest()
    if digest != EXPECTED_SHA256:
        raise RuntimeError(f"wheel hash mismatch: {digest}")
    partial.replace(target)
    install_dir.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(target) as archive:
        archive.extractall(install_dir)
    print(f"installed encoder dependency in {install_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
