/* ========================================
   Unified View JavaScript
   PyCatan - Combined Game Board & AI Analysis
   ======================================== */

// ========== State Management ==========
let currentView = 'game';
let currentAIView = null;
let currentAIPlayer = null;
let aiSessionData = null;
let lastAIUpdate = null;

// Resource icons mapping
const RESOURCE_ICONS = {
    'wood': '🌲',
    'brick': '🧱',
    'sheep': '🐑',
    'wheat': '🌾',
    'ore': '⛰️',
    'lumber': '🌲',
    'grain': '🌾',
    'wool': '🐑'
};

// Dev card icons
const DEV_CARD_ICONS = {
    'knight': '🛡️',
    'road_building': '🛤️',
    'year_of_plenty': '🎁',
    'monopoly': '💰',
    'victory_point': '⭐'
};

// Player colors
const PLAYER_COLORS = ['#FF4444', '#4444FF', '#44FF44', '#FFAA00'];

// ========== View Switching ==========
function switchView(view) {
    currentView = view;
    
    // Update nav tabs
    document.querySelectorAll('.nav-tab').forEach(tab => {
        tab.classList.remove('active');
        if (tab.dataset.view === view) {
            tab.classList.add('active');
        }
    });
    
    // Update view containers
    document.querySelectorAll('.view-container').forEach(container => {
        container.classList.remove('active');
    });
    
    document.getElementById(`${view}-view`).classList.add('active');
    
    // Load AI data if switching to AI view
    if (view === 'ai' && !aiSessionData) {
        loadAIData();
    }
}

function switchLogTab(tab, evt) {
    // Update tab buttons
    document.querySelectorAll('.panel-tab').forEach(t => t.classList.remove('active'));
    if (evt && evt.target) {
        evt.target.classList.add('active');
    } else {
        // Fallback: find the tab button by tab name
        document.querySelectorAll('.panel-tab').forEach(t => {
            if (t.textContent.toLowerCase().includes(tab)) {
                t.classList.add('active');
            }
        });
    }
    
    // Update panels
    document.querySelectorAll('.log-panel').forEach(p => p.classList.remove('active'));
    const panel = document.getElementById(`${tab}-log-panel`);
    if (panel) {
        panel.classList.add('active');
    }
}

// ========== Player Hub Rendering ==========
function renderPlayerHub(players) {
    const hub = document.getElementById('player-hub');
    if (!hub) return; // Not on unified page
    
    if (!players || players.length === 0) {
        hub.innerHTML = '<div class="loading-state">Waiting for players...</div>';
        return;
    }
    
    hub.innerHTML = players.map((player, index) => {
        const playerNum = index + 1;
        // Check both formats for "is current player"
        const isActive = player.is_current || (window.gameState && window.gameState.current_player === index);
        const color = PLAYER_COLORS[index] || '#888';
        
        // Get total cards - handle both formats
        const totalCards = player.total_cards || getTotalCards(player);
        
        // Get resources - handle different formats
        const resources = player.resources || {};
        const woodCount = resources.wood || resources.lumber || 0;
        const brickCount = resources.brick || 0;
        const sheepCount = resources.sheep || resources.wool || 0;
        const wheatCount = resources.wheat || resources.grain || 0;
        const oreCount = resources.ore || 0;
        
        return `
            <div class="player-card player-${playerNum} ${isActive ? 'active' : ''}" data-player="${playerNum}" data-player-name="${escapeHtml(player.name || '')}">
                <div class="player-header">
                    <div class="player-avatar player-${playerNum}">
                        ${getPlayerInitial(player.name)}
                    </div>
                    <div class="player-info-header">
                        <div class="player-name">${escapeHtml(player.name || 'Player ' + playerNum)}</div>
                        <div class="player-stats">
                            <span>🏆 ${player.victory_points || 0} VP</span>
                            <span>🃏 ${totalCards} Cards</span>
                        </div>
                    </div>
                </div>
                
                <div class="player-thinking-log" id="thinking-log-${escapeHtml(player.name || 'player' + playerNum)}">
                    <!-- Thinking steps will be added here -->
                </div>
                
                ${renderPlayerChatBubble(player, index)}
                
                <div class="player-resources-grid">
                    ${renderResourceItem('wood', woodCount)}
                    ${renderResourceItem('brick', brickCount)}
                    ${renderResourceItem('sheep', sheepCount)}
                    ${renderResourceItem('wheat', wheatCount)}
                    ${renderResourceItem('ore', oreCount)}
                </div>
                
                ${renderDevCards(player.development_cards || player.dev_cards)}
            </div>
        `;
    }).join('');
}

function getPlayerInitial(name) {
    if (!name) return '?';
    return name.charAt(0).toUpperCase();
}

function getTotalCards(player) {
    // Check cards_list first (accurate count)
    if (player.cards_list && Array.isArray(player.cards_list)) {
        return player.cards_list.length;
    }
    // Fall back to resources object
    if (player.resources) {
        return Object.values(player.resources).reduce((sum, val) => sum + (val || 0), 0);
    }
    return 0;
}

function renderResourceItem(type, count) {
    const icon = RESOURCE_ICONS[type] || '❓';
    return `
        <div class="resource-item">
            <span class="resource-icon">${icon}</span>
            <span class="resource-count">${count}</span>
        </div>
    `;
}

function renderDevCards(devCards) {
    if (!devCards || Object.keys(devCards).length === 0) return '';
    
    const totalCards = Object.values(devCards).reduce((sum, val) => sum + (val || 0), 0);
    if (totalCards === 0) return '';
    
    return `
        <div class="player-dev-cards">
            ${Object.entries(devCards).map(([type, count]) => {
                if (count === 0) return '';
                const icon = DEV_CARD_ICONS[type] || '🃏';
                return `
                    <div class="dev-card-mini">
                        <span class="card-icon">${icon}</span>
                        <span>${count}</span>
                    </div>
                `;
            }).join('')}
        </div>
    `;
}

// Store chat bubble timeouts to manage auto-hide
const chatBubbleTimeouts = {};
// Store active chat messages with their expiry time
const activeChatMessages = {};

function renderPlayerChatBubble(player, playerIndex) {
    const playerName = player.name || 'player' + playerIndex;
    
    // Check if there's an active (non-expired) message for this player
    const activeMsg = activeChatMessages[playerName];
    if (!activeMsg || Date.now() > activeMsg.expiresAt) {
        // No active message or expired
        delete activeChatMessages[playerName];
        return '';
    }
    
    const bubbleId = `chat-bubble-${playerName}`;
    
    return `
        <div class="player-chat-bubble" id="${bubbleId}">
            ${escapeHtml(activeMsg.message)}
        </div>
    `;
}

function showPlayerChatBubble(playerName, message) {
    // Store message with expiry time (5 seconds from now)
    activeChatMessages[playerName] = {
        message: message,
        expiresAt: Date.now() + 5000
    };
    
    // Clear any existing timeout for this player
    if (chatBubbleTimeouts[playerName]) {
        clearTimeout(chatBubbleTimeouts[playerName]);
    }
    
    // Re-render player hub to show the bubble
    if (window.gameState && window.gameState.players) {
        renderPlayerHub(window.gameState.players);
    }
    
    // Set timeout to hide after 5 seconds
    chatBubbleTimeouts[playerName] = setTimeout(() => {
        delete activeChatMessages[playerName];
        delete chatBubbleTimeouts[playerName];
        
        // Re-render to remove the bubble
        if (window.gameState && window.gameState.players) {
            renderPlayerHub(window.gameState.players);
        }
    }, 5000);
}

// ========== AI View Functions ==========
async function loadAIData() {
    try {
        const response = await fetch('http://localhost:5001/api/current');
        if (!response.ok) {
            throw new Error('No active session');
        }
        
        aiSessionData = await response.json();
        updateAIUI();
        
        // Check for new data
        if (lastAIUpdate && aiSessionData.requests?.length > lastAIUpdate) {
            showAINewBadge();
        }
        lastAIUpdate = aiSessionData.requests?.length || 0;
        
    } catch (error) {
        console.log('AI data not available:', error.message);
        showAIEmptyState('No active AI session', 'Start a game with AI agents to see data');
    }
}

function updateAIUI() {
    if (!aiSessionData) return;
    
    // Update session info
    const sessionInfo = document.getElementById('session-info');
    if (sessionInfo) {
        sessionInfo.innerHTML = `
            <strong>${aiSessionData.session_name}</strong><br>
            Players: ${Object.keys(aiSessionData.players || {}).length}<br>
            Requests: ${aiSessionData.requests?.length || 0}
        `;
    }
    
    // Update player nav
    const playersNav = document.getElementById('ai-players-nav');
    if (playersNav && aiSessionData.players) {
        playersNav.innerHTML = Object.keys(aiSessionData.players).sort().map(player => `
            <div class="nav-item ${currentAIPlayer === player ? 'active' : ''}" onclick="showAIPlayer('${player}')">
                <span class="nav-icon">🤖</span>
                <span>${player}</span>
            </div>
        `).join('');
    }
    
    // Update counts
    document.getElementById('chat-count').textContent = aiSessionData.chat?.length || 0;
    document.getElementById('requests-count').textContent = aiSessionData.requests?.length || 0;
    
    // Show default view if none selected
    if (!currentAIView && Object.keys(aiSessionData.players || {}).length > 0) {
        showAIPlayer(Object.keys(aiSessionData.players).sort()[0]);
    }
}

function showAIPlayer(player) {
    currentAIView = 'player';
    currentAIPlayer = player;
    updateAINavActive();
    
    const playerData = aiSessionData?.players?.[player];
    if (!playerData) return;
    
    document.getElementById('ai-content-title').textContent = `${player} - AI Log`;
    
    // Get requests for this player
    const playerRequests = (aiSessionData.requests || []).filter(r => r.player_name === player);
    
    if (playerRequests.length === 0) {
        document.getElementById('ai-content-body').innerHTML = `
            <div class="ai-player-log">
                ${renderMarkdown(playerData.content)}
            </div>
        `;
        return;
    }
    
    // Show requests in accordion format for this player
    const requestsHTML = playerRequests.slice().reverse().map((req, index) => generateRequestCard(req, index)).join('');
    
    document.getElementById('ai-content-body').innerHTML = `
        <div class="player-requests-header">
            <h3>📊 ${playerRequests.length} Request${playerRequests.length > 1 ? 's' : ''}</h3>
        </div>
        <div class="request-list">
            ${requestsHTML}
        </div>
    `;
    
    // Restore expanded state
    expandedRequests.forEach(id => {
        const card = document.getElementById(id);
        if (card) card.classList.add('expanded');
    });
}

function showAIView(view) {
    currentAIView = view;
    currentAIPlayer = null;
    updateAINavActive();
    
    switch (view) {
        case 'chat':
            showAIChat();
            break;
        case 'memories':
            showAIMemories();
            break;
        case 'requests':
            showAIRequests();
            break;
    }
}

function showAIChat() {
    document.getElementById('ai-content-title').textContent = 'Chat History';
    
    if (!aiSessionData?.chat?.length) {
        document.getElementById('ai-content-body').innerHTML = `
            <div class="empty-state">
                <div class="empty-icon">💬</div>
                <h3>No messages yet</h3>
                <p>Chat messages will appear here when players communicate</p>
            </div>
        `;
        return;
    }
    
    const chatHTML = aiSessionData.chat.map(msg => {
        const playerName = msg.player || msg.player_name || 'Unknown';
        const messageNum = msg.msg || msg.message_number || '?';
        const messageText = msg.message || msg.text || msg.content || '';
        const timestamp = msg.timestamp ? formatTimestamp(msg.timestamp) : '';
        
        return `
            <div class="chat-message-card">
                <div class="chat-message-header">
                    <div class="chat-player-name">${playerName.toUpperCase()}</div>
                    <div class="chat-message-meta">
                        <span>#${messageNum}</span>
                        ${timestamp ? `<span>🕐 ${timestamp}</span>` : ''}
                    </div>
                </div>
                <div class="chat-message-bubble">
                    "${escapeHtml(messageText)}"
                </div>
            </div>
        `;
    }).join('');
    
    document.getElementById('ai-content-body').innerHTML = `
        <div class="chat-history-container">${chatHTML}</div>
    `;
}

function showAIMemories() {
    document.getElementById('ai-content-title').textContent = 'Agent Memories';
    
    if (!aiSessionData?.memories || Object.keys(aiSessionData.memories).length === 0) {
        document.getElementById('ai-content-body').innerHTML = `
            <div class="empty-state">
                <div class="empty-icon">📝</div>
                <h3>No memories stored</h3>
                <p>AI agents haven't saved any notes yet</p>
            </div>
        `;
        return;
    }
    
    const memoriesHTML = Object.entries(aiSessionData.memories).map(([player, memory]) => `
        <div class="memory-card">
            <div class="memory-player">${player.toUpperCase()}</div>
            <div class="memory-text">"${escapeHtml(memory)}"</div>
        </div>
    `).join('');
    
    document.getElementById('ai-content-body').innerHTML = memoriesHTML;
}

// Track expanded state for requests
const expandedRequests = new Set();

function showAIRequests(filter = 'all') {
    document.getElementById('ai-content-title').textContent = 'All Requests';
    
    if (!aiSessionData?.requests?.length) {
        document.getElementById('ai-content-body').innerHTML = `
            <div class="empty-state">
                <div class="empty-icon">📡</div>
                <h3>No requests yet</h3>
                <p>AI requests will appear here during the game</p>
            </div>
        `;
        return;
    }
    
    // Filter requests
    let requests = aiSessionData.requests.slice();
    if (filter === 'new') {
        requests = requests.filter(r => r.is_new);
    } else if (filter === 'has_action') {
        requests = requests.filter(r => r.response && (r.response.action || r.response.action_type));
    }
    
    // Calculate stats
    const stats = calculateRequestStats(requests);
    
    // Stats grid HTML
    const statsHTML = `
        <div class="stats-grid-ai">
            <div class="stat-card-ai">
                <div class="stat-value-ai">${stats.total}</div>
                <div class="stat-label-ai">Total Requests</div>
            </div>
            <div class="stat-card-ai">
                <div class="stat-value-ai new">${stats.newCount}</div>
                <div class="stat-label-ai">New</div>
            </div>
            <div class="stat-card-ai">
                <div class="stat-value-ai">${stats.totalTokens.toLocaleString()}</div>
                <div class="stat-label-ai">Total Tokens</div>
            </div>
            <div class="stat-card-ai">
                <div class="stat-value-ai cost">$${stats.totalCost.toFixed(4)}</div>
                <div class="stat-label-ai">💰 Cost</div>
            </div>
        </div>
    `;
    
    // Filter bar HTML
    const filterHTML = `
        <div class="filter-bar">
            <button class="filter-btn ${filter === 'all' ? 'active' : ''}" onclick="showAIRequests('all')">All</button>
            <button class="filter-btn ${filter === 'new' ? 'active' : ''}" onclick="showAIRequests('new')">New Only</button>
            <button class="filter-btn ${filter === 'has_action' ? 'active' : ''}" onclick="showAIRequests('has_action')">Has Action</button>
        </div>
    `;
    
    // Requests HTML (newest first)
    const requestsHTML = requests.slice().reverse().map((req, index) => generateRequestCard(req, index)).join('');
    
    document.getElementById('ai-content-body').innerHTML = `
        ${statsHTML}
        ${filterHTML}
        <div class="request-list">${requestsHTML}</div>
    `;
    
    // Restore expanded state
    expandedRequests.forEach(id => {
        const card = document.getElementById(id);
        if (card) card.classList.add('expanded');
    });
}

function calculateRequestStats(requests) {
    const stats = {
        total: requests.length,
        newCount: 0,
        totalTokens: 0,
        totalCost: 0
    };
    
    requests.forEach(req => {
        if (req.is_new) stats.newCount++;
        if (req.tokens) {
            const total = req.tokens.total || (req.tokens.input || 0) + (req.tokens.output || 0);
            stats.totalTokens += total;
        }
        if (req.cost) {
            stats.totalCost += parseFloat(req.cost) || 0;
        }
    });
    
    return stats;
}

function generateRequestCard(req, index) {
    const requestId = `req_${req.player_name}_${req.request_number || index}`;
    const response = req.response || {};
    const thinking = response.internal_thinking || '';
    const note = response.note_to_self || '';
    const chat = response.say_outloud || '';
    const actionType = response.action_type || (response.action ? response.action.type : null);
    const actionParams = response.parameters || (response.action ? response.action.parameters : null);
    
    // Content icons for header
    const icons = [];
    if (thinking) icons.push('<span title="Has Thinking">💭</span>');
    if (note) icons.push('<span title="Has Note">📝</span>');
    if (chat) icons.push('<span title="Says Out Loud">💬</span>');
    if (actionType) icons.push('<span title="Has Action">🎮</span>');
    const iconsHTML = icons.length ? `<span class="content-icons">${icons.join('')}</span>` : '';
    
    // Trigger text
    const trigger = req.prompt?.task_context?.what_just_happened || 'AI Decision Request';
    const tokens = req.tokens || {};
    const tokenCount = tokens.total || (tokens.input || 0) + (tokens.output || 0);
    
    return `
        <div class="request-card ${req.is_new ? 'new' : ''}" id="${requestId}">
            <div class="request-header" onclick="toggleRequest('${requestId}')">
                <div class="request-num">#${req.request_number || index + 1}</div>
                <div class="request-summary">
                    <div class="request-trigger">
                        ${req.is_new ? '<span class="badge new">NEW</span>' : ''}
                        <strong>${(req.player_name || 'Unknown').toUpperCase()}:</strong> 
                        ${escapeHtml(trigger.substring(0, 80))}${trigger.length > 80 ? '...' : ''}
                        ${iconsHTML}
                    </div>
                    <div class="request-meta">
                        <span>🔢 ${tokenCount} tokens</span>
                        <span>${req.success !== false ? '✅' : '❌'}</span>
                        <span>📅 ${formatTimestamp(req.timestamp)}</span>
                    </div>
                </div>
                <div class="request-expand-icon">▶</div>
            </div>
            <div class="request-body">
                ${thinking ? `
                    <div class="request-section">
                        <h4>💭 Internal Thinking</h4>
                        <div class="thinking-box">${escapeHtml(thinking)}</div>
                    </div>
                ` : ''}
                
                ${note ? `
                    <div class="request-section">
                        <h4>📝 Note to Self</h4>
                        <div class="note-box">${escapeHtml(note)}</div>
                    </div>
                ` : ''}
                
                ${chat ? `
                    <div class="request-section">
                        <h4>💬 Says Out Loud</h4>
                        <div class="chat-box-ai">"${escapeHtml(chat)}"</div>
                    </div>
                ` : ''}
                
                ${actionType ? `
                    <div class="request-section">
                        <h4>🎮 Action</h4>
                        <div class="action-box">
                            <div class="action-type">${actionType}</div>
                            ${actionParams ? `<div class="action-params">Parameters: ${JSON.stringify(actionParams)}</div>` : ''}
                        </div>
                    </div>
                ` : ''}
                
                ${generateToolIterationsSection(req)}
                
                ${tokenCount ? `
                    <div class="request-section">
                        <h4>📊 Token Usage</h4>
                        <div class="token-info">
                            Total: ${tokenCount} | Prompt: ${tokens.prompt || tokens.input || 'N/A'} | Completion: ${tokens.completion || tokens.output || 'N/A'}
                        </div>
                    </div>
                ` : ''}
                
                <div class="request-section">
                    <details>
                        <summary>📤 Original Prompt</summary>
                        <pre><code>${escapeHtml(JSON.stringify(req.prompt, null, 2))}</code></pre>
                    </details>
                </div>
                
                ${req.raw_response ? `
                    <div class="request-section">
                        <details>
                            <summary style="color: #f48771;">🔴 Raw Response</summary>
                            <pre><code>${escapeHtml(req.raw_response)}</code></pre>
                        </details>
                    </div>
                ` : ''}
            </div>
        </div>
    `;
}

function toggleRequest(requestId) {
    const card = document.getElementById(requestId);
    if (!card) return;
    
    card.classList.toggle('expanded');
    
    if (card.classList.contains('expanded')) {
        expandedRequests.add(requestId);
    } else {
        expandedRequests.delete(requestId);
    }
}

function formatTimestamp(ts) {
    if (!ts) return '';
    try {
        return new Date(ts).toLocaleTimeString();
    } catch {
        return ts;
    }
}

// ========== Tool Iterations ==========
function generateToolIterationsSection(req) {
    const iterations = req.tool_iterations || [];
    if (iterations.length === 0) {
        return '';
    }
    
    const iterationsHTML = iterations.map(iter => {
        const toolCalls = parseToolResults(iter.tool_results);
        
        const toolCallsHTML = toolCalls.map(tool => `
            <div class="tool-call">
                <div class="tool-call-header">
                    <span class="tool-call-name">🔧 ${escapeHtml(tool.name)}</span>
                </div>
                ${tool.parameters ? `
                    <div class="tool-section">
                        <div class="tool-section-label">📥 Input:</div>
                        <pre class="tool-params-pre">${escapeHtml(tool.parameters)}</pre>
                    </div>
                ` : ''}
                ${tool.reasoning ? `
                    <div class="tool-reasoning">
                        💭 ${escapeHtml(tool.reasoning)}
                    </div>
                ` : ''}
                <div class="tool-section">
                    <details>
                        <summary class="tool-result-summary">📤 Output (${tool.resultPreview})</summary>
                        <pre class="tool-result-pre">${escapeHtml(tool.result)}</pre>
                    </details>
                </div>
            </div>
        `).join('');
        
        return `
            <div class="tool-iteration">
                <div class="tool-iteration-header" onclick="toggleToolIteration(this)">
                    <span>🔄 Iteration ${iter.iteration}</span>
                    <span class="tool-iteration-meta">${iter.timestamp ? formatTimestamp(iter.timestamp) : ''}</span>
                    <span class="tool-expand-icon">▶</span>
                </div>
                <div class="tool-iteration-body">
                    ${toolCallsHTML}
                </div>
            </div>
        `;
    }).join('');
    
    return `
        <div class="request-section">
            <h4>🛠️ Tool Calls (${iterations.length} iteration${iterations.length > 1 ? 's' : ''})</h4>
            <div class="tools-section">
                ${iterationsHTML}
            </div>
        </div>
    `;
}

function parseToolResults(toolResultsStr) {
    const tools = [];
    if (!toolResultsStr) return tools;
    
    // Split by "Tool: " to get each tool call
    const parts = toolResultsStr.split(/Tool:\s+/);
    
    for (let i = 1; i < parts.length; i++) {
        const part = parts[i];
        
        // Extract tool name (first line)
        const lines = part.split('\n');
        const name = lines[0].trim();
        
        // Extract parameters JSON
        let parameters = '';
        const paramsMatch = part.match(/Parameters:\s*(\{[\s\S]*?\})\s*(?=Result:|$)/);
        if (paramsMatch) {
            try {
                const parsed = JSON.parse(paramsMatch[1]);
                const displayParams = {...parsed};
                delete displayParams.reasoning;
                parameters = JSON.stringify(displayParams, null, 2);
            } catch (e) {
                parameters = paramsMatch[1].trim();
            }
        }
        
        // Extract reasoning
        let reasoning = '';
        const reasoningMatch = part.match(/"(?:reasoning|llm_reasoning)":\s*"([^"]+)"/);
        if (reasoningMatch) {
            reasoning = reasoningMatch[1];
        }
        
        // Extract result
        const resultMatch = part.match(/Result:\s*([\s\S]*?)(?=---|\Z|$)/);
        let result = resultMatch ? resultMatch[1].trim() : '';
        
        // Create preview
        let resultPreview = 'click to expand';
        try {
            const parsed = JSON.parse(result);
            if (parsed.total_found !== undefined) {
                resultPreview = `${parsed.total_found} items found`;
            } else if (parsed.node_id !== undefined) {
                resultPreview = `Node ${parsed.node_id}`;
            } else if (typeof parsed === 'object') {
                resultPreview = `${Object.keys(parsed).length} fields`;
            }
        } catch (e) {
            if (result.length > 50) {
                resultPreview = result.substring(0, 50) + '...';
            } else {
                resultPreview = result || 'empty';
            }
        }
        
        tools.push({ name, parameters, reasoning, result, resultPreview });
    }
    
    return tools;
}

function toggleToolIteration(header) {
    const iteration = header.closest('.tool-iteration');
    if (iteration) {
        iteration.classList.toggle('expanded');
    }
}

function updateAINavActive() {
    // Reset all
    document.querySelectorAll('.ai-sidebar .nav-item').forEach(item => {
        item.classList.remove('active');
    });
    
    // Set active based on current view
    if (currentAIPlayer) {
        document.querySelectorAll('#ai-players-nav .nav-item').forEach(item => {
            if (item.textContent.includes(currentAIPlayer)) {
                item.classList.add('active');
            }
        });
    }
}

function showAIEmptyState(title, message) {
    document.getElementById('ai-content-title').textContent = 'AI Analysis';
    document.getElementById('ai-content-body').innerHTML = `
        <div class="empty-state">
            <div class="empty-icon">🤖</div>
            <h3>${title}</h3>
            <p>${message}</p>
        </div>
    `;
}

function showAINewBadge() {
    const badge = document.getElementById('ai-new-badge');
    if (badge) {
        badge.style.display = 'inline';
        // Hide after 5 seconds
        setTimeout(() => {
            badge.style.display = 'none';
        }, 5000);
    }
}

// ========== Markdown Rendering ==========
function renderMarkdown(text) {
    if (!text) return '';
    
    let html = escapeHtml(text);
    
    // Code blocks
    html = html.replace(/```(\w*)\n([\s\S]*?)```/g, '<pre><code>$2</code></pre>');
    
    // Headers
    html = html.replace(/^### (.+)$/gm, '<h3>$1</h3>');
    html = html.replace(/^## (.+)$/gm, '<h2>$1</h2>');
    html = html.replace(/^# (.+)$/gm, '<h1>$1</h1>');
    
    // Horizontal rules
    html = html.replace(/^---+$/gm, '<hr>');
    
    // Bold and italic
    html = html.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');
    html = html.replace(/\*(.+?)\*/g, '<em>$1</em>');
    
    // Inline code
    html = html.replace(/`([^`]+)`/g, '<code>$1</code>');
    
    // Details/Summary
    html = html.replace(/&lt;details&gt;/g, '<details>');
    html = html.replace(/&lt;\/details&gt;/g, '</details>');
    html = html.replace(/&lt;summary&gt;(.+?)&lt;\/summary&gt;/g, '<summary>$1</summary>');
    
    // Paragraphs
    html = html.replace(/\n\n/g, '</p><p>');
    html = '<p>' + html + '</p>';
    
    // Clean up
    html = html.replace(/<p><\/p>/g, '');
    html = html.replace(/<p>\s*<(h[123]|hr|pre|details)/g, '<$1');
    html = html.replace(/<\/(h[123]|hr|pre|details)>\s*<\/p>/g, '</$1>');
    
    return html;
}

// ========== Utility Functions ==========
function escapeHtml(text) {
    if (!text) return '';
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// ========== Integration with Game Data ==========
// Override the game state update to also update player hub
const originalUpdateGameInfo = typeof updateGameInfo === 'function' ? updateGameInfo : null;

function enhancedUpdateGameInfo(data) {
    // Call original if exists
    if (originalUpdateGameInfo) {
        originalUpdateGameInfo(data);
    }
    
    // Update player hub
    if (data && data.players) {
        renderPlayerHub(data.players);
    }
}

// Hook into game state updates
document.addEventListener('DOMContentLoaded', function() {
    // Set up periodic AI data refresh when on AI view
    setInterval(() => {
        if (currentView === 'ai') {
            loadAIData();
        }
    }, 2000);
    
    // Initial AI data load
    setTimeout(loadAIData, 1000);
});

// ========== Game Details Panel ==========
function updateGameDetails(data) {
    const detailsPanel = document.getElementById('game-details');
    if (!detailsPanel || !data) return;
    
    detailsPanel.innerHTML = `
        <div class="detail-section">
            <h4>🎲 Current Turn</h4>
            <p>Player: <strong>${data.current_player_name || 'N/A'}</strong></p>
            <p>Turn: <strong>${data.turn_number || 0}</strong></p>
            <p>Phase: <strong>${data.current_phase || 'N/A'}</strong></p>
        </div>
        <div class="detail-section">
            <h4>🎯 Last Dice Roll</h4>
            <p>${data.dice_result ? `${data.dice_result[0]} + ${data.dice_result[1]} = ${data.dice_result[0] + data.dice_result[1]}` : 'No roll yet'}</p>
        </div>
        <div class="detail-section">
            <h4>🏴‍☠️ Robber</h4>
            <p>Position: Hex ${data.robber_position || 'N/A'}</p>
        </div>
    `;
}

function updateGameStats(data) {
    const statsPanel = document.getElementById('game-stats');
    if (!statsPanel || !data?.players) return;
    
    const stats = data.players.map((p, i) => ({
        name: p.name,
        vp: p.victory_points || 0,
        resources: Object.values(p.resources || {}).reduce((a, b) => a + b, 0),
        devCards: Object.values(p.development_cards || {}).reduce((a, b) => a + b, 0),
        settlements: p.settlements_left !== undefined ? (5 - p.settlements_left) : 0,
        cities: p.cities_left !== undefined ? (4 - p.cities_left) : 0,
        roads: p.roads_left !== undefined ? (15 - p.roads_left) : 0
    }));
    
    statsPanel.innerHTML = `
        <table class="stats-table">
            <thead>
                <tr>
                    <th>Player</th>
                    <th>VP</th>
                    <th>Resources</th>
                    <th>Dev Cards</th>
                    <th>Buildings</th>
                </tr>
            </thead>
            <tbody>
                ${stats.map(s => `
                    <tr>
                        <td><strong>${s.name}</strong></td>
                        <td>${s.vp}</td>
                        <td>${s.resources}</td>
                        <td>${s.devCards}</td>
                        <td>${s.settlements}S/${s.cities}C/${s.roads}R</td>
                    </tr>
                `).join('')}
            </tbody>
        </table>
    `;
}

// Export for main.js integration
window.unifiedUI = {
    renderPlayerHub,
    updateGameDetails,
    updateGameStats,
    switchView,
    loadAIData
};

// Export chat bubble function globally
window.showPlayerChatBubble = showPlayerChatBubble;
