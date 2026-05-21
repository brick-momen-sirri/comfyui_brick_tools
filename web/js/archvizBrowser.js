import { app } from "../../scripts/app.js";
import { api } from "../../scripts/api.js";

const TAB_ID = "archviz-browser";
const PAGE_SIZE = 48;
const CATEGORIES = ["images", "sequences"];
const SIDEBAR_TITLE = "Brick Browser";
const SIDEBAR_TAB_LINES = ["Brick", "Asset"];
const DEFAULT_PROJECT = "0000_base";
const SORT_OPTIONS = [
  { value: "newest", label: "Newest" },
  { value: "oldest", label: "Oldest" },
  { value: "name", label: "Name" },
  { value: "largest", label: "Largest" },
  { value: "smallest", label: "Smallest" },
];
const STORAGE_KEY = "brick-browser-state-v2";

const state = {
  projects: [],
  project: DEFAULT_PROJECT,
  category: "images",
  query: "",
  sort: "newest",
  workflowOnly: false,
  page: 1,
  hasMore: false,
  loading: false,
  total: 0,
  items: [],
  lastRequestId: 0,
  modalIndex: -1,
  deletingPaths: new Set(),
  renamingPaths: new Set(),
  creatingProject: false,
};

function toast(severity, detail) {
  app.extensionManager.toast?.add?.({
    severity,
    summary: "Brick Browser",
    detail,
    life: 4200,
  });
}

async function fetchJSON(url, options = {}) {
  const resp = await api.fetchApi(url, { method: "GET", ...options });
  const data = await resp.json().catch(() => ({}));
  if (!resp.ok) {
    throw new Error(data?.error || `Request failed: ${resp.status}`);
  }
  return data;
}

function el(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined) node.textContent = text;
  return node;
}

function createIconButton(iconClass, label) {
  const button = el("button", "avb-icon-btn");
  button.type = "button";
  button.title = label;
  button.setAttribute("aria-label", label);
  button.appendChild(el("i", iconClass));
  return button;
}

function restoreState() {
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    if (!raw) return;
    const saved = JSON.parse(raw);
    if (!saved || typeof saved !== "object") return;
    state.project = saved.project || state.project;
    state.category = CATEGORIES.includes(saved.category) ? saved.category : state.category;
    state.query = typeof saved.query === "string" ? saved.query : state.query;
    state.sort = SORT_OPTIONS.some((option) => option.value === saved.sort) ? saved.sort : state.sort;
    state.workflowOnly = !!saved.workflowOnly;
  } catch (error) {
    console.warn("Brick Browser: restore failed", error);
  }
}

function persistState() {
  try {
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify({
      project: state.project,
      category: state.category,
      query: state.query,
      sort: state.sort,
      workflowOnly: state.workflowOnly,
    }));
  } catch (error) {
    console.warn("Brick Browser: persist failed", error);
  }
}

function injectStyles() {
  if (document.getElementById("archviz-browser-styles")) return;
  const style = document.createElement("style");
  style.id = "archviz-browser-styles";
  style.textContent = `
    .avb-root { --bg:#0f141a; --panel:#141b23; --panel-2:#1a232d; --card:#18212b; --border:rgba(201,214,228,.12); --border-strong:rgba(201,214,228,.22); --text:#edf3f9; --muted:#94a7ba; --accent:#62c7a3; --accent-2:#88b9ff; height:100%; display:flex; flex-direction:column; color:var(--text); background:var(--bg); }
    .avb-toolbar { display:grid; gap:12px; padding:14px; border-bottom:1px solid var(--border); background:var(--panel); }
    .avb-hero { display:grid; grid-template-columns:1fr auto; gap:10px; align-items:start; }
    .avb-title { font-size:18px; font-weight:700; letter-spacing:.02em; }
    .avb-subtitle { margin-top:4px; color:var(--muted); font-size:12px; line-height:1.5; }
    .avb-badge { display:inline-flex; align-items:center; padding:7px 10px; border-radius:999px; background:#1c2832; border:1px solid var(--border); color:var(--text); font-size:11px; font-weight:700; text-transform:uppercase; letter-spacing:.06em; }
    .avb-row { display:flex; gap:10px; align-items:center; flex-wrap:wrap; }
    .avb-control, .avb-button, .avb-toggle { border:1px solid var(--border); background:var(--panel-2); color:var(--text); border-radius:10px; min-height:40px; padding:9px 12px; font:inherit; transition:border-color 120ms ease, transform 120ms ease, background 120ms ease, opacity 120ms ease; }
    .avb-control:focus, .avb-button:focus, .avb-toggle:focus { outline:none; border-color:var(--accent-2); box-shadow:0 0 0 1px rgba(123,194,255,.32); }
    .avb-button { cursor:pointer; font-weight:600; }
    .avb-button:hover, .avb-toggle:hover { border-color:var(--border-strong); transform:translateY(-1px); }
    .avb-button.is-primary { background:var(--accent); border-color:var(--accent); color:#0c1512; }
    .avb-button.is-danger { background:#3a1f22; border-color:#7d363f; color:#ffe8ea; }
    .avb-button.is-danger:hover { background:#472529; border-color:#ad4d59; }
    .avb-button:disabled { cursor:default; transform:none; opacity:.55; }
    .avb-input-wrap { position:relative; flex:1 1 220px; min-width:180px; }
    .avb-input-icon { position:absolute; top:50%; left:12px; transform:translateY(-50%); color:var(--muted); font-size:13px; pointer-events:none; }
    .avb-search { width:100%; padding-left:34px; }
    .avb-select { min-width:150px; flex:1 1 180px; }
    .avb-tabs { display:grid; grid-template-columns:repeat(2, minmax(0, 1fr)); gap:8px; flex:1 1 240px; }
    .avb-tab.is-active, .avb-toggle.is-active { border-color:rgba(98,199,163,.44); background:#203129; color:#eefdf6; }
    .avb-pill-row { display:flex; gap:8px; flex-wrap:wrap; }
    .avb-summary { display:grid; grid-template-columns:repeat(3, minmax(0, 1fr)); gap:10px; }
    .avb-summary-card { padding:12px; border-radius:12px; border:1px solid var(--border); background:var(--card); }
    .avb-summary-label { font-size:11px; color:var(--muted); text-transform:uppercase; letter-spacing:.08em; }
    .avb-summary-value { margin-top:6px; font-size:18px; font-weight:700; }
    .avb-summary-meta { margin-top:4px; font-size:12px; color:var(--muted); }
    .avb-grid-wrap { flex:1; overflow:auto; min-height:0; }
    .avb-grid { display:grid; grid-template-columns:repeat(auto-fill, minmax(210px, 1fr)); gap:14px; padding:14px; align-content:start; }
    .avb-card { position:relative; display:flex; flex-direction:column; min-height:260px; overflow:hidden; border-radius:14px; border:1px solid var(--border); background:var(--card); box-shadow:none; transition:border-color 140ms ease, background 140ms ease; }
    .avb-card:hover { border-color:var(--border-strong); background:#1b2530; transform:none; box-shadow:none; }
    .avb-card-media { position:relative; aspect-ratio:1/1; overflow:hidden; background:#10171e; }
    .avb-card-media img { width:100%; height:100%; object-fit:cover; display:block; }
    .avb-card-media-tools { position:absolute; top:10px; right:10px; display:flex; gap:8px; z-index:2; }
    .avb-icon-btn { width:32px; height:32px; display:inline-flex; align-items:center; justify-content:center; padding:0; border-radius:8px; border:1px solid rgba(201,214,228,.16); background:rgba(15,20,26,.82); color:var(--text); cursor:pointer; transition:border-color 120ms ease, background 120ms ease, opacity 120ms ease; }
    .avb-icon-btn:hover { border-color:var(--border-strong); background:rgba(26,35,45,.96); }
    .avb-icon-btn:focus { outline:none; border-color:var(--accent-2); box-shadow:0 0 0 1px rgba(123,194,255,.32); }
    .avb-icon-btn:disabled { cursor:default; opacity:.45; }
    .avb-icon-btn .pi { font-size:13px; }
    .avb-card-overlay { position:absolute; inset:auto 0 0 0; display:flex; justify-content:space-between; gap:8px; padding:12px 12px 10px; background:linear-gradient(180deg, transparent, rgba(15,20,26,.82)); pointer-events:none; }
    .avb-chip { display:inline-flex; align-items:center; min-height:24px; padding:4px 8px; border-radius:999px; font-size:11px; font-weight:700; letter-spacing:.03em; background:#16202a; border:1px solid var(--border); color:var(--text); }
    .avb-chip.is-accent { background:#203129; border-color:rgba(98,199,163,.32); color:#e4fff4; }
    .avb-card-body { display:grid; gap:10px; padding:12px; }
    .avb-name { font-size:13px; line-height:1.45; font-weight:700; word-break:break-word; overflow:hidden; display:-webkit-box; -webkit-box-orient:vertical; -webkit-line-clamp:2; line-clamp:2; min-height:2.9em; }
    .avb-meta { display:flex; gap:6px; flex-wrap:wrap; }
    .avb-meta-pill { display:inline-flex; align-items:center; min-height:22px; padding:3px 7px; border-radius:999px; background:#1a232d; border:1px solid var(--border); color:var(--muted); font-size:11px; }
    .avb-actions { display:flex; gap:8px; flex-wrap:wrap; }
    .avb-actions .avb-button { flex:1 1 96px; min-height:36px; padding:7px 10px; font-size:12px; }
    .avb-status, .avb-empty { margin:14px; padding:18px; border-radius:12px; border:1px dashed var(--border); color:var(--muted); background:var(--panel); font-size:13px; line-height:1.6; }
    .avb-footer { padding:0 14px 14px; }
    .avb-loadmore { width:100%; }
    .avb-modal { position:fixed; inset:0; z-index:99999; display:none; align-items:center; justify-content:center; background:rgba(8,12,16,.76); backdrop-filter:blur(4px); padding:24px; }
    .avb-modal.is-open { display:flex; }
    .avb-modal-card { width:min(1260px, calc(100vw - 36px)); max-height:calc(100vh - 36px); display:grid; grid-template-columns:minmax(0, 1.4fr) minmax(320px, .8fr); overflow:hidden; border-radius:16px; border:1px solid var(--border-strong); background:var(--panel); box-shadow:none; }
    .avb-modal-media { display:grid; grid-template-rows:auto 1fr auto; min-height:0; border-right:1px solid var(--border); }
    .avb-modal-head, .avb-modal-side { padding:16px; }
    .avb-modal-head { display:flex; align-items:center; justify-content:space-between; gap:12px; border-bottom:1px solid var(--border); }
    .avb-modal-title { font-size:16px; font-weight:700; line-height:1.4; }
    .avb-modal-subtitle { margin-top:4px; color:var(--muted); font-size:12px; word-break:break-all; }
    .avb-preview-wrap { position:relative; display:flex; align-items:center; justify-content:center; min-height:0; padding:16px; background:#10171e; }
    .avb-preview { max-width:100%; max-height:calc(100vh - 210px); border-radius:12px; object-fit:contain; background:#0d141b; box-shadow:none; }
    .avb-modal-nav { position:absolute; top:50%; transform:translateY(-50%); width:42px; height:42px; border-radius:999px; border:1px solid var(--border); background:#16202a; color:var(--text); font-size:18px; cursor:pointer; }
    .avb-modal-nav[data-dir="prev"] { left:18px; }
    .avb-modal-nav[data-dir="next"] { right:18px; }
    .avb-modal-nav:disabled { opacity:.35; cursor:default; }
    .avb-modal-actions { display:flex; gap:10px; padding:16px; border-top:1px solid var(--border); flex-wrap:wrap; }
    .avb-modal-actions .avb-button { flex:1 1 140px; }
    .avb-modal-side { overflow:auto; display:grid; gap:14px; align-content:start; }
    .avb-side-block { padding:14px; border-radius:12px; border:1px solid var(--border); background:var(--card); }
    .avb-side-label { font-size:11px; color:var(--muted); text-transform:uppercase; letter-spacing:.08em; }
    .avb-side-value { margin-top:8px; font-size:14px; line-height:1.55; word-break:break-word; }
    .avb-side-grid { display:grid; grid-template-columns:repeat(2, minmax(0, 1fr)); gap:10px; }
    .avb-side-kv { padding:10px; border-radius:10px; background:#141d26; border:1px solid var(--border); }
    .avb-side-kv .avb-side-value { margin-top:4px; font-size:13px; }
    .avb-keyhint { color:var(--muted); font-size:12px; line-height:1.6; }
    .avb-sidebar-title-host { min-width:0 !important; overflow:visible !important; text-overflow:clip !important; }
    .avb-sidebar-title-wrap { display:grid !important; gap:1px !important; width:100% !important; white-space:normal !important; overflow:visible !important; text-overflow:clip !important; word-break:normal !important; overflow-wrap:normal !important; text-align:center !important; line-height:1 !important; font-size:9px !important; font-weight:700 !important; letter-spacing:.03em !important; text-transform:uppercase !important; }
    .avb-sidebar-title-wrap > span { display:block !important; }
    .avb-sidebar-title-wrap > span:last-child { opacity:.92 !important; }
    @media (max-width:980px) { .avb-summary { grid-template-columns:1fr; } .avb-modal-card { grid-template-columns:1fr; } .avb-modal-media { border-right:none; border-bottom:1px solid var(--border); } }
  `;
  document.head.appendChild(style);
}

function normalizeText(value) {
  return `${value || ""}`.replace(/\s+/g, " ").trim();
}

function styleSidebarLabelNode(node) {
  if (!node || node.dataset.avbSidebarStyled === "1") return;
  node.dataset.avbSidebarStyled = "1";
  node.classList.add("avb-sidebar-title-host");

  if (!node.querySelector(".avb-sidebar-title-wrap")) {
    node.replaceChildren();
    const wrap = el("span", "avb-sidebar-title-wrap");
    SIDEBAR_TAB_LINES.forEach((line) => wrap.appendChild(el("span", null, line)));
    node.appendChild(wrap);
  }

  const properties = {
    "white-space": "normal",
    "overflow": "visible",
    "text-overflow": "clip",
    "word-break": "break-word",
    "overflow-wrap": "anywhere",
    "line-height": "1.05",
    "text-align": "center",
    "max-width": "100%",
  };
  Object.entries(properties).forEach(([name, value]) => node.style.setProperty(name, value, "important"));

  const tab = node.closest("button, [role='tab'], [class*='sidebar'], [class*='SideBar']");
  if (tab) {
    tab.classList.add("avb-sidebar-tab");
    tab.style.setProperty("overflow", "visible", "important");
    tab.style.setProperty("text-overflow", "clip", "important");
    tab.style.setProperty("align-items", "center", "important");
    tab.style.setProperty("justify-content", "center", "important");
    tab.style.setProperty("padding-top", "6px", "important");
    tab.style.setProperty("padding-bottom", "6px", "important");
    tab.style.setProperty("gap", "5px", "important");
  }
}

function applySidebarTitleFix(root = document) {
  const scope = typeof root.querySelectorAll === "function" ? root.querySelectorAll("button, span, div, p") : [];
  const candidates = [...scope]
    .filter((node) => !node.closest(".avb-root"))
    .filter((node) => node.childElementCount === 0)
    .filter((node) => normalizeText(node.textContent) === SIDEBAR_TITLE)
    .filter((node) => ![...node.children].some((child) => normalizeText(child.textContent) === SIDEBAR_TITLE));

  candidates.forEach(styleSidebarLabelNode);
}

function ensureSidebarTitleFix() {
  if (state.sidebarTitleObserver) return;

  const observer = new MutationObserver((mutations) => {
    for (const mutation of mutations) {
      mutation.addedNodes.forEach((addedNode) => {
        if (addedNode instanceof Element) {
          applySidebarTitleFix(addedNode);
        }
      });
    }
    applySidebarTitleFix(document);
  });

  observer.observe(document.body, { childList: true, subtree: true });
  state.sidebarTitleObserver = observer;
  applySidebarTitleFix(document);
}

function formatDate(raw) {
  if (!raw || `${raw}`.length !== 8) return "Unknown";
  return `${raw.slice(0, 4)}-${raw.slice(4, 6)}-${raw.slice(6, 8)}`;
}

function formatBytes(value) {
  const bytes = Number(value || 0);
  if (!bytes) return "Unknown";
  const units = ["B", "KB", "MB", "GB", "TB"];
  let size = bytes;
  let index = 0;
  while (size >= 1024 && index < units.length - 1) {
    size /= 1024;
    index += 1;
  }
  const decimals = size >= 100 || index === 0 ? 0 : 1;
  return `${size.toFixed(decimals)} ${units[index]}`;
}

function formatTime(value) {
  if (!value) return "Unknown";
  const date = new Date(value * 1000);
  if (Number.isNaN(date.getTime())) return "Unknown";
  return date.toLocaleString();
}

function itemSecondaryLabel(item) {
  return item.asset_type === "sequence" ? (item.shot || "Sequence") : (item.camera || "Image");
}

function exportImageUrlFor(item) {
  return `/archviz_browser/export_image?path=${encodeURIComponent(item.relative_path)}`;
}

function downloadUrlFor(item) {
  return `/archviz_browser/download?path=${encodeURIComponent(item.relative_path)}`;
}

function buildQueryUrl() {
  return `/archviz_browser/assets?project=${encodeURIComponent(state.project)}&category=${encodeURIComponent(state.category)}&page=${state.page}&page_size=${PAGE_SIZE}&query=${encodeURIComponent(state.query)}&sort=${encodeURIComponent(state.sort)}&workflow_only=${state.workflowOnly ? "1" : "0"}`;
}

async function loadProjects() {
  const data = await fetchJSON("/archviz_browser/projects");
  state.projects = data.projects || [];
  if (!state.projects.includes(state.project)) {
    state.project = data.default_project || state.projects[0] || DEFAULT_PROJECT;
  }
}

async function createProject(projectName) {
  return fetchJSON("/archviz_browser/projects", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ project_name: projectName }),
  });
}

async function loadAssets({ append = false } = {}) {
  if (!state.project) return;
  const requestId = ++state.lastRequestId;
  state.loading = true;
  renderBody();
  try {
    const data = await fetchJSON(buildQueryUrl());
    if (requestId !== state.lastRequestId) return;
    state.hasMore = !!data.has_more;
    state.total = data.total || 0;
    state.items = append ? [...state.items, ...(data.items || [])] : (data.items || []);
  } catch (error) {
    console.error(error);
    toast("error", error.message || "Could not load assets.");
    if (!append) {
      state.items = [];
      state.total = 0;
      state.hasMore = false;
    }
  } finally {
    if (requestId === state.lastRequestId) {
      state.loading = false;
      renderBody();
    }
  }
}

function visibleCountLabel() {
  if (state.loading && !state.items.length) return "Loading library";
  if (!state.total) return "No assets";
  return `Showing ${state.items.length} of ${state.total}`;
}

function latestItemLabel() {
  if (!state.items.length) return "Waiting for content";
  const firstWithDate = state.items.find((item) => item.date);
  if (!firstWithDate) return "Date unavailable";
  return formatDate(firstWithDate.date);
}

function injectProjectOptions() {
  if (!state.projectSelect) return;
  state.projectSelect.innerHTML = "";
  for (const project of state.projects) {
    const option = document.createElement("option");
    option.value = project;
    option.textContent = project;
    state.projectSelect.appendChild(option);
  }
  state.projectSelect.value = state.project || "";
}

function metaPills(item) {
  const pills = [itemSecondaryLabel(item)];
  if (item.version) pills.push(item.version);
  if (item.resolution) pills.push(item.resolution);
  if (item.asset_type === "sequence" && item.frame_count) pills.push(`${item.frame_count} frames`);
  return pills;
}

function infoGridFor(item) {
  return [
    ["Type", item.asset_type],
    ["Project", item.project],
    ["Date", formatDate(item.date)],
    ["Version", item.version || "Unknown"],
    ["Resolution", item.resolution || "Unknown"],
    ["Size", formatBytes(item.size_bytes)],
    ["Modified", formatTime(item.mtime)],
    ["Workflow", item.workflow_available ? "Available" : "Not embedded"],
  ];
}

async function copyToClipboard(text, label) {
  try {
    await navigator.clipboard.writeText(text);
    toast("success", `${label} copied`);
  } catch (error) {
    console.error(error);
    toast("warn", `Could not copy ${label.toLowerCase()}.`);
  }
}

function triggerDownload(item) {
  const link = document.createElement("a");
  link.href = downloadUrlFor(item);
  link.rel = "noopener";
  link.download = "";
  link.style.display = "none";
  document.body.appendChild(link);
  link.click();
  link.remove();
  toast("success", item.asset_type === "sequence" ? "ZIP download started" : "PNG download started");
}

async function copyAssetImage(item) {
  if (!navigator.clipboard?.write || typeof window.ClipboardItem === "undefined") {
    toast("warn", "Clipboard image copy is not supported here.");
    return;
  }

  try {
    const resp = await api.fetchApi(exportImageUrlFor(item), { method: "GET" });
    if (!resp.ok) {
      const data = await resp.json().catch(() => ({}));
      throw new Error(data?.error || `Request failed: ${resp.status}`);
    }

    const blob = await resp.blob();
    const type = blob.type || "image/png";
    await navigator.clipboard.write([new window.ClipboardItem({ [type]: blob })]);
    toast("success", item.asset_type === "sequence" ? "Sequence frame copied" : "Image copied");
  } catch (error) {
    console.error(error);
    toast("error", error.message || "Could not copy image.");
  }
}

async function openWorkflowFor(item) {
  try {
    const payload = await fetchJSON(`/archviz_browser/workflow?path=${encodeURIComponent(item.relative_path)}`);
    if (!payload?.workflow) throw new Error("No workflow data found.");
    await app.loadGraphData(payload.workflow);
    toast("success", `Workflow loaded from ${item.display_name}`);
  } catch (error) {
    console.error(error);
    toast("error", error.message || "Could not load workflow.");
  }
}

function deletePromptFor(item) {
  const target = item.asset_type === "sequence" ? "this sequence and all of its frames" : "this asset file";
  return `Delete ${target}?\n\n${item.relative_path}\n\nThis cannot be undone.`;
}

async function reloadLoadedPages() {
  const targetPage = Math.max(1, state.page);
  state.page = 1;
  await loadAssets();
  while (state.page < targetPage && state.hasMore) {
    state.page += 1;
    await loadAssets({ append: true });
  }
}

async function promptAndCreateProject() {
  if (state.creatingProject) return;

  try {
    const name = await app.extensionManager.dialog.prompt({
      title: "Create Brick Project",
      message: "Enter project name:",
      defaultValue: "",
    });

    if (name === null) return;
    const trimmed = String(name).trim();
    if (!trimmed) return;

    state.creatingProject = true;
    renderBody();

    const data = await createProject(trimmed);
    state.projects = data.projects || state.projects;
    state.project = data.project_name || state.project;
    injectProjectOptions();
    persistState();
    toast("success", `Project created: ${state.project}`);
    await refreshAssets();
  } catch (error) {
    console.error(error);
    toast("error", error.message || "Could not create project.");
  } finally {
    state.creatingProject = false;
    renderBody();
  }
}

function closePreviewModal() {
  state.modal?.close?.();
}

function renameDialogConfigFor(item) {
  if (item.asset_type === "sequence") {
    return {
      title: "Rename Sequence",
      message: "Enter new sequence name:",
      defaultValue: item.display_name,
    };
  }

  return {
    title: "Rename Asset",
    message: "Enter new asset filename:",
    defaultValue: item.display_name,
  };
}

async function deleteAsset(item) {
  const relPath = item?.relative_path;
  if (!relPath || state.deletingPaths.has(relPath)) return;
  if (!window.confirm(deletePromptFor(item))) return;

  state.deletingPaths.add(relPath);
  renderBody();
  if (state.modal?.modal.classList.contains("is-open") && state.items[state.modalIndex]?.relative_path === relPath) {
    renderModal(item);
  }

  try {
    await fetchJSON("/archviz_browser/delete", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ path: relPath }),
    });
    if (state.items[state.modalIndex]?.relative_path === relPath) {
      closePreviewModal();
    }
    toast("success", `${item.asset_type === "sequence" ? "Sequence" : "Asset"} deleted`);
    await reloadLoadedPages();
  } catch (error) {
    console.error(error);
    toast("error", error.message || "Could not delete asset.");
  } finally {
    state.deletingPaths.delete(relPath);
    renderBody();
  }
}

async function renameAsset(item) {
  const relPath = item?.relative_path;
  if (!relPath || state.renamingPaths.has(relPath) || state.deletingPaths.has(relPath)) return;

  try {
    const input = await app.extensionManager.dialog.prompt(renameDialogConfigFor(item));
    if (input === null) return;

    const newName = String(input).trim();
    if (!newName || newName === item.display_name) return;

    const reopenModal = state.modal?.modal.classList.contains("is-open") && state.items[state.modalIndex]?.relative_path === relPath;

    state.renamingPaths.add(relPath);
    renderBody();
    if (reopenModal) {
      renderModal(item);
    }

    const payload = await fetchJSON("/archviz_browser/rename", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ path: relPath, new_name: newName }),
    });

    if (reopenModal) {
      closePreviewModal();
    }

    toast("success", `${item.asset_type === "sequence" ? "Sequence" : "Asset"} renamed to ${payload.display_name || newName}`);
    await reloadLoadedPages();

    if (reopenModal) {
      const nextIndex = state.items.findIndex((entry) => entry.relative_path === payload.relative_path);
      if (nextIndex >= 0) {
        openPreview(state.items[nextIndex], nextIndex);
      }
    }
  } catch (error) {
    console.error(error);
    toast("error", error.message || "Could not rename asset.");
  } finally {
    state.renamingPaths.delete(relPath);
    renderBody();
  }
}

function ensureModal() {
  if (state.modal) return state.modal;

  const modal = el("div", "avb-modal");
  const card = el("div", "avb-modal-card");
  const mediaColumn = el("div", "avb-modal-media");
  const head = el("div", "avb-modal-head");
  const headText = el("div");
  const title = el("div", "avb-modal-title", "Preview");
  const subtitle = el("div", "avb-modal-subtitle");
  headText.append(title, subtitle);
  const closeBtn = el("button", "avb-button", "Close");
  head.append(headText, closeBtn);

  const previewWrap = el("div", "avb-preview-wrap");
  const preview = document.createElement("img");
  preview.className = "avb-preview";
  const prevBtn = el("button", "avb-modal-nav", "<");
  const nextBtn = el("button", "avb-modal-nav", ">");
  prevBtn.dataset.dir = "prev";
  nextBtn.dataset.dir = "next";
  previewWrap.append(preview, prevBtn, nextBtn);

  const actions = el("div", "avb-modal-actions");
  const workflowBtn = el("button", "avb-button is-primary", "Load Workflow");
  const downloadBtn = el("button", "avb-button", "Download");
  const copyImageBtn = el("button", "avb-button", "Copy Image");
  const openBtn = el("button", "avb-button", "Open File");
  const copyPathBtn = el("button", "avb-button", "Copy Path");
  const renameBtn = el("button", "avb-button", "Rename");
  const deleteBtn = el("button", "avb-button is-danger", "Delete");
  actions.append(workflowBtn, downloadBtn, copyImageBtn, openBtn, copyPathBtn, renameBtn, deleteBtn);
  mediaColumn.append(head, previewWrap, actions);

  const side = el("div", "avb-modal-side");
  const summaryBlock = el("div", "avb-side-block");
  const summaryLabel = el("div", "avb-side-label", "Selection");
  const summaryValue = el("div", "avb-side-value");
  summaryBlock.append(summaryLabel, summaryValue);

  const detailsBlock = el("div", "avb-side-block");
  const detailsLabel = el("div", "avb-side-label", "Asset Details");
  const detailsGrid = el("div", "avb-side-grid");
  detailsBlock.append(detailsLabel, detailsGrid);

  const hintBlock = el("div", "avb-side-block");
  const hintLabel = el("div", "avb-side-label", "Quick Controls");
  const hintValue = el("div", "avb-keyhint");
  hintValue.textContent = "Use Left and Right to move between assets. Press Escape to close the viewer.";
  hintBlock.append(hintLabel, hintValue);

  side.append(summaryBlock, detailsBlock, hintBlock);
  card.append(mediaColumn, side);
  modal.appendChild(card);
  document.body.appendChild(modal);

  function closeModal() {
    modal.classList.remove("is-open");
    state.modalIndex = -1;
  }

  closeBtn.addEventListener("click", closeModal);
  modal.addEventListener("click", (event) => {
    if (event.target === modal) closeModal();
  });
  prevBtn.addEventListener("click", () => stepModal(-1));
  nextBtn.addEventListener("click", () => stepModal(1));

  document.addEventListener("keydown", (event) => {
    if (!modal.classList.contains("is-open")) return;
    if (event.key === "Escape") closeModal();
    if (event.key === "ArrowLeft") stepModal(-1);
    if (event.key === "ArrowRight") stepModal(1);
  });

  state.modal = {
    modal,
    title,
    subtitle,
    preview,
    prevBtn,
    nextBtn,
    workflowBtn,
    downloadBtn,
    copyImageBtn,
    openBtn,
    copyPathBtn,
    renameBtn,
    deleteBtn,
    summaryValue,
    detailsGrid,
    close: closeModal,
  };
  return state.modal;
}

function renderModal(item) {
  const modal = ensureModal();
  const deleting = state.deletingPaths.has(item.relative_path);
  const renaming = state.renamingPaths.has(item.relative_path);
  const busy = deleting || renaming;
  modal.title.textContent = item.display_name;
  modal.subtitle.textContent = item.relative_path;
  modal.preview.src = item.asset_type === "sequence" ? item.preview_url : item.full_url;
  modal.summaryValue.textContent = `${itemSecondaryLabel(item)} in ${item.project}`;
  modal.detailsGrid.innerHTML = "";

  for (const [label, value] of infoGridFor(item)) {
    const cell = el("div", "avb-side-kv");
    cell.append(el("div", "avb-side-label", label), el("div", "avb-side-value", String(value || "Unknown")));
    modal.detailsGrid.appendChild(cell);
  }

  modal.workflowBtn.disabled = busy || !item.workflow_available;
  modal.workflowBtn.style.opacity = busy || !item.workflow_available ? "0.45" : "1";
  modal.workflowBtn.onclick = () => openWorkflowFor(item);
  modal.downloadBtn.disabled = busy;
  modal.downloadBtn.onclick = () => triggerDownload(item);
  modal.copyImageBtn.disabled = busy;
  modal.copyImageBtn.onclick = () => copyAssetImage(item);
  modal.openBtn.disabled = busy;
  modal.openBtn.onclick = () => window.open(item.full_url, "_blank", "noopener,noreferrer");
  modal.copyPathBtn.disabled = busy;
  modal.copyPathBtn.onclick = () => copyToClipboard(item.relative_path, "Path");
  modal.renameBtn.disabled = busy;
  modal.renameBtn.textContent = renaming ? "Renaming..." : "Rename";
  modal.renameBtn.onclick = () => renameAsset(item);
  modal.deleteBtn.disabled = busy;
  modal.deleteBtn.textContent = deleting ? "Deleting..." : "Delete";
  modal.deleteBtn.onclick = () => deleteAsset(item);
  modal.prevBtn.disabled = state.modalIndex <= 0;
  modal.nextBtn.disabled = state.modalIndex >= state.items.length - 1;
  modal.modal.classList.add("is-open");
}

function openPreview(item, index) {
  state.modalIndex = index;
  renderModal(item);
}

function stepModal(direction) {
  const nextIndex = state.modalIndex + direction;
  if (nextIndex < 0 || nextIndex >= state.items.length) return;
  state.modalIndex = nextIndex;
  renderModal(state.items[nextIndex]);
}

function createCard(item, index) {
  const deleting = state.deletingPaths.has(item.relative_path);
  const renaming = state.renamingPaths.has(item.relative_path);
  const busy = deleting || renaming;
  const card = el("div", "avb-card");
  const media = el("div", "avb-card-media");
  const img = document.createElement("img");
  img.loading = "lazy";
  img.src = item.thumb_url;
  img.alt = item.display_name;
  const mediaTools = el("div", "avb-card-media-tools");
  const downloadBtn = createIconButton("pi pi-download", item.asset_type === "sequence" ? "Download ZIP" : "Download PNG");
  downloadBtn.disabled = busy;
  downloadBtn.addEventListener("click", (event) => {
    event.stopPropagation();
    triggerDownload(item);
  });
  mediaTools.append(downloadBtn);

  if (item.asset_type === "image") {
    const copyImageBtn = createIconButton("pi pi-copy", "Copy image");
    copyImageBtn.disabled = busy;
    copyImageBtn.addEventListener("click", async (event) => {
      event.stopPropagation();
      await copyAssetImage(item);
    });
    mediaTools.append(copyImageBtn);
  }

  const overlay = el("div", "avb-card-overlay");
  const leftChip = el("div", "avb-chip", item.asset_type);
  const rightChip = el("div", `avb-chip${item.workflow_available ? " is-accent" : ""}`, item.workflow_available ? "Workflow" : "Preview");
  overlay.append(leftChip, rightChip);
  media.append(img, mediaTools, overlay);

  if (item.asset_type === "sequence") {
    media.addEventListener("mouseenter", () => { img.src = item.preview_url; });
    media.addEventListener("mouseleave", () => { img.src = item.thumb_url; });
  }

  const body = el("div", "avb-card-body");
  const name = el("div", "avb-name", item.display_name);
  const meta = el("div", "avb-meta");
  for (const pill of metaPills(item)) {
    meta.appendChild(el("div", "avb-meta-pill", pill));
  }

  const actions = el("div", "avb-actions");
  const previewBtn = el("button", "avb-button is-primary", item.asset_type === "sequence" ? "View Sequence" : "View Asset");
  const workflowBtn = el("button", "avb-button", "Workflow");
  const renameBtn = el("button", "avb-button", renaming ? "Renaming..." : "Rename");
  const deleteBtn = el("button", "avb-button is-danger", deleting ? "Deleting..." : "Delete");
  previewBtn.disabled = busy;
  workflowBtn.disabled = busy || !item.workflow_available;
  workflowBtn.style.opacity = busy || !item.workflow_available ? "0.45" : "1";
  renameBtn.disabled = busy;
  deleteBtn.disabled = busy;
  previewBtn.addEventListener("click", () => openPreview(item, index));
  workflowBtn.addEventListener("click", () => openWorkflowFor(item));
  renameBtn.addEventListener("click", () => renameAsset(item));
  deleteBtn.addEventListener("click", () => deleteAsset(item));
  actions.append(previewBtn, workflowBtn, renameBtn, deleteBtn);

  card.addEventListener("dblclick", () => openPreview(item, index));
  body.append(name, meta, actions);
  card.append(media, body);
  return card;
}

function updateSummary() {
  if (!state.summaryTotal) return;
  state.summaryTotal.textContent = `${state.total || 0}`;
  state.summaryVisible.textContent = `${state.items.length}`;
  state.summaryLatest.textContent = latestItemLabel();
  state.summaryVisibleMeta.textContent = visibleCountLabel();
  state.summaryTotalMeta.textContent = `${state.category} in ${state.project || "no project"}`;
  state.summaryLatestMeta.textContent = state.workflowOnly ? "Workflow-only filter active" : "All matching assets";
}

function renderBody() {
  if (!state.grid) return;
  state.projectSelect.value = state.project || "";
  state.createProjectBtn.disabled = state.creatingProject;
  state.createProjectBtn.textContent = state.creatingProject ? "Creating..." : "Create Project";
  state.searchInput.value = state.query || "";
  state.sortSelect.value = state.sort;
  state.workflowToggle.classList.toggle("is-active", state.workflowOnly);
  state.workflowToggle.textContent = state.workflowOnly ? "Workflow Only: On" : "Workflow Only: Off";
  state.tabs.forEach((button) => button.classList.toggle("is-active", button.dataset.category === state.category));
  updateSummary();

  state.grid.innerHTML = "";
  if (state.loading && !state.items.length) {
    state.grid.appendChild(el("div", "avb-status", "Loading project content..."));
  } else if (!state.items.length) {
    const empty = el("div", "avb-empty");
    empty.textContent = "No assets matched this view. Try another project, search term, or turn off the workflow-only filter.";
    state.grid.appendChild(empty);
  } else {
    state.items.forEach((item, index) => state.grid.appendChild(createCard(item, index)));
  }

  state.status.textContent = state.loading ? "Refreshing asset list..." : visibleCountLabel();
  state.loadMoreBtn.style.display = state.hasMore ? "block" : "none";
  state.loadMoreBtn.disabled = state.loading;
  state.loadMoreBtn.textContent = state.loading && state.items.length ? "Loading more..." : "Load More";
}

async function refreshAssets() {
  state.page = 1;
  persistState();
  await loadAssets();
}

async function maybeLoadMore() {
  if (!state.hasMore || state.loading) return;
  state.page += 1;
  await loadAssets({ append: true });
}

function buildUI(container) {
  injectStyles();
  restoreState();

  const root = el("div", "avb-root");
  const toolbar = el("div", "avb-toolbar");

  const hero = el("div", "avb-hero");
  const heroText = el("div");
  heroText.append(
    el("div", "avb-title", "Brick Asset Browser"),
    el("div", "avb-subtitle", "Browse project renders and sequences inside ComfyUI with stronger search, sorting, previews, and workflow loading."),
  );
  hero.append(heroText, el("div", "avb-badge", "Sidebar Browser"));

  const topRow = el("div", "avb-row");
  const projectSelect = el("select", "avb-control avb-select");
  const createProjectBtn = el("button", "avb-button", "Create Project");
  const refreshBtn = el("button", "avb-button", "Refresh");
  topRow.append(projectSelect, createProjectBtn, refreshBtn);

  const tabs = CATEGORIES.map((category) => {
    const button = el("button", "avb-button avb-tab", category);
    button.dataset.category = category;
    return button;
  });
  const tabsWrap = el("div", "avb-tabs");
  tabs.forEach((button) => tabsWrap.appendChild(button));

  const middleRow = el("div", "avb-row");
  const sortSelect = el("select", "avb-control avb-select");
  for (const option of SORT_OPTIONS) {
    const node = document.createElement("option");
    node.value = option.value;
    node.textContent = option.label;
    sortSelect.appendChild(node);
  }
  const workflowToggle = el("button", "avb-toggle", "Workflow Only: Off");
  middleRow.append(tabsWrap, sortSelect, workflowToggle);

  const searchRow = el("div", "avb-row");
  const inputWrap = el("div", "avb-input-wrap");
  const searchIcon = el("div", "avb-input-icon", ">");
  const searchInput = el("input", "avb-control avb-search");
  searchInput.placeholder = "Search filename, shot, camera, date, version, resolution";
  inputWrap.append(searchIcon, searchInput);
  searchRow.appendChild(inputWrap);

  const summary = el("div", "avb-summary");
  const totalCard = el("div", "avb-summary-card");
  const totalValue = el("div", "avb-summary-value", "0");
  const totalMeta = el("div", "avb-summary-meta", "Waiting for project data");
  totalCard.append(el("div", "avb-summary-label", "Total Matches"), totalValue, totalMeta);

  const visibleCard = el("div", "avb-summary-card");
  const visibleValue = el("div", "avb-summary-value", "0");
  const visibleMeta = el("div", "avb-summary-meta", "No assets yet");
  visibleCard.append(el("div", "avb-summary-label", "Loaded In Grid"), visibleValue, visibleMeta);

  const latestCard = el("div", "avb-summary-card");
  const latestValue = el("div", "avb-summary-value", "Unknown");
  const latestMeta = el("div", "avb-summary-meta", "All matching assets");
  latestCard.append(el("div", "avb-summary-label", "Latest Date"), latestValue, latestMeta);
  summary.append(totalCard, visibleCard, latestCard);

  const pillRow = el("div", "avb-pill-row");
  const status = el("div", "avb-chip", "Ready");
  const tip = el("div", "avb-chip", "Double-click a card to open viewer");
  pillRow.append(status, tip);

  toolbar.append(hero, topRow, middleRow, searchRow, summary, pillRow);

  const wrap = el("div", "avb-grid-wrap");
  const grid = el("div", "avb-grid");
  wrap.appendChild(grid);

  const footer = el("div", "avb-footer");
  const loadMoreBtn = el("button", "avb-button avb-loadmore", "Load More");
  footer.appendChild(loadMoreBtn);

  root.append(toolbar, wrap, footer);
  container.replaceChildren(root);

  Object.assign(state, {
    root,
    grid,
    projectSelect,
    createProjectBtn,
    refreshBtn,
    searchInput,
    sortSelect,
    workflowToggle,
    tabs,
    loadMoreBtn,
    status,
    summaryTotal: totalValue,
    summaryTotalMeta: totalMeta,
    summaryVisible: visibleValue,
    summaryVisibleMeta: visibleMeta,
    summaryLatest: latestValue,
    summaryLatestMeta: latestMeta,
  });

  refreshBtn.addEventListener("click", async () => {
    await loadProjects();
    injectProjectOptions();
    await refreshAssets();
  });

  createProjectBtn.addEventListener("click", async () => {
    await promptAndCreateProject();
  });

  projectSelect.addEventListener("change", async () => {
    state.project = projectSelect.value;
    await refreshAssets();
  });

  sortSelect.addEventListener("change", async () => {
    state.sort = sortSelect.value;
    await refreshAssets();
  });

  workflowToggle.addEventListener("click", async () => {
    state.workflowOnly = !state.workflowOnly;
    await refreshAssets();
  });

  let searchTimer = null;
  searchInput.addEventListener("input", () => {
    clearTimeout(searchTimer);
    searchTimer = setTimeout(async () => {
      state.query = searchInput.value.trim();
      await refreshAssets();
    }, 220);
  });

  for (const tab of tabs) {
    tab.addEventListener("click", async () => {
      if (state.category === tab.dataset.category) return;
      state.category = tab.dataset.category;
      await refreshAssets();
    });
  }

  wrap.addEventListener("scroll", async () => {
    const threshold = 420;
    const nearBottom = wrap.scrollTop + wrap.clientHeight >= wrap.scrollHeight - threshold;
    if (nearBottom) await maybeLoadMore();
  });

  loadMoreBtn.addEventListener("click", async () => {
    await maybeLoadMore();
  });
}

app.registerExtension({
  name: "archviz.browser.sidebar",
  async setup() {
    ensureSidebarTitleFix();
    app.extensionManager.registerSidebarTab({
      id: TAB_ID,
      icon: "pi pi-images",
      title: SIDEBAR_TITLE,
      tooltip: "Browse Brick projects",
      type: "custom",
      render: async (container) => {
        buildUI(container);
        ensureSidebarTitleFix();
        try {
          await loadProjects();
          injectProjectOptions();
          persistState();
          await loadAssets();
        } catch (error) {
          console.error(error);
          toast("error", error.message || "Could not initialize Brick Browser.");
          renderBody();
        }
      },
    });
  },
});
