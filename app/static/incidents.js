const incidentGrid = document.getElementById("incidentGrid");
const incidentCount = document.getElementById("incidentCount");
const searchInput = document.getElementById("searchInput");
const severityFilter = document.getElementById("severityFilter");
const categoryFilter = document.getElementById("categoryFilter");
const limitFilter = document.getElementById("limitFilter");
const searchBtn = document.getElementById("searchBtn");
const clearBtn = document.getElementById("clearBtn");
const exportCsvBtn = document.getElementById("exportCsvBtn");

function severityClass(level) {
  return `pill ${String(level || "low").toLowerCase()}`;
}

function createReasonList(reasons) {
  const list = document.createElement("ul");
  list.className = "reason-list compact";

  if (!reasons.length) {
    const item = document.createElement("li");
    item.textContent = "No explanation saved";
    list.appendChild(item);
    return list;
  }

  reasons.forEach((reason) => {
    const item = document.createElement("li");
    item.textContent = reason;
    list.appendChild(item);
  });

  return list;
}

function renderIncidents(events) {
  incidentGrid.innerHTML = "";
  incidentCount.textContent = `${events.length} incidents`;

  if (!events.length) {
    const empty = document.createElement("article");
    empty.className = "panel empty-state";
    empty.innerHTML = `
      <span class="panel-label">No Results</span>
      <strong>Nothing matched this filter</strong>
      <p>Try a broader severity or clear the search term.</p>
    `;
    incidentGrid.appendChild(empty);
    return;
  }

  events.forEach((event) => {
    const card = document.createElement("article");
    card.className = "panel incident-card";

    const createdAt = new Date(event.created_at);
    const timeLabel = Number.isNaN(createdAt.getTime())
      ? event.created_at
      : createdAt.toLocaleString();

    const categoryText = event.category || "General Safety";
    const confidencePct = Number(event.confidence || 1.0).toFixed(2);
    const ackStatusHtml = event.acknowledged
      ? '<span class="pill low" style="margin-top:4px; font-size:11px;">✓ Acknowledged</span>'
      : `<button class="ack-btn pill" data-id="${event.id}" style="margin-top:4px; font-size:11px; cursor:pointer; background:#2563eb; color:white; border:none; padding:3px 8px;" title="Mark incident as reviewed">Acknowledge</button>`;

    card.innerHTML = `
      <div class="incident-card-top">
        <div>
          <span class="panel-label">Incident #${event.id} &bull; ${categoryText}</span>
          <h2>${timeLabel}</h2>
        </div>
        <div class="incident-card-score" style="display:flex; flex-direction:column; align-items:flex-end;">
          <div style="display:flex; align-items:center; gap:6px;">
            <span class="${severityClass(event.risk_level)}">${event.risk_level}</span>
            <strong>${event.risk_score}</strong>
          </div>
          ${ackStatusHtml}
        </div>
      </div>
      <div class="incident-summary-grid">
        <div>
          <span class="panel-label">Inside State</span>
          <p>${event.inside_status}</p>
        </div>
        <div>
          <span class="panel-label">Outside Traffic</span>
          <p>${event.outside_traffic}</p>
        </div>
        <div>
          <span class="panel-label">AI Confidence</span>
          <p>${confidencePct}</p>
        </div>
      </div>
      <div class="snapshot-grid">
        <figure class="snapshot-card">
          <img src="${event.inside_snapshot_url}" alt="Inside snapshot for incident ${event.id}" loading="lazy" />
          <figcaption>Inside snapshot</figcaption>
        </figure>
        <figure class="snapshot-card">
          <img src="${event.outside_snapshot_url}" alt="Outside snapshot for incident ${event.id}" loading="lazy" />
          <figcaption>Outside snapshot</figcaption>
        </figure>
      </div>
      <div class="incident-reasons">
        <span class="panel-label">Reasons</span>
      </div>
    `;

    card.appendChild(createReasonList(event.reasons || []));
    incidentGrid.appendChild(card);
  });
}

async function fetchIncidents() {
  const params = new URLSearchParams({
    limit: limitFilter.value,
  });

  if (severityFilter.value && severityFilter.value !== "All") {
    params.set("risk_level", severityFilter.value);
  }

  if (categoryFilter && categoryFilter.value) {
    params.set("category", categoryFilter.value);
  }

  const searchValue = searchInput.value.trim();
  if (searchValue) {
    params.set("search", searchValue);
  }

  if (exportCsvBtn) {
    exportCsvBtn.href = `/api/events/export-csv?${params.toString()}`;
  }

  const response = await fetch(`/api/events?${params.toString()}`);
  const data = await response.json();
  renderIncidents(data.events || []);
}

function clearFilters() {
  searchInput.value = "";
  severityFilter.value = "All";
  if (categoryFilter) categoryFilter.value = "";
  limitFilter.value = "24";
  fetchIncidents().catch((error) => console.error("Incident refresh failed", error));
}

searchBtn.addEventListener("click", () => {
  fetchIncidents().catch((error) => console.error("Incident refresh failed", error));
});

clearBtn.addEventListener("click", clearFilters);

searchInput.addEventListener("keydown", (event) => {
  if (event.key === "Enter") {
    fetchIncidents().catch((error) => console.error("Incident refresh failed", error));
  }
});

severityFilter.addEventListener("change", () => {
  fetchIncidents().catch((error) => console.error("Incident refresh failed", error));
});

if (categoryFilter) {
  categoryFilter.addEventListener("change", () => {
    fetchIncidents().catch((error) => console.error("Incident refresh failed", error));
  });
}

limitFilter.addEventListener("change", () => {
  fetchIncidents().catch((error) => console.error("Incident refresh failed", error));
});

if (incidentGrid) {
  incidentGrid.addEventListener("click", async (e) => {
    const btn = e.target.closest(".ack-btn");
    if (!btn) return;
    const eventId = btn.getAttribute("data-id");
    if (!eventId) return;
    btn.disabled = true;
    btn.textContent = "Saving...";
    try {
      const res = await fetch(`/api/events/${eventId}/acknowledge`, { method: "POST" });
      if (res.ok) {
        btn.outerHTML = '<span class="pill low" style="margin-top:4px; font-size:11px;">✓ Acknowledged</span>';
      } else {
        btn.textContent = "Retry";
        btn.disabled = false;
      }
    } catch (err) {
      console.error("Ack error", err);
      btn.textContent = "Retry";
      btn.disabled = false;
    }
  });
}

fetchIncidents().catch((error) => console.error("Incident refresh failed", error));
