const replayState = {
    manifest: null,
    sessions: [],
    defaultSession: "",
    index: -1,
    playing: false,
    timer: null,
    audio: null,
    filter: "all",
    boardReady: false,
    selectedAIView: "chat",
};

let catanBoard = null;
window.catanBoard = null;
window.gameState = null;

const $ = (id) => document.getElementById(id);

document.addEventListener("DOMContentLoaded", () => {
    bindReplayControls();
    initialiseBoard();
    initialiseSessions().catch(showFatalError);
});

function bindReplayControls() {
    $("replay-play").addEventListener("click", togglePlayback);
    $("replay-start").addEventListener("click", () => {
        pausePlayback();
        goToEvent(-1, false);
    });
    $("replay-prev").addEventListener("click", () => {
        pausePlayback();
        goToEvent(Math.max(0, replayState.index - 1), false);
    });
    $("replay-next").addEventListener("click", () => {
        pausePlayback();
        goToEvent(Math.min(events().length - 1, replayState.index + 1), true);
    });
    $("replay-end").addEventListener("click", () => {
        pausePlayback();
        goToEvent(events().length - 1, false);
    });
    $("replay-slider").addEventListener("input", (event) => {
        pausePlayback();
        goToEvent(Number(event.target.value), false);
    });
    $("replay-analyse").addEventListener("click", () => openReplayAnalysis());
    $("session-load").addEventListener("click", () => loadManifest($("session-select").value));
    $("session-select").addEventListener("change", () => loadManifest($("session-select").value));
    window.addEventListener("pagehide", stopAudio);
    window.addEventListener("beforeunload", stopAudio);
}

function initialiseBoard() {
    catanBoard = new CatanBoard();
    window.catanBoard = catanBoard;
    waitForBoardReady();
}

function waitForBoardReady() {
    if (catanBoard && (catanBoard.boardMapping || catanBoard.vertices.length)) {
        replayState.boardReady = true;
        renderCurrent();
        return;
    }
    window.setTimeout(waitForBoardReady, 40);
}

async function initialiseSessions() {
    const response = await fetch("/api/sessions");
    const payload = await response.json();
    replayState.sessions = payload.sessions || [];
    replayState.defaultSession = payload.default_session || "";

    const selected = new URLSearchParams(location.search).get("session")
        || replayState.defaultSession
        || replayState.sessions[0]?.name
        || "";

    $("session-select").innerHTML = replayState.sessions.length
        ? replayState.sessions.map((session) => {
            const label = `${session.name} (${session.responses || 0} responses${session.audio != null ? `, ${session.audio} audio` : ""})`;
            return `<option value="${escapeAttr(session.name)}" ${session.name === selected ? "selected" : ""}>${escapeHtml(label)}</option>`;
        }).join("")
        : "<option value=\"\">No sessions found</option>";

    if (selected) {
        await loadManifest(selected);
    } else {
        renderCurrent();
    }
}

async function loadManifest(sessionName) {
    if (!sessionName) return;
    pausePlayback();
    $("replay-context").textContent = `Loading ${sessionName}...`;
    const response = await fetch(`/api/manifest?session=${encodeURIComponent(sessionName)}`);
    if (!response.ok) throw new Error(await response.text());
    replayState.manifest = await response.json();
    replayState.index = -1;
    replayState.filter = "all";
    if (catanBoard && replayState.manifest.board) {
        catanBoard.boardMapping = replayState.manifest.board;
        catanBoard.generateVerticesFromServer();
        replayState.boardReady = true;
    }
    $("replay-slider").max = Math.max(0, events().length - 1);
    $("replay-slider").value = 0;
    if ($("session-select").value !== sessionName) $("session-select").value = sessionName;
    history.replaceState(null, "", `?session=${encodeURIComponent(sessionName)}`);
    renderFilters();
    renderAIChrome();
    renderCurrent();
}

function events() {
    return replayState.manifest?.events || [];
}

function currentEvent() {
    return replayState.index >= 0 ? events()[replayState.index] : null;
}

function renderCurrent() {
    renderTimeline();
    renderTransport();

    const boardState = deriveBoardState(replayState.index);
    const gameState = buildGameState(boardState);
    window.gameState = gameState;

    if (replayState.boardReady && catanBoard && replayState.manifest) {
        catanBoard.updateFromGameState(gameState);
    }

    renderPlayerHub(gameState);
    renderLogs();
    renderDetails(gameState);
    renderAIContent();
}

function renderTransport() {
    const total = events().length;
    const current = replayState.index < 0 ? 0 : replayState.index + 1;
    const event = currentEvent();
    $("replay-label").textContent = `${current} / ${total}`;
    $("replay-slider").value = Math.max(0, replayState.index);
    $("replay-context").textContent = event
        ? `${event.player_name}${event.request_number ? ` #${event.request_number}` : ""} ${event.kind}`
        : (replayState.manifest ? "Press Play to start" : "Choose a session");
    $("replay-play").textContent = replayState.playing ? "Pause" : "Play";
}

function renderFilters() {
    const players = playerNames();
    $("replay-player-filters").innerHTML = ["all", ...players].map((name) => {
        const label = name === "all" ? "All" : name;
        return `<button class="replay-filter ${replayState.filter === name ? "active" : ""}" type="button" data-player="${escapeAttr(name)}">${escapeHtml(label)}</button>`;
    }).join("");
    $("replay-player-filters").querySelectorAll("button").forEach((button) => {
        button.addEventListener("click", () => {
            replayState.filter = button.dataset.player;
            renderFilters();
            renderTimeline();
        });
    });
}

function renderTimeline() {
    const active = currentEvent();
    $("replay-timeline-track").innerHTML = events().map((event) => {
        const hidden = replayState.filter !== "all" && event.player_name !== replayState.filter;
        const label = pointLabel(event);
        const classes = [
            "replay-point",
            event.has_action ? "has-action" : "",
            event.has_speech ? "has-speech" : "",
            event.kind === "chat" ? "chat-only" : "",
            event.kind === "memory" ? "memory-only" : "",
            event.index === replayState.index ? "active" : "",
            active && event.player_name === active.player_name ? "current-speaker" : "",
        ].filter(Boolean).join(" ");
        const title = `${event.player_name}${event.request_number ? ` #${event.request_number}` : ""} - ${event.kind}${event.action_type ? ` - ${event.action_type}` : ""}`;
        return `<button class="${classes}" type="button" data-index="${event.index}" title="${escapeAttr(title)}" style="${hidden ? "display:none" : ""}">${escapeHtml(label)}</button>`;
    }).join("");
    $("replay-timeline-track").querySelectorAll("button").forEach((button) => {
        button.addEventListener("click", () => {
            pausePlayback();
            goToEvent(Number(button.dataset.index), true);
        });
    });
}

function pointLabel(event) {
    if (event.kind === "chat") return "C";
    if (event.kind === "memory") return "M";
    if (event.has_action && event.has_speech) return "A";
    if (event.has_action) return "A";
    if (event.has_speech) return "S";
    return "R";
}

function playerNames() {
    const fromManifest = (replayState.manifest?.players || []).map((player) => player.name).filter(Boolean);
    const fromEvents = [...new Set(events().map((event) => event.player_name).filter(Boolean))];
    return [...new Set([...fromManifest, ...fromEvents])];
}

function playerIndex(playerName) {
    const index = playerNames().indexOf(playerName);
    return index >= 0 ? index + 1 : 1;
}

function playerInitial(playerName) {
    return String(playerName || "?").trim().slice(0, 1) || "?";
}

function deriveBoardState(untilIndex) {
    const board = replayState.manifest?.board || {};
    const derived = {
        robber: board.initial_robber || null,
        settlements: new Map(),
        cities: new Map(),
        roads: new Map(),
        lastDice: null,
        lastAction: null,
    };
    if (!replayState.manifest || untilIndex < 0) return derived;

    events().slice(0, untilIndex + 1).forEach((event) => {
        const action = String(event.action_type || "").toLowerCase();
        const params = event.parameters || {};
        const player = event.player_name;
        if (!action) return;
        derived.lastAction = event;

        if (["place_starting_settlement", "build_settlement", "place_settlement"].includes(action)) {
            const node = Number(params.node ?? params.point ?? params.vertex ?? params.point_id);
            if (node) {
                derived.cities.delete(node);
                derived.settlements.set(node, player);
            }
        } else if (["build_city", "upgrade_city"].includes(action)) {
            const node = Number(params.node ?? params.point ?? params.vertex ?? params.point_id);
            if (node) {
                derived.settlements.delete(node);
                derived.cities.set(node, player);
            }
        } else if (["place_starting_road", "build_road", "place_road"].includes(action)) {
            addRoadToState(derived, params.from ?? params.start, params.to ?? params.end, player);
        } else if (action === "use_dev_card") {
            collectRoadsFromParams(params).forEach(([from, to]) => addRoadToState(derived, from, to, player));
        } else if (["robber_move", "move_robber"].includes(action)) {
            derived.robber = Number(params.hex ?? params.tile ?? params.robber_position) || derived.robber;
        } else if (action === "roll_dice") {
            derived.lastDice = params.dice || params.roll || params.result || null;
        }
    });
    return derived;
}

function collectRoadsFromParams(params) {
    const roads = [];
    ["road_1", "road_2"].forEach((key) => {
        const road = params[key];
        if (Array.isArray(road) && road.length >= 2) roads.push([road[0], road[1]]);
    });
    ["road_edges", "roads"].forEach((key) => {
        const value = params[key];
        if (!Array.isArray(value)) return;
        value.forEach((road) => {
            if (Array.isArray(road) && road.length >= 2) roads.push([road[0], road[1]]);
            else if (road && typeof road === "object") roads.push([road.from ?? road.start, road.to ?? road.end]);
        });
    });
    return roads;
}

function addRoadToState(boardState, from, to, player) {
    const a = Number(from);
    const b = Number(to);
    if (!a || !b) return;
    const key = [a, b].sort((left, right) => left - right).join("-");
    boardState.roads.set(key, { from: a, to: b, player });
}

function buildGameState(boardState) {
    const board = replayState.manifest?.board || {};
    const players = playerNames().map((name) => {
        const settlements = [...boardState.settlements.values()].filter((value) => value === name).length;
        const cities = [...boardState.cities.values()].filter((value) => value === name).length;
        const roads = [...boardState.roads.values()].filter((road) => road.player === name).length;
        return {
            id: playerIndex(name) - 1,
            name,
            victory_points: settlements + cities * 2,
            total_cards: 0,
            resources: { wood: 0, brick: 0, sheep: 0, wheat: 0, ore: 0 },
            dev_cards: [],
            roads_count: roads,
            settlements_count: settlements,
            cities_count: cities,
            is_current: currentEvent()?.player_name === name,
        };
    });

    return {
        hexes: (board.hexes || []).map((hex) => ({
            ...hex,
            has_robber: Number(boardState.robber) === Number(hex.id),
            robber: Number(boardState.robber) === Number(hex.id),
        })),
        settlements: [...boardState.settlements.entries()].map(([vertex, player], index) => ({
            id: `s-${index}`,
            vertex,
            player: playerIndex(player),
        })),
        cities: [...boardState.cities.entries()].map(([vertex, player], index) => ({
            id: `c-${index}`,
            vertex,
            player: playerIndex(player),
        })),
        roads: [...boardState.roads.values()].map((road, index) => ({
            id: `r-${index}`,
            from: road.from,
            to: road.to,
            player: playerIndex(road.player),
        })),
        harbors: [],
        players,
        robber_position: boardState.robber,
        current_player: Math.max(0, playerIndex(currentEvent()?.player_name) - 1),
        current_phase: currentEvent()?.action_type || currentEvent()?.kind || "REPLAY",
        dice_result: boardState.lastDice,
        replay_index: replayState.index,
    };
}

function renderPlayerHub(gameState) {
    const current = currentEvent();
    if (!gameState.players.length) {
        $("player-hub").innerHTML = "<div class=\"loading-state\">Choose a session...</div>";
        return;
    }
    const resources = [
        ["wood", "🌲"],
        ["brick", "🧱"],
        ["sheep", "🐑"],
        ["wheat", "🌾"],
        ["ore", "⛰️"],
    ];
    $("player-hub").innerHTML = gameState.players.map((player) => {
        const cssIndex = player.id + 1;
        const isSpeaking = current?.player_name === player.name && current?.say_outloud;
        const latestSpeech = latestSpeechForPlayer(player.name);
        return `
            <div class="player-card player-${cssIndex} ${player.is_current ? "active" : ""} ${isSpeaking ? "replay-speaking" : ""}">
                <div class="player-header">
                    <div class="player-avatar player-${cssIndex}">${escapeHtml(playerInitial(player.name))}</div>
                    <div class="player-info-header">
                        <div class="player-name">${escapeHtml(player.name)}</div>
                        <div class="player-stats">
                            <span>🏆 ${player.victory_points} VP</span>
                            <span>${player.roads_count} roads</span>
                        </div>
                    </div>
                </div>
                <div class="player-resources-grid">
                    ${resources.map(([key, icon]) => `
                        <div class="resource-item">
                            <span class="resource-icon">${icon}</span>
                            <span class="resource-count">${player.resources[key] || 0}</span>
                        </div>
                    `).join("")}
                </div>
                <div class="player-dev-cards detailed empty">
                    <span class="dev-card-empty">${player.settlements_count} settlements, ${player.cities_count} cities</span>
                </div>
                ${latestSpeech ? `<div class="player-chat-bubble"><strong>${escapeHtml(latestSpeech.kindLabel)}</strong><br>${escapeHtml(latestSpeech.text)}</div>` : ""}
            </div>`;
    }).join("");
}

function latestSpeechForPlayer(playerName) {
    if (replayState.index < 0) return null;
    const event = [...events().slice(0, replayState.index + 1)]
        .reverse()
        .find((candidate) => candidate.player_name === playerName && candidate.say_outloud);
    if (!event) return null;
    return {
        text: event.say_outloud,
        kindLabel: event.index === replayState.index ? "Now speaking" : "Last said",
    };
}

function renderLogs() {
    const visible = replayState.index < 0 ? [] : events().filter((event) => event.index <= replayState.index);
    const actions = visible.filter((event) => event.has_action).slice(-40).reverse();
    const chat = visible.filter((event) => event.has_speech).slice(-40).reverse();

    $("action-log").innerHTML = actions.length ? actions.map((event) => `
        <div class="event-log-entry ${actionLogClass(event)} ${event.index === replayState.index ? "is-current" : ""}" data-index="${event.index}" role="button" tabindex="0">
            <div class="event-log-main">
                <span class="event-log-prefix">${event.index === replayState.index ? "✓ ▶" : "✓"}</span>
                <span class="event-log-message">${escapeHtml(event.player_name)}: ${escapeHtml(event.action_type || "")}</span>
                <span class="event-log-time">${formatTime(event.timestamp)}</span>
            </div>
            <div class="event-log-details">
                ${event.request_number ? `<span>#${escapeHtml(String(event.request_number))}</span>` : ""}
                ${event.has_audio ? "<span>audio</span>" : ""}
            </div>
        </div>
    `).join("") : "<div class=\"info\">Waiting for updates...</div>";

    $("chat-log").innerHTML = chat.length ? chat.map((event) => `
        <div class="chat-log-message ${event.index === replayState.index ? "is-current" : ""}" data-index="${event.index}" role="button" tabindex="0">
            <div class="chat-log-header">
                <span class="chat-log-player">${escapeHtml(event.player_name)}</span>
                <span class="chat-log-time">${formatTime(event.timestamp)}</span>
            </div>
            <div class="chat-log-text">${escapeHtml(event.say_outloud || "")}</div>
        </div>
    `).join("") : "<div class=\"info\">No chat messages yet...</div>";

    document.querySelectorAll("#action-log [data-index], #chat-log [data-index]").forEach((node) => {
        node.addEventListener("click", () => {
            pausePlayback();
            goToEvent(Number(node.dataset.index), true);
        });
    });
}

function actionLogClass(event) {
    const action = String(event.action_type || "").toLowerCase();
    if (action.includes("build") || action.includes("place")) return "log-build";
    if (action.includes("trade") || action.includes("roll")) return "log-resource";
    return "success";
}

function renderDetails(gameState) {
    const event = currentEvent();
    const stats = replayState.manifest?.stats || {};
    $("game-details").innerHTML = `
        <div class="detail-row"><strong>Session</strong><span>${escapeHtml(replayState.manifest?.session?.name || "-")}</span></div>
        <div class="detail-row"><strong>Events</strong><span>${stats.events || 0}</span></div>
        <div class="detail-row"><strong>Actions</strong><span>${stats.actions || 0}</span></div>
        <div class="detail-row"><strong>Speech</strong><span>${stats.speech || 0}</span></div>
        <div class="detail-row"><strong>Audio</strong><span>${stats.audio || 0}</span></div>
        <div class="detail-row"><strong>Current</strong><span>${event ? `${escapeHtml(event.player_name)} #${escapeHtml(String(event.request_number || ""))}` : "-"}</span></div>
        <div class="detail-row"><strong>Phase</strong><span>${escapeHtml(gameState.current_phase || "-")}</span></div>
    `;
}

function renderAIChrome() {
    const players = playerNames();
    $("ai-players-nav").innerHTML = players.map((name) => `
        <div class="nav-item" data-player="${escapeAttr(name)}" onclick="filterAIPlayer('${escapeJs(name)}')">
            <span class="nav-icon">${escapeHtml(playerInitial(name))}</span>
            <span>${escapeHtml(name)}</span>
        </div>
    `).join("");
    $("chat-count").textContent = String(events().filter((event) => event.has_speech).length);
    $("requests-count").textContent = String(events().filter((event) => event.response_id).length);
    $("session-info").innerHTML = replayState.manifest
        ? `${escapeHtml(replayState.manifest.session.name)}<br>${escapeHtml(replayState.manifest.session.path || "")}`
        : "No active session";
}

function renderAIContent() {
    if (!replayState.manifest) {
        $("ai-content-body").innerHTML = "<div class=\"empty-state\"><div class=\"empty-icon\">🤖</div><h3>No session loaded</h3></div>";
        return;
    }
    const event = currentEvent();
    const list = replayState.selectedAIView === "chat"
        ? events().filter((candidate) => candidate.has_speech)
        : events().filter((candidate) => candidate.response_id);
    $("ai-content-title").textContent = replayState.selectedAIView === "chat" ? "Chat History" : "All Requests";
    $("ai-content-body").innerHTML = list.slice(-80).reverse().map((candidate) => `
        <div class="ai-response-card ${event?.index === candidate.index ? "active" : ""}">
            <h3>${escapeHtml(candidate.player_name)} ${candidate.request_number ? `#${escapeHtml(String(candidate.request_number))}` : ""}</h3>
            <div class="ai-response-meta">${escapeHtml(candidate.timestamp || "")} · ${escapeHtml(candidate.kind || "")} ${candidate.action_type ? `· ${escapeHtml(candidate.action_type)}` : ""}</div>
            <div class="ai-response-text">${escapeHtml(candidate.say_outloud || candidate.note_to_self || candidate.internal_thinking || "(no visible speech)")}</div>
        </div>
    `).join("");
}

function filterAIPlayer(playerName) {
    replayState.filter = playerName;
    switchView("game");
    renderFilters();
    renderTimeline();
}

function showAIView(viewName) {
    replayState.selectedAIView = viewName;
    document.querySelectorAll("[data-ai-view]").forEach((node) => node.classList.toggle("active", node.dataset.aiView === viewName));
    renderAIContent();
}

function switchView(viewName) {
    document.querySelectorAll(".nav-tab").forEach((button) => {
        button.classList.toggle("active", button.dataset.view === viewName);
    });
    $("game-view").classList.toggle("active", viewName === "game");
    $("ai-view").classList.toggle("active", viewName === "ai");
}

function switchLogTab(tabName, event) {
    const panelIds = {
        actions: "actions-log-panel",
        details: "details-log-panel",
        chat: "chat-log-panel",
    };
    document.querySelectorAll(".panel-tab").forEach((button) => button.classList.remove("active"));
    if (event?.currentTarget) event.currentTarget.classList.add("active");
    Object.entries(panelIds).forEach(([name, id]) => {
        $(id).classList.toggle("active", name === tabName);
    });
}

function togglePlayback() {
    if (replayState.playing) pausePlayback();
    else startPlayback();
}

function startPlayback() {
    if (replayState.playing || !events().length) return;
    replayState.playing = true;
    renderTransport();
    if (replayState.index < 0) goToEvent(0, true);
    else scheduleNext(currentEvent()?.timeline_gap_seconds || 0);
}

function pausePlayback() {
    replayState.playing = false;
    if (replayState.timer) window.clearTimeout(replayState.timer);
    replayState.timer = null;
    stopAudio();
    renderTransport();
}

function goToEvent(index, speak) {
    stopAudio();
    replayState.index = Math.max(-1, Math.min(index, events().length - 1));
    renderCurrent();
    const event = currentEvent();
    if (!event) return;
    if (speak && event.audio_url) {
        playAudio(event);
    } else if (replayState.playing) {
        scheduleNext(event.timeline_gap_seconds || 0);
    }
}

function playAudio(event) {
    const audio = new Audio(event.audio_url);
    replayState.audio = audio;
    audio.onended = () => {
        replayState.audio = null;
        if (replayState.playing) scheduleNext(event.timeline_gap_seconds || 0);
    };
    audio.onerror = () => {
        replayState.audio = null;
        if (replayState.playing) scheduleNext(event.timeline_gap_seconds || 0);
    };
    audio.play().catch((error) => {
        console.warn("Audio play failed", error);
        replayState.audio = null;
        if (replayState.playing) scheduleNext(event.timeline_gap_seconds || 0);
    });
}

function stopAudio() {
    if (!replayState.audio) return;
    try {
        replayState.audio.pause();
        replayState.audio.currentTime = 0;
        replayState.audio.src = "";
        replayState.audio.load();
    } catch {
        // Best effort cleanup for browser-owned audio.
    }
    replayState.audio = null;
}

function scheduleNext(seconds) {
    if (!replayState.playing) return;
    if (replayState.index >= events().length - 1) {
        pausePlayback();
        return;
    }
    if (replayState.timer) window.clearTimeout(replayState.timer);
    replayState.timer = window.setTimeout(
        () => goToEvent(replayState.index + 1, true),
        Math.max(0, Number(seconds) || 0) * 1000,
    );
}

function openReplayAnalysis() {
    const event = currentEvent();
    const modal = $("analysis-modal");
    $("analysis-title").textContent = event
        ? `${event.player_name}${event.request_number ? ` #${event.request_number}` : ""}`
        : "AI Decision Analysis";
    $("analysis-subtitle").textContent = event?.source_file || "No response selected";
    $("analysis-body").innerHTML = event ? analysisHtml(event) : "<div class=\"analysis-empty\">Select a response first.</div>";
    modal.classList.remove("hidden");
}

function closeReplayAnalysis() {
    $("analysis-modal").classList.add("hidden");
}

function analysisHtml(event) {
    const fields = [
        ["Thinking", event.internal_thinking],
        ["Note to Self", event.note_to_self],
        ["Speech", event.say_outloud],
        ["Action", event.action_type ? `${event.action_type}\n${JSON.stringify(event.parameters || {}, null, 2)}` : ""],
    ].filter(([, value]) => value);
    return `
        <div class="analysis-turn-flow">
            <div class="analysis-section-title">Timeline Position</div>
            <div class="analysis-turn-steps">
                <button class="analysis-turn-step active" type="button">
                    <span>${escapeHtml(event.kind)}</span>
                    <strong>${escapeHtml(event.player_name)} ${event.request_number ? `#${escapeHtml(String(event.request_number))}` : ""}</strong>
                </button>
            </div>
        </div>
        <div class="analysis-flow">
            ${fields.map(([title, value]) => `
                <div class="analysis-node">
                    <div class="analysis-node-marker"></div>
                    <div class="analysis-node-content">
                        <div class="analysis-node-title">${escapeHtml(title)}</div>
                        <div class="analysis-node-subtitle">${escapeHtml(event.timestamp || "")}</div>
                        <div class="analysis-text">${escapeHtml(value)}</div>
                    </div>
                </div>
            `).join("")}
        </div>
        <div class="analysis-field">
            <div class="analysis-field-label">Parsed Response</div>
            <pre class="analysis-text">${escapeHtml(JSON.stringify({
                action_type: event.action_type,
                parameters: event.parameters,
                say_outloud: event.say_outloud,
                chat_to: event.chat_to,
                tokens: event.tokens,
                model: event.model,
            }, null, 2))}</pre>
        </div>
        ${event.raw_content ? `<div class="analysis-field"><div class="analysis-field-label">Raw</div><pre class="analysis-text">${escapeHtml(event.raw_content)}</pre></div>` : ""}
    `;
}

function zoomIn() {
    if (catanBoard) catanBoard.zoomIn();
}

function zoomOut() {
    if (catanBoard) catanBoard.zoomOut();
}

function resetZoom() {
    if (catanBoard) catanBoard.resetZoom();
}

function toggleVertices() {
    if (catanBoard) catanBoard.toggleVertices();
}

function toggleBuildingCosts() {
    $("buildingCostsModal").classList.toggle("hidden");
}

function formatTime(value) {
    if (!value) return "";
    const date = new Date(value);
    return Number.isNaN(date.getTime()) ? String(value).slice(11, 19) : date.toLocaleTimeString();
}

function escapeHtml(value) {
    const div = document.createElement("div");
    div.textContent = value ?? "";
    return div.innerHTML;
}

function escapeAttr(value) {
    return escapeHtml(value).replace(/"/g, "&quot;");
}

function escapeJs(value) {
    return String(value || "").replace(/\\/g, "\\\\").replace(/'/g, "\\'");
}

function showFatalError(error) {
    document.body.innerHTML = `<pre>${escapeHtml(error.stack || String(error))}</pre>`;
}
