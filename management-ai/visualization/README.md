# SMT loading animation

`manim_smt_loading.py` renders an explanatory/replay animation for the SMT
material-loading cycle. It is intentionally separate from MES/PDA runtime code:
the animation cannot approve, reject, or write a loading record.

This workspace includes a ready-to-use Python 3.11 environment under `.venv`
with ManimGL and a portable FFmpeg binary. Render the sample from PowerShell:

```powershell
uv pip install --python .venv\Scripts\python.exe manimgl imageio-ffmpeg "setuptools<81"
Copy-Item (Get-ChildItem .venv -Recurse -Filter ffmpeg-win-*.exe | Select-Object -First 1) .venv\Scripts\ffmpeg.exe -Force
$env:PATH = "$(Resolve-Path .venv\Scripts);$env:PATH"
.\.venv\Scripts\manimgl.exe manim_smt_loading.py SmtLoadingReplay -w
```

To replay exported MES events, set `SMT_EVENTS_JSON` to a JSON array file:

```powershell
$env:SMT_EVENTS_JSON = (Resolve-Path .\events.json)
manimgl manim_smt_loading.py SmtLoadingReplay -w
```

Each event has `step`, `value`, and `ok` fields. Green cards mean the recorded
step passed; red cards mean the recorded step failed. The renderer does not
contact MES and should only use sanitized exports.
