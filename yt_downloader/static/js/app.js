const queueBody = document.getElementById("queueBody");
const historyList = document.getElementById("historyList");
const logOutput = document.getElementById("logOutput");
const queueCount = document.getElementById("queueCount");
const activeWorkers = document.getElementById("activeWorkers");
const concurrencyInput = document.getElementById("concurrency");
const concurrencyValue = document.getElementById("concurrencyValue");
const toast = document.getElementById("toast");
const statQueued = document.getElementById("statQueued");
const statRunning = document.getElementById("statRunning");
const statCompleted = document.getElementById("statCompleted");
const statAvgProgress = document.getElementById("statAvgProgress");
const statFailed = document.getElementById("statFailed");
const qualitySelect = document.getElementById("qualitySelect");
const summaryWorkers = document.getElementById("summaryWorkers");
const summaryAvg = document.getElementById("summaryAvg");
const summaryFailed = document.getElementById("summaryFailed");
const summaryCompleted = document.getElementById("summaryCompleted");

const form = document.getElementById("configForm");
let refreshHandle = null;

function showToast(message) {
  toast.textContent = message;
  toast.classList.add("show");
  window.clearTimeout(toast.timer);
  toast.timer = window.setTimeout(() => {
    toast.classList.remove("show");
  }, 2600);
}

async function fetchStatus() {
  try {
    const response = await fetch("/api/status");
    if (!response.ok) {
      throw new Error("Unable to reach the server");
    }
    const data = await response.json();
    renderQueue(data.tasks);
    renderHistory(data.history);
    renderLog(data.log);
    renderStats(data.insights);
    queueCount.textContent = `${data.tasks.length} queued`;
    activeWorkers.textContent = data.active_workers;
    concurrencyValue.textContent = data.concurrency;
    if (summaryWorkers) {
      summaryWorkers.textContent = data.active_workers;
    }
  } catch (error) {
    console.error(error);
  }
}

function renderQueue(tasks) {
  if (!tasks.length) {
    queueBody.innerHTML = '<tr><td colspan="6" class="empty">No tasks queued</td></tr>';
    return;
  }
  queueBody.innerHTML = tasks
    .map((task) => {
      const eta = formatEta(task.eta);
      const progress = Math.min(100, Math.max(0, Number(task.progress) || 0));
      const statusClass = `status-${task.status.toLowerCase().replace(/\s+/g, "-")}`;
      const qualityLabel = task.quality_label || task.quality_filter || "Auto";
      const downloadReady = task.download_ready;
      const downloadAction = downloadReady
        ? `<a class="download-link download-ready" href="/download/${task.id}" download>Download</a>`
        : `<span class="download-placeholder">waiting</span>`;
      return `
        <tr>
          <td>${task.id}</td>
          <td>
            <div class="url">${task.url}</div>
            <small>${task.message || task.status}</small>
            ${task.notes ? `<span class="note-text">${task.notes}</span>` : ""}
          </td>
          <td>
            ${task.format_mode}
            <small class="field-hint">Quality: ${qualityLabel}</small>
          </td>
          <td><span class="status-badge ${statusClass}">${task.status}</span></td>
          <td>
            <div class="progress-track"><span style="width:${progress}%"></span></div>
            <small>${progress.toFixed(1)}% · ${eta}</small>
          </td>
          <td class="tags-cell">
            ${renderTags(task.tags)}
          </td>
          <td class="download-cell">
            ${downloadAction}
          </td>
        </tr>
      `;
    })
    .join("");
}

function renderTags(tags = []) {
  if (!tags.length) {
    return '<span class="tag-chip">—</span>';
  }
  return tags.map((tag) => `<span class="tag-chip">${tag}</span>`).join("");
}

function renderHistory(entries) {
  if (!entries.length) {
    historyList.innerHTML = "<li>No downloads yet.</li>";
    return;
  }
  historyList.innerHTML = entries
    .map((entry) => {
      const time = new Date(entry.timestamp).toLocaleTimeString();
      return `<li><strong>[${time}]</strong> ${entry.url}</li>`;
    })
    .join("");
}

function renderLog(lines) {
  logOutput.textContent = lines.join("\n");
  logOutput.scrollTop = logOutput.scrollHeight;
}

function renderStats(stats) {
  if (!stats) {
    return;
  }
  statQueued.textContent = stats.queued;
  statRunning.textContent = stats.running;
  statCompleted.textContent = stats.completed;
  statFailed.textContent = stats.failed;
  statAvgProgress.textContent = `${stats.avg_progress}%`;
  if (summaryAvg) {
    summaryAvg.textContent = `${stats.avg_progress}%`;
  }
  if (summaryFailed) {
    summaryFailed.textContent = stats.failed;
  }
  if (summaryCompleted) {
    summaryCompleted.textContent = stats.completed;
  }
}

function formatEta(value) {
  if (!value || Number.isNaN(Number(value))) {
    return "ETA —";
  }
  const seconds = Number(value);
  const mins = Math.floor(seconds / 60);
  const secs = Math.floor(seconds % 60);
  return `${mins}m ${secs}s`;
}

async function submitQueueEntry() {
  const payload = {
    urls: document.getElementById("urlList").value.trim(),
    output_dir: document.getElementById("outputDir").value.trim(),
    filename_template: document.getElementById("filenameTpl").value.trim(),
    format_mode: document.getElementById("formatPreset").value,
    audio_codec: document.getElementById("audioCodec").value,
    subtitle_lang: document.getElementById("subtitleLang").value.trim(),
    proxy: document.getElementById("proxy").value.trim(),
    playlist_limit: Number(document.getElementById("playlistLimit").value) || 0,
    embed_subtitles: document.getElementById("embedSubs").checked,
    embed_metadata: document.getElementById("embedMeta").checked,
    keep_thumbnails: document.getElementById("keepThumb").checked,
    simulate: document.getElementById("simulate").checked,
    quality_filter: qualitySelect?.value || "best",
    quality_label: qualitySelect?.options[qualitySelect.selectedIndex]?.text || "",
  };

  if (!payload.urls) {
    showToast("Please add at least one URL.");
    return;
  }

  try {
    const response = await fetch("/api/queue", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    if (!response.ok) {
      throw new Error("Server rejected the queue request");
    }
    document.getElementById("urlList").value = "";
    showToast("Queued successfully");
    await fetchStatus();
  } catch (error) {
    console.error(error);
    showToast("Failed to queue items");
  }
}

async function startDownloads() {
  try {
    await fetch("/api/start", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ concurrency: Number(concurrencyInput.value) }),
    });
    showToast("Workers updated");
    await fetchStatus();
  } catch (error) {
    console.error(error);
    showToast("Unable to start downloads");
  }
}

async function clearCompleted() {
  try {
    await fetch("/api/clear", { method: "POST" });
    showToast("Cleared finished tasks");
    await fetchStatus();
  } catch (error) {
    console.error(error);
    showToast("Clear request failed");
  }
}

form.addEventListener("submit", (event) => {
  event.preventDefault();
  submitQueueEntry();
});

concurrencyInput.addEventListener("input", () => {
  concurrencyValue.textContent = concurrencyInput.value;
});

document.getElementById("addBtn").addEventListener("click", submitQueueEntry);
document.getElementById("startBtn").addEventListener("click", startDownloads);
document.getElementById("clearBtn").addEventListener("click", clearCompleted);

document.addEventListener("DOMContentLoaded", () => {
  fetchStatus();
  refreshHandle = window.setInterval(fetchStatus, 2400);
});
