// Main file - Game initialization
let catanBoard;
let gameState = null;
let eventSource = null;
let pointMapping = null; // Point mapping - will be loaded from server
let playerNames = {}; // Store player names from game

// Global functions for control buttons
function zoomIn() {
    if (catanBoard) {
        catanBoard.zoomIn();
    }
}

function zoomOut() {
    if (catanBoard) {
        catanBoard.zoomOut();
    }
}

function resetZoom() {
    if (catanBoard) {
        catanBoard.resetZoom();
    }
}

function toggleVertices() {
    if (catanBoard) {
        catanBoard.toggleVertices();
    }
}

// Toggle building costs modal
function toggleBuildingCosts() {
    const modal = document.getElementById('buildingCostsModal');
    if (modal) {
        modal.classList.toggle('hidden');
    }
}

// Clear action log
function clearActionLog() {
    const logDiv = document.getElementById('action-log');
    if (logDiv) {
        logDiv.innerHTML = '<div class="info">Log cleared ✓</div>';
    }
}

// טעינת מיפוי נקודות מהשרת
function loadPointMapping() {
    return fetch('/api/point_mapping')
        .then(response => response.json())
        .then(data => {
            pointMapping = data;
            // console.log('🗺️ Point mapping loaded:', `${data.total_points} points`);
            // console.log('   Example: point 1 at', data.point_to_coords[1]);
            
            // Make mapping global so board.js can access it
            window.pointMapping = pointMapping;
            
            return pointMapping;
        })
        .catch(error => {
            console.error('❌ Error loading point mapping:', error);
            // fallback - create basic mapping
            pointMapping = {
                point_to_coords: {},
                coords_to_point: {},
                total_points: 54,
                all_points: Array.from({length: 54}, (_, i) => i + 1)
            };
            return pointMapping;
        });
}

// חיבור ל-Flask server
function connectToServer() {
    console.log('🔗 Connecting to server...');
    
    // First load point mapping
    loadPointMapping().then(() => {
        console.log('✓ Point mapping loaded');
        
        // Now load game state
        return Promise.all([
            fetch('/api/game-state', {timeout: 5000}),
            fetch('/api/actions')
        ]);
    })
    .then(responses => {
        return Promise.all(responses.map(r => {
            if (!r.ok) throw new Error(`Server responded with ${r.status}`);
            return r.json();
        }));
    })
    .then(([gameStateData, actionsData]) => {
        console.log('📥 Game state received from server:', gameStateData);
        
        // Check if state is empty (no hexes)
        if (!gameStateData.hexes || gameStateData.hexes.length === 0) {
            console.log('⚠️ Server state is empty, using GAMEDATA as fallback');
            updateGameState(GAMEDATA);
        } else {
            updateGameState(gameStateData);
        }
        
        // Store player names for later use
        if (gameStateData.players) {
            gameStateData.players.forEach((player, index) => {
                playerNames[index] = player.name || `Player ${index + 1}`;
            });
        }
        
        // Load action history
        if (actionsData && Array.isArray(actionsData)) {
            console.log(`📥 Loaded ${actionsData.length} previous actions`);
            actionsData.forEach(action => logAction(action));
        }
        
        console.log('✓ Server connection established successfully');
        
        // Connect to real-time updates
        connectToSSE();
    })
    .catch(error => {
        console.error('❌ Error connecting to server:', error);
        console.log('🔄 Using GAMEDATA as fallback');
        updateGameState(GAMEDATA);
    });
}

// Connect to Server-Sent Events for real-time updates
function connectToSSE() {
    try {
        eventSource = new EventSource('/api/events');
            
            eventSource.onmessage = function(event) {
                const data = JSON.parse(event.data);
                // console.log('📡 Update from server:', data);
                
                if (data.type === 'game_update' || data.type === 'state_updated') {
                    // Update player names if we get new player data
                    if (data.payload.players) {
                        data.payload.players.forEach((player, index) => {
                            playerNames[index] = player.name || `Player ${index + 1}`;
                        });
                    }
                    updateGameState(data.payload);
                } else if (data.type === 'action_executed') {
                    logAction(data.payload);
                    // Refresh game state to show any changes
                    refreshGameState();
                } else if (data.type === 'dice_roll') {
                    logEvent(data.payload, 'log-dice');
                } else if (data.type === 'resource_distribution') {
                    logResourceDistribution(data.payload);
                    // Refresh game state to show updated resources
                    refreshGameState();
                } else if (data.type === 'turn_start') {
                    logEvent(data.payload, 'log-turn');
                } else if (data.type === 'message') {
                    logEvent(data.payload, 'info');
                } else if (data.type === 'error') {
                    logEvent(data.payload, 'error');
                } else if (data.type === 'player_chat') {
                    // Handle player chat message (say_outloud)
                    handlePlayerChat(data.payload);
                } else if (data.type === 'ai_status') {
                    // Handle AI thinking status update
                    handleAIStatus(data.payload);
                }
            };
            
            eventSource.onerror = function(error) {
                console.error('❌ Error in SSE connection:', error);
            };
            
        console.log('✅ Connected to real-time updates');
    } catch (error) {
        console.warn('⚠️ Unable to connect to SSE:', error);
    }
}

// Refresh game state from server
async function refreshGameState() {
    try {
        const response = await fetch('/api/game-state');
        if (response.ok) {
            const newState = await response.json();
            updateGameState(newState);
        }
    } catch (error) {
        console.warn('Failed to refresh game state:', error);
    }
}

// Update game state
function updateGameState(newState) {
    gameState = newState;
    window.gameState = gameState; // Make globally accessible for unified UI
    
    if (catanBoard) {
        catanBoard.updateFromGameState(gameState);
        
        // Update vertex IDs if we have mapping
        if (pointMapping) {
            catanBoard.updateVertexIDsFromMapping();
        }
    }
    
    updateGameInfo(gameState);
}

// Update player information display
function updateGameInfo(state) {
    const gameInfoDiv = document.getElementById('game-info');
    if (!gameInfoDiv) return;
    
    // Preserve expanded state
    const expandedPlayers = new Set();
    document.querySelectorAll('.player-info.expanded').forEach(el => {
        expandedPlayers.add(el.dataset.playerId);
    });
    
    let html = '<h3>📋 Game Info</h3>';
    
    if (state.players) {
        state.players.forEach((player, index) => {
            const activeClass = state.current_player === index ? 'active' : '';
            const isExpanded = expandedPlayers.has(String(index)) ? 'expanded' : '';
            const playerColors = ['#FF4444', '#4444FF', '#44FF44', '#FFAA00'];
            const playerColor = playerColors[index % 4];
            
            // Get player name from stored names or use default
            const playerName = playerNames[index] || player.name || `Player ${index + 1}`;
            
            // Format cards lists
            let cardsHtml = '';
            if (player.cards_list && player.cards_list.length > 0) {
                // Count cards by type
                const cardCounts = {};
                player.cards_list.forEach(card => {
                    cardCounts[card] = (cardCounts[card] || 0) + 1;
                });
                
                cardsHtml += '<div><strong>Resources:</strong><ul class="card-list">';
                for (const [card, count] of Object.entries(cardCounts)) {
                    cardsHtml += `<li>${card}: ${count}</li>`;
                }
                cardsHtml += '</ul></div>';
            } else {
                cardsHtml += '<div><em>No resource cards</em></div>';
            }
            
            let devCardsHtml = '';
            if (player.dev_cards_list && player.dev_cards_list.length > 0) {
                // Count dev cards by type
                const devCardCounts = {};
                player.dev_cards_list.forEach(card => {
                    devCardCounts[card] = (devCardCounts[card] || 0) + 1;
                });
                
                devCardsHtml += '<div style="margin-top:5px;"><strong>Development:</strong><ul class="card-list">';
                for (const [card, count] of Object.entries(devCardCounts)) {
                    devCardsHtml += `<li>${card}: ${count}</li>`;
                }
                devCardsHtml += '</ul></div>';
            }
            
            html += `
                <div class="player-info ${activeClass} ${isExpanded}" data-player-id="${index}" onclick="togglePlayerInfo(this)" style="border-left-color: ${playerColor};">
                    <h4>👤 ${playerName}</h4>
                    <div class="player-resources">
                        <strong>🏆 VP:</strong> ${player.victory_points || 0} | 
                        <strong>🎴 Cards:</strong> ${player.total_cards || 0}
                    </div>
                    <div class="player-resources">
                        <strong>🏘️:</strong> ${player.settlements || 0} |
                        <strong>🏛️:</strong> ${player.cities || 0} |
                        <strong>🛣️:</strong> ${player.roads || 0}
                    </div>
                    <div class="player-cards">
                        ${cardsHtml}
                        ${devCardsHtml}
                    </div>
                </div>
            `;
        });
    }
    
    if (state.current_phase) {
        html += `<div style="margin-top: 10px; padding: 10px; background: rgba(52, 152, 219, 0.1); border-radius: 6px;"><strong>📍 Current Phase:</strong> ${state.current_phase}</div>`;
    }
    
    gameInfoDiv.innerHTML = html;
    
    // Update unified UI if available (for unified view)
    if (window.unifiedUI) {
        window.unifiedUI.renderPlayerHub(state.players);
        window.unifiedUI.updateGameDetails(state);
        window.unifiedUI.updateGameStats(state);
    }
}

// Toggle player info visibility
window.togglePlayerInfo = function(element) {
    element.classList.toggle('expanded');
}

// Log action
function logAction(actionData) {
    const logDiv = document.getElementById('action-log');
    if (!logDiv) return;
    
    const actionElement = document.createElement('div');
    
    // Determine class based on action type if needed, or just success/error
    let className = actionData.success ? 'success' : 'error';
    let prefix = actionData.success ? '✓' : '✗';
    
    // Add specific classes for certain actions
    if (actionData.success) {
        if (actionData.action_type && actionData.action_type.includes('BUILD')) {
            className = 'log-build';
            prefix = '🔨';
        }
    }
    
    actionElement.className = className;
    const timestamp = actionData.timestamp || new Date().toLocaleTimeString('en-GB', { hour12: false });
    actionElement.textContent = `${prefix} ${actionData.message}`;
    
    appendToLog(logDiv, actionElement);
}

// Log generic event
function logEvent(data, className) {
    const logDiv = document.getElementById('action-log');
    if (!logDiv) return;
    
    const element = document.createElement('div');
    element.className = className;
    
    const timestamp = data.timestamp || new Date().toLocaleTimeString('en-GB', { hour12: false });
    
    // Add emoji prefix based on type
    let prefix = '';
    if (className === 'log-dice') prefix = '🎲';
    else if (className === 'log-turn') prefix = '➤';
    else if (className === 'info') prefix = 'ℹ️';
    else if (className === 'error') prefix = '⚠️';
    
    element.textContent = `${prefix} ${data.message}`;
    
    appendToLog(logDiv, element);
}

// Log resource distribution specifically
function logResourceDistribution(data) {
    const logDiv = document.getElementById('action-log');
    if (!logDiv) return;
    
    const timestamp = data.timestamp || new Date().toLocaleTimeString('en-GB', { hour12: false });
    
    // If we have detailed distributions, log them
    if (data.distributions) {
        for (const [player, resources] of Object.entries(data.distributions)) {
            if (resources && resources.length > 0) {
                const element = document.createElement('div');
                element.className = 'log-resource';
                
                // Count resources
                const counts = {};
                resources.forEach(r => counts[r] = (counts[r] || 0) + 1);
                
                const resourceStr = Object.entries(counts)
                    .map(([res, count]) => `${count}×${res}`)
                    .join(' ');
                
                element.textContent = `📦 ${player}: ${resourceStr}`;
                appendToLog(logDiv, element);
            }
        }
    } else {
        // Fallback to generic message
        const element = document.createElement('div');
        element.className = 'log-resource';
        element.textContent = `📦 ${data.message}`;
        appendToLog(logDiv, element);
    }
}

// Handle player chat message (say_outloud)
function handlePlayerChat(data) {
    const playerName = data.player_name;
    const message = data.message;
    const timestamp = new Date().toLocaleTimeString();
    
    // Store chat message for player
    if (!window.playerChatMessages) {
        window.playerChatMessages = {};
    }
    window.playerChatMessages[playerName] = message;
    
    // Add to chat log panel only (not action log)
    const chatLog = document.getElementById('chat-log');
    if (chatLog) {
        // Remove "no messages" placeholder if exists
        const placeholder = chatLog.querySelector('.info');
        if (placeholder) {
            placeholder.remove();
        }
        
        const chatElement = document.createElement('div');
        chatElement.className = 'chat-log-message';
        chatElement.innerHTML = `
            <div class="chat-log-header">
                <span class="chat-log-player">🤖 ${playerName}</span>
                <span class="chat-log-time">${timestamp}</span>
            </div>
            <div class="chat-log-text">"${message}"</div>
        `;
        chatLog.appendChild(chatElement);
        chatLog.scrollTop = chatLog.scrollHeight;
        
        // Keep only last 50 messages
        while (chatLog.children.length > 50) {
            chatLog.removeChild(chatLog.firstChild);
        }
    }
    
    // Update unified UI if available - show chat bubble
    if (window.showPlayerChatBubble) {
        window.showPlayerChatBubble(playerName, message);
    }
}

// Track current active player for thinking log
let currentThinkingPlayer = null;

// Handle AI thinking status update
function handleAIStatus(data) {
    const playerName = data.player_name;
    const status = data.status; // 'thinking', 'tool_call', 'processing', 'done'
    const details = data.details || '';
    
    console.log(`[AI_STATUS] ${playerName}: ${status} - ${details.substring(0, 30)}...`);
    
    // Find the thinking log element for this player
    const logElement = document.getElementById(`thinking-log-${playerName}`);
    if (!logElement) {
        console.warn(`[AI_STATUS] Could not find thinking-log-${playerName}`);
        return;
    }
    
    if (status === 'done' || status === 'idle') {
        // Don't hide immediately - let the reasoning stay visible
        // It will be cleared when a different player starts thinking
        return;
    } else if (status === 'thinking') {
        // Check if this is a NEW player starting to think
        if (currentThinkingPlayer !== playerName) {
            // Different player - clear ALL player logs first
            document.querySelectorAll('.player-thinking-log').forEach(log => {
                log.innerHTML = '';
                log.style.display = 'none';
            });
            currentThinkingPlayer = playerName;
        }
        // Don't clear - just show and add to the log
        logElement.style.display = 'block';
    } else {
        // Show the log container for other statuses
        logElement.style.display = 'block';
    }
    
    // Create status entry
    const entry = document.createElement('div');
    entry.className = `thinking-entry thinking-${status}`;
    
    let icon = '';
    let text = '';
    
    if (status === 'thinking') {
        icon = '💭';
        text = details || 'Thinking...';
    } else if (status === 'tool_call') {
        icon = '🔧';
        // Handle multiline tool calls (reasoning on separate line)
        text = (details || 'Using tools...').replace(/\n/g, '<br>');
    } else if (status === 'processing') {
        icon = '⚙️';
        text = details || 'Processing...';
    } else if (status === 'reasoning') {
        icon = '💡';
        text = details;
    } else {
        icon = '•';
        text = details || status;
    }
    
    entry.innerHTML = `<span class="thinking-icon">${icon}</span><span class="thinking-text">${text}</span>`;
    logElement.appendChild(entry);
    
    // Scroll to show latest
    logElement.scrollTop = logElement.scrollHeight;
    
    // Keep only last 15 entries to show full chain
    while (logElement.children.length > 15) {
        logElement.removeChild(logElement.firstChild);
    }
}

// Helper to append to log and scroll
function appendToLog(container, element) {
    container.appendChild(element);
    
    // Keep only last 100 items
    while (container.children.length > 100) {
        container.removeChild(container.firstChild);
    }
    
    // Scroll to bottom
    container.scrollTop = container.scrollHeight;
}

// Game initialization
document.addEventListener('DOMContentLoaded', async function() {
    console.log('🎲 Starting Catan board with server connection...');
    
    try {
        // Create board instance (async)
        catanBoard = new CatanBoard();
        window.catanBoard = catanBoard; // Expose to window for console access
        
        // Wait for board initialization
        if (catanBoard.init && typeof catanBoard.init === 'function') {
            console.log('⏳ Waiting for board initialization...');
            await catanBoard.init();
            console.log('✓ Board initialized successfully');
        }
        
        // Connect to server
        connectToServer();
        
        console.log('✅ Catan board created successfully!');
        console.log('🎮 Usage instructions:');
        console.log('   - Click on hex to move robber');
        console.log('   - Use mouse wheel to zoom');
        console.log('   - Drag mouse to pan');
        console.log('   - Click 📍 to see vertex numbers');
        
    } catch (error) {
        console.error('❌ Error initializing board:', error);
        // Try to create simple board anyway
        catanBoard = new CatanBoard();
        connectToServer();
    }
});

// Cleanup on close
window.addEventListener('beforeunload', function() {
    if (eventSource) {
        eventSource.close();
    }
});