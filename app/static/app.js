const riskLevel = document.getElementById("riskLevel");
const riskScore = document.getElementById("riskScore");
const modeValue = document.getElementById("modeValue");
const modeNote = document.getElementById("modeNote");
const driverStatus = document.getElementById("driverStatus");
const driverNote = document.getElementById("driverNote");
const earValue = document.getElementById("earValue");
const phoneUsageValue = document.getElementById("phoneUsageValue");
const phoneUsageNote = document.getElementById("phoneUsageNote");
const seatbeltValue = document.getElementById("seatbeltValue");
const seatbeltNote = document.getElementById("seatbeltNote");
const laneStatusValue = document.getElementById("laneStatusValue");
const laneStatusNote = document.getElementById("laneStatusNote");
const vehicleCount = document.getElementById("vehicleCount");
const trafficLevel = document.getElementById("trafficLevel");
const fpsValue = document.getElementById("fpsValue");
const reasonsList = document.getElementById("reasonsList");
const playbackSection = document.getElementById("playbackSection");
const insideFileName = document.getElementById("insideFileName");
const outsideFileName = document.getElementById("outsideFileName");
const insideProgressLabel = document.getElementById("insideProgressLabel");
const outsideProgressLabel = document.getElementById("outsideProgressLabel");
const insideProgressBar = document.getElementById("insideProgressBar");
const outsideProgressBar = document.getElementById("outsideProgressBar");
const insideStreamBadge = document.getElementById("insideStreamBadge");
const outsideStreamBadge = document.getElementById("outsideStreamBadge");
const insideHealth = document.getElementById("insideHealth");
const outsideHealth = document.getElementById("outsideHealth");
const eventsList = document.getElementById("eventsList");
const validationPanel = document.getElementById("validationPanel");
const insideValidationSummary = document.getElementById("insideValidationSummary");
const outsideValidationSummary = document.getElementById("outsideValidationSummary");
const insideValidationMeta = document.getElementById("insideValidationMeta");
const outsideValidationMeta = document.getElementById("outsideValidationMeta");
const validationWarnings = document.getElementById("validationWarnings");

const headPoseValue = document.getElementById("headPoseValue");
const headPoseNote = document.getElementById("headPoseNote");
const perclosValue = document.getElementById("perclosValue");
const speedEstimateValue = document.getElementById("speedEstimateValue");
const aggressiveRiskValue = document.getElementById("aggressiveRiskValue");
const aggressiveRiskNote = document.getElementById("aggressiveRiskNote");
const voiceToggleBtn = document.getElementById("voiceToggleBtn");

let voiceEnabled = true;
let lastSpokenTime = 0;
let lastSpokenReason = "";

function speakAlert(text) {
  if (!voiceEnabled || !("speechSynthesis" in window)) return;
  const now = Date.now();
  if (now - lastSpokenTime < 8000 && text === lastSpokenReason) return;
  if (now - lastSpokenTime < 4500) return;

  try {
    window.speechSynthesis.cancel();
    const utterance = new SpeechSynthesisUtterance(text);
    utterance.rate = 1.05;
    utterance.pitch = 1.0;
    utterance.volume = 1.0;
    window.speechSynthesis.speak(utterance);
    lastSpokenTime = now;
    lastSpokenReason = text;
  } catch (err) {
    console.warn("Voice speech error", err);
  }
}

if (voiceToggleBtn) {
  voiceToggleBtn.addEventListener("click", () => {
    voiceEnabled = !voiceEnabled;
    voiceToggleBtn.textContent = voiceEnabled ? "🔊 Voice: ON" : "🔇 Voice: OFF";
    voiceToggleBtn.style.opacity = voiceEnabled ? "1" : "0.6";
  });
}

const liveModeBtn = document.getElementById("liveModeBtn");
const recordedModeBtn = document.getElementById("recordedModeBtn");
const startBtn = document.getElementById("startBtn");
const stopBtn = document.getElementById("stopBtn");
const applyConfigBtn = document.getElementById("applyConfigBtn");
const insideSourceInput = document.getElementById("insideSourceInput");
const outsideSourceInput = document.getElementById("outsideSourceInput");
const insideUploadInput = document.getElementById("insideUploadInput");
const outsideUploadInput = document.getElementById("outsideUploadInput");
const uploadInsideBtn = document.getElementById("uploadInsideBtn");
const uploadOutsideBtn = document.getElementById("uploadOutsideBtn");
const configStatus = document.getElementById("configStatus");
const uploadGrid = document.getElementById("uploadGrid");

let selectedMode = "live";
let activeMode = "live";
let processingEnabled = false;
let hasPendingConfig = false;
let latestValidation = null;

function setRiskPill(level) {
  riskLevel.textContent = level;
  riskLevel.className = `pill ${level.toLowerCase()}`;
}

function setSelectedModeUI(mode) {
  selectedMode = mode;
  liveModeBtn.classList.toggle("active", mode === "live");
  recordedModeBtn.classList.toggle("active", mode === "recorded");
  uploadGrid.classList.toggle("hidden", mode !== "recorded");
  if (mode !== "recorded") {
    validationPanel.classList.add("hidden");
  } else if (latestValidation) {
    renderValidation(latestValidation, mode);
  }
}

function setActiveModeUI(mode) {
  activeMode = mode;
  modeValue.textContent = mode === "live" ? "Live" : "Recorded";
  if (processingEnabled) {
    modeNote.textContent = mode === "live" ? "Camera sources active" : "Uploaded or local videos active";
  }
  playbackSection.classList.toggle("hidden", mode !== "recorded");
}

function setStreamBadges(mode, enabled) {
  const label = enabled ? (mode === "live" ? "Live" : "Recorded") : "Stopped";
  const className = enabled ? mode : "stopped";

  insideStreamBadge.textContent = label;
  outsideStreamBadge.textContent = label;
  insideStreamBadge.className = `stream-badge ${className}`;
  outsideStreamBadge.className = `stream-badge ${className}`;
}

function setHealthIndicator(element, status) {
  const healthLabel = element.querySelector(".health-label");
  element.className = `stream-health ${status}`;
  if (status === "online") {
    healthLabel.textContent = "Online";
  } else if (status === "paused") {
    healthLabel.textContent = "Paused";
  } else if (status === "idle") {
    healthLabel.textContent = "Idle";
  } else {
    healthLabel.textContent = "Offline";
  }
}

function setProcessingState(enabled) {
  processingEnabled = enabled;
  startBtn.disabled = enabled;
  stopBtn.disabled = !enabled;
  startBtn.style.opacity = enabled ? "0.55" : "1";
  stopBtn.style.opacity = enabled ? "1" : "0.55";
  if (!enabled) {
    modeNote.textContent = "Click Start to begin analysis";
  } else {
    modeNote.textContent = activeMode === "live" ? "Camera sources active" : "Uploaded or local videos active";
  }
  setStreamBadges(activeMode, enabled);
}

function setStatus(message, isError = false, tone = "info") {
  configStatus.textContent = message;
  configStatus.className = "status-chip";
  if (isError || tone === "error") {
    configStatus.classList.add("error");
  } else if (tone === "warn") {
    configStatus.classList.add("warn");
  }
}

function isLiveCameraIndex(value) {
  return /^\d+$/.test(value.trim());
}

function renderReasons(reasons) {
  reasonsList.innerHTML = "";
  reasons.forEach((reason) => {
    const item = document.createElement("li");
    item.textContent = reason;
    reasonsList.appendChild(item);
  });
}

function renderRecentEvents(events) {
  eventsList.innerHTML = "";

  if (!events || !events.length) {
    const item = document.createElement("li");
    item.className = "event-item";
    item.innerHTML = `
      <strong>No saved alerts yet</strong>
      <p>High and critical incidents will appear here once the system starts logging them.</p>
    `;
    eventsList.appendChild(item);
    return;
  }

  events.forEach((event) => {
    const item = document.createElement("li");
    item.className = "event-item";

    const createdAt = new Date(event.created_at);
    const timeLabel = Number.isNaN(createdAt.getTime())
      ? event.created_at
      : createdAt.toLocaleString();

    const summary = `${event.inside_status} | ${event.outside_traffic} traffic`;
    const reason = (event.reasons && event.reasons[0]) || "No explanation saved";

    item.innerHTML = `
      <div class="section-head">
        <strong>${timeLabel}</strong>
        <span class="pill ${String(event.risk_level || "low").toLowerCase()}">${event.risk_level}</span>
      </div>
      <p>${summary}</p>
      <small>${reason}</small>
    `;
    eventsList.appendChild(item);
  });
}

function normalizeValidation(bundle) {
  return bundle || {
    inside: { scene: "unknown", confidence: 0, summary: "No validation yet", warning: "" },
    outside: { scene: "unknown", confidence: 0, summary: "No validation yet", warning: "" },
    warnings: [],
  };
}

function formatValidationMeta(validation, streamName) {
  if (!validation || !validation.sampled_frames) {
    return streamName === "inside"
      ? "Upload a cabin video to inspect its scene type."
      : "Upload a road video to inspect its scene type.";
  }
  return `Scene: ${validation.scene} | Confidence: ${Number(validation.confidence || 0).toFixed(2)} | Sampled frames: ${validation.sampled_frames}`;
}

function renderValidation(bundle, mode = selectedMode) {
  latestValidation = normalizeValidation(bundle);
  const { inside, outside, warnings } = latestValidation;

  const hasContent = Boolean(
    (inside && inside.sampled_frames) ||
    (outside && outside.sampled_frames) ||
    (warnings && warnings.length),
  );

  if (mode !== "recorded" || !hasContent) {
    validationPanel.classList.add("hidden");
    return;
  }

  validationPanel.classList.remove("hidden");
  insideValidationSummary.textContent = inside.summary || "No validation yet";
  outsideValidationSummary.textContent = outside.summary || "No validation yet";
  insideValidationMeta.textContent = formatValidationMeta(inside, "inside");
  outsideValidationMeta.textContent = formatValidationMeta(outside, "outside");

  validationWarnings.innerHTML = "";
  if (warnings && warnings.length) {
    validationWarnings.classList.remove("hidden");
    warnings.forEach((warning) => {
      const item = document.createElement("li");
      item.textContent = warning;
      validationWarnings.appendChild(item);
    });
  } else {
    validationWarnings.classList.add("hidden");
  }
}

function renderPlayback(playback, mode) {
  if (mode !== "recorded") {
    insideFileName.textContent = "No inside video";
    outsideFileName.textContent = "No outside video";
    insideProgressLabel.textContent = "0%";
    outsideProgressLabel.textContent = "0%";
    insideProgressBar.style.width = "0%";
    outsideProgressBar.style.width = "0%";
    return;
  }

  const insidePct = Number(playback.inside_progress || 0).toFixed(1);
  const outsidePct = Number(playback.outside_progress || 0).toFixed(1);
  insideFileName.textContent = playback.inside_name || "No inside video";
  outsideFileName.textContent = playback.outside_name || "No outside video";
  insideProgressLabel.textContent = `${insidePct}%`;
  outsideProgressLabel.textContent = `${outsidePct}%`;
  insideProgressBar.style.width = `${insidePct}%`;
  outsideProgressBar.style.width = `${outsidePct}%`;
}

function renderStreamHealth(input, inside, outside) {
  const insideStatus = !input.enabled ? "idle" : (inside.available ? "online" : "offline");
  const outsideStatus = !input.enabled ? "idle" : (outside.available ? "online" : "offline");
  setHealthIndicator(insideHealth, insideStatus);
  setHealthIndicator(outsideHealth, outsideStatus);
}

async function fetchState() {
  const response = await fetch("/api/state");
  const data = await response.json();

  // Spoken voice warnings (P2-FR09)
  if (data.input.enabled) {
    if (data.fused.level === "Critical") {
      const topReason = (data.fused.reasons && data.fused.reasons[0]) || "Critical collision or fatigue danger detected";
      speakAlert(`Critical Warning: ${topReason}`);
    } else if (data.fused.level === "High") {
      const topReason = (data.fused.reasons && data.fused.reasons[0]) || "Elevated driving hazard detected";
      speakAlert(`Warning: ${topReason}`);
    }
  }

  setRiskPill(data.fused.level);
  riskScore.textContent = data.fused.score;
  setActiveModeUI(data.input.mode);
  if (!hasPendingConfig) {
    setSelectedModeUI(data.input.mode);
  }
  setProcessingState(data.input.enabled);
  driverStatus.textContent = data.inside.status;
  const phoneLabel = data.inside.phone_detected
    ? `Phone ${Number(data.inside.phone_confidence || 0).toFixed(2)} (${Number(data.inside.phone_duration_sec || 0).toFixed(1)}s)`
    : "Phone clear";
  driverNote.textContent = `${data.inside.confidence_note} | ${phoneLabel} | MAR ${Number(data.inside.mar || 0).toFixed(2)} | Attn ${Number(data.inside.attention_score || 0).toFixed(2)}`;
  earValue.textContent = Number(data.inside.ear).toFixed(2);
  phoneUsageValue.textContent = data.inside.phone_detected ? "Detected" : "Clear";
  const pDur = Number(data.inside.phone_duration_sec || 0).toFixed(1);
  phoneUsageNote.textContent = data.inside.phone_detected
    ? `Sustained ${pDur}s (conf ${Number(data.inside.phone_confidence || 0).toFixed(2)})`
    : "No handheld phone seen";

  if (headPoseValue) {
    const pose = data.inside.head_pose_direction || "Forward";
    headPoseValue.textContent = pose;
    headPoseValue.style.color = pose === "Forward" ? "#10b981" : (pose === "Unavailable" ? "#94a3b8" : "#f59e0b");
    if (headPoseNote) headPoseNote.textContent = `Gaze: ${pose}`;
  }

  if (perclosValue) {
    const pVal = Number(data.inside.perclos || 0).toFixed(1);
    perclosValue.textContent = `${pVal}%`;
    perclosValue.style.color = Number(pVal) >= 25 ? "#ef4444" : "#10b981";
  }

  const sbStatus = data.inside.seatbelt_status || "Unknown";
  if (seatbeltValue) {
    if (sbStatus === "Fastened") {
      seatbeltValue.textContent = "Fastened (Worn)";
      seatbeltValue.style.color = "#10b981";
      seatbeltNote.textContent = "Safety restraint fastened";
    } else if (sbStatus === "Unfastened") {
      seatbeltValue.textContent = "No Seatbelt";
      seatbeltValue.style.color = "#ef4444";
      seatbeltNote.textContent = "Seatbelt NOT fastened";
    } else {
      seatbeltValue.textContent = sbStatus;
      seatbeltValue.style.color = "#94a3b8";
      seatbeltNote.textContent = "Restraint status unconfirmed";
    }
  }

  const laneStatus = data.outside.lane_status || "Unmarked";
  if (laneStatusValue) {
    laneStatusValue.textContent = laneStatus;
    if (laneStatus === "Centered") {
      laneStatusValue.style.color = "#10b981";
      laneStatusNote.textContent = `Offset ${Number(data.outside.lane_offset || 0).toFixed(2)}`;
    } else if (laneStatus.includes("Drift") || laneStatus.includes("Weaving") || laneStatus.includes("Sudden")) {
      laneStatusValue.style.color = "#f59e0b";
      laneStatusNote.textContent = `${laneStatus} (${Number(data.outside.lane_offset || 0).toFixed(2)})`;
    } else {
      laneStatusValue.style.color = "#94a3b8";
      laneStatusNote.textContent = "Road markings unconfirmed";
    }
  }

  if (speedEstimateValue) {
    speedEstimateValue.textContent = data.outside.relative_speed_estimate || "Stable";
  }

  if (aggressiveRiskValue) {
    const aggScore = data.outside.aggressive_driving_score || 0;
    aggressiveRiskValue.textContent = `${aggScore} / 100`;
    aggressiveRiskValue.style.color = aggScore >= 50 ? "#ef4444" : (aggScore > 0 ? "#f59e0b" : "#10b981");
    if (aggressiveRiskNote) {
      aggressiveRiskNote.textContent = data.outside.weaving_detected
        ? "Weaving active"
        : (data.outside.sudden_lane_change ? "Sudden shift" : "Maneuvers stable");
    }
  }

  vehicleCount.textContent = data.outside.vehicle_count;
  trafficLevel.textContent = `${data.outside.traffic_level} traffic | close ${data.outside.close_vehicle_count || 0}`;
  fpsValue.textContent = `${Number(data.inside_fps).toFixed(1)} / ${Number(data.outside_fps).toFixed(1)}`;
  renderReasons(data.fused.reasons);
  renderPlayback(data.playback, data.input.mode);
  renderStreamHealth(data.input, data.inside, data.outside);
}

async function fetchInputConfig() {
  const response = await fetch("/api/input-config");
  const data = await response.json();
  const isEditing = document.activeElement === insideSourceInput || document.activeElement === outsideSourceInput;
  if (!hasPendingConfig && !isEditing) {
    insideSourceInput.value = data.inside_source || "";
    outsideSourceInput.value = data.outside_source || "";
    setSelectedModeUI(data.mode || "live");
  }
  setActiveModeUI(data.mode || "live");
  setProcessingState(data.enabled !== false);
  renderValidation(data.validation, selectedMode);
}

async function fetchRecentEvents() {
  const response = await fetch("/api/events?limit=4");
  const data = await response.json();
  renderRecentEvents(data.events || []);
}

async function applyConfig() {
  setStatus("Updating input mode...");
  const response = await fetch("/api/input-config", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      mode: selectedMode,
      inside_source: insideSourceInput.value.trim(),
      outside_source: outsideSourceInput.value.trim(),
    }),
  });
  const data = await response.json();
  if (!response.ok) {
    setStatus(data.error || "Update failed", true);
    return;
  }
  hasPendingConfig = false;
  setSelectedModeUI(data.config.mode);
  setActiveModeUI(data.config.mode);
  setProcessingState(data.config.enabled);
  insideSourceInput.value = data.config.inside_source;
  outsideSourceInput.value = data.config.outside_source;
  renderValidation(data.config.validation, data.config.mode);
  if (data.config.validation?.warnings?.length) {
    setStatus(`Mode updated. Note: ${data.config.validation.warnings[0]}`, false, "warn");
    return;
  }
  setStatus("Input mode updated successfully");
}

async function sendControl(action) {
  const response = await fetch("/api/control", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ action }),
  });
  const data = await response.json();
  if (!response.ok) {
    setStatus(data.error || "Control request failed", true);
    return;
  }
  setActiveModeUI(data.config.mode);
  if (!hasPendingConfig) {
    setSelectedModeUI(data.config.mode);
  }
  setProcessingState(data.config.enabled);
  setStatus(data.message || "Updated");
}

function uploadRecording(streamName, inputElement) {
  const file = inputElement.files[0];
  if (!file) {
    setStatus(`Choose a ${streamName} video first`, true);
    return;
  }

  const fileSizeMB = (file.size / (1024 * 1024)).toFixed(1);
  setStatus(`Uploading ${streamName} video (${fileSizeMB} MB)...`);

  const xhr = new XMLHttpRequest();
  xhr.open("POST", `/api/upload/${streamName}?filename=${encodeURIComponent(file.name)}`, true);
  xhr.setRequestHeader("Content-Type", file.type || "application/octet-stream");

  xhr.upload.onprogress = (event) => {
    if (event.lengthComputable) {
      const percent = Math.round((event.loaded / event.total) * 100);
      setStatus(`Uploading ${streamName} video: ${percent}% (${fileSizeMB} MB)...`);
    }
  };

  xhr.onload = () => {
    let data;
    try {
      data = JSON.parse(xhr.responseText);
    } catch (e) {
      setStatus(`Upload failed: invalid server response`, true);
      return;
    }

    if (xhr.status < 200 || xhr.status >= 300) {
      setStatus(data.error || "Upload failed", true);
      return;
    }

    const label = streamName === "inside" ? "Inside" : "Outside";
    if (streamName === "inside") {
      insideSourceInput.value = data.path;
      if (isLiveCameraIndex(outsideSourceInput.value)) {
        outsideSourceInput.value = "";
      }
    } else {
      outsideSourceInput.value = data.path;
      if (isLiveCameraIndex(insideSourceInput.value)) {
        insideSourceInput.value = "";
      }
    }
    hasPendingConfig = true;
    setSelectedModeUI("recorded");
    renderValidation(data.bundle, "recorded");
    if (data.bundle?.warnings?.length) {
      setStatus(`${label} video uploaded (${fileSizeMB} MB). Advisory: ${data.bundle.warnings[0]}`, false, "warn");
    } else {
      setStatus(`${label} video (${fileSizeMB} MB) uploaded successfully. Click Apply to analyze`);
    }
  };

  xhr.onerror = () => {
    setStatus(`Upload connection error for ${streamName} video`, true);
  };

  xhr.send(file);
}

async function refresh() {
  try {
    await Promise.all([fetchState(), fetchInputConfig(), fetchRecentEvents()]);
  } catch (error) {
    console.error("Dashboard refresh failed", error);
  }
}

liveModeBtn.addEventListener("click", () => {
  hasPendingConfig = true;
  setSelectedModeUI("live");
  if (!insideSourceInput.value || !isLiveCameraIndex(insideSourceInput.value)) {
    insideSourceInput.value = "0";
  }
  if (!outsideSourceInput.value || !isLiveCameraIndex(outsideSourceInput.value)) {
    outsideSourceInput.value = "1";
  }
  setStatus("Live mode selected. Click Apply");
});

recordedModeBtn.addEventListener("click", () => {
  hasPendingConfig = true;
  setSelectedModeUI("recorded");
  if (isLiveCameraIndex(insideSourceInput.value)) {
    insideSourceInput.value = "";
  }
  if (isLiveCameraIndex(outsideSourceInput.value)) {
    outsideSourceInput.value = "";
  }
  setStatus("Recorded mode selected. Choose videos and click Apply");
});

applyConfigBtn.addEventListener("click", async () => {
  try {
    await applyConfig();
  } catch (error) {
    setStatus("Could not update input mode", true);
    console.error(error);
  }
});

startBtn.addEventListener("click", async () => {
  try {
    await sendControl("start");
  } catch (error) {
    setStatus("Could not start processing", true);
    console.error(error);
  }
});

stopBtn.addEventListener("click", async () => {
  try {
    await sendControl("stop");
  } catch (error) {
    setStatus("Could not stop processing", true);
    console.error(error);
  }
});

uploadInsideBtn.addEventListener("click", async () => {
  try {
    await uploadRecording("inside", insideUploadInput);
  } catch (error) {
    setStatus("Inside upload failed", true);
    console.error(error);
  }
});

uploadOutsideBtn.addEventListener("click", async () => {
  try {
    await uploadRecording("outside", outsideUploadInput);
  } catch (error) {
    setStatus("Outside upload failed", true);
    console.error(error);
  }
});

insideSourceInput.addEventListener("input", () => {
  hasPendingConfig = true;
});

outsideSourceInput.addEventListener("input", () => {
  hasPendingConfig = true;
});

refresh();
setInterval(refresh, 1500);
