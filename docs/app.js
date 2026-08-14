const WORKFLOW_FILE = "process-tiktok-live.yml";
const $ = (id) => document.getElementById(id);
const els = {
  owner: $("owner"), repo: $("repo"), branch: $("branch"), token: $("token"),
  saveConnection: $("saveConnection"), url: $("tiktokLiveUrl"),
  chunk: $("chunkMinutes"), chunkWrap: $("chunkWrap"),
  title: $("title"), description: $("description"), privacy: $("privacy"),
  scheduledAt: $("scheduledAt"), scheduleWrap: $("scheduleWrap"),
  start: $("start"), status: $("status"), runInfo: $("runInfo"), results: $("results")
};

function mode() {
  return document.querySelector('input[name="mode"]:checked').value;
}
function connection() {
  return {
    owner: els.owner.value.trim(),
    repo: els.repo.value.trim(),
    branch: els.branch.value.trim() || "main",
    token: els.token.value.trim()
  };
}
function headers(token) {
  return {
    "Accept":"application/vnd.github+json",
    "Authorization":`Bearer ${token}`,
    "X-GitHub-Api-Version":"2022-11-28",
    "Content-Type":"application/json"
  };
}
function setStatus(text, kind="") {
  els.status.textContent = text;
  els.status.className = kind;
}
function updateVisibility() {
  els.chunkWrap.style.display = mode() === "live_chunked" ? "block" : "none";
  els.scheduleWrap.style.display = els.privacy.value === "scheduled" ? "block" : "none";
}
document.querySelectorAll('input[name="mode"]').forEach(x => x.addEventListener("change", updateVisibility));
els.privacy.addEventListener("change", updateVisibility);

els.saveConnection.addEventListener("click", () => {
  const c = connection();
  localStorage.setItem("tiktok-live-is-connection", JSON.stringify(c));
  setStatus("Conexión guardada solo en este navegador.", "ok");
});
const saved = localStorage.getItem("tiktok-live-is-connection");
if (saved) {
  try {
    const c = JSON.parse(saved);
    els.owner.value=c.owner||""; els.repo.value=c.repo||""; els.branch.value=c.branch||"main"; els.token.value=c.token||"";
  } catch {}
}

async function dispatch(c, inputs) {
  const url = `https://api.github.com/repos/${c.owner}/${c.repo}/actions/workflows/${WORKFLOW_FILE}/dispatches`;
  const r = await fetch(url, {method:"POST", headers:headers(c.token), body:JSON.stringify({ref:c.branch, inputs})});
  if (!r.ok) throw new Error(`GitHub API: ${r.status} ${await r.text()}`);
}

async function findRun(c, startedAt) {
  const url = `https://api.github.com/repos/${c.owner}/${c.repo}/actions/workflows/${WORKFLOW_FILE}/runs?event=workflow_dispatch&per_page=10`;
  const r = await fetch(url, {headers:headers(c.token)});
  if (!r.ok) throw new Error("No se pudieron consultar las ejecuciones.");
  const data = await r.json();
  return data.workflow_runs.find(run => new Date(run.created_at).getTime() >= startedAt - 5000);
}

async function pollRun(c, runId) {
  const url = `https://api.github.com/repos/${c.owner}/${c.repo}/actions/runs/${runId}`;
  while (true) {
    const r = await fetch(url, {headers:headers(c.token)});
    if (!r.ok) throw new Error("No se pudo consultar el estado.");
    const run = await r.json();
    els.runInfo.textContent = `Run #${run.id}: ${run.status}${run.conclusion ? " — "+run.conclusion : ""}`;
    if (run.status === "completed") return run;
    await new Promise(x => setTimeout(x, 5000));
  }
}

async function loadResult(c, runId) {
  const url = `https://raw.githubusercontent.com/${c.owner}/${c.repo}/${c.branch}/run_status/${runId}.json?${Date.now()}`;
  const r = await fetch(url);
  if (!r.ok) {
    els.results.textContent = "El workflow terminó, pero el resultado aún no está disponible.";
    return;
  }
  const data = await r.json();
  const items = data.live_parts?.length ? data.live_parts : (data.main ? [data.main] : []);
  els.results.innerHTML = items.length
    ? items.map(x => `<div class="result"><a target="_blank" rel="noopener" href="${x.video_url}">${x.title || x.video_url}</a></div>`).join("")
    : "No se encontraron vídeos.";
}

els.start.addEventListener("click", async () => {
  try {
    const c = connection();
    if (!c.owner || !c.repo || !c.token) throw new Error("Completa owner, repositorio y token de GitHub.");
    const liveUrl = els.url.value.trim();
    if (!liveUrl || !liveUrl.toLowerCase().includes("tiktok.com")) throw new Error("Introduce una URL válida de TikTok.");
    let scheduled = "";
    if (els.privacy.value === "scheduled") {
      if (!els.scheduledAt.value) throw new Error("Selecciona fecha y hora.");
      scheduled = new Date(els.scheduledAt.value).toISOString().replace(/\.\d{3}Z$/, "Z");
      if (new Date(scheduled) <= new Date()) throw new Error("La programación debe ser futura.");
    }
    const inputs: {
    tiktok_url: tiktokUrl,
    mode: mode,
    title: title,
    description: description,
    privacy_status: privacy,
    scheduled_at: scheduledAt,
    max_record_seconds: String(maxRecordSeconds),
    chunk_seconds: String(chunkMinutes * 60)
}
    };
    els.start.disabled = true;
    const startedAt = Date.now();
    setStatus("Lanzando workflow...");
    await dispatch(c, inputs);
    setStatus("Workflow lanzado. Buscando ejecución...");
    let run;
    for (let i=0;i<12 && !run;i++) {
      await new Promise(x => setTimeout(x, 2000));
      run = await findRun(c, startedAt);
    }
    if (!run) throw new Error("GitHub aceptó el workflow, pero no se encontró la ejecución.");
    const finalRun = await pollRun(c, run.id);
    if (finalRun.conclusion === "success") {
      setStatus("Proceso completado.", "ok");
      await new Promise(x => setTimeout(x, 3000));
      await loadResult(c, run.id);
    } else {
      setStatus(`El workflow terminó con: ${finalRun.conclusion}`, "error");
    }
  } catch (e) {
    setStatus(e.message || String(e), "error");
  } finally {
    els.start.disabled = false;
  }
});

updateVisibility();
