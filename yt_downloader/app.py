import json
import os
import sys
from dataclasses import dataclass, field
from typing import Dict, List, Optional

import yt_dlp
from PyQt6.QtCore import QCoreApplication, QObject, QRunnable, QThreadPool, pyqtSignal
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (QApplication, QCheckBox, QComboBox, QFileDialog,
                             QGroupBox, QHeaderView, QLabel, QLineEdit, QMainWindow,
                             QMessageBox, QPushButton, QPlainTextEdit,
                             QSpinBox, QTableWidget, QTableWidgetItem, QVBoxLayout,
                             QWidget, QHBoxLayout)

HISTORY_FILENAME = "downloads-history.json"
FORMAT_PRESETS = [
    "Smart (best combined)",
    "Video + Audio (muxed)",
    "Audio only",
    "Subtitle + metadata",
    "Playlist (flat)",
]
AUDIO_CODECS = ["mp3", "m4a", "wav", "opus"]


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
    status: str = "Queued"
    progress_label: str = ""
    eta: str = ""
    speed: str = ""
    id: int = field(default=0)

    def build_options(self) -> Dict:
        os.makedirs(self.output_dir, exist_ok=True)
        options: Dict = {
            "outtmpl": os.path.join(self.output_dir, self.filename_template or "%(title)s.%(ext)s"),
            "nopart": True,
            "noplaylist": False,
            "restrictfilenames": True,
            "progress_hooks": [],
            "simulate": self.simulate,
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
        options["format"] = format_string
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
            options["subtitleslangs"] = [lang.strip() for lang in self.subtitle_lang.split(",") if lang.strip()]
        if self.proxy:
            options["proxy"] = self.proxy.strip()
        if self.playlist_limit > 0:
            options["max_downloads"] = self.playlist_limit
        return options


class DownloadHistory:
    def __init__(self, root: str):
        self.path = os.path.join(root, HISTORY_FILENAME)
        self._ensure_file()

    def _ensure_file(self) -> None:
        if not os.path.exists(self.path):
            with open(self.path, "w", encoding="utf-8") as handle:
                json.dump([], handle, indent=2)

    def append(self, record: Dict) -> None:
        self._ensure_file()
        with open(self.path, "r", encoding="utf-8") as handle:
            history = json.load(handle)
        history.append(record)
        with open(self.path, "w", encoding="utf-8") as handle:
            json.dump(history[-100:], handle, ensure_ascii=False, indent=2)

    def tail(self, limit: int = 5) -> List[Dict]:
        self._ensure_file()
        with open(self.path, "r", encoding="utf-8") as handle:
            history = json.load(handle)
        return history[-limit:]


class WorkerSignals(QObject):
    progress = pyqtSignal(dict)
    finished = pyqtSignal(int, str)
    errored = pyqtSignal(int, str)


class DownloadWorker(QRunnable):
    def __init__(self, task: DownloadTask):
        super().__init__()
        self.task = task
        self.signals = WorkerSignals()
        self.task.status = "Running"

    def run(self) -> None:
        self.task.progress_label = "Starting"
        options = self.task.build_options()
        options["progress_hooks"] = [self._progress_hook]
        try:
            with yt_dlp.YoutubeDL(options) as ydl:
                ydl.download([self.task.url])
        except Exception as exc:  # pylint: disable=broad-except
            self.signals.errored.emit(self.task.id, str(exc))
        else:
            self.signals.finished.emit(self.task.id, self.task.url)

    def _progress_hook(self, info: Dict) -> None:
        payload = {
            "task_id": self.task.id,
            "status": info.get("status", ""),
            "percent": info.get("percent"),
            "filename": info.get("filename"),
            "eta": info.get("eta"),
            "speed": info.get("speed"),
        }
        self.signals.progress.emit(payload)


class DownloaderWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Artemis Video Suite")
        self.resize(1100, 720)
        self.queue: List[DownloadTask] = []
        self.thread_pool = QThreadPool()
        self.history = DownloadHistory(os.getcwd())
        self.next_task_id = 1
        self._build_ui()

    def _build_ui(self) -> None:
        base_font = QFont("Segoe UI", 10)
        self.setFont(base_font)
        self.setStyleSheet("""
            QWidget { background-color: #0f1117; color: #f0f6ff; }
            QLineEdit, QPlainTextEdit, QSpinBox, QComboBox { background-color: #1d2230; border: 1px solid #323c55; border-radius: 6px; padding: 4px; }
            QTableWidget { gridline-color: #2f3649; }
            QPushButton { background-color: #5c6cff; border-radius: 6px; padding: 8px 16px; color: white; }
            QPushButton:hover { background-color: #4a54e1; }
            QPushButton:pressed { background-color: #3c44bb; }
        """)
        central = QWidget()
        main_layout = QVBoxLayout()
        header = QLabel("Artemis · yt-dlp download cockpit")
        header.setStyleSheet("font-size: 24px; font-weight: 600; color: #c8d7ff;")
        main_layout.addWidget(header)
        cards = QHBoxLayout()
        cards.addLayout(self._build_controls_card())
        cards.addLayout(self._build_status_card())
        main_layout.addLayout(cards)
        main_layout.addSpacing(12)
        main_layout.addWidget(self._build_footer_group())
        central.setLayout(main_layout)
        self.setCentralWidget(central)
        self._dump_history()

    def _build_controls_card(self) -> QVBoxLayout:
        layout = QVBoxLayout()
        group = QGroupBox("Download configuration")
        group_layout = QVBoxLayout()
        self.url_input = QPlainTextEdit(placeholderText="Paste URLs (one per line)")
        self.url_input.setFixedHeight(120)
        group_layout.addWidget(self.url_input)
        output_layout = QHBoxLayout()
        self.output_input = QLineEdit(os.getcwd())
        browse_btn = QPushButton("Browse")
        browse_btn.clicked.connect(self._choose_output_dir)
        output_layout.addWidget(QLabel("Output folder:"))
        output_layout.addWidget(self.output_input)
        output_layout.addWidget(browse_btn)
        group_layout.addLayout(output_layout)
        row_layout = QHBoxLayout()
        self.format_combo = QComboBox()
        self.format_combo.addItems(FORMAT_PRESETS)
        self.audio_combo = QComboBox()
        self.audio_combo.addItems(AUDIO_CODECS)
        row_layout.addWidget(QLabel("Format preset:"))
        row_layout.addWidget(self.format_combo)
        row_layout.addWidget(QLabel("Audio codec:"))
        row_layout.addWidget(self.audio_combo)
        group_layout.addLayout(row_layout)
        proxy_layout = QHBoxLayout()
        self.proxy_input = QLineEdit(placeholderText="http://127.0.0.1:8080")
        proxy_layout.addWidget(QLabel("Proxy (optional):"))
        proxy_layout.addWidget(self.proxy_input)
        group_layout.addLayout(proxy_layout)
        self.subtitle_input = QLineEdit(placeholderText="en, es")
        group_layout.addWidget(QLabel("Subtitle languages (comma separated):"))
        group_layout.addWidget(self.subtitle_input)
        template_layout = QHBoxLayout()
        self.template_input = QLineEdit("%(title)s.%(ext)s")
        template_layout.addWidget(QLabel("Filename template:"))
        template_layout.addWidget(self.template_input)
        group_layout.addLayout(template_layout)
        options_layout = QHBoxLayout()
        self.embed_subtitles = QCheckBox("Embed subtitles")
        self.embed_metadata = QCheckBox("Embed metadata")
        self.keep_thumbnails = QCheckBox("Keep thumbnail")
        self.simulate_checkbox = QCheckBox("Dry run")
        options_layout.addWidget(self.embed_subtitles)
        options_layout.addWidget(self.embed_metadata)
        options_layout.addWidget(self.keep_thumbnails)
        options_layout.addWidget(self.simulate_checkbox)
        group_layout.addLayout(options_layout)
        playlist_layout = QHBoxLayout()
        self.playlist_spin = QSpinBox()
        self.playlist_spin.setRange(0, 1000)
        playlist_layout.addWidget(QLabel("Playlist download limit (0 = all):"))
        playlist_layout.addWidget(self.playlist_spin)
        group_layout.addLayout(playlist_layout)
        button_row = QHBoxLayout()
        add_btn = QPushButton("Add to queue")
        add_btn.clicked.connect(self._add_to_queue)
        start_btn = QPushButton("Start queued downloads")
        start_btn.clicked.connect(self._start_queue)
        button_row.addWidget(add_btn)
        button_row.addWidget(start_btn)
        group_layout.addLayout(button_row)
        group.setLayout(group_layout)
        layout.addWidget(group)
        return layout

    def _build_status_card(self) -> QVBoxLayout:
        layout = QVBoxLayout()
        group = QGroupBox("Queue & telemetry")
        group_layout = QVBoxLayout()
        self.queue_table = QTableWidget(0, 5)
        self.queue_table.setHorizontalHeaderLabels(["ID", "URL", "Format", "Status", "Progress"])
        self.queue_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        group_layout.addWidget(self.queue_table)
        controls = QHBoxLayout()
        self.concurrency_spin = QSpinBox()
        self.concurrency_spin.setRange(1, 8)
        self.concurrency_spin.setValue(2)
        clear_btn = QPushButton("Clear queue")
        clear_btn.clicked.connect(self._clear_queue)
        controls.addWidget(QLabel("Workers:"))
        controls.addWidget(self.concurrency_spin)
        controls.addStretch(1)
        controls.addWidget(clear_btn)
        group_layout.addLayout(controls)
        log_label = QLabel("Console log")
        log_label.setStyleSheet("font-weight: 600; color: #b6c4ff;")
        group_layout.addWidget(log_label)
        self.log_output = QPlainTextEdit()
        self.log_output.setReadOnly(True)
        self.log_output.setFixedHeight(120)
        group_layout.addWidget(self.log_output)
        history_btn = QPushButton("Refresh history preview")
        history_btn.clicked.connect(self._dump_history)
        group_layout.addWidget(history_btn)
        self.history_preview = QPlainTextEdit()
        self.history_preview.setReadOnly(True)
        self.history_preview.setFixedHeight(140)
        group_layout.addWidget(self.history_preview)
        group.setLayout(group_layout)
        layout.addWidget(group)
        return layout

    def _build_footer_group(self) -> QWidget:
        frame = QWidget()
        footer_layout = QHBoxLayout()
        exit_btn = QPushButton("Quit")
        exit_btn.clicked.connect(QCoreApplication.instance().quit)
        footer_layout.addStretch(1)
        footer_layout.addWidget(exit_btn)
        frame.setLayout(footer_layout)
        return frame

    def _choose_output_dir(self) -> None:
        target = QFileDialog.getExistingDirectory(self, "Choose output folder", self.output_input.text())
        if target:
            self.output_input.setText(target)

    def _add_to_queue(self) -> None:
        raw = self.url_input.toPlainText().splitlines()
        urls = [line.strip() for line in raw if line.strip()]
        if not urls:
            QMessageBox.warning(self, "No URL", "Paste at least one URL before adding to the queue.")
            return
        for url in urls:
            task = DownloadTask(
                url=url,
                output_dir=self.output_input.text() or os.getcwd(),
                format_mode=self.format_combo.currentText(),
                audio_codec=self.audio_combo.currentText(),
                subtitle_lang=self.subtitle_input.text(),
                proxy=self.proxy_input.text(),
                playlist_limit=self.playlist_spin.value(),
                filename_template=self.template_input.text(),
                embed_subtitles=self.embed_subtitles.isChecked(),
                embed_metadata=self.embed_metadata.isChecked(),
                keep_thumbnails=self.keep_thumbnails.isChecked(),
                simulate=self.simulate_checkbox.isChecked(),
            )
            task.id = self.next_task_id
            self.next_task_id += 1
            self.queue.append(task)
            self._log(f"Queued {url}")
        self.url_input.clear()
        self._refresh_queue_table()

    def _start_queue(self) -> None:
        if not self.queue:
            QMessageBox.information(self, "Nothing to do", "Queue is empty; add some URLs first.")
            return
        self.thread_pool.setMaxThreadCount(self.concurrency_spin.value())
        for task in self.queue:
            if task.status == "Queued":
                worker = DownloadWorker(task)
                worker.signals.progress.connect(self._handle_progress)
                worker.signals.finished.connect(self._handle_finish)
                worker.signals.errored.connect(self._handle_error)
                self.thread_pool.start(worker)
        self._refresh_queue_table()

    def _clear_queue(self) -> None:
        self.queue = [task for task in self.queue if task.status == "Running"]
        self._refresh_queue_table()

    def _handle_progress(self, data: Dict) -> None:
        task = self._find_task(data["task_id"]) if data else None
        if not task:
            return
        percent = data.get("percent")
        task.progress_label = f"{percent:.1f}%" if percent else data.get("status", "")
        task.eta = str(data.get("eta"))
        task.speed = f"{data.get('speed', 0):.2f} {task.status}" if data.get("speed") else ""
        task.status = data.get("status", task.status)
        self._log(f"{task.url} → {task.progress_label} ({task.status})")
        self._refresh_queue_table()

    def _handle_finish(self, task_id: int, url: str) -> None:
        task = self._find_task(task_id)
        if not task:
            return
        task.status = "Completed"
        task.progress_label = "100%"
        self.history.append({
            "url": url,
            "output": task.output_dir,
            "format": task.format_mode,
            "timestamp": task.id,
        })
        self._log(f"Finished {url}")
        self._refresh_queue_table()
        self._dump_history()

    def _handle_error(self, task_id: int, message: str) -> None:
        task = self._find_task(task_id)
        if not task:
            return
        task.status = "Failed"
        task.progress_label = "Error"
        self._log(f"Error {task.url}: {message}")
        self._refresh_queue_table()

    def _find_task(self, task_id: int) -> Optional[DownloadTask]:
        for task in self.queue:
            if task.id == task_id:
                return task
        return None

    def _refresh_queue_table(self) -> None:
        self.queue_table.setRowCount(0)
        for task in self.queue:
            row = self.queue_table.rowCount()
            self.queue_table.insertRow(row)
            self.queue_table.setItem(row, 0, QTableWidgetItem(str(task.id)))
            self.queue_table.setItem(row, 1, QTableWidgetItem(task.url))
            self.queue_table.setItem(row, 2, QTableWidgetItem(task.format_mode))
            self.queue_table.setItem(row, 3, QTableWidgetItem(task.status))
            self.queue_table.setItem(row, 4, QTableWidgetItem(task.progress_label or "—"))

    def _log(self, message: str) -> None:
        self.log_output.appendPlainText(message)

    def _dump_history(self) -> None:
        preview = self.history.tail()
        text = "\n".join([f"[{item['timestamp']}] {item['url']}" for item in preview])
        self.history_preview.setPlainText(text)


def main() -> None:
    app = QApplication(sys.argv)
    window = DownloaderWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
