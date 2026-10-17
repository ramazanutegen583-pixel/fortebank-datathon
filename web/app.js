"use strict";

const byId = (id) => document.getElementById(id);
const state = { file: null, jobId: null, timer: null, startedAt: 0, busy: false, limit: 100 * 1024 * 1024, pollRun: 0 };
const clock = (seconds) => {
  const value = Math.max(0, Number(seconds) || 0);
  return `${Math.floor(value / 60).toString().padStart(2, "0")}:${Math.floor(value % 60).toString().padStart(2, "0")}`;
};
const node = (tag, className, text) => {
  const item = document.createElement(tag);
  if (className) item.className = className;
  if (text !== undefined) item.textContent = text;
  return item;
};
function error(message) {
  byId("form-error").textContent = message;
  byId("form-error").hidden = !message;
}
function selectFile(file) {
  if (state.busy) return;
  error("");
  if (!file) return;
  if (!file.name.toLowerCase().endsWith(".mov")) return error("Choose a .mov video file.");
  if (!file.size) return error("This file is empty. Choose a recording with video content.");
  if (file.size > state.limit) return error(`This file exceeds the ${Math.round(state.limit / 1024 / 1024)} MB upload limit.`);
  state.file = file;
  byId("file-name").textContent = file.name;
  byId("file-size").textContent = `${(file.size / 1024 / 1024).toFixed(2)} MB · MOV recording`;
  byId("selected-file").hidden = false;
  byId("dropzone").hidden = true;
}
function setBusy(busy) {
  state.busy = busy;
  byId("submit-review").disabled = busy;
  byId("submit-review").firstElementChild.textContent = busy ? "Review in progress" : "Start review";
  byId("video-file").disabled = busy;
  byId("dropzone").disabled = busy;
  byId("remove-file").disabled = busy;
  byId("new-review").hidden = busy;
  byId("api-key").disabled = busy;
}
function startTimer(startedAt = Date.now()) {
  clearInterval(state.timer);
  state.startedAt = startedAt;
  const update = () => { byId("elapsed-label").textContent = `${clock((Date.now() - state.startedAt) / 1000)} elapsed`; };
  update();
  state.timer = setInterval(update, 1000);
}
function beginProgress() {
  byId("review-result").hidden = false;
  byId("result-heading").textContent = "Review in progress";
  byId("result-badge").textContent = "Processing";
  byId("result-badge").className = "status-badge";
  byId("result-body").replaceChildren();
  byId("progress-block").hidden = false;
  byId("progress-bar").className = "";
  byId("progress-bar").style.width = "0%";
  byId("progress-label").textContent = "Uploading recording";
  byId("progress-value").textContent = "0%";
  byId("job-label").textContent = "Preparing upload";
  byId("copy-job").hidden = true;
  startTimer();
  byId("review-result").scrollIntoView({ behavior: "smooth", block: "nearest" });
}
async function authenticatedFetch(url, key) {
  const response = await fetch(url, { headers: { "X-API-Key": key }, cache: "no-store" });
  const data = await response.json();
  if (!response.ok) throw new Error(data.error?.message || `Request failed (${response.status}).`);
  return data;
}
function submitVideo(file, key) {
  return new Promise((resolve, reject) => {
    const request = new XMLHttpRequest();
    request.open("POST", "/api/v1/analyze");
    request.setRequestHeader("X-API-Key", key);
    request.timeout = 125000;
    request.upload.onprogress = (event) => {
      if (!event.lengthComputable) return;
      const percent = Math.round(event.loaded / event.total * 100);
      byId("progress-bar").style.width = `${percent}%`;
      byId("progress-value").textContent = `${percent}%`;
    };
    request.onload = () => {
      let data;
      try { data = JSON.parse(request.responseText); } catch { return reject(new Error("The server returned an unreadable response.")); }
      if (request.status !== 202) return reject(new Error(data.error?.message || `Upload failed (${request.status}).`));
      resolve(data.job_id);
    };
    request.onerror = () => reject(new Error("The service could not be reached. Check your connection and try again."));
    request.ontimeout = () => reject(new Error("The upload timed out. Check the connection and try a smaller file."));
    const form = new FormData();
    form.append("file", file);
    request.send(form);
  });
}
function showSummary(className, title, message, code) {
  const box = node("div", `result-summary ${className}`);
  box.append(node("strong", "", title), node("span", "", message));
  if (code) { box.append(node("br"), node("code", "", code)); }
  byId("result-body").append(box);
}
function finish(result, details) {
  clearInterval(state.timer);
  setBusy(false);
  byId("progress-block").hidden = true;
  byId("result-body").replaceChildren();
  const badge = byId("result-badge");
  if (details?.elapsed_sec !== undefined) byId("elapsed-label").textContent = `${clock(details.elapsed_sec)} total processing time`;
  if (result.status === "failed") {
    byId("result-heading").textContent = "Review could not complete";
    badge.textContent = "Failed"; badge.className = "status-badge error";
    showSummary("error", "No conclusion was produced.", result.error.message, result.error.code);
    return;
  }
  byId("result-heading").textContent = "Review complete";
  if (result.verdict === "no_violation") {
    badge.textContent = "No violation detected"; badge.className = "status-badge success";
    showSummary("", "No visible violation detected.", "The analyzer did not identify a reviewable event in this recording. Human review remains the final step.");
    return;
  }
  badge.textContent = "Review required"; badge.className = "status-badge warning";
  showSummary("warning", `${result.violations.length} possible ${result.violations.length === 1 ? "violation" : "violations"} identified.`, "Check each event against its supporting frames and the referenced rule before making a decision.");
  result.violations.forEach((event, index) => {
    const card = node("article", "event-card");
    const heading = node("div", "event-header");
    heading.append(node("span", "event-number", String(index + 1).padStart(2, "0")), node("h3", "", event.type), node("span", "timecode", clock(event.timecode_sec)));
    const sources = details?.details?.sources?.[index] || [];
    const description = sources.length ? event.description.split("\n\nSource:")[0] : event.description;
    card.append(heading, node("div", "event-description", description));
    const frames = node("div", "frames");
    event.evidence_frames.forEach((frame, frameIndex) => {
      const button = node("button", "frame-button"); button.type = "button";
      const img = node("img"); img.src = `data:image/jpeg;base64,${frame.image_base64}`;
      img.alt = `Evidence frame ${frameIndex + 1} at ${clock(frame.timestamp_sec)}`;
      button.append(img, node("span", "", `${clock(frame.timestamp_sec)} · View frame ↗`));
      button.addEventListener("click", () => {
        byId("evidence-image").src = img.src;
        byId("evidence-caption").textContent = `${event.type} · ${clock(frame.timestamp_sec)} from the start of the recording`;
        byId("evidence-dialog").showModal();
      });
      frames.append(button);
    });
    card.append(frames);
    if (sources.length) {
      const list = node("div", "source-list"); list.append(node("h4", "", "RULE REFERENCES"));
      sources.forEach((source) => {
        const row = node("div");
        try {
          const url = new URL(source.url);
          if (!["http:", "https:"].includes(url.protocol)) return;
          const link = node("a", "", `${source.document_title} ↗`);
          link.href = url.href; link.target = "_blank"; link.rel = "noopener noreferrer";
          row.append(link);
        } catch { return; }
        if (source.section) row.append(node("span", "source-section", source.section));
        row.append(node("p", "", source.rationale)); list.append(row);
      });
      card.append(list);
    }
    byId("result-body").append(card);
  });
}
async function poll(jobId, key) {
  const run = ++state.pollRun;
  byId("job-label").textContent = `JOB ${jobId}`;
  byId("copy-job").hidden = false;
  byId("progress-bar").style.width = "";
  byId("progress-bar").className = "indeterminate";
  byId("progress-label").textContent = "Queued or processing locally";
  byId("progress-value").textContent = "Waiting for result";
  let failures = 0;
  while (run === state.pollRun) {
    try {
      const result = await authenticatedFetch(`/api/v1/jobs/${encodeURIComponent(jobId)}`, key);
      failures = 0;
      if (result.status !== "processing") {
        let details = null;
        try { details = await authenticatedFetch(`/ui/jobs/${encodeURIComponent(jobId)}`, key); } catch { /* Public results remain usable. */ }
        finish(result, details);
        return;
      }
      byId("progress-label").textContent = "Queued or processing locally";
    } catch (cause) {
      failures++;
      byId("progress-label").textContent = "Connection interrupted. Retrying…";
      if (failures >= 4) {
        clearInterval(state.timer); setBusy(false); byId("progress-block").hidden = true;
        byId("result-heading").textContent = "Connection interrupted";
        byId("result-badge").textContent = "Status unknown"; byId("result-badge").className = "status-badge warning";
        showSummary("warning", "The result could not be retrieved.", `${cause.message} The job may still be processing. Keep the job ID and check it through the API.`);
        return;
      }
    }
    await new Promise((resolve) => setTimeout(resolve, 1200));
  }
}

byId("dropzone").addEventListener("click", () => byId("video-file").click());
byId("video-file").addEventListener("change", (event) => selectFile(event.target.files[0]));
byId("dropzone").addEventListener("dragover", (event) => { event.preventDefault(); byId("dropzone").classList.add("dragover"); });
byId("dropzone").addEventListener("dragleave", () => byId("dropzone").classList.remove("dragover"));
byId("dropzone").addEventListener("drop", (event) => { event.preventDefault(); byId("dropzone").classList.remove("dragover"); if (event.dataTransfer.files.length !== 1) return error("Choose one recording at a time."); selectFile(event.dataTransfer.files[0]); });
byId("remove-file").addEventListener("click", () => { state.file = null; byId("video-file").value = ""; byId("selected-file").hidden = true; byId("dropzone").hidden = false; error(""); });
byId("toggle-key").addEventListener("click", () => { const input = byId("api-key"); const show = input.type === "password"; input.type = show ? "text" : "password"; byId("toggle-key").textContent = show ? "Hide" : "Show"; byId("toggle-key").setAttribute("aria-label", show ? "Hide access key" : "Show access key"); });
byId("review-form").addEventListener("submit", async (event) => {
  event.preventDefault(); if (state.busy) return; error("");
  if (!state.file) return error("Choose a .mov recording before starting a review.");
  const key = byId("api-key").value.trim();
  if (!key) return error("Enter your service access key.");
  setBusy(true); beginProgress();
  try { state.jobId = await submitVideo(state.file, key); await poll(state.jobId, key); }
  catch (cause) { clearInterval(state.timer); setBusy(false); byId("progress-block").hidden = true; byId("result-heading").textContent = "Upload could not complete"; byId("result-badge").textContent = "Not submitted"; byId("result-badge").className = "status-badge error"; showSummary("error", "The recording was not accepted.", cause.message); }
});
byId("new-review").addEventListener("click", () => { state.pollRun++; byId("review-result").hidden = true; byId("remove-file").click(); byId("upload-heading").scrollIntoView({ behavior: "smooth", block: "center" }); byId("dropzone").focus(); });
byId("copy-job").addEventListener("click", async () => { try { await navigator.clipboard.writeText(state.jobId); byId("copy-job").textContent = "Copied"; setTimeout(() => { byId("copy-job").textContent = "Copy ID"; }, 1800); } catch { error("Copy is unavailable in this browser. Select the job ID shown below."); } });
byId("close-evidence").addEventListener("click", () => byId("evidence-dialog").close());
byId("evidence-dialog").addEventListener("click", (event) => { if (event.target === byId("evidence-dialog")) byId("evidence-dialog").close(); });

async function checkHealth() {
  try {
    const response = await fetch("/health", { cache: "no-store" });
    if (!response.ok) throw new Error("unavailable");
    const data = await response.json();
    state.limit = data.max_upload_bytes;
    byId("upload-limits").textContent = `MOV video · Up to ${Math.round(state.limit / 1024 / 1024)} MB`;
    byId("service-state").className = "service-indicator online";
    byId("service-state").lastElementChild.textContent = "Service online";
    byId("test-notice").hidden = !data.test_mode;
    byId("analyzer-notice").hidden = data.analyzer_module_present;
  } catch {
    byId("service-state").className = "service-indicator offline";
    byId("service-state").lastElementChild.textContent = "Service unavailable";
  }
}
checkHealth();
setInterval(checkHealth, 30000);
