# CodeFellow two-minute demo

The video is a 120-second hybrid product demo. It combines recorded model
outputs and a genuine run of `codefellow.py` with restrained motion graphics.
It does not imply that a pre-rendered response is live.

| Time | Scene | Evidence shown |
|---:|---|---|
| 0:00–0:12 | Access problem | Data cost, unreliable internet, cloud dependency |
| 0:12–0:22 | Product | Offline tutor, English/Kiswahili, ordinary laptop |
| 0:22–0:37 | English demo | Audited `get_positive` prompt and executable response |
| 0:37–0:51 | Kiswahili demo | Audited `triangle_area` prompt and executable response |
| 0:51–1:07 | Debugging | Genuine `codefellow.py` run on `average_bug.js` |
| 1:07–1:22 | Engineering | 10,000 examples, locked code, execution and mutation gates |
| 1:22–1:37 | Performance | Official local profiler measurements |
| 1:37–1:52 | Impact | Students, bootcamps and technical colleges |
| 1:52–2:00 | Close | Tagline and public repository |

The flat visual system deliberately avoids gradients, stock AI imagery, and
base-model branding. All performance claims correspond to the final profiler
report in `benchmark-results/submission-2026/submission.json`.

## Reproduce the export on Windows

From the repository root, with Python and Pillow installed:

```powershell
python tools/download_video_encoder.py
powershell -ExecutionPolicy Bypass -File tools/render_demo_narration.ps1
python tools/render_demo_video.py `
  --segments video/demo_segments.json `
  --narration-dir video/rendered/narration `
  --video-tools video/rendered/video-tools `
  --output-dir video/rendered
```

The renderer enforces a 120-second runtime and produces an H.264/AAC MP4 at
`video/rendered/CodeFellow-ADTC-2026-demo.mp4`. Generated audio, encoder files,
and video exports remain local and are excluded from Git.

### Optional Southern African neural narration

The release cut uses `en-ZA-LeahNeural`, a Southern African English voice. This
is intentionally described as Southern African rather than Zimbabwean or
Zambian because no `en-ZW` or `en-ZM` voice is available in the provider's
catalogue. Install `edge-tts` into an ignored local directory, then run:

```powershell
$env:PYTHONPATH = (Resolve-Path video/rendered/audio-tools).Path
$ffmpeg = (Resolve-Path video/rendered/video-tools/imageio_ffmpeg/binaries/ffmpeg*.exe).Path
python tools/render_demo_neural_narration.py `
  --segments video/demo_segments.json `
  --output-directory video/rendered/narration-en-za `
  --ffmpeg $ffmpeg `
  --voice en-ZA-LeahNeural `
  --rate +5%
```

Pass `video/rendered/narration-en-za` to `render_demo_video.py` as the narration
directory. This voice-generation step is used only for the pitch video; it is
not part of CodeFellow's model or evaluation path.
