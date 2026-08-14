const WORKFLOW_FILE = "process-tiktok-live.yml";

const $ = (id) => document.getElementById(id);

const els = {
  owner: $("owner"),
  repo: $("repo"),
  branch: $("branch"),
  token: $("token"),
  saveConnection: $("saveConnection"),
  tiktokLiveUrl: $("tiktokLiveUrl"),
  mode: $("mode"),
  chunkMinutes: $("chunkMinutes"),
  chunkWrap: $("chunkWrap"),
  title: $("title"),
  description: $("description"),
  privacy: $("privacy"),
  scheduledAt: $("scheduledAt"),
  scheduleWrap: $("scheduleWrap"),
  maxRecordHours: $("maxRecordHours"),
  start: $("start"),
  status: $("status"),
  runInfo: $("runInfo"),
  results: $("results")
};

function setStatus(message) {
  els.status.textContent = message;
  console.log(message);
}

function getConnection() {
  return {
    owner: els.owner.value.trim(),
    repo: els.repo.value.trim(),
    branch: els.branch.value.trim() || "main",
    token: els.token.value.trim()
  };
}

function apiHeaders(token) {
  return {
    "Accept": "application/vnd.github+json",
    "Authorization": "Bearer " + token,
    "X-GitHub-Api-Version": "2022-11-28",
    "Content-Type": "application/json"
  };
}

function updateUI() {
  els.chunkWrap.style.display =
    els.mode.value === "chunked" ? "block" : "none";

  els.scheduleWrap.style.display =
    els.privacy.value === "scheduled" ? "block" : "none";
}

els.mode.addEventListener("change", updateUI);
els.privacy.addEventListener("change", updateUI);

els.saveConnection.addEventListener("click", () => {
  const connection = getConnection();
  localStorage.setItem(
    "vodtiktok_connection",
    JSON.stringify(connection)
  );
  setStatus("Conexión guardada en este navegador.");
});

try {
  const saved = localStorage.getItem("vodtiktok_connection");
  if (saved) {
    const connection = JSON.parse(saved);
    els.owner.value = connection.owner || "DavidRJ91";
    els.repo.value = connection.repo || "VODTiktok";
    els.branch.value = connection.branch || "main";
    els.token.value = connection.token || "";
  }
} catch (error) {
  console.error(error);
}

async function dispatchWorkflow(connection, inputs) {
  const endpoint =
    "https://api.github.com/repos/" +
    encodeURIComponent(connection.owner) +
    "/" +
    encodeURIComponent(connection.repo) +
    "/actions/workflows/" +
    encodeURIComponent(WORKFLOW_FILE) +
    "/dispatches";

  const response = await fetch(endpoint, {
    method: "POST",
    headers: apiHeaders(connection.token),
    body: JSON.stringify({
      ref: connection.branch,
      inputs: inputs
    })
  });

  if (!response.ok) {
    const text = await response.text();
    throw new Error(
      "GitHub API: " + response.status + " " + text
    );
  }
}

els.start.addEventListener("click", async () => {
  try {
    const connection = getConnection();

    if (!connection.owner || !connection.repo || !connection.token) {
      throw new Error(
        "Completa Owner, Repositorio y Token de GitHub."
      );
    }

    const liveUrl = els.tiktokLiveUrl.value.trim();

    if (!liveUrl || !liveUrl.toLowerCase().includes("tiktok.com")) {
      throw new Error("Introduce una URL válida de TikTok.");
    }

    const selectedMode = els.mode.value;
    const privacyChoice = els.privacy.value;

    let privacyStatus = privacyChoice;
    let scheduledAt = "";

    if (privacyChoice === "scheduled") {
      if (!els.scheduledAt.value) {
        throw new Error(
          "Selecciona una fecha y hora para programar."
        );
      }

      scheduledAt = new Date(
        els.scheduledAt.value
      ).toISOString();

      if (new Date(scheduledAt) <= new Date()) {
        throw new Error(
          "La fecha programada debe ser futura."
        );
      }

      privacyStatus = "private";
    }

    const maxHours = Number(els.maxRecordHours.value) || 4;
    const chunkMinutes = Number(els.chunkMinutes.value) || 5;

    const inputs = {
      tiktok_url: liveUrl,
      mode: selectedMode,
      title: els.title.value.trim() || "TikTok LIVE",
      description: els.description.value.trim(),
      privacy_status: privacyStatus,
      scheduled_at: scheduledAt,
      max_record_seconds: String(maxHours * 3600),
      chunk_seconds: String(chunkMinutes * 60)
    };

    els.start.disabled = true;
    setStatus("Lanzando workflow...");

    await dispatchWorkflow(connection, inputs);

    setStatus(
      "Workflow lanzado correctamente. Revisa la pestaña Actions de GitHub."
    );
  } catch (error) {
    console.error(error);
    setStatus(error.message || String(error));
  } finally {
    els.start.disabled = false;
  }
});

updateUI();
console.log("VODTiktok app.js cargado correctamente.");
