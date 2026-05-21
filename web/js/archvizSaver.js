import { app } from "../../scripts/app.js";
import { api } from "../../scripts/api.js";

const IMAGE_NODE = "SaveArchVizImage";
const SEQUENCE_NODE = "SaveArchVizSequence";
const TARGETS = new Set([IMAGE_NODE, SEQUENCE_NODE]);
const DEFAULT_PROJECT = "0000_base";
const NODE_MIN_WIDTH = 340;

function applyNodeLook(node) {
  node.color = "#364152";
  node.bgcolor = "#1c222b";
  node.boxcolor = "#0f141a";
  node.round_radius = 10;
  node.size = [Math.max(node.size?.[0] || 0, NODE_MIN_WIDTH), Math.max(node.size?.[1] || 0, 220)];
}

function stylePanel(element) {
  element.style.width = "100%";
  element.style.boxSizing = "border-box";
  element.style.display = "flex";
  element.style.flexDirection = "column";
  element.style.gap = "8px";
  element.style.padding = "8px";
  element.style.borderRadius = "10px";
  element.style.background = "#222b36";
  element.style.border = "1px solid rgba(255,255,255,0.08)";
}

function styleLabel(element) {
  element.style.fontSize = "12px";
  element.style.fontWeight = "600";
  element.style.letterSpacing = "0.02em";
  element.style.opacity = "0.92";
}

function styleInput(element) {
  element.style.width = "100%";
  element.style.boxSizing = "border-box";
  element.style.padding = "8px 10px";
  element.style.borderRadius = "8px";
  element.style.border = "1px solid rgba(255,255,255,0.12)";
  element.style.background = "#151b22";
  element.style.color = "inherit";
  element.style.outline = "none";
}

function styleButton(element) {
  element.style.width = "100%";
  element.style.boxSizing = "border-box";
  element.style.padding = "8px 10px";
  element.style.borderRadius = "8px";
  element.style.border = "1px solid rgba(255,255,255,0.12)";
  element.style.background = "#2a3340";
  element.style.color = "inherit";
  element.style.fontWeight = "600";
  element.style.cursor = "pointer";
}

function setDomWidgetHeight(widget, height) {
  if (!widget) return;
  widget.computeSize = (width) => [Math.max(width || NODE_MIN_WIDTH, NODE_MIN_WIDTH) - 24, height];
}

async function fetchProjects() {
  const resp = await api.fetchApi("/archviz_saver/projects", { method: "GET" });
  if (!resp.ok) {
    throw new Error(`Failed to fetch projects: ${resp.status}`);
  }
  const data = await resp.json();
  return data.projects || [DEFAULT_PROJECT];
}

async function createProject(projectName) {
  const body = new FormData();
  body.append("project_name", projectName);
  const resp = await api.fetchApi("/archviz_saver/projects", { method: "POST", body });
  const data = await resp.json();
  if (!resp.ok) {
    throw new Error(data?.error || "Failed to create project.");
  }
  return data;
}

function getWidget(node, name) {
  return node.widgets?.find((w) => w.name === name);
}

function setWidgetVisible(widget, visible) {
  if (!widget) return;

  widget.options = widget.options || {};
  widget.options.hidden = !visible;
  widget.hidden = !visible;

  if (!widget.__archvizOriginalType) {
    widget.__archvizOriginalType = widget.type;
  }
  if (!widget.__archvizOriginalComputeSize) {
    widget.__archvizOriginalComputeSize = widget.computeSize;
  }

  if (visible) {
    widget.type = widget.__archvizOriginalType || widget.type;
    widget.computeSize = widget.__archvizOriginalComputeSize || widget.computeSize;
    delete widget.__archvizHidden;
  } else {
    widget.type = widget.__archvizOriginalType || widget.type;
    widget.computeSize = () => [0, -4];
    widget.__archvizHidden = true;
  }

  for (const linked of widget.linkedWidgets || []) {
    linked.options = linked.options || {};
    linked.options.hidden = !visible;
    linked.hidden = !visible;
  }
}

function ensureCameraInputWidget(node) {
  if ((node.comfyClass || node.constructor?.comfyClass) !== IMAGE_NODE) return;
  if (node.__archvizCameraDomWidget) return node.__archvizCameraDomWidget;

  const wrap = document.createElement("div");
  stylePanel(wrap);
  wrap.style.marginBottom = "6px";

  const label = document.createElement("label");
  label.textContent = "Camera Number";
  styleLabel(label);

  const input = document.createElement("input");
  input.type = "number";
  input.step = "1";
  input.min = "0";
  input.placeholder = "0";
  styleInput(input);

  wrap.appendChild(label);
  wrap.appendChild(input);

  const domWidget = node.addDOMWidget("camera_value", "camera_value", wrap);
  setDomWidgetHeight(domWidget, 86);
  node.__archvizCameraDomWidget = domWidget;
  node.__archvizCameraDomLabel = label;
  node.__archvizCameraDomInput = input;

  input.addEventListener("input", () => {
    syncCameraDomToHiddenWidgets(node);
  });
  input.addEventListener("change", () => {
    syncCameraDomToHiddenWidgets(node);
  });

  return domWidget;
}

function syncCameraDomToHiddenWidgets(node) {
  const modeWidget = getWidget(node, "camera_mode");
  const numberWidget = getWidget(node, "camera_number");
  const nameWidget = getWidget(node, "camera_name");
  const input = node.__archvizCameraDomInput;
  if (!modeWidget || !numberWidget || !nameWidget || !input) return;

  if (modeWidget.value === "camera_name") {
    const value = String(input.value ?? "");
    nameWidget.value = value;
    if (typeof nameWidget.callback === "function") nameWidget.callback(value, app.canvas, node, null, nameWidget);
  } else {
    const parsed = Number.parseInt(input.value, 10);
    const value = Number.isFinite(parsed) ? parsed : 0;
    numberWidget.value = value;
    if (typeof numberWidget.callback === "function") numberWidget.callback(value, app.canvas, node, null, numberWidget);
  }
}

function updateCameraWidgets(node) {
  if ((node.comfyClass || node.constructor?.comfyClass) !== IMAGE_NODE) return;

  const modeWidget = getWidget(node, "camera_mode");
  const numberWidget = getWidget(node, "camera_number");
  const nameWidget = getWidget(node, "camera_name");
  if (!modeWidget || !numberWidget || !nameWidget) return;

  setWidgetVisible(numberWidget, false);
  setWidgetVisible(nameWidget, false);
  ensureCameraInputWidget(node);

  const input = node.__archvizCameraDomInput;
  const label = node.__archvizCameraDomLabel;
  if (!input || !label) return;

  if (modeWidget.value === "camera_name") {
    label.textContent = "Camera Name";
    input.type = "text";
    input.step = "";
    input.min = "";
    input.placeholder = "name";
    input.value = nameWidget.value ?? "";
  } else {
    label.textContent = "Camera Number";
    input.type = "number";
    input.step = "1";
    input.min = "0";
    input.placeholder = "0";
    const value = Number.isFinite(Number(numberWidget.value)) ? String(numberWidget.value) : "0";
    input.value = value;
  }

  reorderImageNodeWidgets(node);

  if (typeof node.computeSize === "function") {
    node.size = [Math.max(node.computeSize()[0], NODE_MIN_WIDTH), node.computeSize()[1]];
  }
  node.setDirtyCanvas?.(true, true);
  app.graph.setDirtyCanvas(true, true);
}


function reorderImageNodeWidgets(node) {
  if ((node.comfyClass || node.constructor?.comfyClass) !== IMAGE_NODE) return;
  if (!Array.isArray(node.widgets) || !node.widgets.length) return;

  const get = (name) => node.widgets.find((w) => w?.name === name);
  const projectWidget = get("project_name");
  const modeWidget = get("camera_mode");
  const cameraDomWidget = get("camera_value");
  const createDomWidget = get("create_project_dom");
  const numberWidget = get("camera_number");
  const nameWidget = get("camera_name");

  const preferred = [projectWidget, modeWidget, cameraDomWidget, createDomWidget, numberWidget, nameWidget].filter(Boolean);
  const preferredSet = new Set(preferred);
  const remaining = node.widgets.filter((w) => !preferredSet.has(w));
  node.widgets = [...preferred, ...remaining];

  if (typeof node.computeSize === "function") {
    node.size = [Math.max(node.computeSize()[0], NODE_MIN_WIDTH), node.computeSize()[1]];
  }
  node.setDirtyCanvas?.(true, true);
  app.graph.setDirtyCanvas(true, true);
}

function getProjectWidget(node) {
  return getWidget(node, "project_name");
}

function setProjectOptions(node, projects, selected = null) {
  const projectWidget = getProjectWidget(node);
  if (!projectWidget) return;

  const values = Array.from(new Set([DEFAULT_PROJECT, ...(projects || [])]));
  projectWidget.options = projectWidget.options || {};
  projectWidget.options.values = values;

  if (selected && values.includes(selected)) {
    projectWidget.value = selected;
  } else if (!values.includes(projectWidget.value)) {
    projectWidget.value = DEFAULT_PROJECT;
  } else if (!projectWidget.value) {
    projectWidget.value = DEFAULT_PROJECT;
  }

  node.setDirtyCanvas?.(true, true);
  app.graph.setDirtyCanvas(true, true);
}

async function refreshProjects(node, selected = null) {
  const projects = await fetchProjects();
  const projectWidget = getProjectWidget(node);
  const preferredSelection =
    selected !== null && selected !== undefined ? selected : projectWidget?.value ?? null;
  setProjectOptions(node, projects, preferredSelection);
}

function toast(severity, detail) {
  app.extensionManager.toast?.add?.({
    severity,
    summary: "Brick Saver",
    detail,
    life: 4000,
  });
}

function isMissingProjectName(value) {
  const clean = String(value ?? "").trim();
  return !clean || clean === DEFAULT_PROJECT;
}

function findInvalidSaverProjectNodes(prompt) {
  const output = prompt?.output || {};
  const invalid = [];

  for (const [nodeId, nodeData] of Object.entries(output)) {
    if (!TARGETS.has(nodeData?.class_type)) continue;

    const graphNode = app.graph?.getNodeById?.(Number(nodeId));
    const widgetValue = graphNode ? getProjectWidget(graphNode)?.value : undefined;
    const promptValue = nodeData?.inputs?.project_name;
    const projectName = typeof promptValue === "string" ? promptValue : widgetValue;

    if (isMissingProjectName(projectName)) {
      invalid.push({
        id: nodeId,
        title: graphNode?.title || nodeData.class_type,
      });
    }
  }

  return invalid;
}

function installProjectQueueGuard() {
  if (window.__brickSaverProjectQueueGuardInstalled) return;
  window.__brickSaverProjectQueueGuardInstalled = true;

  const originalQueuePrompt = api.queuePrompt;
  api.queuePrompt = async function (number, prompt, ...args) {
    const invalid = findInvalidSaverProjectNodes(prompt);
    if (invalid.length) {
      const nodeList = invalid.map((node) => `${node.title} (#${node.id})`).join(", ");
      const message =
        `Brick Saver blocked this run. Choose or create the correct project before queueing. ` +
        `"${DEFAULT_PROJECT}" is only a placeholder. Check: ${nodeList}`;

      toast("error", message);
      alert(message);
      throw new Error(message);
    }

    return originalQueuePrompt.call(this, number, prompt, ...args);
  };
}

installProjectQueueGuard();

async function promptAndCreateProject(node) {
  try {
    const name = await app.extensionManager.dialog.prompt({
      title: "Create Brick Project",
      message: "Enter project name:",
      defaultValue: "",
    });

    if (name === null) return;
    const trimmed = String(name).trim();
    if (!trimmed) return;

    const data = await createProject(trimmed);
    setProjectOptions(node, data.projects || [], data.project_name);
    toast("success", `Project created: ${data.project_name}`);
  } catch (error) {
    console.error(error);
    toast("error", error.message || "Could not create project.");
  }
}

function reorderSequenceNodeWidgets(node) {
  if ((node.comfyClass || node.constructor?.comfyClass) !== SEQUENCE_NODE) return;
  if (!Array.isArray(node.widgets) || !node.widgets.length) return;

  const get = (name) => node.widgets.find((w) => w?.name === name);
  const projectWidget = get("project_name");
  const shotWidget = get("shot_number");
  const createDomWidget = get("create_project_dom");
  const downloadDomWidget = get("download_zip_dom");

  const preferred = [projectWidget, shotWidget, createDomWidget, downloadDomWidget].filter(Boolean);
  const preferredSet = new Set(preferred);
  const remaining = node.widgets.filter((w) => !preferredSet.has(w));
  node.widgets = [...preferred, ...remaining];

  if (typeof node.computeSize === "function") {
    node.size = [Math.max(node.computeSize()[0], NODE_MIN_WIDTH), node.computeSize()[1]];
  }
  node.setDirtyCanvas?.(true, true);
  app.graph.setDirtyCanvas(true, true);
}

function ensureCreateProjectDomButton(node) {
  const comfyClass = node.comfyClass || node.constructor?.comfyClass;
  if (!TARGETS.has(comfyClass)) return;
  if (node.__archvizCreateProjectDomWidget) return;

  const wrap = document.createElement("div");
  wrap.style.width = "100%";
  wrap.style.boxSizing = "border-box";
  wrap.style.paddingTop = comfyClass === SEQUENCE_NODE ? "6px" : "10px";
  wrap.style.marginBottom = comfyClass === SEQUENCE_NODE ? "2px" : "4px";

  const button = document.createElement("button");
  button.textContent = "Create Project";
  styleButton(button);
  button.addEventListener("click", async (event) => {
    event.preventDefault();
    event.stopPropagation();
    await promptAndCreateProject(node);
  });

  wrap.appendChild(button);
  const domWidget = node.addDOMWidget("create_project_dom", "create_project_dom", wrap);
  setDomWidgetHeight(domWidget, 54);
  node.__archvizCreateProjectDomWidget = domWidget;

  if (comfyClass === IMAGE_NODE) {
    reorderImageNodeWidgets(node);
  } else if (comfyClass === SEQUENCE_NODE) {
    reorderSequenceNodeWidgets(node);
  }
}

function getDownloadFilenameFromHeader(header) {
  if (!header) return null;
  const match = /filename="?([^";]+)"?/i.exec(header);
  return match?.[1] || null;
}

async function downloadLatestSequenceZip(node) {
  try {
    const resp = await api.fetchApi(`/archviz_saver/sequence/download?node_id=${encodeURIComponent(node.id)}`, { method: "GET" });
    if (!resp.ok) {
      let message = `Download failed: ${resp.status}`;
      try {
        const data = await resp.json();
        if (data?.error) message = data.error;
      } catch {}
      throw new Error(message);
    }

    const blob = await resp.blob();
    const href = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = href;
    a.download = getDownloadFilenameFromHeader(resp.headers.get("Content-Disposition")) || "sequence.zip";
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(href);
    toast("success", "Sequence ZIP downloaded.");
  } catch (error) {
    console.error(error);
    toast("error", error.message || "Could not download sequence ZIP.");
  }
}

function ensureSequenceDownloadDomButton(node) {
  if ((node.comfyClass || node.constructor?.comfyClass) !== SEQUENCE_NODE) return;
  if (node.__archvizSequenceDownloadDomWidget) return;

  const wrap = document.createElement("div");
  wrap.style.width = "100%";
  wrap.style.boxSizing = "border-box";
  wrap.style.paddingTop = "6px";
  wrap.style.marginBottom = "2px";

  const button = document.createElement("button");
  button.textContent = "Download ZIP";
  styleButton(button);
  button.addEventListener("click", async (event) => {
    event.preventDefault();
    event.stopPropagation();
    await downloadLatestSequenceZip(node);
  });

  wrap.appendChild(button);
  const domWidget = node.addDOMWidget("download_zip_dom", "download_zip_dom", wrap);
  setDomWidgetHeight(domWidget, 50);
  node.__archvizSequenceDownloadDomWidget = domWidget;
  reorderSequenceNodeWidgets(node);
}

app.registerExtension({
  name: "archviz.saver.project-ui",
  async nodeCreated(node) {
    const comfyClass = node.comfyClass || node.constructor?.comfyClass || node.constructor?.ComfyClass;
    if (!TARGETS.has(comfyClass)) return;

    applyNodeLook(node);
    ensureCreateProjectDomButton(node);
    ensureSequenceDownloadDomButton(node);

    if (comfyClass === IMAGE_NODE) {
      const modeWidget = getWidget(node, "camera_mode");
      if (modeWidget) {
        const originalCallback = modeWidget.callback;
        modeWidget.callback = (...args) => {
          if (typeof originalCallback === "function") originalCallback(...args);
          updateCameraWidgets(node);
        };
      }

      const originalOnConfigure = node.onConfigure;
      node.onConfigure = function (...args) {
        const result = typeof originalOnConfigure === "function" ? originalOnConfigure.apply(this, args) : undefined;
        queueMicrotask(() => updateCameraWidgets(this));
        return result;
      };

      updateCameraWidgets(node);
      reorderImageNodeWidgets(node);
    }

    if (typeof node.computeSize === "function") {
      node.size = [Math.max(node.computeSize()[0], NODE_MIN_WIDTH), node.computeSize()[1]];
    }

    try {
      await refreshProjects(node);
    } catch (error) {
      console.warn("Brick Saver project refresh failed", error);
    }
  },
});
