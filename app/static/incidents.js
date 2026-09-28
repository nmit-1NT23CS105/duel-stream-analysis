const incidentGrid = document.getElementById("incidentGrid");
const incidentCount = document.getElementById("incidentCount");
const searchInput = document.getElementById("searchInput");
const severityFilter = document.getElementById("severityFilter");
const limitFilter = document.getElementById("limitFilter");
const searchBtn = document.getElementById("searchBtn");
const clearBtn = document.getElementById("clearBtn");

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

    card.innerHTML = `
      <div class="incident-card-top">
        <div>
          <span class="panel-label">Incident #${event.id}</span>
          <h2>${timeLabel}</h2>
        </div>
        <div class="incident-card-score">
          <span class="${severityClass(event.risk_level)}">${event.risk_level}</span>
          <strong>${event.risk_score}</strong>
        </div>
      </div>
      <div class="incident-summary-grid">
        <div>
          <span class="panel-label">Inside</span>
          <p>${event.inside_status}</p>
        </div>
        <div>
          <span class="panel-label">Outside</span>
          <p>${event.outside_traffic}</p>
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

  const searchValue = searchInput.value.trim();
  if (searchValue) {
    params.set("search", searchValue);
  }

  const response = await fetch(`/api/events?${params.toString()}`);
  const data = await response.json();
  renderIncidents(data.events || []);
}

function clearFilters() {
  searchInput.value = "";
  severityFilter.value = "All";
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

limitFilter.addEventListener("change", () => {
  fetchIncidents().catch((error) => console.error("Incident refresh failed", error));
});

fetchIncidents().catch((error) => console.error("Incident refresh failed", error));
