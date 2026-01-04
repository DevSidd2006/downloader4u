import functools
import itertools
import json
import os
import threading
from collections import Counter, deque
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional

from flask import Flask, jsonify, request, render_template, send_file, abort
import yt_dlp

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_DOWNLOAD_DIR = os.path.join(BASE_DIR, "downloads")

HISTORY_FILENAME = "downloads-history.json"
FORMAT_PRESETS = [
    "Smart (best combined)",
    "Video + Audio (muxed)",
    "Audio only",
    "Subtitle + metadata",
    "Playlist (flat)",
]
AUDIO_CODECS = ["mp3", "m4a", "wav", "opus"]
QUALITY_OPTIONS = [
    {"label": "Auto (best)", "value": "best", "hint": "Fallback to preset logic."},
    {"label": "144p", "value": "bestvideo[height<=144]+bestaudio/best", "hint": "Usable on slow connections."},
    {"label": "240p", "value": "bestvideo[height<=240]+bestaudio/best", "hint": "Small files for notes."},
    {"label": "360p", "value": "bestvideo[height<=360]+bestaudio/best", "hint": "Balanced for devices."},
    {"label": "480p", "value": "bestvideo[height<=480]+bestaudio/best", "hint": "Portable + readable."},
    {"label": "720p", "value": "bestvideo[height<=720]+bestaudio/best", "hint": "HD without huge files."},
    {"label": "1080p", "value": "bestvideo[height<=1080]+bestaudio/best", "hint": "Full HD downloads."},
    {"label": "1440p", "value": "bestvideo[height<=1440]+bestaudio/best", "hint": "Quad HD rigs."},
    {"label": "2160p", "value": "bestvideo[height<=2160]+bestaudio/best", "hint": "Ultra HD + 4K."},
]
PRESET_DETAILS = [
    {
        "name": "Smart (best combined)",
        "highlight": "Balanced muxed stream",
        "desc": "Combines best video and audio automatically for a ready-to-watch file.",
    },
    {
        "name": "Video + Audio (muxed)",
        "highlight": "MP4 friendly",
        "desc": "Selects mp4 video plus m4a audio streams for perfect muxing via FFmpeg.",
    },
    {
        "name": "Audio only",
        "highlight": "Podcast-ready",
        "desc": "Downloads the highest bitrate audio and optionally transcodes the codec.",
    },
    {
        "name": "Subtitle + metadata",
        "highlight": "Archive mode",
        "desc": "Captures subtitles, metadata, and thumbnails for compliance archives.",
    },
    {
        "name": "Playlist (flat)",
        "highlight": "Rapid inspection",
        "desc": "Lists playlist entries without downloading payloads for quick auditing.",
    },
]
LOG_LIMIT = 300
MAX_WORKERS = 12
DEFAULT_CONCURRENCY = 2


def now_iso() -> str:
    return datetime.utcnow().isoformat() + "Z"


class DownloadHistory:
    def __init__(self, root: str):
        self.path = os.path.join(root, HISTORY_FILENAME)
        self._ensure_file()

    def _ensure_file(self) -> None:
        directory = os.path.dirname(self.path)
        if directory and not os.path.isdir(directory):
            os.makedirs(directory, exist_ok=True)
        if not os.path.exists(self.path):
            with open(self.path, "w", encoding="utf-8") as handle:
                json.dump([], handle, indent=2)

    def append(self, record: Dict) -> None:
        self._ensure_file()
        with open(self.path, "r", encoding="utf-8") as handle:
            history = json.load(handle)
        history.append(record)
        with open(self.path, "w", encoding="utf-8") as handle:
            json.dump(history[-200:], handle, ensure_ascii=False, indent=2)

    def tail(self, limit: int = 8) -> List[Dict]:
        self._ensure_file()
        with open(self.path, "r", encoding="utf-8") as handle:
            history = json.load(handle)
        return history[-limit:]


@dataclass
class DownloadTask:
    url: str
    output_dir: str
    format_mode: str
    audio_codec: str
    subtitle_lang: str
    proxy: str
    playlist_limit: int
    filename_template: str
    embed_subtitles: bool
    embed_metadata: bool
    keep_thumbnails: bool
    simulate: bool
    id: int
    filepath: Optional[str] = None
    rate_limit: float = 0.0
    start_time: str = ""
    end_time: str = ""
    tags: List[str] = field(default_factory=list)
    notes: str = ""
    priority: int = 3
    quality_filter: str = "best"
    quality_label: str = "Auto (best)"
    status: str = "Queued"
    progress: float = 0.0
    eta: Optional[float] = None
    speed: Optional[float] = None
    message: str = "Queued"
    created_at: str = field(default_factory=now_iso)
    last_update: str = field(default_factory=now_iso)

    def normalize_output(self) -> str:
        target = self.output_dir.strip() or DEFAULT_DOWNLOAD_DIR
        os.makedirs(target, exist_ok=True)
        return target

    def build_options(self) -> Dict:
        resolved_dir = self.normalize_output()
        options: Dict = {
            "outtmpl": os.path.join(resolved_dir, self.filename_template or "%(title)s.%(ext)s"),
            "nopart": True,
            "noplaylist": False,
            "restrictfilenames": True,
            "simulate": self.simulate,
            "progress_hooks": [],
        }
        format_string = "best"
        if self.format_mode == "Smart (best combined)":
            format_string = "bv*+ba/b"
        elif self.format_mode == "Video + Audio (muxed)":
            format_string = "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best"
        elif self.format_mode == "Audio only":
            format_string = "bestaudio"
        elif self.format_mode == "Subtitle + metadata":
            format_string = "best"
            options.update({"writesubtitles": True, "writeautomaticsub": True})
        elif self.format_mode == "Playlist (flat)":
            format_string = "bestaudio/best"
            options["flat_playlist"] = True
        final_format = format_string
        if (
            self.quality_filter
            and self.quality_filter != "best"
            and self.format_mode not in ("Audio only", "Playlist (flat)")
        ):
            final_format = self.quality_filter
        options["format"] = final_format
        if self.audio_codec and self.format_mode == "Audio only":
            options["postprocessors"] = [{
                "key": "FFmpegExtractAudio",
                "preferredcodec": self.audio_codec,
                "preferredquality": "192",
            }]
        if self.embed_subtitles:
            options["embedsubtitles"] = True
        if self.embed_metadata:
            options["addmetadata"] = True
        if self.keep_thumbnails:
            options["writethumbnail"] = True
        if self.subtitle_lang:
            languages = [lang.strip() for lang in self.subtitle_lang.split(",") if lang.strip()]
            if languages:
                options["subtitleslangs"] = languages
        if self.proxy:
            options["proxy"] = self.proxy.strip()
        if self.rate_limit:
            options["ratelimit"] = int(self.rate_limit * 1024)
        sections: List[str] = []
        if self.start_time or self.end_time:
            start = self.start_time or "00:00"
            end = self.end_time
            marker = f"{start}-{end}" if end else f"{start}-"
            sections.append(marker)
        if sections:
            options["download_sections"] = sections
        if self.playlist_limit > 0:
            options["max_downloads"] = self.playlist_limit
        return options

    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "url": self.url,
            "format_mode": self.format_mode,
            "status": self.status,
            "progress": round(self.progress, 1),
            "eta": self.eta,
            "speed": self.speed,
            "message": self.message,
            "created_at": self.created_at,
            "last_update": self.last_update,
            "output_dir": self.output_dir,
            "tags": self.tags,
            "notes": self.notes,
            "priority": self.priority,
            "rate_limit": self.rate_limit,
            "quality_filter": self.quality_filter,
            "quality_label": self.quality_label,
            "download_ready": bool(
                self.filepath and self.status == "Completed" and os.path.isfile(self.filepath)
            ),
        }


app = Flask(__name__, static_folder="static", template_folder="templates")
app.config["JSON_SORT_KEYS"] = False

history = DownloadHistory(BASE_DIR)
task_counter = itertools.count(1)
task_lock = threading.Lock()
tasks: Dict[int, DownloadTask] = {}
task_order: List[int] = []
executor = ThreadPoolExecutor(max_workers=MAX_WORKERS)
current_concurrency = DEFAULT_CONCURRENCY
active_workers = 0
log_lines = deque(maxlen=LOG_LIMIT)


def append_log(message: str) -> None:
    timestamp = datetime.utcnow().strftime("%H:%M:%S")
    log_lines.append(f"[{timestamp}] {message}")


def gather_insights() -> Dict[str, int]:
    with task_lock:
        snapshot = list(tasks.values())
    counter = Counter(task.status for task in snapshot)
    total = len(snapshot)
    avg_progress = (
        sum(task.progress for task in snapshot) / total
        if total
        else 0.0
    )
    return {
        "queued": counter.get("Queued", 0),
        "scheduled": counter.get("Scheduled", 0),
        "running": counter.get("Running", 0),
        "completed": counter.get("Completed", 0),
        "failed": counter.get("Failed", 0),
        "avg_progress": round(avg_progress, 1),
    }

def update_task(task_id: int, **kwargs) -> Optional[DownloadTask]:
    with task_lock:
        task = tasks.get(task_id)
        if not task:
            return None
        for key, value in kwargs.items():
            if hasattr(task, key):
                setattr(task, key, value)
        task.last_update = now_iso()
        return task


def try_schedule_next() -> None:
    global active_workers
    to_start: List[DownloadTask] = []
    with task_lock:
        queued_ids = sorted(
            (tid for tid in task_order if tid in tasks and tasks[tid].status == "Queued"),
            key=lambda tid: (-tasks[tid].priority, tasks[tid].created_at),
        )
        while active_workers < current_concurrency and queued_ids:
            tid = queued_ids.pop(0)
            task = tasks.get(tid)
            if not task or task.status != "Queued":
                continue
            task.status = "Scheduled"
            task.last_update = now_iso()
            to_start.append(task)
            active_workers += 1
    for task in to_start:
        executor.submit(_run_task, task)


def _progress_hook(task_id: int, info: Dict) -> None:
    percent = info.get("percent")
    speed = info.get("speed")
    eta = info.get("eta")
    status = info.get("status") or "running"
    filename = info.get("filename") or info.get("_filename")
    pct_value = round(percent, 1) if isinstance(percent, (int, float)) else 0.0
    update_kwargs = {
        "progress": pct_value,
        "status": status.capitalize(),
        "eta": eta,
        "speed": speed,
        "message": filename or status,
    }
    if filename:
        update_kwargs["filepath"] = filename
    update_task(task_id, **update_kwargs)


def _run_task(task: DownloadTask) -> None:
    global active_workers
    append_log(f"Starting {task.url}")
    update_task(task.id, status="Running", message="Preparing download", progress=0.0)
    options = task.build_options()
    options["progress_hooks"] = [functools.partial(_progress_hook, task.id)]
    try:
        with yt_dlp.YoutubeDL(options) as ydl:
            ydl.download([task.url])
    except Exception as exc:  # pylint: disable=broad-except
        update_task(task.id, status="Failed", message=str(exc))
        append_log(f"Failed {task.url}: {exc}")
    else:
        update_task(task.id, status="Completed", message="Download finished", progress=100.0)
        history.append({
            "url": task.url,
            "output": task.output_dir,
            "format": task.format_mode,
            "notes": task.notes,
            "tags": task.tags,
            "quality": task.quality_filter,
            "timestamp": now_iso(),
        })
        append_log(f"Finished {task.url}")
    finally:
        with task_lock:
            active_workers = max(active_workers - 1, 0)
        try_schedule_next()


def queue_tasks(payload: Dict) -> List[DownloadTask]:
    urls = [line.strip() for line in (payload.get("urls") or "").splitlines() if line.strip()]
    if not urls:
        return []
    output_dir = payload.get("output_dir") or DEFAULT_DOWNLOAD_DIR
    format_mode = payload.get("format_mode") or FORMAT_PRESETS[0]
    audio_codec = payload.get("audio_codec") or AUDIO_CODECS[0]
    subtitle_lang = payload.get("subtitle_lang") or ""
    proxy = payload.get("proxy") or ""
    playlist_limit = int(payload.get("playlist_limit") or 0)
    filename_template = payload.get("filename_template") or "%(title)s.%(ext)s"
    embed_subtitles = bool(payload.get("embed_subtitles"))
    embed_metadata = bool(payload.get("embed_metadata"))
    keep_thumbnails = bool(payload.get("keep_thumbnails"))
    simulate = bool(payload.get("simulate"))
    rate_limit = float(payload.get("rate_limit") or 0.0)
    start_time = payload.get("start_time") or ""
    end_time = payload.get("end_time") or ""
    tags = [segment.strip() for segment in (payload.get("tags") or "").split(",") if segment.strip()]
    notes = payload.get("notes") or ""
    priority_val = int(payload.get("priority") or 3)
    priority = max(1, min(priority_val, 10))
    quality_filter = payload.get("quality_filter") or QUALITY_OPTIONS[0]["value"]
    quality_label = payload.get("quality_label") or QUALITY_OPTIONS[0]["label"]
    created: List[DownloadTask] = []
    with task_lock:
        for url in urls:
            tid = next(task_counter)
            task = DownloadTask(
                url=url,
                output_dir=output_dir,
                format_mode=format_mode,
                audio_codec=audio_codec,
                subtitle_lang=subtitle_lang,
                proxy=proxy,
                playlist_limit=playlist_limit,
                filename_template=filename_template,
                embed_subtitles=embed_subtitles,
                embed_metadata=embed_metadata,
                keep_thumbnails=keep_thumbnails,
                simulate=simulate,
                rate_limit=rate_limit,
                start_time=start_time,
                end_time=end_time,
                tags=tags,
                notes=notes,
                priority=priority,
                quality_label=quality_label,
                quality_filter=quality_filter,
                id=tid,
            )
            tasks[tid] = task
            task_order.append(tid)
            created.append(task)
            append_log(f"Queued {url}")
    return created


def clear_completed_tasks() -> int:
    removed = 0
    with task_lock:
        to_remove = [tid for tid, task in tasks.items() if task.status in ("Completed", "Failed")]
        for tid in to_remove:
            tasks.pop(tid, None)
            if tid in task_order:
                task_order.remove(tid)
            removed += 1
    if removed:
        append_log(f"Cleared {removed} finished task(s)")
    return removed


def set_concurrency(value: int) -> None:
    global current_concurrency
    current_concurrency = max(1, min(value, MAX_WORKERS))
    append_log(f"Concurrency tuned to {current_concurrency}")


@app.route("/")
def index() -> str:
    return render_template(
        "index.html",
        presets=PRESET_DETAILS,
        codecs=AUDIO_CODECS,
        quality_options=QUALITY_OPTIONS,
    )


@app.route("/api/queue", methods=["POST"])
def api_add_to_queue() -> object:
    payload = request.get_json(force=True)
    tasks_created = queue_tasks(payload)
    try_schedule_next()
    return jsonify({
        "created": [task.to_dict() for task in tasks_created],
        "queued": len(tasks_created),
    })


@app.route("/api/start", methods=["POST"])
def api_start_queue() -> object:
    payload = request.get_json(force=True)
    concurrency = int(payload.get("concurrency", current_concurrency))
    set_concurrency(concurrency)
    try_schedule_next()
    return jsonify({
        "status": "scheduled",
        "concurrency": current_concurrency,
    })


@app.route("/api/clear", methods=["POST"])
def api_clear() -> object:
    removed = clear_completed_tasks()
    return jsonify({"removed": removed})


@app.route("/api/status", methods=["GET"])
def api_status() -> object:
    with task_lock:
        ordered = [tasks[tid].to_dict() for tid in task_order if tid in tasks]
    return jsonify({
        "tasks": ordered,
        "concurrency": current_concurrency,
        "active_workers": active_workers,
        "history": history.tail(12),
        "insights": gather_insights(),
        "presets": PRESET_DETAILS,
        "log": list(log_lines),
    })


@app.route("/download/<int:task_id>")
def download_task_file(task_id: int) -> object:
    with task_lock:
        task = tasks.get(task_id)
    if not task or task.status != "Completed" or not task.filepath:
        abort(404)
    if not os.path.isfile(task.filepath):
        abort(404)
    return send_file(task.filepath, as_attachment=True)


def run_server() -> None:
    append_log("Starting Artemis Web Client")
    app.run(host="0.0.0.0", port=8500, debug=False, threaded=True)


if __name__ == "__main__":
    run_server()
