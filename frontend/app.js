const API_BASE = window.API_BASE || "http://localhost:8000";
const POLL_MS = 2000;

const connLabel = document.getElementById("connLabel");
const connStatus = document.getElementById("connStatus");
const jobsTableBody = document.getElementById("jobsTableBody");
const statusFilter = document.getElementById("statusFilter");
const jobForm = document.getElementById("jobForm");
const jobType = document.getElementById("jobType");
const formMsg = document.getElementById("formMsg");

function setConn(ok) {
  const dot = connStatus.querySelector(".dot");
  dot.classList.toggle("live", ok);
  dot.classList.toggle("down", !ok);
  connLabel.textContent = ok ? "live" : "disconnected";
}

async function apiGet(path) {
  const res = await fetch(`${API_BASE}${path}`);
  if (!res.ok) throw new Error(`GET ${path} failed: ${res.status}`);
  return res.json();
}

async function apiPost(path, body) {
  const res = await fetch(`${API_BASE}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    const detail = await res.json().catch(() => ({}));
    throw new Error(detail.detail || `POST ${path} failed: ${res.status}`);
  }
  return res.json();
}

async function apiDelete(path) {
  const res = await fetch(`${API_BASE}${path}`, { method: "DELETE" });
  if (!res.ok) {
    const detail = await res.json().catch(() => ({}));
    throw new Error(detail.detail || `DELETE ${path} failed: ${res.status}`);
  }
  return res.json();
}

// ---- Field visibility for job type ----
const fieldWraps = {
  echo: ["payloadEchoWrap"],
  send_email: ["payloadEmailWrap", "payloadEmailSubjectWrap"],
  ai_summarize: ["payloadAiWrap"],
  flaky: [],
};

function updateFieldVisibility() {
  const type = jobType.value;
  const allWraps = ["payloadEchoWrap", "payloadEmailWrap", "payloadEmailSubjectWrap", "payloadAiWrap"];
  allWraps.forEach(id => document.getElementById(id).classList.add("hidden"));
  (fieldWraps[type] || []).forEach(id => document.getElementById(id).classList.remove("hidden"));
}
jobType.addEventListener("change", updateFieldVisibility);
updateFieldVisibility();

function buildPayload() {
  const type = jobType.value;
  if (type === "echo") {
    return { message: document.getElementById("payloadEcho").value };
  }
  if (type === "send_email") {
    return {
      to: document.getElementById("payloadEmailTo").value,
      subject: document.getElementById("payloadEmailSubject").value,
    };
  }
  if (type === "ai_summarize") {
    return { text: document.getElementById("payloadAiText").value };
  }
  return {};
}

jobForm.addEventListener("submit", async (e) => {
  e.preventDefault();
  formMsg.classList.remove("error");
  formMsg.textContent = "Submitting…";
  try {
    const body = {
      type: jobType.value,
      payload: buildPayload(),
      priority: parseInt(document.getElementById("jobPriority").value, 10),
      max_retries: parseInt(document.getElementById("jobMaxRetries").value, 10),
    };
    const job = await apiPost("/jobs", body);
    formMsg.textContent = `Enqueued ${job.id.slice(0, 8)}…`;
    refresh();
  } catch (err) {
    formMsg.classList.add("error");
    formMsg.textContent = err.message;
  }
});

// ---- Stats ----
async function refreshStats() {
  const stats = await apiGet("/stats");
  document.getElementById("stat-queue_depth").textContent = stats.queue_depth;
  document.getElementById("stat-running").textContent = stats.status_counts.running ?? 0;
  document.getElementById("stat-delayed_depth").textContent = stats.delayed_depth;
  document.getElementById("stat-success").textContent = stats.status_counts.success ?? 0;
  document.getElementById("stat-dead_letter_depth").textContent = stats.dead_letter_depth;
}

// ---- Table ----
function timeAgo(iso) {
  const diff = (Date.now() - new Date(iso).getTime()) / 1000;
  if (diff < 60) return `${Math.floor(diff)}s ago`;
  if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
  return `${Math.floor(diff / 3600)}h ago`;
}

function renderRow(job) {
  const tr = document.createElement("tr");
  tr.innerHTML = `
    <td class="mono-id" data-id="${job.id}">${job.id.slice(0, 8)}</td>
    <td>${job.type}</td>
    <td><span class="badge badge-${job.status}">${job.status}</span></td>
    <td>${job.priority}</td>
    <td>${job.retry_count}/${job.max_retries}</td>
    <td>${job.worker_id ?? "–"}</td>
    <td>${timeAgo(job.updated_at)}</td>
    <td>${job.status === "pending"
      ? `<button class="btn-cancel" data-cancel="${job.id}">cancel</button>`
      : ""}</td>
  `;
  return tr;
}

async function refreshTable() {
  const status = statusFilter.value;
  const jobs = await apiGet(`/jobs?limit=100${status ? `&status=${status}` : ""}`);
  jobsTableBody.innerHTML = "";
  if (jobs.length === 0) {
    jobsTableBody.innerHTML = `<tr><td colspan="8" class="empty-row">No jobs match this filter.</td></tr>`;
    return;
  }
  jobs.forEach(job => jobsTableBody.appendChild(renderRow(job)));
}

jobsTableBody.addEventListener("click", async (e) => {
  const cancelId = e.target.getAttribute("data-cancel");
  if (cancelId) {
    try {
      await apiDelete(`/jobs/${cancelId}`);
      refresh();
    } catch (err) {
      alert(err.message);
    }
    return;
  }
  const idCell = e.target.closest(".mono-id");
  if (idCell) {
    const id = idCell.getAttribute("data-id");
    const job = await apiGet(`/jobs/${id}`);
    document.getElementById("modalContent").textContent = JSON.stringify(job, null, 2);
    document.getElementById("modalBackdrop").classList.remove("hidden");
  }
});

document.getElementById("modalClose").addEventListener("click", () => {
  document.getElementById("modalBackdrop").classList.add("hidden");
});
document.getElementById("modalBackdrop").addEventListener("click", (e) => {
  if (e.target.id === "modalBackdrop") e.target.classList.add("hidden");
});

statusFilter.addEventListener("change", refreshTable);

async function refresh() {
  try {
    await Promise.all([refreshStats(), refreshTable()]);
    setConn(true);
  } catch (err) {
    setConn(false);
    console.error(err);
  }
}

refresh();
setInterval(refresh, POLL_MS);
