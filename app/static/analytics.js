document.addEventListener("DOMContentLoaded", () => {
  const kpiTotalEvents = document.getElementById("kpiTotalEvents");
  const kpiCriticalEvents = document.getElementById("kpiCriticalEvents");
  const kpiAvgScore = document.getElementById("kpiAvgScore");
  const kpiAckRate = document.getElementById("kpiAckRate");
  const kpiAckCount = document.getElementById("kpiAckCount");
  const kpiAckTotal = document.getElementById("kpiAckTotal");
  const timelineSvg = document.getElementById("timelineSvg");
  const riskLevelBars = document.getElementById("riskLevelBars");
  const categoryBars = document.getElementById("categoryBars");
  const driverStateBars = document.getElementById("driverStateBars");
  const trafficBars = document.getElementById("trafficBars");
  const quickTableBody = document.getElementById("quickTableBody");
  const refreshBtn = document.getElementById("refreshBtn");

  async function loadAnalytics() {
    try {
      const [analyticsRes, eventsRes] = await Promise.all([
        fetch("/api/analytics"),
        fetch("/api/events?limit=15"),
      ]);

      if (!analyticsRes.ok || !eventsRes.ok) {
        throw new Error("Failed to fetch analytics data");
      }

      const data = await analyticsRes.json();
      const eventsData = await eventsRes.json();

      renderKPIs(data);
      renderTimeline(data.score_trend || []);
      renderBarGroup(riskLevelBars, formatRiskLevelData(data.risk_levels), getRiskColor);
      renderBarGroup(categoryBars, data.categories || [], () => "var(--brand)");
      renderBarGroup(driverStateBars, (data.driver_states || []).map(d => ({ label: d.status, count: d.count })), () => "#7c3aed");
      renderBarGroup(trafficBars, (data.traffic_levels || []).map(t => ({ label: t.traffic, count: t.count })), () => "#0284c7");
      renderQuickTable(eventsData.events || []);
    } catch (err) {
      console.error("Analytics load error:", err);
    }
  }

  function renderKPIs(data) {
    kpiTotalEvents.textContent = data.total_events || 0;
    kpiCriticalEvents.textContent = data.critical_count || 0;
    kpiAvgScore.textContent = (data.average_risk_score || 0).toFixed(1);

    const total = data.total_events || 0;
    const ack = data.acknowledged_count || 0;
    const rate = total > 0 ? Math.round((ack / total) * 100) : 100;
    kpiAckRate.textContent = `${rate}%`;
    kpiAckCount.textContent = ack;
    kpiAckTotal.textContent = total;
  }

  function formatRiskLevelData(levelsObj) {
    levelsObj = levelsObj || {};
    return [
      { label: "Critical (85-100)", count: levelsObj["Critical"] || 0, key: "Critical" },
      { label: "High (60-84)", count: levelsObj["High"] || 0, key: "High" },
      { label: "Medium (30-59)", count: levelsObj["Medium"] || 0, key: "Medium" },
      { label: "Low (0-29)", count: levelsObj["Low"] || 0, key: "Low" },
    ];
  }

  function getRiskColor(item) {
    const key = item.key || item.label || "";
    if (key.includes("Critical")) return "var(--critical)";
    if (key.includes("High")) return "var(--high)";
    if (key.includes("Medium")) return "var(--warn)";
    return "var(--good)";
  }

  function renderBarGroup(container, items, colorFn) {
    container.innerHTML = "";
    if (!items || items.length === 0) {
      container.innerHTML = "<p style='color: var(--muted); font-size: 0.85rem;'>No records logged yet.</p>";
      return;
    }

    const maxCount = Math.max(...items.map(i => i.count || 0), 1);

    items.forEach(item => {
      const label = item.label || item.category || "Unknown";
      const count = item.count || 0;
      const pct = Math.round((count / maxCount) * 100);
      const color = colorFn(item);

      const row = document.createElement("div");
      row.className = "bar-row";
      row.innerHTML = `
        <span class="bar-label" title="${label}">${label}</span>
        <div class="bar-track">
          <div class="bar-fill" style="width: ${pct}%; background: ${color};"></div>
        </div>
        <span class="bar-count">${count}</span>
      `;
      container.appendChild(row);
    });
  }

  function renderTimeline(trend) {
    if (!trend || trend.length === 0) {
      timelineSvg.innerHTML = `
        <text x="450" y="120" text-anchor="middle" fill="#6e7f95" font-size="16" font-family="sans-serif">
          No incident history available yet. Events will appear as driving sessions are analyzed.
        </text>
      `;
      return;
    }

    const width = 900;
    const height = 240;
    const padX = 50;
    const padY = 25;
    const plotW = width - 2 * padX;
    const plotH = height - 2 * padY;

    let svgHtml = `
      <defs>
        <linearGradient id="trendGrad" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stop-color="#da3d4b" stop-opacity="0.35"/>
          <stop offset="100%" stop-color="#2267ff" stop-opacity="0.02"/>
        </linearGradient>
      </defs>

      <!-- Background Bands -->
      <rect x="${padX}" y="${padY}" width="${plotW}" height="${plotH * 0.15}" fill="rgba(218,61,75,0.08)"/>
      <rect x="${padX}" y="${padY + plotH * 0.15}" width="${plotW}" height="${plotH * 0.25}" fill="rgba(242,109,79,0.06)"/>
      <rect x="${padX}" y="${padY + plotH * 0.40}" width="${plotW}" height="${plotH * 0.30}" fill="rgba(213,154,30,0.05)"/>
      <rect x="${padX}" y="${padY + plotH * 0.70}" width="${plotW}" height="${plotH * 0.30}" fill="rgba(31,154,113,0.05)"/>

      <!-- Grid lines -->
      <line x1="${padX}" y1="${padY}" x2="${width - padX}" y2="${padY}" stroke="rgba(0,0,0,0.08)" stroke-dasharray="3"/>
      <text x="${padX - 8}" y="${padY + 4}" font-size="10" fill="#da3d4b" text-anchor="end" font-weight="700">100</text>

      <line x1="${padX}" y1="${padY + plotH * 0.15}" x2="${width - padX}" y2="${padY + plotH * 0.15}" stroke="rgba(0,0,0,0.08)" stroke-dasharray="3"/>
      <text x="${padX - 8}" y="${padY + plotH * 0.15 + 4}" font-size="10" fill="#da3d4b" text-anchor="end">85</text>

      <line x1="${padX}" y1="${padY + plotH * 0.40}" x2="${width - padX}" y2="${padY + plotH * 0.40}" stroke="rgba(0,0,0,0.08)" stroke-dasharray="3"/>
      <text x="${padX - 8}" y="${padY + plotH * 0.40 + 4}" font-size="10" fill="#f26d4f" text-anchor="end">60</text>

      <line x1="${padX}" y1="${padY + plotH * 0.70}" x2="${width - padX}" y2="${padY + plotH * 0.70}" stroke="rgba(0,0,0,0.08)" stroke-dasharray="3"/>
      <text x="${padX - 8}" y="${padY + plotH * 0.70 + 4}" font-size="10" fill="#d59a1e" text-anchor="end">30</text>

      <line x1="${padX}" y1="${height - padY}" x2="${width - padX}" y2="${height - padY}" stroke="rgba(0,0,0,0.15)"/>
      <text x="${padX - 8}" y="${height - padY + 4}" font-size="10" fill="#1f9a71" text-anchor="end" font-weight="700">0</text>
    `;

    const points = trend.map((d, i) => {
      const x = padX + (trend.length > 1 ? (i / (trend.length - 1)) * plotW : plotW / 2);
      const y = padY + plotH - (Math.min(Math.max(d.score, 0), 100) / 100) * plotH;
      return { x, y, ...d };
    });

    const pathD = points.reduce((acc, pt, i) => `${acc} ${i === 0 ? "M" : "L"} ${pt.x} ${pt.y}`, "");
    const areaD = `${pathD} L ${points[points.length - 1].x} ${height - padY} L ${points[0].x} ${height - padY} Z`;

    svgHtml += `
      <path d="${areaD}" fill="url(#trendGrad)"/>
      <path d="${pathD}" fill="none" stroke="#2267ff" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"/>
    `;

    points.forEach((pt) => {
      const nodeColor = pt.score >= 85 ? "#da3d4b" : pt.score >= 60 ? "#f26d4f" : pt.score >= 30 ? "#d59a1e" : "#1f9a71";
      svgHtml += `
        <circle cx="${pt.x}" cy="${pt.y}" r="4.5" fill="${nodeColor}" stroke="#ffffff" stroke-width="2">
          <title>Event #${pt.id} [${pt.time}]: ${pt.level} (${pt.score}) - ${pt.category}</title>
        </circle>
      `;
    });

    timelineSvg.innerHTML = svgHtml;
  }

  function renderQuickTable(events) {
    quickTableBody.innerHTML = "";
    if (!events || events.length === 0) {
      quickTableBody.innerHTML = `
        <tr>
          <td colspan="8" style="text-align: center; color: var(--muted); padding: 24px;">No safety events recorded yet.</td>
        </tr>
      `;
      return;
    }

    events.forEach(ev => {
      const tr = document.createElement("tr");
      const timeStr = (ev.created_at || "").replace("T", " ");
      const isAck = Boolean(ev.acknowledged);
      const reasonStr = (ev.reasons && ev.reasons.length > 0) ? ev.reasons[0] : "Normal observation";

      tr.innerHTML = `
        <td style="font-weight: 700;">#${ev.id}</td>
        <td style="font-size: 0.82rem; color: var(--muted);">${timeStr}</td>
        <td><span class="pill ${ev.risk_level.toLowerCase()}">${ev.risk_level}</span></td>
        <td style="font-weight: 700;">${ev.risk_score}</td>
        <td>${ev.category || "General"}</td>
        <td style="max-width: 280px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;" title="${reasonStr}">${reasonStr}</td>
        <td>
          <span class="${isAck ? 'ack-badge' : 'unack-badge'}">
            ${isAck ? '✓ Acknowledged' : '● Unreviewed'}
          </span>
        </td>
        <td>
          ${isAck ? '<span style="color:var(--muted); font-size:0.75rem;">Done</span>' : `<button class="ack-btn" data-id="${ev.id}">Acknowledge</button>`}
        </td>
      `;
      quickTableBody.appendChild(tr);
    });

    quickTableBody.querySelectorAll(".ack-btn").forEach(btn => {
      btn.addEventListener("click", async (e) => {
        const id = e.target.getAttribute("data-id");
        if (!id) return;
        try {
          btn.disabled = true;
          btn.textContent = "Updating...";
          const res = await fetch(`/api/events/${id}/acknowledge`, { method: "POST" });
          if (res.ok) {
            loadAnalytics();
          } else {
            btn.textContent = "Failed";
          }
        } catch (err) {
          console.error("Ack error:", err);
          btn.textContent = "Error";
        }
      });
    });
  }

  refreshBtn.addEventListener("click", loadAnalytics);
  loadAnalytics();
  setInterval(loadAnalytics, 6000);
});
