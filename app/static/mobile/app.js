/**
 * DriveGuardian - Mobile In-Car Driver Companion
 * High-performance, touch-first driver safety monitor
 */

// State
let eventSource = null;
let voiceEnabled = true;
let vibrationEnabled = true;
let lastSpokenText = "";
let lastSpokenTime = 0;
const VOICE_COOLDOWN_MS = 6000;
let currentTab = "dashboard";

// DOM Elements
const elConnStatus = document.getElementById("conn-status");
const elEmergencyBanner = document.getElementById("emergency-banner");
const elEmergencyText = document.getElementById("emergency-text");
const elVoiceToggle = document.getElementById("btn-voice-toggle");
const elFullscreenToggle = document.getElementById("btn-fullscreen-toggle");

// Cockpit Elements
const elCockpitCard = document.getElementById("risk-cockpit-card");
const elRiskLevelText = document.getElementById("cockpit-risk-level");
const elRiskScoreVal = document.getElementById("cockpit-score-val");
const elCockpitCategory = document.getElementById("cockpit-category");
const elCockpitHazardMsg = document.getElementById("cockpit-hazard-msg");
const elCockpitConfidence = document.getElementById("cockpit-confidence");

// Telemetry Elements
const elHeadPoseDirection = document.getElementById("telem-head-direction");
const elHeadPoseIcon = document.getElementById("telem-head-icon");
const elAttentionScore = document.getElementById("telem-attention-score");
const elAttentionBar = document.getElementById("telem-attention-bar");

const elPerclosVal = document.getElementById("telem-perclos-val");
const elPerclosBar = document.getElementById("telem-perclos-bar");
const elFatigueSub = document.getElementById("telem-fatigue-sub");

const elPhoneVal = document.getElementById("telem-phone-val");
const elPhoneSub = document.getElementById("telem-phone-sub");

const elSeatbeltBadge = document.getElementById("telem-seatbelt-badge");

const elSpeedVal = document.getElementById("telem-speed-val");
const elSpeedSub = document.getElementById("telem-speed-sub");

const elAggressiveVal = document.getElementById("telem-aggressive-val");
const elAggressiveBar = document.getElementById("telem-aggressive-bar");
const elLaneSub = document.getElementById("telem-lane-sub");

// Camera Elements
const elStreamInside = document.getElementById("stream-inside");
const elStreamOutside = document.getElementById("stream-outside");

// Settings Elements
const elSettingVoice = document.getElementById("setting-voice");
const elSettingVibration = document.getElementById("setting-vibration");

// Initialize Mobile App
document.addEventListener("DOMContentLoaded", () => {
  setupNavigation();
  setupSettings();
  setupControls();
  connectSSE();
  registerServiceWorker();
});

// Setup Tab Navigation
function setupNavigation() {
  const navItems = document.querySelectorAll(".nav-item");
  navItems.forEach((btn) => {
    btn.addEventListener("click", () => {
      const targetTab = btn.getAttribute("data-tab");
      switchTab(targetTab);
    });
  });
}

function switchTab(tabId) {
  currentTab = tabId;
  document.querySelectorAll(".nav-item").forEach((btn) => {
    btn.classList.toggle("active", btn.getAttribute("data-tab") === tabId);
  });
  document.querySelectorAll(".tab-pane").forEach((pane) => {
    pane.classList.toggle("active", pane.id === `tab-${tabId}`);
  });

  if (tabId === "cameras") {
    loadCameraStreams();
  } else if (tabId === "incidents") {
    loadMobileIncidents();
  }
}

// Setup Service Worker
function registerServiceWorker() {
  if ("serviceWorker" in navigator) {
    navigator.serviceWorker
      .register("/static/mobile/sw.js")
      .then((reg) => console.log("DriveGuardian ServiceWorker active:", reg.scope))
      .catch((err) => console.warn("SW register notice:", err));
  }
}

// Connect SSE stream
function connectSSE() {
  if (eventSource) {
    eventSource.close();
  }

  updateConnectionStatus(false);
  eventSource = new EventSource("/api/stream/metrics");

  eventSource.onopen = () => {
    updateConnectionStatus(true);
  };

  eventSource.onmessage = (event) => {
    try {
      const data = JSON.parse(event.data);
      updateDashboard(data);
    } catch (e) {
      console.error("Metric parse error", e);
    }
  };

  eventSource.onerror = () => {
    updateConnectionStatus(false);
    eventSource.close();
    // Reconnect after 2 seconds
    setTimeout(connectSSE, 2000);
  };
}

function updateConnectionStatus(isConnected) {
  if (isConnected) {
    elConnStatus.className = "conn-pill";
    elConnStatus.innerHTML = `<span class="conn-dot"></span> Live`;
  } else {
    elConnStatus.className = "conn-pill disconnected";
    elConnStatus.innerHTML = `<span class="conn-dot"></span> Connecting...`;
  }
}

// Update Dashboard View
function updateDashboard(data) {
  const inside = data.inside || {};
  const outside = data.outside || {};
  const fused = data.fused || {};

  const level = fused.level || "Low";
  const score = fused.score !== undefined ? fused.score : 0;
  const category = fused.category || "Normal Driving";
  const confidence = fused.confidence !== undefined ? Math.round(fused.confidence * 100) : 95;
  const reasons = fused.reasons || [];
  const primaryReason = reasons.length > 0 ? reasons[0] : "All driving indicators within safe normal limits.";

  // Update Cockpit Card
  elRiskLevelText.textContent = level.toUpperCase();
  elRiskScoreVal.textContent = score;
  elCockpitCategory.textContent = category;
  elCockpitConfidence.textContent = `${confidence}% AI Conf`;
  elCockpitHazardMsg.innerHTML = `<span class="hazard-icon">${getHazardIcon(level, category)}</span><span>${primaryReason}</span>`;

  // Apply Risk Level Theme Classes
  elCockpitCard.className = `risk-cockpit-card risk-${level.toLowerCase().substring(0, 4)}`;

  // Emergency Flash Banner
  if (level === "Critical" || level === "High") {
    elEmergencyBanner.style.display = "flex";
    elEmergencyText.textContent = `${level.toUpperCase()} WARNING: ${primaryReason}`;
  } else {
    elEmergencyBanner.style.display = "none";
  }

  // Voice Alert & Haptic
  handleVoiceAndHaptics(level, category, primaryReason);

  // Telemetry 1: Driver Attention & Head Pose
  const headDir = inside.head_pose_direction || "Forward";
  elHeadPoseDirection.textContent = headDir;
  elHeadPoseIcon.textContent = getHeadDirectionIcon(headDir);
  const attScore = inside.attention_score !== undefined ? Math.round(inside.attention_score * 100) : 100;
  elAttentionScore.textContent = `${attScore}% Attentive`;
  elAttentionBar.style.width = `${attScore}%`;
  elAttentionBar.style.background = attScore >= 70 ? "var(--risk-low)" : attScore >= 40 ? "var(--risk-med)" : "var(--risk-crit)";

  // Telemetry 2: Fatigue & PERCLOS
  const perclos = inside.perclos !== undefined ? inside.perclos.toFixed(1) : "0.0";
  elPerclosVal.textContent = `${perclos}%`;
  elPerclosBar.style.width = `${Math.min(100, inside.perclos || 0)}%`;
  elPerclosBar.style.background = (inside.perclos || 0) >= 30 ? "var(--risk-crit)" : (inside.perclos || 0) >= 20 ? "var(--risk-med)" : "var(--risk-low)";
  const earStr = inside.ear !== undefined ? inside.ear.toFixed(2) : "0.30";
  const marStr = inside.mar !== undefined ? inside.mar.toFixed(2) : "0.05";
  elFatigueSub.textContent = `EAR: ${earStr} | MAR: ${marStr}`;

  // Telemetry 3: Phone Use & Duration
  if (inside.phone_detected) {
    const dur = inside.phone_duration_sec !== undefined ? inside.phone_duration_sec.toFixed(1) : "0.0";
    elPhoneVal.textContent = `Active (${dur}s)`;
    elPhoneVal.style.color = "var(--risk-crit)";
    elPhoneSub.textContent = `Continuous phone usage detected`;
  } else {
    elPhoneVal.textContent = "None Detected";
    elPhoneVal.style.color = "var(--risk-low)";
    elPhoneSub.textContent = "Hands free";
  }

  // Telemetry 4: Seatbelt Status
  const seatbelt = inside.seatbelt_status || "Fastened (Worn)";
  if (seatbelt.toLowerCase().includes("unfastened") || seatbelt.toLowerCase().includes("no seatbelt")) {
    elSeatbeltBadge.className = "badge-seatbelt unfastened";
    elSeatbeltBadge.textContent = "NO SEATBELT";
  } else {
    elSeatbeltBadge.className = "badge-seatbelt fastened";
    elSeatbeltBadge.textContent = "WORN (FASTENED)";
  }

  // Telemetry 5: Relative Speed
  const relSpeed = outside.relative_speed_estimate || 0;
  if (relSpeed > 0) {
    elSpeedVal.textContent = `+${relSpeed} km/h`;
    elSpeedVal.style.color = relSpeed >= 15 ? "var(--risk-crit)" : "var(--risk-med)";
    elSpeedSub.textContent = "Closing rate (vision estimate)";
  } else {
    elSpeedVal.textContent = "Stable Pace";
    elSpeedVal.style.color = "var(--text-main)";
    elSpeedSub.textContent = "No rapid closing vehicle";
  }

  // Telemetry 6: Lane & Aggressive Driving
  const aggScore = outside.aggressive_driving_score || 0;
  elAggressiveVal.textContent = `${aggScore}/100`;
  elAggressiveBar.style.width = `${aggScore}%`;
  elAggressiveBar.style.background = aggScore >= 50 ? "var(--risk-crit)" : aggScore >= 25 ? "var(--risk-med)" : "var(--risk-low)";
  const laneStatus = outside.lane_status || "Centered";
  elLaneSub.textContent = `Lane: ${laneStatus}`;
}

// Icon helpers
function getHazardIcon(level, category) {
  if (level === "Low") return "🛡️";
  if (category.includes("Fatigue")) return "😴";
  if (category.includes("Phone")) return "📱";
  if (category.includes("Distraction")) return "👀";
  if (category.includes("Aggressive")) return "⚡";
  if (category.includes("Lane")) return "🛣️";
  if (category.includes("Tailgating") || category.includes("Proximity")) return "🚗";
  if (category.includes("Seatbelt")) return "⚠️";
  return "⚠️";
}

function getHeadDirectionIcon(dir) {
  switch (dir) {
    case "Forward": return "⬆️";
    case "Left": return "⬅️";
    case "Right": return "➡️";
    case "Down": return "⬇️";
    default: return "❓";
  }
}

// Voice synthesis and haptic vibrations
function handleVoiceAndHaptics(level, category, reason) {
  const isHighOrCrit = level === "High" || level === "Critical";
  if (!isHighOrCrit) return;

  const now = Date.now();
  if (now - lastSpokenTime < VOICE_COOLDOWN_MS) return;

  // Haptic Feedback
  if (vibrationEnabled && "vibrate" in navigator) {
    if (level === "Critical") {
      navigator.vibrate([250, 100, 250, 100, 300]);
    } else {
      navigator.vibrate([180, 80, 180]);
    }
  }

  // Voice Warning
  if (voiceEnabled && "speechSynthesis" in window) {
    let warningPhrase = "";
    if (level === "Critical") {
      warningPhrase = `Emergency Warning! ${category} hazard detected.`;
    } else {
      warningPhrase = `Caution! High risk: ${category}.`;
    }

    if (warningPhrase !== lastSpokenText || now - lastSpokenTime > 12000) {
      window.speechSynthesis.cancel();
      const utterance = new SpeechSynthesisUtterance(warningPhrase);
      utterance.rate = 1.05;
      utterance.pitch = 1.0;
      utterance.volume = 1.0;
      window.speechSynthesis.speak(utterance);
      lastSpokenText = warningPhrase;
      lastSpokenTime = now;
    }
  }
}

// Setup Settings and quick toggles
function setupSettings() {
  elSettingVoice.checked = voiceEnabled;
  elSettingVibration.checked = vibrationEnabled;

  elSettingVoice.addEventListener("change", (e) => {
    voiceEnabled = e.target.checked;
    updateVoiceButtonUI();
  });

  elSettingVibration.addEventListener("change", (e) => {
    vibrationEnabled = e.target.checked;
  });

  elVoiceToggle.addEventListener("click", () => {
    voiceEnabled = !voiceEnabled;
    elSettingVoice.checked = voiceEnabled;
    updateVoiceButtonUI();
    if (voiceEnabled && "speechSynthesis" in window) {
      const u = new SpeechSynthesisUtterance("Voice alerts enabled");
      u.rate = 1.1;
      window.speechSynthesis.speak(u);
    }
  });

  elFullscreenToggle.addEventListener("click", toggleFullscreen);
}

function updateVoiceButtonUI() {
  if (voiceEnabled) {
    elVoiceToggle.classList.add("active");
    elVoiceToggle.innerHTML = "🔊";
  } else {
    elVoiceToggle.classList.remove("active");
    elVoiceToggle.innerHTML = "🔇";
  }
}

function toggleFullscreen() {
  if (!document.fullscreenElement) {
    document.documentElement.requestFullscreen().catch((err) => {
      console.warn("Fullscreen request:", err);
    });
  } else {
    if (document.exitFullscreen) {
      document.exitFullscreen();
    }
  }
}

// Quick Controls (Start / Stop)
function setupControls() {
  const btnStart = document.getElementById("btn-ctrl-start");
  const btnStop = document.getElementById("btn-ctrl-stop");

  if (btnStart) {
    btnStart.addEventListener("click", () => {
      fetch("/api/control", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ action: "start" }),
      }).then(() => {
        if (voiceEnabled && "speechSynthesis" in window) {
          window.speechSynthesis.speak(new SpeechSynthesisUtterance("Monitoring started"));
        }
      });
    });
  }

  if (btnStop) {
    btnStop.addEventListener("click", () => {
      fetch("/api/control", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ action: "stop" }),
      }).then(() => {
        if (voiceEnabled && "speechSynthesis" in window) {
          window.speechSynthesis.speak(new SpeechSynthesisUtterance("Monitoring stopped"));
        }
      });
    });
  }
}

// Load Camera Streams
function loadCameraStreams() {
  if (elStreamInside) {
    elStreamInside.src = `/api/stream/inside?t=${Date.now()}`;
  }
  if (elStreamOutside) {
    elStreamOutside.src = `/api/stream/outside?t=${Date.now()}`;
  }
}

// Load Mobile Incidents
function loadMobileIncidents() {
  const listEl = document.getElementById("mobile-incidents-list");
  const filterCat = document.getElementById("mobile-filter-category").value;
  const filterRisk = document.getElementById("mobile-filter-risk").value;

  listEl.innerHTML = `<div style="text-align:center; padding: 20px; color: var(--text-muted);">Loading incidents...</div>`;

  let url = `/api/events?limit=25`;
  if (filterRisk) url += `&risk_level=${encodeURIComponent(filterRisk)}`;
  if (filterCat) url += `&category=${encodeURIComponent(filterCat)}`;

  fetch(url)
    .then((res) => res.json())
    .then((events) => {
      if (!events || events.length === 0) {
        listEl.innerHTML = `<div style="text-align:center; padding: 30px; color: var(--text-dim);">No incidents recorded matching filters.</div>`;
        return;
      }

      listEl.innerHTML = events
        .map((ev) => {
          const dt = new Date(ev.timestamp);
          const timeStr = dt.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" });
          const cat = ev.category || "Incident";
          const conf = ev.confidence ? `AI Conf: ${Math.round(ev.confidence * 100)}%` : "";
          const reasonsStr = Array.isArray(ev.reasons) ? ev.reasons.slice(0, 2).join(" • ") : ev.reasons || "";

          let snapsHtml = "";
          if (ev.inside_snapshot_path || ev.outside_snapshot_path) {
            snapsHtml = `
              <div class="incident-snapshots">
                ${ev.inside_snapshot_path ? `<div class="incident-thumb"><img src="/events-media/${ev.inside_snapshot_path.split(/[\\/]/).pop()}" alt="Inside" loading="lazy"></div>` : ""}
                ${ev.outside_snapshot_path ? `<div class="incident-thumb"><img src="/events-media/${ev.outside_snapshot_path.split(/[\\/]/).pop()}" alt="Outside" loading="lazy"></div>` : ""}
              </div>
            `;
          }

          return `
            <div class="incident-card">
              <div class="incident-card-top">
                <span class="incident-badge badge-${ev.risk_level}">${ev.risk_level} (Score: ${ev.risk_score})</span>
                <span class="incident-time">${timeStr}</span>
              </div>
              <div class="incident-cat">${cat} <span style="font-size:0.72rem; color:var(--text-muted); font-weight:normal;">${conf}</span></div>
              <div class="incident-reasons">${reasonsStr}</div>
              ${snapsHtml}
            </div>
          `;
        })
        .join("");
    })
    .catch((err) => {
      listEl.innerHTML = `<div style="color:var(--risk-crit); text-align:center; padding:20px;">Failed to load incidents.</div>`;
    });
}
