const state = {
  activeTaskId: null,
  activeTab: "intro",
  activeInterfaceKey: null,
  interfaceOpenKey: null,
  clearedInterfaceKeys: new Set(),
  logCursor: 0,
  consoleLines: [],
  layoutMode: "grid",
  tasks: new Map(),
};

const LOCAL_SEAMAIL_PATH = "C:\\2026_projects\\seaman_ghi_final\\SeaMail";
const LOCAL_GAME_EXE = "C:\\2026_projects\\seaman_ghi_final\\SeaMail\\Seaman_1_2_57.exe";

const MAX_CONSOLE_LINES = 250;

function setLauncherNote(root, message, tone = "info") {
  const note = root.querySelector("[data-launcher-note]");
  if (!note) {
    return;
  }

  if (!message) {
    note.hidden = true;
    note.textContent = "";
    note.className = "launcher-note";
    return;
  }

  note.hidden = false;
  note.textContent = message;
  note.className = `launcher-note ${tone}`;
}

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

function defaultGameExecutableFor(seamailPath) {
  if (!seamailPath) {
    return LOCAL_GAME_EXE;
  }
  return `${seamailPath.replace(/[\\\/]+$/, "")}\\Seaman_1_2_57.exe`;
}

async function initializeStageSelector(root) {
  const buttons = Array.from(root.querySelectorAll("[data-stage-exe]"));
  const output = root.querySelector("[data-stage-output]");
  if (!buttons.length) return;

  let seamailRoot = "";

  try {
    const resp = await fetch("/api/config");
    const payload = await resp.json();
    seamailRoot = payload.config?.seamail_root || "";
    const currentExe = (payload.config?.game_executable || "").split(/[\\/]/).pop();
    buttons.forEach((btn) => btn.classList.toggle("active", btn.dataset.stageExe === currentExe));
    const active = buttons.find((b) => b.dataset.stageExe === currentExe);
    if (!active) {
      const baby = buttons.find((b) => b.dataset.stageExe === "Seaman_Stage1_Baby.exe");
      if (baby) {
        baby.classList.add("active");
        const fullPath = seamailRoot.replace(/[/\\]$/, "") + "\\Seaman_Stage1_Baby.exe";
        seamailRoot = seamailRoot; // already set
        fetch("/api/config", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ game_executable: fullPath }),
        }).catch(() => {});
      }
    }
    if (output) output.textContent = active ? `Stage: ${active.textContent}` : "Stage: Baby";
  } catch (_) {
    if (output) output.textContent = "Could not load config";
  }

  const FIXLOOP_STAGES = ["Seaman_Stage5_Adult.exe", "Seaman_Stage8_Frog.exe"];
  const fixloopNote = root.querySelector("[data-stage-fixloop-note]");

  function updateFixloopNote(exeName) {
    const needed = FIXLOOP_STAGES.includes(exeName);
    if (fixloopNote) fixloopNote.hidden = !needed;
    root.querySelectorAll("[data-stage-fixloop-row]").forEach((row) => {
      row.hidden = !needed;
    });
  }

  // Set note on load for current active stage
  const currentExeName = (root.querySelector("[data-stage-exe].active") || {}).dataset?.stageExe || "";
  updateFixloopNote(currentExeName);

  buttons.forEach((btn) => {
    btn.addEventListener("click", async () => {
      const exeName = btn.dataset.stageExe;
      const fullPath = seamailRoot.replace(/[/\\]$/, "") + "\\" + exeName;
      try {
        await fetch("/api/config", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ game_executable: fullPath }),
        });
        buttons.forEach((b) => b.classList.toggle("active", b === btn));
        if (output) output.textContent = `Stage: ${btn.textContent.replace(/\s*⚠.*/, "")}`;
        updateFixloopNote(exeName);
        const gameExeInput = root.querySelector("[data-config-game-executable]");
        if (gameExeInput) gameExeInput.value = fullPath;
        const exeSelect = root.querySelector("[data-config-exe-select]");
        if (exeSelect) exeSelect.value = exeName;
      } catch (_) {}
    });
  });
}

function updateLanguage(root) {
  const buttons = Array.from(root.querySelectorAll("[data-language-choice]"));
  const output = root.querySelector("[data-language-output]");
  buttons.forEach((button) => {
    button.addEventListener("click", () => {
      buttons.forEach((item) => item.classList.toggle("active", item === button));
      output.textContent = `${button.dataset.languageChoice} selected for this launcher`;
    });
  });
}

function initializeTabs(root) {
  const buttons = Array.from(root.querySelectorAll("[data-tab-target]"));
  const panels = Array.from(root.querySelectorAll("[data-tab-panel]"));

  buttons.forEach((button) => {
    button.addEventListener("click", () => {
      const target = button.dataset.tabTarget;
      state.activeTab = target;
      state.interfaceOpenKey = null;

      buttons.forEach((item) => {
        item.classList.toggle("active", item === button);
        item.setAttribute("aria-selected", item === button ? "true" : "false");
      });

      panels.forEach((panel) => {
        const isActive = panel.id === target;
        panel.classList.toggle("active", isActive);
        panel.toggleAttribute("hidden", !isActive);
      });

      syncWorkspaceVisibility(root);
      renderInterfaceShell(root);

      const firstTask = root.querySelector(`[data-task-card][data-task-group="${target}"]`);
      const activeCard = state.activeTaskId
        ? root.querySelector(`[data-task-card][data-task-id="${state.activeTaskId}"]`)
        : null;
      if (!["intro", "todo"].includes(target) && firstTask && (!activeCard || activeCard.dataset.taskGroup !== target)) {
        selectTask(firstTask.dataset.taskId, root);
      }

      if (target === "settings") {
        loadConfigSettings(root).catch(() => {});
      }
      if (target === "todo") {
        refreshTodoTab(root).catch(() => {});
      }
    });
  });
}

function applyWorkspaceLayout(root) {
  const prototype = root;
  const workspace = root.querySelector(".workspace");
  const button = root.querySelector("[data-layout-toggle]");
  if (!workspace || !button) {
    return;
  }

  workspace.classList.toggle("workspace-focus", state.layoutMode === "focus");
  workspace.classList.toggle("workspace-stacked", state.layoutMode === "stacked");
  prototype.classList.toggle("layout-grid", state.layoutMode === "grid");
  prototype.classList.toggle("layout-focus", state.layoutMode === "focus");
  prototype.classList.toggle("layout-stacked", state.layoutMode === "stacked");

  const labels = {
    grid: "Layout: Grid",
    focus: "Layout: Focus",
    stacked: "Layout: Stacked",
  };
  button.textContent = labels[state.layoutMode] || "Layout: Grid";
}

function syncWorkspaceVisibility(root) {
  const workspace = root.querySelector("[data-workspace]");
  if (!workspace) {
    return;
  }

  workspace.classList.toggle("workspace-console-hidden", ["intro", "todo", "settings", "docs"].includes(state.activeTab));
  workspace.classList.toggle("workspace-interface-open", Boolean(state.interfaceOpenKey));
}

function initializeLayoutToggle(root) {
  const button = root.querySelector("[data-layout-toggle]");
  if (!button) {
    return;
  }

  const stored = window.localStorage.getItem("launcher-layout-mode");
  if (stored === "grid" || stored === "focus" || stored === "stacked") {
    state.layoutMode = stored;
  }
  applyWorkspaceLayout(root);

  button.addEventListener("click", () => {
    const modes = ["grid", "focus", "stacked"];
    const currentIndex = modes.indexOf(state.layoutMode);
    state.layoutMode = modes[(currentIndex + 1) % modes.length];
    window.localStorage.setItem("launcher-layout-mode", state.layoutMode);
    applyWorkspaceLayout(root);
  });
}

function renderTaskState(root, task) {
  state.tasks.set(task.id, task);
  const badges = Array.from(root.querySelectorAll(`[data-task-status="${task.id}"]`));
  const cards = Array.from(root.querySelectorAll(`[data-task-card][data-task-id="${task.id}"]`));
  const openButtons = Array.from(root.querySelectorAll(`[data-open-button="${task.id}"]`));
  const venvBadges = Array.from(root.querySelectorAll(`[data-venv-status="${task.id}"]`));
  badges.forEach((badge) => {
    badge.textContent = task.status;
    badge.className = `task-status ${task.status}`;
  });
  cards.forEach((card) => {
    card.classList.toggle("active", state.activeTaskId === task.id);
  });
  openButtons.forEach((openButton) => {
    const alwaysOpen = openButton.dataset.openAlways === "true";
    const canOpen = alwaysOpen || (Boolean(task.open_url) && (task.status === "running" || task.status === "completed"));
    openButton.disabled = !canOpen;
  });
  venvBadges.forEach((badge) => {
    if (!task.venv_key) {
      badge.hidden = true;
      return;
    }
    const ready = Boolean(task.venv_status?.ready);
    badge.hidden = false;
    badge.textContent = ready ? "env ready" : "env needed";
    badge.className = `venv-chip ${ready ? "ready" : "missing"}`;
  });
}

function taskMetaText(task) {
  return `${task.kind} ${task.requires_admin ? "admin" : "normal"}`;
}

function getConsoleTaskForInterfaceGroup(group) {
  if (!group?.tasks?.length) {
    return state.activeTaskId ? state.tasks.get(state.activeTaskId) : null;
  }

  const activeGroupTask = state.activeTaskId
    ? group.tasks.find((task) => task.id === state.activeTaskId)
    : null;

  return activeGroupTask || group.tasks[0];
}

function createConsoleMarkup(task, inline = false) {
  const consoleTask = task || { label: "No task selected", status: "idle", script_path: "Choose a task card to view its log" };
  const panelClass = inline ? "console-panel inline-console-panel" : "console-panel";
  const output = state.consoleLines.length ? state.consoleLines.join("\n") : (task ? "No log lines yet." : "Waiting for task selection...");

  return `
    <article class="${panelClass}" ${inline ? 'data-inline-console-panel' : 'data-console-panel'}>
      <div class="console-head">
        <div>
          <p class="section-tag">Live Console</p>
          <h2 data-console-title>${escapeHtml(consoleTask.label)}</h2>
        </div>
        <div class="console-tools">
          <button class="action-button secondary" type="button" data-console-refresh>Refresh Log</button>
          <div class="console-meta">
            <span data-console-status>${escapeHtml(consoleTask.status)}</span>
            <span data-console-path>${escapeHtml(consoleTask.script_path)}</span>
          </div>
        </div>
      </div>
      <pre class="console-output" data-console-output>${escapeHtml(output)}</pre>
    </article>
  `;
}

function createTaskCardMarkup(task, group = task.group) {
  const openButton = task.open_url
    ? `<button class="action-button secondary" type="button" data-open-button="${task.id}"${task.no_start ? ' data-open-always="true"' : ""}>Open</button>`
    : "";
  const launchTag = task.launch_mode === "console" ? `<span>cmd window</span>` : "";
  const venvTag = task.venv_key
    ? `<span class="venv-chip ${task.venv_status?.ready ? "ready" : "missing"}" data-venv-status="${task.id}">${task.venv_status?.ready ? "env ready" : "env needed"}</span>`
    : "";
  const venvButton = task.venv_key
    ? `<button class="action-button secondary" type="button" data-venv-button="${task.id}">Setup Env</button>`
    : "";
  const stopButton = task.launch_mode === "console" || task.can_stop === false
    ? ""
    : `<button class="action-button ghost" type="button" data-stop-button="${task.id}">${escapeHtml(task.stop_label || "Stop")}</button>`;

  return `
    <article class="task-card" data-task-card data-task-id="${task.id}" data-task-group="${group}">
      <div class="task-head">
        <div>
          <h3>${escapeHtml(task.label)}</h3>
          <p class="task-path">${escapeHtml(task.script_path)}</p>
        </div>
        <span class="task-status ${escapeHtml(task.status)}" data-task-status="${task.id}">${escapeHtml(task.status)}</span>
      </div>
      <p>${escapeHtml(task.description)}</p>
      <div class="task-meta">
        <span>${escapeHtml(task.requires_admin ? "needs admin" : "normal")}</span>
        <span>${escapeHtml(group)}</span>
        ${venvTag}
        ${launchTag}
      </div>
      <div class="task-actions">
        <button class="action-button secondary" type="button" data-log-button="${task.id}">View log</button>
        ${venvButton}
        ${openButton}
        ${task.no_start ? "" : `<button class="action-button" type="button" data-start-button="${task.id}">Start</button>`}
        ${stopButton}
      </div>
    </article>
  `;
}

function createActiveTaskCard(task) {
  const wrapper = document.createElement("div");
  wrapper.innerHTML = createTaskCardMarkup(task, "active").trim();
  return wrapper.firstElementChild;
}

function renderActiveTasks(root) {
  const grid = root.querySelector("[data-active-task-grid]");
  const empty = root.querySelector("[data-active-empty]");
  if (!grid || !empty) {
    return;
  }

  const runningTasks = Array.from(state.tasks.values())
    .filter((task) => task.status === "running")
    .sort((a, b) => a.label.localeCompare(b.label));

  grid.innerHTML = "";

  if (!runningTasks.length) {
    grid.hidden = true;
    empty.hidden = false;
    return;
  }

  runningTasks.forEach((task) => {
    grid.appendChild(createActiveTaskCard(task));
  });

  grid.hidden = false;
  empty.hidden = true;
  bindTaskActions(root);
  runningTasks.forEach((task) => renderTaskState(root, task));
}

function buildInterfaceGroups() {
  const groups = new Map();
  Array.from(state.tasks.values())
    .filter((task) => task.status === "running" && (task.has_interface || task.launch_mode === "console"))
    .forEach((task) => {
      const key = task.interface_key || task.id;
      if (!groups.has(key)) {
        groups.set(key, {
          key,
          label: task.interface_label || task.label,
          mode: task.interface_mode || "generic",
          tasks: [],
        });
      }
      groups.get(key).tasks.push(task);
    });

  return Array.from(groups.values())
    .filter((group) => !state.clearedInterfaceKeys.has(group.key))
    .sort((a, b) => a.label.localeCompare(b.label));
}

function renderGenericInterface(root, group) {
  const title = root.querySelector("[data-generic-interface-title]");
  const host = root.querySelector("[data-generic-interface-host]");
  if (!title || !host) {
    return;
  }

  title.textContent = group?.label || "No service selected";
  if (!group) {
    host.innerHTML = "";
    return;
  }

  const cardsMarkup = group.tasks
    .slice()
    .sort((a, b) => a.label.localeCompare(b.label))
    .map((task) => createTaskCardMarkup(task, "interface"))
    .join("");

  const firstWebTask = group.tasks.find((task) => Boolean(task.open_url));
  const consoleTask = getConsoleTaskForInterfaceGroup(group);
  const consoleOnlyGroup = group.tasks.every((task) => task.launch_mode === "console");
  const sidebarMarkup = `
    <div class="service-interface-sidebar">
      <div class="service-task-stack">
        ${cardsMarkup}
      </div>
      ${createConsoleMarkup(consoleTask, true)}
    </div>
  `;

  if (!firstWebTask) {
    title.textContent = consoleOnlyGroup ? `${group.label} launched` : group.label;
    host.innerHTML = `
      ${consoleOnlyGroup ? `
        <div class="toolbar compact">
          <div>
            <p class="section-tag">External Console</p>
            <h2>${escapeHtml(group.label)} is running in its own CMD window.</h2>
          </div>
          <div class="task-actions">
            <button class="action-button secondary" type="button" data-interface-clear>Clear From Bar</button>
          </div>
        </div>
      ` : ""}
      ${sidebarMarkup}
    `;

    const clearButton = host.querySelector("[data-interface-clear]");
    if (clearButton) {
      clearButton.addEventListener("click", () => {
        state.clearedInterfaceKeys.add(group.key);
        if (state.interfaceOpenKey === group.key) {
          state.interfaceOpenKey = null;
        }
        renderInterfaceShell(root);
      });
    }

    bindRefreshActions(root);
    bindTaskActions(root);
    group.tasks.forEach((task) => renderTaskState(root, task));
    updateConsole(root, consoleTask, []);
    return;
  }

  host.innerHTML = `
    <div class="service-interface-layout">
      ${sidebarMarkup}
      <article class="panel interface-web-panel">
        <div class="toolbar compact">
          <div>
            <p class="section-tag">Embedded Interface</p>
            <h2>${escapeHtml(firstWebTask.label)}</h2>
          </div>
          <div class="task-actions">
            ${consoleOnlyGroup ? '<button class="action-button secondary" type="button" data-interface-clear>Clear From Bar</button>' : ""}
            <button class="action-button secondary" type="button" data-interface-refresh>Reload Interface</button>
            <button class="action-button secondary" type="button" data-open-button="${firstWebTask.id}">Open In Tab</button>
          </div>
        </div>
        <iframe
          class="interface-frame"
          src="${escapeHtml(firstWebTask.open_url)}"
          title="${escapeHtml(firstWebTask.label)}"
          loading="lazy"></iframe>
      </article>
    </div>
  `;

  const clearButton = host.querySelector("[data-interface-clear]");
  if (clearButton) {
    clearButton.addEventListener("click", () => {
      state.clearedInterfaceKeys.add(group.key);
      if (state.interfaceOpenKey === group.key) {
        state.interfaceOpenKey = null;
      }
      renderInterfaceShell(root);
    });
  }

  bindRefreshActions(root);
  bindTaskActions(root);
  group.tasks.forEach((task) => renderTaskState(root, task));
  updateConsole(root, consoleTask, []);
}

function renderInterfaceShell(root) {
  const shell = root.querySelector("[data-interface-shell]");
  const bar = root.querySelector("[data-interface-bar]");
  const content = root.querySelector(".interface-content");
  const mailPanel = root.querySelector('[data-interface-panel="mail"]');
  const genericPanel = root.querySelector('[data-interface-panel="generic"]');
  if (!shell || !bar || !content || !mailPanel || !genericPanel) {
    return;
  }

  const groups = buildInterfaceGroups();
  const liveKeys = new Set(
    Array.from(state.tasks.values())
      .filter((task) => task.status === "running" && (task.has_interface || task.launch_mode === "console"))
      .map((task) => task.interface_key || task.id),
  );
  state.clearedInterfaceKeys.forEach((key) => {
    if (!liveKeys.has(key)) {
      state.clearedInterfaceKeys.delete(key);
    }
  });

  if (!groups.length) {
    shell.hidden = true;
    bar.innerHTML = "";
    state.activeInterfaceKey = null;
    state.interfaceOpenKey = null;
    mailPanel.hidden = true;
    genericPanel.hidden = true;
    content.hidden = true;
    syncWorkspaceVisibility(root);
    return;
  }

  shell.hidden = false;
  if (!state.activeInterfaceKey || !groups.some((group) => group.key === state.activeInterfaceKey)) {
    state.activeInterfaceKey = groups[0].key;
  }
  if (state.interfaceOpenKey && !groups.some((group) => group.key === state.interfaceOpenKey)) {
    state.interfaceOpenKey = null;
  }

  const buttonMarkup = groups.map((group) => `
    <button
      class="tab-button ${group.key === state.interfaceOpenKey ? "active" : ""}"
      type="button"
      data-interface-target="${group.key}">
      ${escapeHtml(group.label)}
    </button>
  `).join("");

  const closeMarkup = state.interfaceOpenKey
    ? `<button class="tab-button" type="button" data-interface-close>Back To Launchers</button>`
    : "";

  bar.innerHTML = `${buttonMarkup}${closeMarkup}`;

  bar.querySelectorAll("[data-interface-target]").forEach((button) => {
    button.addEventListener("click", () => {
      const target = button.dataset.interfaceTarget;
      state.activeInterfaceKey = target;
      state.interfaceOpenKey = state.interfaceOpenKey === target ? null : target;
      syncWorkspaceVisibility(root);
      renderInterfaceShell(root);
    });
  });

  const closeButton = bar.querySelector("[data-interface-close]");
  if (closeButton) {
    closeButton.addEventListener("click", () => {
      state.interfaceOpenKey = null;
      syncWorkspaceVisibility(root);
      renderInterfaceShell(root);
    });
  }

  if (!state.interfaceOpenKey) {
    content.hidden = true;
    mailPanel.hidden = true;
    genericPanel.hidden = true;
    syncWorkspaceVisibility(root);
    return;
  }

  content.hidden = false;
  const activeGroup = groups.find((group) => group.key === state.interfaceOpenKey) || groups[0];
  state.activeInterfaceKey = activeGroup.key;

  const showMail = activeGroup.mode === "custom" && activeGroup.key === "mail";
  mailPanel.hidden = !showMail;
  genericPanel.hidden = showMail;
  syncWorkspaceVisibility(root);

  if (showMail) {
    refreshMailTab(root).catch(() => {});
    return;
  }

  renderGenericInterface(root, activeGroup);
}

function renderMailStatus(root, payload) {
  const standardStatus = root.querySelector("[data-mail-standard-status]");
  const standardMeta = root.querySelector("[data-mail-standard-meta]");
  const debugStatus = root.querySelector("[data-mail-debug-status]");
  const debugMeta = root.querySelector("[data-mail-debug-meta]");

  if (standardStatus && payload.standard) {
    standardStatus.textContent = payload.standard.status;
    standardMeta.textContent = `Ports 25 / 110 | ${payload.standard.status === "running" ? "Running in launcher" : "Not running"}`;
  }

  if (debugStatus && payload.debug) {
    debugStatus.textContent = payload.debug.status;
    debugMeta.textContent = `Ports 2525 / 1100 | ${payload.debug.status === "running" ? "Running in launcher" : "Not running"}`;
  }
}

function renderConfigStatus(root, validation) {
  const container = root.querySelector("[data-config-status]");
  if (!container || !validation) {
    return;
  }

  const rows = [
    { label: "Project Root", value: validation.game_root, ok: validation.game_root_exists },
    { label: "SeaMail Folder", value: validation.seamail_root, ok: validation.seamail_exists },
    { label: "Game EXE", value: validation.game_executable, ok: validation.game_executable_exists },
    { label: "hostDB", value: validation.hostdb_path, ok: validation.hostdb_exists },
    { label: "Resource", value: validation.resource_path, ok: validation.resource_exists },
    { label: "WeatherGet.dll", value: validation.weather_dll_path, ok: validation.weather_dll_exists },
  ];

  container.innerHTML = rows.map((row) => `
    <div>
      <strong>${escapeHtml(row.label)} ${row.ok ? "OK" : "Missing"}</strong>
      <p>${escapeHtml(row.value)}</p>
    </div>
  `).join("");
}

async function loadConfigSettings(root) {
  const response = await fetch("/api/config");
  const payload = await response.json();

  const gameRoot = root.querySelector("[data-config-game-root]");
  const seamailRoot = root.querySelector("[data-config-seamail-root]");
  const gameExecutable = root.querySelector("[data-config-game-executable]");
  const exeSelect = root.querySelector("[data-config-exe-select]");
  const note = root.querySelector("[data-config-note]");

  if (gameRoot) {
    gameRoot.value = payload.config?.game_root || "";
  }
  if (seamailRoot) {
    seamailRoot.value = payload.config?.seamail_root || "";
  }
  if (gameExecutable) {
    gameExecutable.value = payload.config?.game_executable || "";
  }
  if (exeSelect && payload.config?.game_executable) {
    const currentName = payload.config.game_executable.split(/[\\/]/).pop();
    for (const opt of exeSelect.options) {
      if (opt.value === currentName) {
        exeSelect.value = opt.value;
        break;
      }
    }
  }
  if (note) {
    note.textContent = payload.validation?.valid
      ? "Saved path looks usable."
      : "Saved path still needs attention.";
  }

  renderConfigStatus(root, payload.validation);
}

async function chooseConfigFolder(root, target) {
  const input = target === "game_root"
    ? root.querySelector("[data-config-game-root]")
    : root.querySelector("[data-config-seamail-root]");
  const gameExecutable = root.querySelector("[data-config-game-executable]");
  const response = await fetch("/api/config/choose-folder", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      target,
      initial_dir: input?.value || undefined,
    }),
  });
  const payload = await response.json();
  if (payload.path && input) {
    input.value = payload.path;
    if (target === "seamail_root" && gameExecutable) {
      gameExecutable.value = defaultGameExecutableFor(payload.path);
    }
  }
}

async function chooseConfigFile(root, target) {
  const input = root.querySelector("[data-config-game-executable]");
  const response = await fetch("/api/config/choose-file", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      target,
      initial_dir: input?.value || undefined,
    }),
  });
  const payload = await response.json();
  if (payload.path && input) {
    input.value = payload.path;
  }
}

async function testConfigSettings(root) {
  const gameRoot = root.querySelector("[data-config-game-root]");
  const seamailRoot = root.querySelector("[data-config-seamail-root]");
  const gameExecutable = root.querySelector("[data-config-game-executable]");
  const note = root.querySelector("[data-config-note]");

  const response = await fetch("/api/config/test", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      game_root: gameRoot?.value || "",
      seamail_root: seamailRoot?.value || "",
      game_executable: gameExecutable?.value || "",
    }),
  });
  const payload = await response.json();
  renderConfigStatus(root, payload.validation);

  if (note) {
    note.textContent = payload.validation?.valid
      ? "Path test passed."
      : "Path test failed. Check the missing entries below.";
  }
}

function bindConfigActions(root) {
  const form = root.querySelector("[data-config-form]");
  const note = root.querySelector("[data-config-note]");
  const gameRoot = root.querySelector("[data-config-game-root]");
  const seamailRoot = root.querySelector("[data-config-seamail-root]");
  const gameExecutable = root.querySelector("[data-config-game-executable]");
  const exeSelect = root.querySelector("[data-config-exe-select]");
  const exeSetButton = root.querySelector("[data-config-exe-set]");

  if (exeSetButton && exeSetButton.dataset.bound !== "true") {
    exeSetButton.dataset.bound = "true";
    exeSetButton.addEventListener("click", async () => {
      const seamailVal = (seamailRoot?.value || "").replace(/[/\\]$/, "");
      const selectedName = exeSelect?.value || "";
      if (!seamailVal || !selectedName) return;
      const fullPath = seamailVal + "\\" + selectedName;
      if (gameExecutable) gameExecutable.value = fullPath;
      const response = await fetch("/api/config", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          game_root: gameRoot?.value || "",
          seamail_root: seamailVal,
          game_executable: fullPath,
        }),
      });
      const payload = await response.json();
      renderConfigStatus(root, payload.validation);
      if (note) {
        note.textContent = payload.validation?.game_executable_exists
          ? `EXE set to ${selectedName}.`
          : `EXE set to ${selectedName} — file not found in SeaMail folder.`;
      }
    });
  }

  if (form && form.dataset.bound !== "true") {
    form.dataset.bound = "true";
    form.addEventListener("submit", async (event) => {
      event.preventDefault();
      const response = await fetch("/api/config", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          game_root: gameRoot?.value || "",
          seamail_root: seamailRoot?.value || "",
          game_executable: gameExecutable?.value || "",
        }),
      });
      const payload = await response.json();
      renderConfigStatus(root, payload.validation);
      if (note) {
        note.textContent = payload.validation?.valid
          ? "Paths saved."
          : "Paths saved, but the validation still found missing items.";
      }
    });
  }

  root.querySelectorAll("[data-config-choose]").forEach((button) => {
    if (button.dataset.bound === "true") {
      return;
    }
    button.dataset.bound = "true";
    button.addEventListener("click", async () => {
      await chooseConfigFolder(root, button.dataset.configChoose);
    });
  });

  root.querySelectorAll("[data-config-choose-file]").forEach((button) => {
    if (button.dataset.bound === "true") {
      return;
    }
    button.dataset.bound = "true";
    button.addEventListener("click", async () => {
      await chooseConfigFile(root, button.dataset.configChooseFile);
    });
  });

  const useLocalButton = root.querySelector("[data-config-use-local]");
  if (useLocalButton && useLocalButton.dataset.bound !== "true") {
    useLocalButton.dataset.bound = "true";
    useLocalButton.addEventListener("click", () => {
      if (seamailRoot) {
        seamailRoot.value = LOCAL_SEAMAIL_PATH;
      }
      if (gameExecutable) {
        gameExecutable.value = defaultGameExecutableFor(LOCAL_SEAMAIL_PATH);
      }
    });
  }

  const useDefaultGameButton = root.querySelector("[data-config-use-default-game]");
  if (useDefaultGameButton && useDefaultGameButton.dataset.bound !== "true") {
    useDefaultGameButton.dataset.bound = "true";
    useDefaultGameButton.addEventListener("click", () => {
      if (gameExecutable) {
        gameExecutable.value = defaultGameExecutableFor(seamailRoot?.value || LOCAL_SEAMAIL_PATH);
      }
    });
  }

  const testButton = root.querySelector("[data-config-test]");
  if (testButton && testButton.dataset.bound !== "true") {
    testButton.dataset.bound = "true";
    testButton.addEventListener("click", async () => {
      await testConfigSettings(root);
    });
  }
}

function renderMailInbox(root, payload) {
  const summary = root.querySelector("[data-mail-inbox-summary]");
  const list = root.querySelector("[data-mail-inbox-list]");
  const senderList = root.querySelector("[data-mail-sender-list]");
  if (!summary || !list || !senderList) {
    return;
  }

  summary.textContent = `${payload.summary.enabled} active, ${payload.summary.pulled} pulled, ${payload.summary.total} total`;
  senderList.innerHTML = payload.senders.map((sender) => `<option value="${escapeHtml(sender)}"></option>`).join("");

  if (!payload.messages.length) {
    list.innerHTML = `<article class="mail-item-empty">No inbox messages yet.</article>`;
    bindMailActions(root);
    return;
  }

  list.innerHTML = payload.messages.map((message) => {
    const primary = message.subject || message.sender || message.filename;
    const toggleLabel = message.enabled ? "Disable" : (message.pulled_once ? "Requeue" : "Enable");
    const toggleEnabled = message.enabled ? "false" : "true";
    const resetPulled = message.pulled_once ? "true" : "false";
    const deliveredText = message.body_translated || message.delivery_text || message.body_original;

    return `
      <article class="mail-item">
        <div class="mail-item-head">
          <div>
            <h3>${escapeHtml(primary)}</h3>
            <p>${escapeHtml(message.sender || "Unknown sender")} | ${escapeHtml(message.filename)}</p>
          </div>
          <div class="mail-item-badges">
            <span class="task-status ${message.enabled ? "running" : "idle"}">${message.enabled ? "Active" : "Inactive"}</span>
            <span class="task-status ${message.pulled_once ? "completed" : "idle"}">${message.pulled_once ? "Pulled" : "Waiting"}</span>
          </div>
        </div>
        <p>${escapeHtml(message.description || "No description")}</p>
        <div class="task-actions">
          <button class="action-button secondary" type="button" data-mail-enable="${escapeHtml(message.id)}" data-mail-enabled="${toggleEnabled}" data-mail-reset="${resetPulled}">${toggleLabel}</button>
        </div>
        <details class="mail-details">
          <summary>More info</summary>
          <div class="mail-detail-grid">
            <div>
              <strong>Original / English</strong>
              <pre>${escapeHtml(message.body_original || "")}</pre>
            </div>
            <div>
              <strong>Delivered / Japanese</strong>
              <pre>${escapeHtml(deliveredText || "")}</pre>
            </div>
          </div>
        </details>
      </article>
    `;
  }).join("");

  bindMailActions(root);
}

function renderMailOutbox(root, payload) {
  const list = root.querySelector("[data-mail-outbox-list]");
  if (!list) {
    return;
  }

  if (!payload.messages.length) {
    list.innerHTML = `<article class="mail-item-empty">No outgoing Seamail has been captured yet.</article>`;
    return;
  }

  list.innerHTML = payload.messages.map((message) => {
    const headerRows = Object.entries(message.headers || {})
      .map(([key, value]) => `<div><strong>${escapeHtml(key)}</strong><span>${escapeHtml(value)}</span></div>`)
      .join("");

    return `
      <details class="mail-item">
        <summary>
          <span>${escapeHtml(message.subject || message.filename)}</span>
          <span>${escapeHtml(message.modified_at)}</span>
        </summary>
        <div class="mail-item-head">
          <div>
            <h3>${escapeHtml(message.subject || message.filename)}</h3>
            <p>${escapeHtml(message.sender || "Unknown sender")} | ${escapeHtml(message.relative_path)}</p>
          </div>
        </div>
        <div class="mail-detail-grid">
          <div>
            <strong>Headers</strong>
            <div class="mail-headers">${headerRows || "<div><span>No parsed headers</span></div>"}</div>
          </div>
          <div>
            <strong>Body</strong>
            <pre>${escapeHtml(message.body || "")}</pre>
          </div>
        </div>
      </details>
    `;
  }).join("");
}

async function refreshMailTab(root) {
  const [statusResponse, inboxResponse, outboxResponse] = await Promise.all([
    fetch("/api/mail/status"),
    fetch("/api/mail/inbox"),
    fetch("/api/mail/outbox"),
  ]);

  const [statusPayload, inboxPayload, outboxPayload] = await Promise.all([
    statusResponse.json(),
    inboxResponse.json(),
    outboxResponse.json(),
  ]);

  renderMailStatus(root, statusPayload);
  renderMailInbox(root, inboxPayload);
  renderMailOutbox(root, outboxPayload);
}

function renderTodoTab(root, payload) {
  const summaryTitle = root.querySelector("[data-todo-summary-title]");
  const summaryBar = root.querySelector("[data-todo-summary-bar]");
  const list = root.querySelector("[data-todo-flat-list]");
  if (!summaryTitle || !summaryBar || !list) return;

  const summary = payload.summary || { total_items: 0, progress_percent: 0 };
  summaryTitle.textContent = `Overall progress — ${summary.progress_percent || 0}%`;
  summaryBar.style.width = `${summary.progress_percent || 0}%`;

  const allItems = [];
  for (const category of payload.categories || []) {
    for (const item of category.items || []) {
      allItems.push({ ...item, category_id: category.id, category_title: category.title });
    }
  }

  list.innerHTML = allItems.map((item) => {
    const pct = item.progress ?? 0;
    return `
      <div class="todo-flat-item">
        <div class="todo-flat-head">
          <span class="todo-cat-tag">${escapeHtml(item.category_title)}</span>
          <span class="todo-item-title">${escapeHtml(item.title)}</span>
          <span class="todo-pct-label">${pct}%</span>
        </div>
        <div class="todo-bar-track"
             data-todo-bar
             data-category-id="${escapeHtml(item.category_id)}"
             data-item-id="${escapeHtml(item.id)}">
          <div class="todo-bar-fill" style="width: ${pct}%;"></div>
        </div>
      </div>
    `;
  }).join("");

  bindTodoActions(root);
}

async function refreshTodoTab(root) {
  const response = await fetch("/api/todo");
  const payload = await response.json();
  renderTodoTab(root, payload);
}

async function updateTodoItem(root, categoryId, itemId, progress) {
  const response = await fetch(`/api/todo/${categoryId}/${itemId}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ progress }),
  });
  const payload = await response.json();
  if (!response.ok) {
    setLauncherNote(root, payload.error || "Could not update the to-do item.", "error");
    return;
  }
  renderTodoTab(root, payload);
}

function bindTodoActions(root) {
  root.querySelectorAll("[data-todo-bar]").forEach((track) => {
    if (track.dataset.bound === "true") return;
    track.dataset.bound = "true";
    track.addEventListener("click", async (e) => {
      const rect = track.getBoundingClientRect();
      const raw = ((e.clientX - rect.left) / rect.width) * 100;
      const pct = Math.round(Math.max(0, Math.min(100, raw)) / 5) * 5;
      const fill = track.querySelector(".todo-bar-fill");
      if (fill) fill.style.width = `${pct}%`;
      const head = track.previousElementSibling;
      if (head) {
        const label = head.querySelector(".todo-pct-label");
        if (label) label.textContent = `${pct}%`;
      }
      await updateTodoItem(root, track.dataset.categoryId, track.dataset.itemId, pct);
    });
  });
}

function bindMailActions(root) {
  root.querySelectorAll("[data-mail-enable]").forEach((button) => {
    if (button.dataset.bound === "true") {
      return;
    }
    button.dataset.bound = "true";
    button.addEventListener("click", async () => {
      await fetch(`/api/mail/inbox/${button.dataset.mailEnable}/enable`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          enabled: button.dataset.mailEnabled === "true",
          reset_pulled: button.dataset.mailReset === "true",
        }),
      });
      await refreshMailTab(root);
    });
  });
}

function bindMailCompose(root) {
  const form = root.querySelector("[data-mail-compose-form]");
  const note = root.querySelector("[data-mail-compose-note]");
  if (!form || !note) {
    return;
  }

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    const formData = new FormData(form);
    const payload = {
      sender: formData.get("sender"),
      subject: formData.get("subject"),
      body_original: formData.get("body_original"),
      body_translated: formData.get("body_translated"),
      description: formData.get("description"),
      deliver_translated: formData.get("deliver_translated") === "on",
      preset: formData.get("preset") === "on",
      enabled: true,
    };

    const response = await fetch("/api/mail/inbox", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    const result = await response.json();

    if (!response.ok) {
      note.textContent = result.error || "Failed to add message.";
      return;
    }

    form.reset();
    note.textContent = "Message added to the inbox queue.";
    await refreshMailTab(root);
  });
}

function updateConsole(root, task, lines) {
  const titles = Array.from(root.querySelectorAll("[data-console-title]"));
  const statuses = Array.from(root.querySelectorAll("[data-console-status]"));
  const paths = Array.from(root.querySelectorAll("[data-console-path]"));
  const outputs = Array.from(root.querySelectorAll("[data-console-output]"));

  titles.forEach((title) => {
    title.textContent = task ? task.label : "No task selected";
  });
  statuses.forEach((status) => {
    status.textContent = task ? task.status : "idle";
  });
  paths.forEach((path) => {
    path.textContent = task ? task.script_path : "Choose a task card to view its log";
  });

  if (!task) {
    state.consoleLines = [];
    outputs.forEach((output) => {
      output.textContent = "Waiting for task selection...";
    });
    return;
  }

  if (lines.length) {
    const formatted = lines.map((line) => `[${line.stream}] ${line.text}`).reverse();
    state.consoleLines = [...formatted, ...state.consoleLines];
    if (state.consoleLines.length > MAX_CONSOLE_LINES) {
      state.consoleLines = state.consoleLines.slice(0, MAX_CONSOLE_LINES);
    }
  }

  if (!state.consoleLines.length) {
    const emptyMessage = task?.launch_mode === "console"
      ? "This task runs in a visible CMD window. Use that window for interaction."
      : "No log lines yet.";
    outputs.forEach((output) => {
      output.textContent = emptyMessage;
    });
    return;
  }

  outputs.forEach((output) => {
    output.textContent = state.consoleLines.join("\n");
    output.scrollTop = 0;
  });
}

function selectTask(taskId, root) {
  state.activeTaskId = taskId;
  state.logCursor = 0;
  state.consoleLines = [];
  root.querySelectorAll("[data-task-card]").forEach((card) => {
    card.classList.toggle("active", card.dataset.taskId === taskId);
  });

  const task = state.tasks.get(taskId) || { label: taskId, status: "idle", script_path: "" };
  root.querySelectorAll("[data-console-output]").forEach((output) => {
    output.textContent = "";
  });
  updateConsole(root, task, []);
  fetchLogs(root);
}

async function refreshTasks(root) {
  const response = await fetch("/api/tasks");
  const payload = await response.json();
  payload.tasks.forEach((task) => renderTaskState(root, task));
  renderActiveTasks(root);
  renderInterfaceShell(root);

  if (!state.activeTaskId) {
    const firstTask = root.querySelector(`[data-task-card][data-task-group="${state.activeTab}"]`);
    if (firstTask) {
      selectTask(firstTask.dataset.taskId, root);
    }
  } else {
    const task = state.tasks.get(state.activeTaskId);
    updateConsole(root, task, []);
  }
}

async function fetchLogs(root) {
  if (!state.activeTaskId) {
    return;
  }
  if (["intro", "todo"].includes(state.activeTab)) {
    return;
  }

  const response = await fetch(`/api/tasks/${state.activeTaskId}/logs?after=${state.logCursor}&limit=200`);
  const payload = await response.json();
  state.logCursor = payload.cursor;
  updateConsole(root, state.tasks.get(state.activeTaskId), payload.lines);
}

async function postTaskAction(taskId, action) {
  const response = await fetch(`/api/tasks/${taskId}/${action}`, { method: "POST" });
  const payload = await response.json();
  return { ok: response.ok, status: response.status, payload };
}

async function postTaskEnvCreate(taskId) {
  const response = await fetch(`/api/tasks/${taskId}/venv/create`, { method: "POST" });
  const payload = await response.json();
  return { ok: response.ok, status: response.status, payload };
}

function refreshInterfaceFrame(root) {
  const frame = root.querySelector(".interface-frame");
  if (!frame) {
    return;
  }

  frame.src = frame.src;
}

async function handleManualRefresh(root, options = {}) {
  const { reloadFrame = false } = options;
  await refreshTasks(root);
  if (state.activeTaskId && !["intro", "todo"].includes(state.activeTab)) {
    await fetchLogs(root);
  }
  if (state.interfaceOpenKey === "mail") {
    await refreshMailTab(root);
  }
  if (state.activeTab === "todo") {
    await refreshTodoTab(root);
  }
  if (reloadFrame) {
    refreshInterfaceFrame(root);
  }
}

function bindRefreshActions(root) {
  root.querySelectorAll("[data-manual-refresh]").forEach((button) => {
    if (button.dataset.bound === "true") {
      return;
    }
    button.dataset.bound = "true";
    button.addEventListener("click", async () => {
      await handleManualRefresh(root);
    });
  });

  root.querySelectorAll("[data-console-refresh]").forEach((button) => {
    if (button.dataset.bound === "true") {
      return;
    }
    button.dataset.bound = "true";
    button.addEventListener("click", async () => {
      await fetchLogs(root);
    });
  });

  root.querySelectorAll("[data-mail-refresh]").forEach((button) => {
    if (button.dataset.bound === "true") {
      return;
    }
    button.dataset.bound = "true";
    button.addEventListener("click", async () => {
      await refreshMailTab(root);
      await refreshTasks(root);
    });
  });

  root.querySelectorAll("[data-todo-refresh]").forEach((button) => {
    if (button.dataset.bound === "true") {
      return;
    }
    button.dataset.bound = "true";
    button.addEventListener("click", async () => {
      await refreshTodoTab(root);
    });
  });

  root.querySelectorAll("[data-interface-refresh]").forEach((button) => {
    if (button.dataset.bound === "true") {
      return;
    }
    button.dataset.bound = "true";
    button.addEventListener("click", async () => {
      await handleManualRefresh(root, { reloadFrame: true });
    });
  });
}

function bindTaskActions(root) {
  root.querySelectorAll("[data-log-button]").forEach((button) => {
    if (button.dataset.bound === "true") {
      return;
    }
    button.dataset.bound = "true";
    button.addEventListener("click", () => selectTask(button.dataset.logButton, root));
  });

  root.querySelectorAll("[data-open-button]").forEach((button) => {
    if (button.dataset.bound === "true") {
      return;
    }
    button.dataset.bound = "true";
    button.addEventListener("click", () => {
      const taskId = button.dataset.openButton;
      const task = state.tasks.get(taskId);
      if (task && task.open_url) {
        window.open(task.open_url, "_blank", "noopener,noreferrer");
      }
    });
  });

  root.querySelectorAll("[data-venv-button]").forEach((button) => {
    if (button.dataset.bound === "true") {
      return;
    }
    button.dataset.bound = "true";
    button.addEventListener("click", async () => {
      const taskId = button.dataset.venvButton;
      const task = state.tasks.get(taskId);
      selectTask(taskId, root);
      setLauncherNote(root, `Setting up environment for ${task?.label || taskId}...`);
      const { ok, payload } = await postTaskEnvCreate(taskId);
      if (!ok) {
        setLauncherNote(root, payload.error || `Could not set up an environment for ${task?.label || taskId}.`, "error");
      } else {
        setLauncherNote(root, `${task?.label || taskId} environment setup finished.`, "success");
      }
      await refreshTasks(root);
      await fetchLogs(root);
    });
  });

  root.querySelectorAll("[data-start-button]").forEach((button) => {
    if (button.dataset.bound === "true") {
      return;
    }
    button.dataset.bound = "true";
    button.addEventListener("click", async () => {
      const taskId = button.dataset.startButton;
      const task = state.tasks.get(taskId);
      const interfaceKey = task?.interface_key || task?.id;
      if (interfaceKey) {
        state.clearedInterfaceKeys.delete(interfaceKey);
      }
      selectTask(taskId, root);
      const { ok, payload } = await postTaskAction(taskId, "start");
      if (payload.task) {
        renderTaskState(root, payload.task);
        state.tasks.set(payload.task.id, payload.task);
      }
      if (!ok) {
        setLauncherNote(root, payload.error || `Could not start ${task?.label || taskId}.`, "error");
      } else if (payload.task) {
        setLauncherNote(root, `${payload.task.label} started.`, "success");
      }
      await refreshTasks(root);
      await fetchLogs(root);
    });
  });

  root.querySelectorAll("[data-stop-button]").forEach((button) => {
    if (button.dataset.bound === "true") {
      return;
    }
    button.dataset.bound = "true";
    button.addEventListener("click", async () => {
      const taskId = button.dataset.stopButton;
      selectTask(taskId, root);
      const { ok, payload } = await postTaskAction(taskId, "stop");
      if (payload.task) {
        renderTaskState(root, payload.task);
        state.tasks.set(payload.task.id, payload.task);
      }
      if (!ok) {
        setLauncherNote(root, payload.error || `Could not stop ${taskId}.`, "error");
      } else if (payload.task) {
        setLauncherNote(root, `${payload.task.label} stop requested.`, "success");
      }
      await refreshTasks(root);
      await fetchLogs(root);
    });
  });

  const SUGGESTED_TASK_IDS = ["menu_overlay_replacement", "menu_translation_v24", "comparison_monitor", "fix_loop_v33"];
  const SUGGESTED_LAUNCH_TOOL_IDS = ["menu_overlay_replacement", "menu_translation_v24", "comparison_monitor", "fix_loop_v33"];

  const launchAllBtn = root.querySelector("[data-suggested-launch-all]");
  if (launchAllBtn && launchAllBtn.dataset.bound !== "true") {
    launchAllBtn.dataset.bound = "true";
    launchAllBtn.addEventListener("click", async () => {
      await postTaskAction("launch_game", "start");
      await refreshTasks(root);
      setLauncherNote(root, "Game started — launching tools in 2 seconds…", "success");
      await new Promise((resolve) => setTimeout(resolve, 2000));
      await Promise.all(SUGGESTED_LAUNCH_TOOL_IDS.map((id) => postTaskAction(id, "start")));
      await refreshTasks(root);
      setLauncherNote(root, "Full session launched.", "success");
    });
  }

  const launchStopAllBtn = root.querySelector("[data-suggested-launch-stop-all]");
  if (launchStopAllBtn && launchStopAllBtn.dataset.bound !== "true") {
    launchStopAllBtn.dataset.bound = "true";
    launchStopAllBtn.addEventListener("click", async () => {
      await Promise.all(["launch_game", ...SUGGESTED_LAUNCH_TOOL_IDS].map((id) => postTaskAction(id, "stop")));
      await refreshTasks(root);
      setLauncherNote(root, "Full session stopped.", "success");
    });
  }

  const startAllBtn = root.querySelector("[data-suggested-start-all]");
  if (startAllBtn && startAllBtn.dataset.bound !== "true") {
    startAllBtn.dataset.bound = "true";
    startAllBtn.addEventListener("click", async () => {
      await Promise.all(SUGGESTED_TASK_IDS.map((id) => postTaskAction(id, "start")));
      await refreshTasks(root);
      setLauncherNote(root, "Suggested tools started.", "success");
    });
  }

  const stopAllBtn = root.querySelector("[data-suggested-stop-all]");
  if (stopAllBtn && stopAllBtn.dataset.bound !== "true") {
    stopAllBtn.dataset.bound = "true";
    stopAllBtn.addEventListener("click", async () => {
      await Promise.all(SUGGESTED_TASK_IDS.map((id) => postTaskAction(id, "stop")));
      await refreshTasks(root);
      setLauncherNote(root, "Suggested tools stopped.", "success");
    });
  }
}

document.addEventListener("DOMContentLoaded", async () => {
  const root = document.querySelector("[data-prototype-root]");
  if (!root) {
    return;
  }

  initializeTabs(root);
  await initializeStageSelector(root);
  initializeLayoutToggle(root);
  syncWorkspaceVisibility(root);
  bindRefreshActions(root);
  bindTaskActions(root);
  bindMailCompose(root);
  bindConfigActions(root);
  await refreshTasks(root);
  await loadConfigSettings(root);
  await refreshTodoTab(root);
  await refreshEnvPanel(root);
  await refreshSnapshot(root);
});

async function refreshEnvPanel(root) {
  root = root || document.querySelector("[data-prototype-root]");
  const headline = root.querySelector("[data-env-headline]");
  const rows = root.querySelector("[data-env-rows]");
  const hint = root.querySelector("[data-env-hint]");
  if (!rows) return;

  try {
    const res = await fetch("/api/envs");
    const envs = await res.json();

    const labels = { "launcher-app": "App env (Flask / DB tools)", "launcher-frida": "Frida env (hooks / trackers)" };

    let allReady = true;
    rows.innerHTML = Object.entries(envs).map(([key, status]) => {
      if (!status.ready) allReady = false;
      const dot = status.ready
        ? `<span style="color:#4ade80">●</span>`
        : `<span style="color:#fb923c">●</span>`;
      const label = labels[key] || key;
      const state = status.ready ? "Ready" : "Missing";
      return `<div style="display:flex;align-items:center;gap:0.5rem;">${dot} <span>${label}</span> <span style="color:${status.ready ? '#4ade80' : '#fb923c'};font-size:0.8rem;">${state}</span></div>`;
    }).join("");

    if (headline) headline.textContent = allReady ? "Both environments ready." : "Some environments need setup.";
    if (hint) hint.textContent = allReady ? "" : "Run the .bat files in launcher/ to set up missing environments.";
  } catch (e) {
    if (headline) headline.textContent = "Could not check environments.";
  }
}

async function refreshSnapshot(root) {
  root = root || document.querySelector("[data-prototype-root]");
  const grid = root ? root.querySelector("[data-snapshot-grid]") : null;
  const errEl = root ? root.querySelector("[data-snapshot-error]") : null;
  if (!grid) return;

  try {
    const res = await fetch("/api/snapshot");
    const payload = await res.json();

    if (payload.error) {
      grid.innerHTML = "";
      if (errEl) errEl.textContent = payload.error;
      return;
    }

    if (errEl) errEl.textContent = "";
    grid.innerHTML = payload.snapshot.map(item => `
      <div style="background:#0d1829;border:1px solid #1e293b;border-radius:8px;padding:0.6rem 0.8rem;">
        <div style="font-size:0.7rem;color:#64748b;text-transform:uppercase;letter-spacing:0.05em;margin-bottom:0.2rem;">${escapeHtml(item.label)}</div>
        <div style="font-size:0.95rem;color:#f8fafc;">${escapeHtml(item.value)}</div>
      </div>
    `).join("");
  } catch (e) {
    if (errEl) errEl.textContent = "Could not read creature state.";
  }
}
