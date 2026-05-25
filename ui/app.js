const DEMO_USERS = [
  {
    id: "retail-mobile",
    label: "Retail — mobile",
    userId: "U001",
    segment: "retail",
    channel: "mobile",
    description: "Individual client, mobile app only",
  },
  {
    id: "pyme-web",
    label: "PyME — web",
    userId: "U009",
    segment: "pyme",
    channel: "web",
    description: "SME user, business web portal",
  },
  {
    id: "corporate-web",
    label: "Corporate — web",
    userId: "U011",
    segment: "corporate",
    channel: "web",
    description: "Corporate treasury, web channel",
  },
];

const SIMULATED_EVENTS = ["view", "click", "conversion", "dismiss"];

const els = {
  apiBase: document.getElementById("apiBase"),
  apiStatus: document.getElementById("apiStatus"),
  userOptions: document.getElementById("userOptions"),
  btnRefresh: document.getElementById("btnRefresh"),
  userSummary: document.getElementById("userSummary"),
  cardCount: document.getElementById("cardCount"),
  cards: document.getElementById("cards"),
  emptyState: document.getElementById("emptyState"),
  errorBox: document.getElementById("errorBox"),
  lastEvent: document.getElementById("lastEvent"),
};

let selectedUser = DEMO_USERS[0];

function apiUrl(path) {
  const base = els.apiBase.value.replace(/\/$/, "");
  return `${base}${path}`;
}

function showError(message) {
  els.errorBox.hidden = !message;
  els.errorBox.textContent = message || "";
}

function formatScore(score) {
  return typeof score === "number" ? score.toFixed(4) : String(score);
}

function formatType(type) {
  return String(type).replace(/_/g, " ");
}

function renderUserOptions() {
  els.userOptions.innerHTML = DEMO_USERS.map(
    (user) => `
    <label class="user-option ${user.id === selectedUser.id ? "selected" : ""}">
      <input type="radio" name="demoUser" value="${user.id}" ${
        user.id === selectedUser.id ? "checked" : ""
      } />
      <div>
        <strong>${user.label}</strong>
        <span>${user.userId} · ${user.segment} · ${user.channel}</span>
        <span>${user.description}</span>
      </div>
    </label>
  `,
  ).join("");

  els.userOptions.querySelectorAll('input[name="demoUser"]').forEach((input) => {
    input.addEventListener("change", () => {
      selectedUser = DEMO_USERS.find((u) => u.id === input.value);
      renderUserOptions();
      loadRecommendations();
    });
  });
}

function renderCards(recommendations) {
  els.cards.innerHTML = recommendations
    .map(
      (rec) => `
    <article class="card" data-item-id="${rec.itemId}">
      <div class="card-header">
        <h3>${rec.title}</h3>
        <div class="tags">
          <span class="tag type">${formatType(rec.type)}</span>
          <span class="tag priority-${rec.priority}">priority: ${rec.priority}</span>
          <span class="tag">${rec.channel}</span>
        </div>
      </div>
      <dl class="card-meta">
        <div>
          <dt>Scenario</dt>
          <dd>${rec.scenario}</dd>
        </div>
        <div>
          <dt>Score</dt>
          <dd>${formatScore(rec.score)}</dd>
        </div>
        <div>
          <dt>Action target</dt>
          <dd><code>${rec.action}</code></dd>
        </div>
        <div>
          <dt>Item ID</dt>
          <dd>${rec.itemId}</dd>
        </div>
      </dl>
      <p class="reason">${rec.reason}</p>
      <div class="events">
        <span class="events-label">Simulate event</span>
        ${SIMULATED_EVENTS.map(
          (ev) =>
            `<button type="button" class="btn event" data-event="${ev}" data-item="${rec.itemId}">${ev}</button>`,
        ).join("")}
      </div>
    </article>
  `,
    )
    .join("");

  els.cards.querySelectorAll(".btn.event").forEach((btn) => {
    btn.addEventListener("click", () =>
      postEvent(btn.dataset.item, btn.dataset.event, btn),
    );
  });

  els.emptyState.hidden = recommendations.length > 0;
  els.cardCount.textContent = `${recommendations.length} item${recommendations.length === 1 ? "" : "s"}`;
}

async function checkHealth() {
  try {
    const res = await fetch(apiUrl("/health"));
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    els.apiStatus.textContent = "API online";
    els.apiStatus.className = "status-pill status-ok";
  } catch {
    els.apiStatus.textContent = "API offline";
    els.apiStatus.className = "status-pill status-error";
  }
}

async function loadRecommendations() {
  showError("");
  els.userSummary.textContent = "Loading…";
  els.cards.innerHTML = "";

  const { userId, segment, channel } = selectedUser;
  const url = apiUrl(
    `/recommendations/${encodeURIComponent(userId)}?segment=${segment}&channel=${channel}&limit=5`,
  );

  try {
    const res = await fetch(url);
    const data = await res.json();
    if (!res.ok) {
      throw new Error(data.detail || `HTTP ${res.status}`);
    }

    els.userSummary.textContent = `${data.userId} · segment ${data.segment} · preferred ${data.preferredChannel}`;
    renderCards(data.recommendations || []);
  } catch (err) {
    showError(err.message || "Failed to load recommendations");
    els.userSummary.textContent = "Could not load recommendations.";
    renderCards([]);
  }
}

async function postEvent(itemId, event, button) {
  showError("");
  button.disabled = true;

  try {
    const res = await fetch(apiUrl("/events"), {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        userId: selectedUser.userId,
        itemId,
        event,
      }),
    });
    const data = await res.json();
    if (!res.ok) {
      throw new Error(data.detail || `HTTP ${res.status}`);
    }

    els.lastEvent.hidden = false;
    els.lastEvent.textContent = `Recorded ${event} on ${itemId}. ${data.message}`;
  } catch (err) {
    showError(err.message || "Failed to post event");
  } finally {
    button.disabled = false;
  }
}

els.btnRefresh.addEventListener("click", loadRecommendations);
els.apiBase.addEventListener("change", () => {
  checkHealth();
  loadRecommendations();
});

renderUserOptions();
checkHealth();
loadRecommendations();
