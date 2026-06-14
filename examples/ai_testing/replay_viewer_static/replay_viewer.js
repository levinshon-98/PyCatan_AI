const replayState = {
    manifest: null,
    sessions: [],
    defaultSession: "",
    index: -1,
    playing: false,
    timer: null,
    thinkingTimer: null,
    thinking: null,
    audio: null,
    filter: "all",
    boardReady: false,
    selectedAIView: "chat",
    adminUnlocked: false,
    publicConfig: null,
    introStep: 0,
};

let catanBoard = null;
window.catanBoard = null;
window.gameState = null;

const $ = (id) => document.getElementById(id);
const RESOURCE_ORDER = [
    ["wood", "🌲", "wood"],
    ["brick", "🧱", "brick"],
    ["sheep", "🐑", "sheep"],
    ["wheat", "🌾", "wheat"],
    ["ore", "⛰️", "ore"],
];
const DEV_CARD_LABELS = {
    K: "Knight",
    KNIGHT: "Knight",
    VP: "VP",
    VICTORY_POINT: "VP",
    ROAD: "Road",
    ROAD_BUILDING: "Road",
    RB: "Road",
    MONOPOLY: "Monopoly",
    MON: "Monopoly",
    PLENTY: "Plenty",
    YEAR_OF_PLENTY: "Plenty",
    YOP: "Plenty",
};
const INTRO_STORAGE_KEY = "pycatan_replay_intro_seen";
const ADMIN_PASSWORD = "catan-replay";
const EMAILJS_SERVICE_ID = "service_7zvgf1d";
const EMAILJS_TEMPLATE_ID = "template_8fhb9w1";
const EMAILJS_PUBLIC_KEY = "IxysEF7YkU8-Qnd-s";
const OWNER_EMAIL = "levinshon@gmail.com";
const LINKEDIN_URL = "https://www.linkedin.com/in/shon-levin/";

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
    $("replay-help")?.addEventListener("click", () => showIntro(true));
    $("intro-close")?.addEventListener("click", closeIntro);
    $("intro-back")?.addEventListener("click", () => setIntroStep(replayState.introStep - 1));
    $("intro-next")?.addEventListener("click", nextIntroStep);
    $("replay-admin-unlock")?.addEventListener("click", unlockAdmin);
    $("admin-close")?.addEventListener("click", closeAdmin);
    $("admin-save")?.addEventListener("click", saveAdminConfig);
    $("mobile-link-form")?.addEventListener("submit", submitMobileLinkRequest);
    window.addEventListener("resize", updateMobileGate);
    window.addEventListener("orientationchange", updateMobileGate);
    window.addEventListener("pagehide", stopAudio);
    window.addEventListener("beforeunload", stopAudio);
    updateMobileGate();
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
    replayState.publicConfig = payload.public_config || null;

    const selected = new URLSearchParams(location.search).get("session")
        || replayState.defaultSession
        || replayState.sessions[0]?.name
        || "";

    $("session-select").innerHTML = replayState.sessions.length
        ? replayState.sessions.map((session) => {
            const label = `${sessionLabel(session)} (${session.responses || 0} responses${session.audio != null ? `, ${session.audio} audio` : ""})`;
            return `<option value="${escapeAttr(session.name)}" ${session.name === selected ? "selected" : ""}>${escapeHtml(label)}</option>`;
        }).join("")
        : "<option value=\"\">No published sessions</option>";

    renderIntroSessions();
    showIntro(false);

    if (selected) {
        await loadManifest(selected);
    } else {
        renderCurrent();
    }
}

function sessionLabel(session) {
    return session?.title || session?.display_name || session?.name || "";
}

function renderIntroSessions() {
    const container = $("intro-session-list");
    if (!container) return;
    container.innerHTML = replayState.sessions.length
        ? replayState.sessions.map((session) => `
            <button class="replay-intro-session" type="button" data-session="${escapeAttr(session.name)}">
                <strong>${escapeHtml(sessionLabel(session))}</strong>
                <span>${escapeHtml(session.description || `${session.responses || 0} responses · ${session.audio || 0} audio clips`)}</span>
            </button>
        `).join("")
        : "<div class=\"replay-intro-empty\">No published sessions yet.</div>";
    container.querySelectorAll("[data-session]").forEach((button) => {
        button.addEventListener("click", async () => {
            await loadManifest(button.dataset.session);
            closeIntro();
        });
    });
}

function showIntro(force) {
    const modal = $("intro-modal");
    if (!modal) return;
    const seen = localStorage.getItem(INTRO_STORAGE_KEY) === "1";
    if (force || !seen) {
        setIntroStep(0);
        modal.classList.remove("hidden");
    }
}

function closeIntro() {
    if ($("intro-hide-next")?.checked) {
        localStorage.setItem(INTRO_STORAGE_KEY, "1");
    }
    $("intro-modal")?.classList.add("hidden");
}

function setIntroStep(step) {
    const steps = [...document.querySelectorAll(".replay-intro-step")];
    if (!steps.length) return;
    replayState.introStep = Math.max(0, Math.min(step, steps.length - 1));
    steps.forEach((node, index) => node.classList.toggle("active", index === replayState.introStep));
    $("intro-back").disabled = replayState.introStep === 0;
    $("intro-next").textContent = replayState.introStep === steps.length - 1 ? "Close guide" : "Next";
    renderIntroProgress(steps.length);
}

function nextIntroStep() {
    const steps = document.querySelectorAll(".replay-intro-step").length;
    if (replayState.introStep >= steps - 1) {
        closeIntro();
        return;
    }
    setIntroStep(replayState.introStep + 1);
}

function renderIntroProgress(total) {
    const progress = $("intro-progress");
    if (!progress) return;
    progress.innerHTML = Array.from({ length: total }, (_, index) => `
        <span class="${index === replayState.introStep ? "active" : ""}">${index + 1}</span>
    `).join("");
}

async function unlockAdmin() {
    const password = window.prompt("Admin password");
    if (password !== ADMIN_PASSWORD) return;
    replayState.adminUnlocked = true;
    await openAdmin();
}

async function openAdmin() {
    const modal = $("admin-modal");
    if (!modal) return;
    modal.classList.remove("hidden");
    $("admin-status").textContent = "Loading sessions...";
    const response = await fetch("/api/admin/sessions", {
        headers: { "X-Replay-Admin": ADMIN_PASSWORD },
    });
    if (!response.ok) {
        $("admin-status").textContent = "Could not load sessions.";
        return;
    }
    const payload = await response.json();
    renderAdminSessions(payload.sessions || []);
    $("admin-status").textContent = "Client-side lock only. Use for demo publishing, not private data.";
}

function closeAdmin() {
    $("admin-modal")?.classList.add("hidden");
}

function isMobileReplayViewport() {
    const narrow = window.matchMedia("(max-width: 820px)").matches;
    const compactTouch = window.matchMedia("(pointer: coarse)").matches && window.innerWidth < 1024;
    return narrow || compactTouch;
}

function updateMobileGate() {
    const gate = $("mobile-gate");
    if (!gate) return;
    gate.hidden = !isMobileReplayViewport();
}

async function submitMobileLinkRequest(event) {
    event.preventDefault();
    const email = $("mobile-link-email")?.value?.trim() || "";
    const status = $("mobile-link-status");
    if (!email) return;
    if (status) status.textContent = "Saving your email...";
    const response = await fetch("/api/mobile_link_request", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
            email,
            session: $("session-select")?.value || replayState.defaultSession || "",
            page: window.location.href,
        }),
    });
    const payload = await response.json().catch(() => ({}));
    if (!response.ok) {
        if (status) status.textContent = payload.error || "Could not save this email. Please try again.";
        return;
    }
    if (payload.email_sent) {
        if (status) status.textContent = "Sent. Check your inbox for the desktop link.";
        $("mobile-link-form")?.reset();
        return;
    }
    if (status) status.textContent = "Saved. Sending the email from your browser...";
    try {
        await sendMobileLinkWithEmailJs(email);
        if (status) status.textContent = "Sent. Check your inbox for the desktop link.";
    } catch (error) {
        console.warn("EmailJS browser fallback failed", error);
        if (status) status.textContent = "Got it. We saved your email, but the automatic send failed.";
    }
    $("mobile-link-form")?.reset();
}

async function sendMobileLinkWithEmailJs(email) {
    const sessionName = $("session-select")?.value || replayState.defaultSession || "";
    const link = window.location.href;
    await sendEmailJsTemplate({
        title: "Your AI Catan replay link is ready",
        to: email,
        data: buildMobileEmailHtml({ link, sessionName }),
        message: buildMobileEmailText({ link, sessionName }),
        link,
        session: sessionName,
    });
    try {
        await sendEmailJsTemplate({
            title: `Replay link sent to ${email}`,
            to: OWNER_EMAIL,
            data: buildOwnerNotificationHtml({ recipient: email, link, sessionName }),
            message: buildOwnerNotificationText({ recipient: email, link, sessionName }),
            link,
            session: sessionName,
            visitor_email: email,
        });
    } catch (error) {
        console.warn("Owner notification email failed", error);
    }
}

async function sendEmailJsTemplate(templateParams) {
    const payload = {
        service_id: EMAILJS_SERVICE_ID,
        template_id: EMAILJS_TEMPLATE_ID,
        user_id: EMAILJS_PUBLIC_KEY,
        template_params: {
            ...templateParams,
            name: "AI Catan Replay Viewer",
            email: OWNER_EMAIL,
            linkedin: LINKEDIN_URL,
        },
    };
    const response = await fetch("https://api.emailjs.com/api/v1.0/email/send", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
    });
    if (!response.ok) {
        throw new Error(await response.text());
    }
}

function buildOwnerNotificationText({ recipient, link, sessionName }) {
    return [
        "A mobile replay link email was sent.",
        "",
        `Recipient: ${recipient}`,
        `Session: ${sessionName || "Selected replay"}`,
        `Link: ${link}`,
    ].join("\n");
}

function buildOwnerNotificationHtml({ recipient, link, sessionName }) {
    const safeLink = escapeAttr(link);
    const safeRecipient = escapeHtml(recipient);
    const safeSession = escapeHtml(sessionName || "Selected replay");
    return `
        <div style="margin:0;padding:0;background:#f3f6fb;font-family:Inter,Segoe UI,Arial,sans-serif;color:#172033;">
          <div style="max-width:620px;margin:0 auto;padding:32px 18px;">
            <div style="background:#ffffff;border:1px solid #dbe4f0;border-radius:14px;padding:28px;box-shadow:0 14px 38px rgba(15,23,42,0.10);">
              <div style="font-size:12px;font-weight:900;letter-spacing:.08em;text-transform:uppercase;color:#2f6fed;">AI Catan Replay Viewer</div>
              <h1 style="margin:10px 0 16px;font-size:24px;line-height:1.2;color:#111827;">Replay link email sent</h1>
              <p style="margin:0 0 18px;font-size:15px;line-height:1.6;color:#475569;">A desktop replay link was sent to a mobile visitor.</p>
              <div style="background:#f8fafc;border:1px solid #e2e8f0;border-radius:10px;padding:16px;font-size:14px;line-height:1.7;color:#334155;">
                <div><strong>Recipient:</strong> ${safeRecipient}</div>
                <div><strong>Session:</strong> ${safeSession}</div>
              </div>
              <div style="margin-top:22px;">
                <a href="${safeLink}" style="display:inline-block;background:#2f6fed;color:#ffffff;text-decoration:none;font-weight:900;border-radius:10px;padding:12px 18px;">Open replay link</a>
              </div>
            </div>
          </div>
        </div>
    `.trim();
}

function buildMobileEmailText({ link, sessionName }) {
    return [
        "Thanks for checking out the AI Catan Replay Viewer.",
        "",
        "This is an experimental replay interface for Catan games played by AI agents. Instead of only seeing the final board, you can replay a recorded session step by step: board state, table talk, actions, dice rolls, resource changes, and parts of the AI decision trace.",
        "",
        "It is best viewed on a laptop or desktop because the board, timeline, logs, chat, audio, and analysis panel all need room.",
        "",
        `Open the replay: ${link}`,
        `Session: ${sessionName || "Selected replay"}`,
        "",
        `Shon Levin: ${LINKEDIN_URL}`,
    ].join("\n");
}

function buildMobileEmailHtml({ link, sessionName }) {
    const safeLink = escapeAttr(link);
    const safeSession = escapeHtml(sessionName || "Selected replay");
    return `
        <div style="margin:0;padding:0;background:#f3f6fb;font-family:Inter,Segoe UI,Arial,sans-serif;color:#172033;">
          <div style="max-width:660px;margin:0 auto;padding:36px 18px;">
            <div style="background:#ffffff;border:1px solid #dbe4f0;border-radius:14px;overflow:hidden;box-shadow:0 18px 48px rgba(15,23,42,0.12);">
              <div style="background:#111827;color:#ffffff;padding:30px;">
                <div style="font-size:12px;font-weight:800;letter-spacing:.08em;text-transform:uppercase;color:#93c5fd;">AI Catan Replay Viewer</div>
                <h1 style="margin:12px 0 0;font-size:28px;line-height:1.15;font-weight:900;">Your replay link is ready</h1>
              </div>
              <div style="padding:30px;">
                <p style="margin:0 0 16px;font-size:16px;line-height:1.65;color:#334155;">Thanks for checking out the AI Catan Replay Viewer.</p>
                <p style="margin:0 0 16px;font-size:16px;line-height:1.65;color:#334155;">This is an experimental replay interface for Catan games played by AI agents. Instead of only seeing the final board, you can replay a recorded session step by step.</p>
                <div style="margin:22px 0;padding:18px;background:#f8fafc;border:1px solid #e2e8f0;border-radius:10px;">
                  <div style="font-size:13px;font-weight:900;color:#111827;margin-bottom:10px;">Inside the replay you can follow:</div>
                  <ul style="margin:0;padding-left:20px;color:#475569;font-size:14px;line-height:1.75;">
                    <li>the board state as it changes over time</li>
                    <li>the table talk and recorded audio</li>
                    <li>actions, dice rolls, and resource changes</li>
                    <li>the AI decision trace behind interesting moves</li>
                  </ul>
                </div>
                <p style="margin:0 0 24px;font-size:16px;line-height:1.65;color:#334155;">The viewer is best on a laptop or desktop because the board, timeline, logs, chat, audio, and analysis panel all need room to breathe.</p>
                <div style="margin:24px 0;text-align:center;">
                  <a href="${safeLink}" style="display:inline-block;background:#2f6fed;color:#ffffff;text-decoration:none;font-weight:900;border-radius:10px;padding:14px 22px;">Open the replay</a>
                </div>
                <div style="margin:22px 0;padding:14px 16px;background:#eff6ff;border:1px solid #bfdbfe;border-radius:10px;color:#1e3a8a;font-size:14px;">
                  <strong>Session:</strong> ${safeSession}
                </div>
                <p style="margin:24px 0 0;font-size:14px;line-height:1.6;color:#64748b;">
                  Curious about the project or want to follow along?
                  <a href="${escapeAttr(LINKEDIN_URL)}" style="color:#2f6fed;font-weight:800;text-decoration:none;">Connect with Shon Levin on LinkedIn</a>.
                </p>
              </div>
            </div>
            <p style="margin:18px 0 0;text-align:center;font-size:12px;color:#94a3b8;">Sent because this replay is much happier on a real screen.</p>
          </div>
        </div>
    `.trim();
}

function renderAdminSessions(sessions) {
    const container = $("admin-session-list");
    if (!container) return;
    container.innerHTML = sessions.length
        ? sessions.map((session, index) => `
            <div class="replay-admin-session" data-session="${escapeAttr(session.name)}">
                <label class="replay-admin-toggle">
                    <input type="checkbox" data-field="enabled" ${session.public_enabled ? "checked" : ""}>
                    <span>Publish</span>
                </label>
                <div class="replay-admin-session-main">
                    <div class="replay-admin-session-name">${escapeHtml(session.name)}</div>
                    <input data-field="title" value="${escapeAttr(session.title || session.name)}" placeholder="Public title">
                    <textarea data-field="description" placeholder="Short public description">${escapeHtml(session.description || "")}</textarea>
                    <input data-field="order" type="number" value="${escapeAttr(String(session.public_order ?? index))}" placeholder="Order">
                </div>
            </div>
        `).join("")
        : "<div class=\"replay-intro-empty\">No recorded sessions were found.</div>";
}

async function saveAdminConfig() {
    if (!replayState.adminUnlocked) return;
    const rows = [...document.querySelectorAll(".replay-admin-session")];
    const sessions = rows.map((row, index) => ({
        name: row.dataset.session,
        enabled: row.querySelector('[data-field="enabled"]')?.checked || false,
        title: row.querySelector('[data-field="title"]')?.value || "",
        description: row.querySelector('[data-field="description"]')?.value || "",
        order: Number(row.querySelector('[data-field="order"]')?.value || index),
    }));
    $("admin-status").textContent = "Saving...";
    const response = await fetch("/api/public_config", {
        method: "POST",
        headers: { "Content-Type": "application/json", "X-Replay-Admin": ADMIN_PASSWORD },
        body: JSON.stringify({ sessions }),
    });
    if (!response.ok) {
        $("admin-status").textContent = "Save failed.";
        return;
    }
    $("admin-status").textContent = "Saved. Public list updated.";
    await initialiseSessions();
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
    renderDiceOverlay(gameState);
    renderAIContent();
}

function renderTransport() {
    const total = events().length;
    const pending = replayState.thinking;
    const event = pending?.event || currentEvent();
    const shownIndex = pending ? pending.index : replayState.index;
    const current = shownIndex < 0 ? 0 : shownIndex + 1;
    $("replay-label").textContent = `${current} / ${total}`;
    $("replay-slider").value = Math.max(0, shownIndex);
    $("replay-context").textContent = pending
        ? `${pending.event.player_name} thinking...`
        : event
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
    const active = replayState.thinking?.event || currentEvent();
    $("replay-timeline-track").innerHTML = events().map((event) => {
        const hidden = replayState.filter !== "all" && event.player_name !== replayState.filter;
        const label = pointLabel(event);
        const classes = [
            "replay-point",
            event.has_action ? "has-action" : "",
            event.has_speech ? "has-speech" : "",
            event.kind === "chat" ? "chat-only" : "",
            event.kind === "memory" ? "memory-only" : "",
            event.index === active?.index ? "active" : "",
            event.index === replayState.thinking?.index ? "thinking" : "",
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
    const snapshot = stateSnapshotForIndex(untilIndex);
    if (snapshot) {
        const fromSnapshot = {
            robber: snapshot.meta?.robber || null,
            settlements: new Map(),
            cities: new Map(),
            roads: new Map(),
            lastDice: snapshot.meta?.dice || null,
            diceTotal: snapshot.meta?.dice_total || null,
            lastAction: currentEvent(),
        };
        (snapshot.state?.buildings || []).forEach((building) => {
            const node = Number(building.node);
            if (!node) return;
            if (String(building.type || "").toUpperCase() === "C") fromSnapshot.cities.set(node, building.owner);
            else fromSnapshot.settlements.set(node, building.owner);
        });
        (snapshot.state?.roads || []).forEach((road) => addRoadToState(fromSnapshot, road.from, road.to, road.owner));
        return fromSnapshot;
    }

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

function stateSnapshotForIndex(index) {
    if (!replayState.manifest || index < 0) return null;
    const event = events()[index];
    if (event?.state_after) return event.state_after;
    if (event?.state_before) return event.state_before;
    for (let cursor = index - 1; cursor >= 0; cursor -= 1) {
        if (events()[cursor]?.state_after) return events()[cursor].state_after;
        if (events()[cursor]?.state_before) return events()[cursor].state_before;
    }
    for (let cursor = index + 1; cursor < events().length; cursor += 1) {
        if (events()[cursor]?.state_before) return events()[cursor].state_before;
    }
    return null;
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
    const snapshot = stateSnapshotForIndex(replayState.index);
    const snapshotPlayers = snapshot?.players || {};
    const players = playerNames().map((name) => {
        const settlements = [...boardState.settlements.values()].filter((value) => value === name).length;
        const cities = [...boardState.cities.values()].filter((value) => value === name).length;
        const roads = [...boardState.roads.values()].filter((road) => road.player === name).length;
        const recorded = snapshotPlayers[name] || {};
        return {
            id: playerIndex(name) - 1,
            name,
            victory_points: Number.isFinite(Number(recorded.vp)) ? Number(recorded.vp) : settlements + cities * 2,
            total_cards: resourceTotal(recorded.resources),
            resources: normalizeRecordedResources(recorded.resources),
            dev_cards: recorded.dev || {},
            stat: Array.isArray(recorded.stat) ? recorded.stat : [],
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
        current_player: Math.max(0, playerIndex(snapshot?.meta?.current_player || currentEvent()?.player_name) - 1),
        current_phase: snapshot?.meta?.turn_phase || snapshot?.meta?.phase || currentEvent()?.action_type || currentEvent()?.kind || "REPLAY",
        dice_result: snapshot?.meta?.dice || boardState.lastDice,
        dice_total: snapshot?.meta?.dice_total || boardState.diceTotal,
        replay_index: replayState.index,
    };
}

function normalizeRecordedResources(resources) {
    const normalized = { wood: 0, brick: 0, sheep: 0, wheat: 0, ore: 0 };
    if (!resources || typeof resources !== "object") return normalized;
    Object.keys(normalized).forEach((key) => {
        normalized[key] = Number(resources[key] || 0);
    });
    return normalized;
}

function resourceTotal(resources) {
    const normalized = normalizeRecordedResources(resources);
    return Object.values(normalized).reduce((sum, value) => sum + Number(value || 0), 0);
}

function renderPlayerHub(gameState) {
    const current = currentEvent();
    const focus = replayState.thinking?.event || current;
    if (!gameState.players.length) {
        $("player-hub").innerHTML = "<div class=\"loading-state\">Choose a session...</div>";
        return;
    }
    $("player-hub").innerHTML = gameState.players.map((player) => {
        const cssIndex = player.id + 1;
        const isThinking = replayState.thinking?.event?.player_name === player.name;
        const isSpeaking = !isThinking && current?.player_name === player.name && current?.say_outloud;
        const latestSpeech = latestSpeechForPlayer(player.name);
        return `
            <div class="player-card player-${cssIndex} ${player.is_current || focus?.player_name === player.name ? "active" : ""} ${isSpeaking ? "replay-speaking" : ""} ${isThinking ? "replay-thinking" : ""}">
                <div class="player-header">
                    <div class="player-avatar player-${cssIndex}">${escapeHtml(playerInitial(player.name))}</div>
                    <div class="player-info-header">
                        <div class="player-name">${escapeHtml(player.name)}</div>
                        <div class="player-stats">
                            <span>🏆 ${player.victory_points} VP</span>
                            <span>${player.roads_count} roads</span>
                        </div>
                        ${playerAwardBadges(player)}
                    </div>
                </div>
                <div class="player-resources-grid">
                    ${RESOURCE_ORDER.map(([key, icon]) => `
                        <div class="resource-item">
                            <span class="resource-icon">${icon}</span>
                            <span class="resource-count">${player.resources[key] || 0}</span>
                        </div>
                    `).join("")}
                </div>
                <div class="player-dev-cards detailed">
                    <span class="dev-card-empty">${player.total_cards} resource cards</span>
                    ${renderDevCards(player.dev_cards)}
                </div>
                ${latestSpeech ? `<div class="player-chat-bubble ${latestSpeech.isThinking ? "thinking-bubble" : ""} ${latestSpeech.isCurrentSpeech ? "now-speaking-bubble" : ""}"><strong class="speech-label">${escapeHtml(latestSpeech.kindLabel)}</strong><br>${latestSpeech.isThinking ? "<span class=\"thinking-dots\"><span></span><span></span><span></span></span>" : escapeHtml(latestSpeech.text)}</div>` : ""}
            </div>`;
    }).join("");
}

function latestSpeechForPlayer(playerName) {
    if (replayState.thinking?.event?.player_name === playerName) {
        return {
            text: "Thinking...",
            kindLabel: "Thinking",
            isThinking: true,
        };
    }
    if (replayState.index < 0) return null;
    const event = [...events().slice(0, replayState.index + 1)]
        .reverse()
        .find((candidate) => candidate.player_name === playerName && candidate.say_outloud);
    if (!event) return null;
    return {
        text: event.say_outloud,
        kindLabel: event.index === replayState.index ? "Now speaking" : "Last said",
        isCurrentSpeech: event.index === replayState.index,
    };
}

function devSummary(devCards) {
    if (!devCards || typeof devCards !== "object") return "no dev cards";
    const revealed = Array.isArray(devCards.r) ? devCards.r.length : 0;
    const hidden = Number(devCards.hidden_count || 0);
    const mine = Array.isArray(devCards.h) ? devCards.h.length : 0;
    const total = revealed + hidden + mine;
    return total ? `${total} dev cards` : "no dev cards";
}

function playerAwardBadges(player) {
    const stat = Array.isArray(player.stat) ? player.stat : [];
    const badges = [];
    if (stat.includes("LR")) badges.push(["LR", "Longest Road"]);
    if (stat.includes("LA")) badges.push(["LA", "Largest Army"]);
    if (!badges.length) return "";
    return `<div class="player-public-cards replay-awards">${badges.map(([icon, label]) => `
        <span class="public-card-chip award" title="${escapeAttr(label)}">
            <span class="public-chip-icon">${escapeHtml(icon)}</span>
            <span class="public-chip-name">${escapeHtml(label)}</span>
        </span>
    `).join("")}</div>`;
}

function renderDevCards(devCards) {
    if (!devCards || typeof devCards !== "object") {
        return "<span class=\"dev-card-empty\">no dev cards</span>";
    }

    const chips = [];
    cardCounts(Array.isArray(devCards.r) ? devCards.r : []).forEach(([card, count]) => {
        chips.push(`<span class="dev-card-chip replay-dev-revealed" title="Revealed development card"><span class="dev-chip-name">${escapeHtml(devCardLabel(card))}${count > 1 ? ` x${count}` : ""}</span></span>`);
    });
    cardCounts(Array.isArray(devCards.h) ? devCards.h : []).forEach(([card, count]) => {
        chips.push(`<span class="dev-card-chip replay-dev-known" title="Known hidden card in this prompt"><span class="dev-chip-name">${escapeHtml(devCardLabel(card))}${count > 1 ? ` x${count}` : ""}</span></span>`);
    });

    const hidden = Number(devCards.hidden_count || 0);
    if (hidden > 0) {
        chips.push(`<span class="dev-card-chip replay-dev-hidden" title="Unrevealed development cards"><span class="dev-chip-name">Hidden x${hidden}</span></span>`);
    }

    return chips.length ? chips.join("") : "<span class=\"dev-card-empty\">no dev cards</span>";
}

function cardCounts(cards) {
    const counts = new Map();
    cards.forEach((card) => {
        const key = String(card || "").trim();
        if (!key) return;
        counts.set(key, (counts.get(key) || 0) + 1);
    });
    return [...counts.entries()];
}

function devCardLabel(card) {
    const normalized = String(card || "").trim().toUpperCase().replace(/[\s-]+/g, "_");
    return DEV_CARD_LABELS[normalized] || String(card || "Dev");
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
                ${diceSummary(event) ? `<span>${escapeHtml(diceSummary(event))}</span>` : ""}
                ${devActionSummary(event) ? `<span class="dev-action-chip">${escapeHtml(devActionSummary(event))}</span>` : ""}
                ${resourceDelta(event).map((delta) => `<span class="${delta.amount > 0 ? "resource-plus" : "resource-minus"}">${escapeHtml(deltaLabel(delta))}</span>`).join("")}
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

function diceSummary(event) {
    const meta = event.state_after?.meta || event.state_before?.meta || {};
    const total = meta.dice_total;
    const dice = Array.isArray(meta.dice) ? meta.dice : null;
    if (!total && !dice) return "";
    return dice && dice.length >= 2 ? `dice ${total || dice.reduce((sum, value) => sum + Number(value || 0), 0)} (${dice.join("+")})` : `dice ${total}`;
}

function devActionSummary(event) {
    const action = String(event.action_type || "").toLowerCase();
    if (action === "buy_dev_card") return "dev card bought";
    if (action !== "use_dev_card") return "";
    const cardType = event.parameters?.card_type || event.parameters?.card || "";
    return `${devCardLabel(cardType)} played`;
}

function renderDiceOverlay(gameState) {
    const layer = $("board-event-layer");
    const popover = $("board-dice-popover");
    if (!layer || !popover) return;
    const event = currentEvent();
    const dice = Array.isArray(gameState.dice_result) ? gameState.dice_result : [];
    const total = Number(gameState.dice_total || (dice.length ? dice.reduce((sum, value) => sum + Number(value || 0), 0) : 0));
    const shouldShow = Boolean(event && total && (String(event.action_type || "").toLowerCase() === "roll_dice" || diceChanged(event)));

    layer.classList.toggle("active", shouldShow);
    popover.hidden = !shouldShow;
    if (!shouldShow) {
        popover.innerHTML = "";
        return;
    }

    const breakdown = dice.length ? dice.join(" + ") : String(total);
    popover.innerHTML = `
        <div class="board-dice-title">Dice roll</div>
        <div class="board-dice-value">
            <span class="board-dice-total">${escapeHtml(String(total))}</span>
            <span class="board-dice-breakdown">${escapeHtml(breakdown)}</span>
        </div>
    `;
}

function diceChanged(event) {
    const before = event.state_before?.meta || {};
    const after = event.state_after?.meta || {};
    if (!after.dice_total && !after.dice) return false;
    return JSON.stringify(before.dice || null) !== JSON.stringify(after.dice || null)
        || Number(before.dice_total || 0) !== Number(after.dice_total || 0);
}

function resourceDelta(event) {
    const before = event.state_before?.players || {};
    const after = event.state_after?.players || {};
    const names = [...new Set([...Object.keys(before), ...Object.keys(after)])];
    const deltas = [];
    names.forEach((name) => {
        const beforeResources = normalizeRecordedResources(before[name]?.resources);
        const afterResources = normalizeRecordedResources(after[name]?.resources);
        RESOURCE_ORDER.forEach(([key, icon, label]) => {
            const amount = Number(afterResources[key] || 0) - Number(beforeResources[key] || 0);
            if (amount) deltas.push({ player: name, key, icon, label, amount });
        });
    });
    return deltas;
}

function deltaLabel(delta) {
    const sign = delta.amount > 0 ? "+" : "";
    return `${delta.player} ${sign}${delta.amount} ${delta.icon}`;
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
        <div class="detail-row"><strong>Dice</strong><span>${escapeHtml(gameState.dice_total ? `${gameState.dice_total} (${(gameState.dice_result || []).join("+")})` : "-")}</span></div>
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
    clearThinking();
    stopAudio();
    renderCurrent();
}

function goToEvent(index, speak) {
    clearThinking();
    stopAudio();
    const targetIndex = Math.max(-1, Math.min(index, events().length - 1));
    const event = targetIndex >= 0 ? events()[targetIndex] : null;
    if (shouldShowThinking(event, speak)) {
        replayState.thinking = { index: targetIndex, event };
        renderTimeline();
        renderTransport();
        renderPlayerHub(window.gameState || buildGameState(deriveBoardState(replayState.index)));
        replayState.thinkingTimer = window.setTimeout(
            () => applyEvent(targetIndex, speak),
            thinkingDurationSeconds(event) * 1000,
        );
        return;
    }
    applyEvent(targetIndex, speak);
}

function applyEvent(index, speak) {
    clearThinking();
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

function clearThinking() {
    if (replayState.thinkingTimer) window.clearTimeout(replayState.thinkingTimer);
    replayState.thinkingTimer = null;
    replayState.thinking = null;
}

function shouldShowThinking(event, speak) {
    return Boolean(speak && event && (event.has_action || event.has_speech));
}

function thinkingDurationSeconds(event) {
    const action = String(event?.action_type || "").toLowerCase();
    if (["trade_propose", "trade_accept", "trade_reject", "use_dev_card", "buy_dev_card", "build_road", "build_settlement", "build_city", "robber_move"].includes(action)) {
        return 1.6;
    }
    if (event?.has_action) return 1.2;
    return 0.75;
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

async function openReplayAnalysis() {
    const event = currentEvent();
    const modal = $("analysis-modal");
    $("analysis-title").textContent = event
        ? `${event.player_name}${event.request_number ? ` #${event.request_number}` : ""}`
        : "AI Decision Analysis";
    $("analysis-subtitle").textContent = event?.source_file || "No response selected";
    $("analysis-body").innerHTML = event ? "<div class=\"analysis-loading\">Loading analysis...</div>" : "<div class=\"analysis-empty\">Select a response first.</div>";
    modal.classList.remove("hidden");
    if (!event) return;

    try {
        const sessionName = encodeURIComponent(replayState.manifest?.session?.name || $("session-select")?.value || "");
        const response = await fetch(`/api/replay/analysis/${event.index}?session=${sessionName}`);
        if (!response.ok) throw new Error(`Analysis unavailable (${response.status})`);
        const analysis = await response.json();
        renderReplayAnalysis(analysis, event);
    } catch (error) {
        $("analysis-body").innerHTML = `
            <div class="analysis-empty">${escapeHtml(error.message || String(error))}</div>
            ${analysisHtml(event)}
        `;
    }
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

function renderReplayAnalysis(analysis, fallbackEvent) {
    if (!analysis || analysis.available === false) {
        $("analysis-body").innerHTML = `<div class="analysis-empty">${escapeHtml(analysis?.message || "No AI decision trace for this replay point.")}</div>`;
        return;
    }

    const worldview = analysis.worldview || {};
    const action = analysis.action || {};
    const result = analysis.engine_result || {};
    $("analysis-title").textContent = analysis.label || $("analysis-title").textContent;
    $("analysis-subtitle").textContent = `${analysis.session || ""} | replay ${Number(analysis.index || 0) + 1} / ${analysis.total || events().length}`;
    $("analysis-body").innerHTML = `
        ${renderAnalysisTurnFlow(analysis.turn_flow || [], fallbackEvent)}
        <div class="analysis-flow">
            ${renderAnalysisNode("Worldview", "What the agent could see before answering", `
                ${renderKeyText("What just happened", worldview.task_context?.what_just_happened)}
                ${renderKeyText("Instructions", worldview.task_context?.instructions)}
                ${renderObservedFacts(worldview.observed_facts || {})}
                ${renderMemory(worldview.memory_before || {})}
                ${renderAllowedActions(worldview.allowed_actions || [])}
                ${renderCompactGameState(worldview)}
            `)}
            ${renderToolTrace(analysis.tool_trace || [])}
            ${renderAnalysisNode("Thinking", "Private reasoning from the final response", `
                <div class="analysis-text">${escapeHtml(analysis.thinking || "No internal thinking recorded.")}</div>
            `)}
            ${renderAnalysisNode("Memory Update", "What was saved for future turns", `
                <div class="analysis-text">${escapeHtml(analysis.memory_write || "No memory update recorded.")}</div>
            `)}
            ${renderAnalysisNode("Communication", "What other players heard", `
                <div class="analysis-quote">${escapeHtml(analysis.say_outloud || "No public message recorded.")}</div>
            `)}
            ${renderAnalysisNode("Action", "Final selected move", `
                <div class="analysis-action-type">${escapeHtml(action.type || "No action")}</div>
                ${renderJsonBlock(action.parameters || {}, "Parameters")}
            `)}
            ${renderAnalysisNode("Engine Result", "What the game engine reported", `
                <div class="analysis-result ${result.success === false ? "fail" : "success"}">
                    ${result.success === false ? "Failed" : "Recorded"}
                </div>
                ${renderKeyText("Message", result.message || result.structured || "")}
                ${renderJsonBlock(result.data || {}, "Result Data")}
            `)}
        </div>
        <details class="analysis-raw">
            <summary>Raw prompt and response</summary>
            ${renderJsonBlock(analysis.raw || {}, "Raw")}
        </details>
    `;
}

function renderAnalysisNode(title, subtitle, innerHtml) {
    return `
        <section class="analysis-node">
            <div class="analysis-node-marker"></div>
            <div class="analysis-node-content">
                <div class="analysis-node-title">${escapeHtml(title)}</div>
                <div class="analysis-node-subtitle">${escapeHtml(subtitle || "")}</div>
                <div class="analysis-node-body">${innerHtml}</div>
            </div>
        </section>
    `;
}

function renderAnalysisTurnFlow(items, fallbackEvent) {
    const flow = items.length ? items : [{
        snapshot_index: fallbackEvent?.index,
        player_name: fallbackEvent?.player_name,
        request_number: fallbackEvent?.request_number,
        action_type: fallbackEvent?.action_type || fallbackEvent?.kind,
    }];
    return `
        <div class="analysis-turn-flow">
            <div class="analysis-section-title">Decision Flow</div>
            <div class="analysis-turn-steps">
                ${flow.map((item) => `
                    <button class="analysis-turn-step ${Number(item.snapshot_index) === replayState.index ? "active" : ""}" type="button"
                            onclick="pausePlayback(); goToEvent(${Number(item.snapshot_index || 0)}, false); openReplayAnalysis()">
                        <span>${escapeHtml(item.player_name || "Player")} #${escapeHtml(String(item.request_number || "?"))}</span>
                        <strong>${escapeHtml(item.action_type || "decision")}</strong>
                    </button>
                `).join("")}
            </div>
        </div>
    `;
}

function renderToolTrace(toolTrace) {
    if (!toolTrace.length) {
        return renderAnalysisNode("Tools", "Tool calls before the final answer", `
            <div class="analysis-text">No tool calls were recorded for this decision.</div>
        `);
    }
    return renderAnalysisNode("Tools", "Tool calls before the final answer", `
        <div class="analysis-tools">
            ${toolTrace.map((iteration) => `
                <div class="analysis-tool-iteration">
                    <div class="analysis-tool-heading">Iteration ${escapeHtml(String(iteration.iteration || "?"))}</div>
                    ${(iteration.tool_calls || []).map((call) => `
                        <div class="analysis-tool-call">
                            <strong>${escapeHtml(call.name || "tool")}</strong>
                            ${call.parameters?.reasoning ? `<div class="analysis-tool-reason">${escapeHtml(call.parameters.reasoning)}</div>` : ""}
                            ${renderJsonBlock(call.parameters || {}, "Input")}
                        </div>
                    `).join("") || "<div class=\"analysis-muted\">Tool input was not logged.</div>"}
                    ${iteration.tool_results_text ? `
                        <details class="analysis-details">
                            <summary>Tool output</summary>
                            <pre class="analysis-pre">${escapeHtml(iteration.tool_results_text)}</pre>
                        </details>
                    ` : "<div class=\"analysis-muted\">No tool output was logged.</div>"}
                </div>
            `).join("")}
        </div>
    `);
}

function renderObservedFacts(facts) {
    if (!facts || Object.keys(facts).length === 0) return "";
    const dice = facts.dice;
    const diceText = Array.isArray(dice) && dice.length
        ? `${dice.join(" + ")} = ${facts.dice_total ?? dice.reduce((sum, value) => sum + Number(value || 0), 0)}`
        : "Not visible";
    return `
        <div class="analysis-observed">
            <div class="analysis-field-label">Observed game facts from prompt</div>
            <div class="analysis-fact-grid">
                <div><span>Current</span><strong>${escapeHtml(facts.current_player || "Unknown")}</strong></div>
                <div><span>Phase</span><strong>${escapeHtml(facts.phase || "Unknown")}</strong></div>
                <div><span>Dice</span><strong>${escapeHtml(diceText)}</strong></div>
                <div><span>Robber hex</span><strong>${escapeHtml(String(facts.robber_hex ?? "Unknown"))}</strong></div>
            </div>
            ${facts.expected_action ? renderKeyText("Expected action", facts.expected_action) : ""}
            ${renderJsonBlock(facts.current_player_state || {}, `${facts.current_player || "Current player"} visible state`)}
        </div>
    `;
}

function renderMemory(memory) {
    if (!memory || Object.keys(memory).length === 0) {
        return renderKeyText("Memory before decision", "No memory was included in this prompt.");
    }
    return `
        <div class="analysis-memory">
            ${renderKeyText("Last note", memory.note_from_last_turn || memory.previous_note_to_self || "")}
            ${renderKeyText("Compacted long-term memory", memory.long_term_summary || "")}
            ${Array.isArray(memory.recent_notes) ? `
                <div class="analysis-field-label">Recent notes</div>
                <ol class="analysis-list">
                    ${memory.recent_notes.map((note) => `<li>${escapeHtml(typeof note === "string" ? note : (note.note || JSON.stringify(note)))}</li>`).join("")}
                </ol>
            ` : ""}
        </div>
    `;
}

function renderAllowedActions(actions) {
    if (!actions.length) return "";
    return `
        <div class="analysis-field-label">Allowed actions</div>
        <div class="analysis-pills">
            ${actions.map((item) => `<span>${escapeHtml(item.type || String(item))}</span>`).join("")}
        </div>
    `;
}

function renderCompactGameState(worldview) {
    const compactJson = worldview.compact_game_state_json;
    const compactText = worldview.compact_game_state;
    if (!compactText && !compactJson) return "";
    return `
        <details class="analysis-details">
            <summary>Compact game state seen by the agent</summary>
            ${compactJson ? renderJsonBlock(compactJson, "Parsed compact state") : ""}
            ${compactText ? `<pre class="analysis-pre">${escapeHtml(compactText)}</pre>` : ""}
        </details>
    `;
}

function renderKeyText(label, text) {
    if (!text) return "";
    return `
        <div class="analysis-field">
            <div class="analysis-field-label">${escapeHtml(label)}</div>
            <div class="analysis-text">${escapeHtml(text)}</div>
        </div>
    `;
}

function renderJsonBlock(value, label) {
    if (value === null || value === undefined || value === "") return "";
    let normalized = value;
    if (typeof value === "string") {
        try {
            normalized = JSON.parse(value);
        } catch {
            return renderKeyText(label, value);
        }
    }
    if (typeof normalized === "object" && !Array.isArray(normalized) && Object.keys(normalized).length === 0) return "";
    return `
        <details class="analysis-details">
            <summary>${escapeHtml(label)}</summary>
            <pre class="analysis-pre">${escapeHtml(JSON.stringify(normalized, null, 2))}</pre>
        </details>
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
