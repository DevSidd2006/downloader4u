# Artemis Video Suite Web UI

`yt_downloader` now exposes a Flask-powered SaaS-style cockpit (`server.py`) that lets you orchestrate `yt-dlp` downloads straight from the browser while surfacing rich telemetry, stats, presets, and history.

## Quick start

1. `pip install -r requirements.txt`
2. `python yt_downloader/server.py`
3. Open `http://localhost:8500` in the browser to queue URLs, pick presets, tweak advanced options, and monitor the worker fleet.

## Deploy on PythonAnywhere

1. Push or upload the repo to your home directory (e.g. `/home/yourname/api_tests`).
2. Install the dependencies into your PythonAnywhere virtualenv: `pip install -r requirements.txt`.
3. Create or reuse a `downloads/` folder inside the project so the default storage target exists.
4. Point the PythonAnywhere WSGI file to this project and expose the Flask app via `application`. Use a snippet like the following in your WSGI config:

```
import sys
import os

path = os.path.expanduser("~/api_tests")
if path not in sys.path:
	sys.path.insert(0, path)
os.chdir(path)

from yt_downloader.server import app as application
```

5. Reload the PythonAnywhere web app and open the provided URL to access the Artemis Video Suite UI. Static files (CSS/JS) are served automatically by Flask from the `static/` folder, and the history file plus downloads stay inside the project directory thanks to the new path defaults.

## Highlights

- **Preset showcase:** five curated format/metadata presets with contextual descriptions to help you pick the right profile.
- **SaaS console flow:** hero CTAs, feature highlights, and insight strips give the experience of a hosted workspace even when self-hosted.
- **Quality targeting:** select from Auto up to 4K heights (144p, 720p, 1080p, etc.) so yt-dlp downloads the bitrate you need.
- **Advanced controls:** rate limits (KB/s), start/end trim, priority slider, tags, and notes that flow into the download options and queue metadata.
- **Live insights:** summary cards for queued/running/completed/failed tasks plus average progress across the fleet.
- **Queue table:** tags rendered as chips, notes displayed inline, and per-task progress bars backed by the `yt_dlp` progress hook.
- **Persisted history and log:** every completed download writes to `downloads-history.json`, and the console log keeps the latest 300 events accessible from the UI.

## Notes

- If you still need the Qt client, the legacy `yt_downloader/app.py` remains as a reference implementation, but the Flask server is the modern entry point.
- Advanced inputs appear in the UI but are optional; missing values default to the previous behavior (no rate limit, no trimming, no tags). Ensure FFmpeg is available on your system if you rely on muxed downloads or audio extraction.
