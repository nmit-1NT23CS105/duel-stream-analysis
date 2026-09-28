/**
 * Dual-Stream Safety Hub - Full-Featured Mobile Controller
 * Complete feature parity with desktop workstation interface
 */

// DOM Elements - Hero & Header
const riskLevel = document.getElementById("riskLevel");
const riskScore = document.getElementById("riskScore");
const voiceToggleBtn = document.getElementById("voiceToggleBtn");

// DOM Elements - Streams & Health
const outsideStreamImg = document.getElementById("outsideStreamImg");
const insideStreamImg = document.getElementById("insideStreamImg");
const outsideStreamBadge = document.getElementById("outsideStreamBadge");
const insideStreamBadge = document.getElementById("insideStreamBadge");
const outsideHealth = document.getElementById("outsideHealth");
const insideHealth = document.getElementById("insideHealth");

// DOM Elements - Stream Manager & Controls
const configStatus = document.getElementById("configStatus");
const liveModeBtn = document.getElementById("liveModeBtn");
const recordedModeBtn = document.getElementById("recordedModeBtn");
const insideSourceInput = document.getElementById("insideSourceInput");
const outsideSourceInput = document.getElementById("outsideSourceInput");
const startBtn = document.getElementById("startBtn");
const stopBtn = document.getElementById("stopBtn");
const applyConfigBtn = document.getElementById("applyConfigBtn");

// DOM Elements - Uploads
const uploadGrid = document.getElementById("uploadGrid");
const insideUploadInput = document.getElementById("insideUploadInput");
const outsideUploadInput = document.getElementById("outsideUploadInput");
const uploadInsideBtn = document.getElementById("uploadInsideBtn");
const uploadOutsideBtn = document.getElementById("uploadOutsideBtn");

// DOM Elements - Validation
const validationPanel = document.getElementById("validationPanel");
const insideValidationSummary = document.getElementById("insideValidationSummary");
const outsideValidationSummary = document.getElementById("outsideValidationSummary");
const insideValidationMeta = document.getElementById("insideValidationMeta");
const outsideValidationMeta = document.getElementById("outsideValidationMeta");
const validationWarnings = document.getElementById("validationWarnings");

// DOM Elements - Playback Progress
const playbackSection = document.getElementById("playbackSection");
const insideFileName = document.getElementById("insideFileName");
const outsideFileName = document.getElementById("outsideFileName");
const insideProgressLabel = document.getElementById("insideProgressLabel");
const outsideProgressLabel = document.getElementById("outsideProgressLabel");
const insideProgressBar = document.getElementById("insideProgressBar");
const outsideProgressBar = document.getElementById("outsideProgressBar");

// DOM Elements - All 12 Metrics
const driverStatus = document.getElementById("driverStatus");
const driverNote = document.getElementById("driverNote");
const modeValue = document.getElementById("modeValue");
const modeNote = document.getElementById("modeNote");
const earValue = document.getElementById("earValue");
const phoneUsageValue = document.getElementById("phoneUsageValue");
const phoneUsageNote = document.getElementById("phoneUsageNote");
const seatbeltValue = document.getElementById("seatbeltValue");
const seatbeltNote = document.getElementById("seatbeltNote");
const vehicleCount = document.getElementById("vehicleCount");
const trafficLevel = document.getElementById("trafficLevel");
const laneStatusValue = document.getElementById("laneStatusValue");
const laneStatusNote = document.getElementById("laneStatusNote");
const headPoseValue = document.getElementById("headPoseValue");
const headPoseNote = document.getElementById("headPoseNote");
const perclosValue = document.getElementById("perclosValue");
const speedEstimateValue = document.getElementById("speedEstimateValue");
const aggressiveRiskValue = document.getElementById("aggressiveRiskValue");
const aggressiveRiskNote = document.getElementById("aggressiveRiskNote");
const fpsValue = document.getElementById("fpsValue");

// DOM Elements - AI Reasoning & Alerts
const reasonsList = document.getElementById("reasonsList");
const eventsList = document.getElementById("eventsList");

// Internal State
let selectedMode = "live";
let activeMode = "live";
let processingEnabled = false;
let hasPendingConfig = false;
let latestValidation = null;

// Voice Alert System
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

// Mobile Tab / Section Navigation
function setupTabNavigation() {
  const topNavBtns = document.querySelectorAll(".section-nav-btn");
  const bottomNavTabs = document.querySelectorAll(".nav-tab");
  const sections = document.querySelectorAll(".mobile-section");

  function activateSection(targetId) {
    sections.forEach((sec) => {
      sec.classList.toggle("active", sec.id === targetId);
    });
    topNavBtns.forEach((btn) => {
      btn.classList.toggle("active", btn.getAttribute("data-target") === targetId);
    });
    bottomNavTabs.forEach((tab) => {
      tab.classList.toggle("active", tab.getAttribute("data-target") === targetId);
    });
    window.scrollTo({ top: 0, behavior: "smooth" });
  }

  topNavBtns.forEach((btn) => {
    btn.addEventListener("click", () => {
      activateSection(btn.getAttribute("data-target"));
    });
  });

  bottomNavTabs.forEach((tab) => {
    tab.addEventListener("click", () => {
      activateSection(tab.getAttribute("data-target"));
    });
  });
}

// UI State Setters
function setRiskPill(level) {
  if (!riskLevel) return;
  riskLevel.textContent = level;
  riskLevel.className = `pill ${String(level).toLowerCase()}`;
}

function setSelectedModeUI(mode) {
  selectedMode = mode;
  if (liveModeBtn) liveModeBtn.classList.toggle("active", mode === "live");
  if (recordedModeBtn) recordedModeBtn.classList.toggle("active", mode === "recorded");
  if (uploadGrid) uploadGrid.classList.toggle("hidden", mode !== "recorded");

  if (mode !== "recorded") {
    if (validationPanel) validationPanel.classList.add("hidden");
  } else if (latestValidation) {
    renderValidation(latestValidation, mode);
  }
}

function setActiveModeUI(mode) {
  activeMode = mode;
  if (modeValue) modeValue.textContent = mode === "live" ? "Live" : "Recorded";
  if (processingEnabled && modeNote) {
    modeNote.textContent = mode === "live" ? "Camera sources active" : "Uploaded or local videos active";
  }
  if (playbackSection) playbackSection.classList.toggle("hidden", mode !== "recorded");
}

function setStreamBadges(mode, enabled) {
  const label = enabled ? (mode === "live" ? "Live" : "Recorded") : "Stopped";
  const className = enabled ? mode : "stopped";

  if (insideStreamBadge) {
    insideStreamBadge.textContent = label;
    insideStreamBadge.className = `stream-badge ${className}`;
  }
  if (outsideStreamBadge) {
    outsideStreamBadge.textContent = label;
    outsideStreamBadge.className = `stream-badge ${className}`;
  }
}

function setHealthIndicator(element, status) {
  if (!element) return;
  const healthLabel = element.querySelector(".health-label");
  element.className = `stream-health ${status}`;
  if (healthLabel) {
    if (status === "online") healthLabel.textContent = "Online";
    else if (status === "paused") healthLabel.textContent = "Paused";
    else if (status === "idle") healthLabel.textContent = "Idle";
    else healthLabel.textContent = "Offline";
  }
}

function setProcessingState(enabled) {
  processingEnabled = enabled;
  if (startBtn) {
    startBtn.disabled = enabled;
    startBtn.style.opacity = enabled ? "0.5" : "1";
  }
  if (stopBtn) {
    stopBtn.disabled = !enabled;
    stopBtn.style.opacity = enabled ? "1" : "0.5";
  }
  if (modeNote) {
    modeNote.textContent = enabled
      ? (activeMode === "live" ? "Camera sources active" : "Uploaded or local videos active")
      : "Click Start to begin analysis";
  }
  setStreamBadges(activeMode, enabled);
}

function setStatus(message, isError = false, tone = "info") {
  if (!configStatus) return;
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
  if (!reasonsList) return;
  reasonsList.innerHTML = "";
  if (!reasons || !reasons.length) {
    const item = document.createElement("li");
    item.textContent = "Awaiting frames...";
    reasonsList.appendChild(item);
    return;
  }
  reasons.forEach((reason) => {
    const item = document.createElement("li");
    item.textContent = reason;
    reasonsList.appendChild(item);
  });
}

function renderRecentEvents(events) {
  if (!eventsList) return;
  eventsList.innerHTML = "";

  if (!events || !events.length) {
    const item = document.createElement("li");
    item.className = "event-mobile-item";
    item.innerHTML = `
      <strong>No saved alerts yet</strong>
      <p style="font-size:0.72rem; color:var(--text-muted);">High and critical incidents will appear here once logged.</p>
    `;
    eventsList.appendChild(item);
    return;
  }

  events.forEach((event) => {
    const item = document.createElement("li");
    item.className = "event-mobile-item";

    const createdAt = new Date(event.created_at);
    const timeLabel = Number.isNaN(createdAt.getTime())
      ? event.created_at
      : createdAt.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" });

    const summary = `${event.inside_status} | ${event.outside_traffic} traffic`;
    const reason = (event.reasons && event.reasons[0]) || "No explanation saved";

    item.innerHTML = `
      <div class="event-item-top">
        <span class="event-time">${timeLabel}</span>
        <span class="pill ${String(event.risk_level || "low").toLowerCase()}">${event.risk_level}</span>
      </div>
      <div class="event-summary">${summary}</div>
      <div class="event-reason">${reason}</div>
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
  return `Scene: ${validation.scene} | Conf: ${Number(validation.confidence || 0).toFixed(2)} | Frames: ${validation.sampled_frames}`;
}

function renderValidation(bundle, mode = selectedMode) {
  if (!validationPanel) return;
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
  if (insideValidationSummary) insideValidationSummary.textContent = inside.summary || "No validation yet";
  if (outsideValidationSummary) outsideValidationSummary.textContent = outside.summary || "No validation yet";
  if (insideValidationMeta) insideValidationMeta.textContent = formatValidationMeta(inside, "inside");
  if (outsideValidationMeta) outsideValidationMeta.textContent = formatValidationMeta(outside, "outside");

  if (validationWarnings) {
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
}

function renderPlayback(playback, mode) {
  if (!playbackSection) return;
  if (mode !== "recorded" || !playback) {
    playbackSection.classList.add("hidden");
    return;
  }

  playbackSection.classList.remove("hidden");
  const inside = playback.inside || {};
  const outside = playback.outside || {};

  const insidePct = Math.round(Number(inside.progress_ratio || 0) * 100);
  const outsidePct = Math.round(Number(outside.progress_ratio || 0) * 100);

  if (insideFileName) insideFileName.textContent = inside.filename || "No inside video";
  if (outsideFileName) outsideFileName.textContent = outside.filename || "No outside video";
  if (insideProgressLabel) insideProgressLabel.textContent = `${insidePct}%`;
  if (outsideProgressLabel) outsideProgressLabel.textContent = `${outsidePct}%`;
  if (insideProgressBar) insideProgressBar.style.width = `${insidePct}%`;
  if (outsideProgressBar) outsideProgressBar.style.width = `${outsidePct}%`;
}

function renderStreamHealth(inputConfig, inside, outside) {
  if (!insideHealth || !outsideHealth) return;
  if (!inputConfig || !inputConfig.enabled) {
    setHealthIndicator(insideHealth, "idle");
    setHealthIndicator(outsideHealth, "idle");
    return;
  }
  setHealthIndicator(insideHealth, inside.available ? "online" : "offline");
  setHealthIndicator(outsideHealth, outside.available ? "online" : "offline");
}

// API Polling Functions
async function fetchState() {
  try {
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
    if (riskScore) riskScore.textContent = data.fused.score;
    setActiveModeUI(data.input.mode);
    if (!hasPendingConfig) {
      setSelectedModeUI(data.input.mode);
    }
    setProcessingState(data.input.enabled);

    // Metric 1: Driver State
    if (driverStatus) driverStatus.textContent = data.inside.status;
    const phoneLabel = data.inside.phone_detected
      ? `Phone (${Number(data.inside.phone_duration_sec || 0).toFixed(1)}s)`
      : "Phone clear";
    if (driverNote) {
      driverNote.textContent = `${data.inside.confidence_note} | ${phoneLabel} | MAR ${Number(data.inside.mar || 0).toFixed(2)} | Attn ${Number(data.inside.attention_score || 0).toFixed(2)}`;
    }

    // Metric 2: EAR
    if (earValue) earValue.textContent = Number(data.inside.ear).toFixed(2);

    // Metric 3: Phone Use
    if (phoneUsageValue) phoneUsageValue.textContent = data.inside.phone_detected ? "Detected" : "Clear";
    const pDur = Number(data.inside.phone_duration_sec || 0).toFixed(1);
    if (phoneUsageNote) {
      phoneUsageNote.textContent = data.inside.phone_detected
        ? `Sustained ${pDur}s (conf ${Number(data.inside.phone_confidence || 0).toFixed(2)})`
        : "No handheld phone seen";
    }

    // Metric 4: Seatbelt
    const sbStatus = data.inside.seatbelt_status || "Unknown";
    if (seatbeltValue) {
      if (sbStatus === "Fastened") {
        seatbeltValue.textContent = "Fastened (Worn)";
        seatbeltValue.style.color = "#10b981";
        if (seatbeltNote) seatbeltNote.textContent = "Safety restraint secured";
      } else if (sbStatus === "Unfastened") {
        seatbeltValue.textContent = "No Seatbelt";
        seatbeltValue.style.color = "#ef4444";
        if (seatbeltNote) seatbeltNote.textContent = "Seatbelt NOT fastened";
      } else {
        seatbeltValue.textContent = sbStatus;
        seatbeltValue.style.color = "#94a3b8";
        if (seatbeltNote) seatbeltNote.textContent = "Restraint status unconfirmed";
      }
    }

    // Metric 5: Lane Position
    const laneStatus = data.outside.lane_status || "Unmarked";
    if (laneStatusValue) {
      laneStatusValue.textContent = laneStatus;
      if (laneStatus === "Centered") {
        laneStatusValue.style.color = "#10b981";
        if (laneStatusNote) laneStatusNote.textContent = `Offset ${Number(data.outside.lane_offset || 0).toFixed(2)}`;
      } else if (laneStatus.includes("Drift") || laneStatus.includes("Weaving") || laneStatus.includes("Sudden")) {
        laneStatusValue.style.color = "#f59e0b";
        if (laneStatusNote) laneStatusNote.textContent = `${laneStatus} (${Number(data.outside.lane_offset || 0).toFixed(2)})`;
      } else {
        laneStatusValue.style.color = "#94a3b8";
        if (laneStatusNote) laneStatusNote.textContent = "Road markings unconfirmed";
      }
    }

    // Metric 6: Vehicles Now
    if (vehicleCount) vehicleCount.textContent = data.outside.vehicle_count;
    if (trafficLevel) trafficLevel.textContent = `${data.outside.traffic_level} traffic | close ${data.outside.close_vehicle_count || 0}`;

    // Metric 7: Head Pose
    if (headPoseValue) {
      const pose = data.inside.head_pose_direction || "Forward";
      headPoseValue.textContent = pose;
      headPoseValue.style.color = pose === "Forward" ? "#10b981" : (pose === "Unavailable" ? "#94a3b8" : "#f59e0b");
      if (headPoseNote) headPoseNote.textContent = `Gaze direction: ${pose}`;
    }

    // Metric 8: PERCLOS
    if (perclosValue) {
      const pVal = Number(data.inside.perclos || 0).toFixed(1);
      perclosValue.textContent = `${pVal}%`;
      perclosValue.style.color = Number(pVal) >= 25 ? "#ef4444" : "#10b981";
    }

    // Metric 9: Relative Speed
    if (speedEstimateValue) {
      speedEstimateValue.textContent = data.outside.relative_speed_estimate || "Stable";
    }

    // Metric 10: Aggressive Risk
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

    // Metric 11: FPS
    if (fpsValue) {
      fpsValue.textContent = `${Number(data.inside_fps).toFixed(1)} / ${Number(data.outside_fps).toFixed(1)}`;
    }

    // AI Reasoning
    renderReasons(data.fused.reasons);
    renderPlayback(data.playback, data.input.mode);
    renderStreamHealth(data.input, data.inside, data.outside);
  } catch (err) {
    console.warn("fetchState error", err);
  }
}

async function fetchInputConfig() {
  try {
    const response = await fetch("/api/input-config");
    const data = await response.json();
    const isEditing = document.activeElement === insideSourceInput || document.activeElement === outsideSourceInput;
    if (!hasPendingConfig && !isEditing) {
      if (insideSourceInput) insideSourceInput.value = data.inside_source || "";
      if (outsideSourceInput) outsideSourceInput.value = data.outside_source || "";
      setSelectedModeUI(data.mode || "live");
    }
    setActiveModeUI(data.mode || "live");
    setProcessingState(data.enabled !== false);
    renderValidation(data.validation, selectedMode);
  } catch (err) {
    console.warn("fetchInputConfig error", err);
  }
}

async function fetchRecentEvents() {
  try {
    const response = await fetch("/api/events?limit=4");
    const data = await response.json();
    renderRecentEvents(data.events || []);
  } catch (err) {
    console.warn("fetchRecentEvents error", err);
  }
}

// User Actions: Apply Config, Controls & Upload
async function applyConfig() {
  setStatus("Updating input mode...");
  try {
    const response = await fetch("/api/input-config", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        mode: selectedMode,
        inside_source: insideSourceInput ? insideSourceInput.value.trim() : "",
        outside_source: outsideSourceInput ? outsideSourceInput.value.trim() : "",
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
    if (insideSourceInput) insideSourceInput.value = data.config.inside_source;
    if (outsideSourceInput) outsideSourceInput.value = data.config.outside_source;
    renderValidation(data.config.validation, data.config.mode);
    if (data.config.validation?.warnings?.length) {
      setStatus(`Mode updated. Note: ${data.config.validation.warnings[0]}`, false, "warn");
      return;
    }
    setStatus("Input mode updated successfully");
  } catch (err) {
    setStatus("Failed to communicate with server", true);
  }
}

async function sendControl(action) {
  try {
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
  } catch (err) {
    setStatus("Control request failed", true);
  }
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

    if (streamName === "inside") {
      if (insideSourceInput) insideSourceInput.value = data.path;
      if (outsideSourceInput && isLiveCameraIndex(outsideSourceInput.value)) {
        outsideSourceInput.value = "";
      }
    } else {
      if (outsideSourceInput) outsideSourceInput.value = data.path;
      if (insideSourceInput && isLiveCameraIndex(insideSourceInput.value)) {
        insideSourceInput.value = "";
      }
    }
    hasPendingConfig = true;
    setSelectedModeUI("recorded");
    renderValidation(data.bundle, "recorded");

    const warn = data.validation?.warning;
    if (warn) {
      setStatus(`Uploaded. Warning: ${warn}`, false, "warn");
    } else {
      setStatus(`${streamName === "inside" ? "Inside" : "Outside"} video ready. Click Apply.`);
    }
  };

  xhr.onerror = () => {
    setStatus(`Upload network error`, true);
  };

  xhr.send(file);
}

// Event Listeners Initialization
function setupEventListeners() {
  if (liveModeBtn) {
    liveModeBtn.addEventListener("click", () => {
      hasPendingConfig = true;
      setSelectedModeUI("live");
      if (insideSourceInput && !insideSourceInput.value.trim()) insideSourceInput.value = "0";
      if (outsideSourceInput && !outsideSourceInput.value.trim()) outsideSourceInput.value = "1";
      setStatus("Selected live mode. Click Apply to activate.");
    });
  }

  if (recordedModeBtn) {
    recordedModeBtn.addEventListener("click", () => {
      hasPendingConfig = true;
      setSelectedModeUI("recorded");
      if (insideSourceInput && isLiveCameraIndex(insideSourceInput.value)) insideSourceInput.value = "";
      if (outsideSourceInput && isLiveCameraIndex(outsideSourceInput.value)) outsideSourceInput.value = "";
      setStatus("Selected recorded mode. Choose video files or enter paths, then click Apply.");
    });
  }

  if (startBtn) startBtn.addEventListener("click", () => sendControl("start"));
  if (stopBtn) stopBtn.addEventListener("click", () => sendControl("stop"));
  if (applyConfigBtn) applyConfigBtn.addEventListener("click", applyConfig);

  if (uploadInsideBtn && insideUploadInput) {
    uploadInsideBtn.addEventListener("click", () => uploadRecording("inside", insideUploadInput));
  }
  if (uploadOutsideBtn && outsideUploadInput) {
    uploadOutsideBtn.addEventListener("click", () => uploadRecording("outside", outsideUploadInput));
  }

  if (insideSourceInput) insideSourceInput.addEventListener("input", () => { hasPendingConfig = true; });
  if (outsideSourceInput) outsideSourceInput.addEventListener("input", () => { hasPendingConfig = true; });
}

// Lifecycle Init
document.addEventListener("DOMContentLoaded", () => {
  setupTabNavigation();
  setupEventListeners();
  fetchInputConfig();
  fetchState();
  fetchRecentEvents();

  setInterval(fetchState, 700);
  setInterval(fetchRecentEvents, 3500);

  // Register PWA Service Worker
  if ("serviceWorker" in navigator) {
    navigator.serviceWorker.register("/static/mobile/sw.js").catch(() => {});
  }
});
