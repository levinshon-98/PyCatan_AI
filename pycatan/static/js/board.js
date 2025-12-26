// CatanBoard class for managing the game board visualization
class CatanBoard {
    constructor() {
        this.svg = document.getElementById('catan-board');
        this.hexRadius = 45;
        this.centerX = 400;
        this.centerY = 300;
        
        this.zoomLevel = 1;
        this.panX = 0;
        this.panY = 0;
        this.isDragging = false;
        this.lastMouseX = 0;
        this.lastMouseY = 0;
        this.showVertices = true;
        
        // Board mapping from server
        this.boardMapping = null;
        this.vertices = [];
        
        this.init();
    }
    
    async init() {
        this.setupEventListeners();
        // Load board mapping from server
        await this.loadBoardMapping();
        
        if (this.boardMapping && this.boardMapping.points) {
            console.log("Using server-provided board mapping for vertices");
            this.generateVerticesFromServer();
        } else {
            // Generate vertices derived directly from hex geometry
            // This ensures perfect visual alignment
            this.generateVerticesFromHexes();
        }
        
        this.createBoard();
    }
    
    async loadBoardMapping() {
        try {
            const response = await fetch('/api/board_mapping');
            this.boardMapping = await response.json();
            console.log('Board mapping loaded from server:', this.boardMapping);
        } catch (error) {
            console.error('Failed to load board mapping:', error);
            // Fallback to default if server fails
            this.boardMapping = null;
        }
    }
    
    setupEventListeners() {
        // Zoom and pan events
        this.svg.addEventListener('wheel', (e) => this.handleZoom(e));
        this.svg.addEventListener('mousedown', (e) => this.startDrag(e));
        this.svg.addEventListener('mousemove', (e) => this.handleDrag(e));
        this.svg.addEventListener('mouseup', () => this.endDrag());
        this.svg.addEventListener('mouseleave', () => this.endDrag());
    }
    
    // Convert hex coordinates to pixels
    hexToPixel(q, r) {
        const x = this.hexRadius * (3/2 * q);
        const y = this.hexRadius * (Math.sqrt(3)/2 * q + Math.sqrt(3) * r);
        return {
            x: this.centerX + x,
            y: this.centerY + y
        };
    }
    
    // Get hexagon vertices
    getHexagonVertices(q, r) {
        const center = this.hexToPixel(q, r);
        const vertices = [];
        
        for (let i = 0; i < 6; i++) {
            const angle = (Math.PI / 3) * i;
            const x = center.x + this.hexRadius * Math.cos(angle);
            const y = center.y + this.hexRadius * Math.sin(angle);
            vertices.push({x: x, y: y});
        }
        
        return vertices;
    }
    
    generateVerticesFromHexes() {
        console.log('Generating vertices derived from hex geometry...');
        this.vertices = [];
        const uniqueVerticesMap = new Map(); // To prevent duplicates
        
        // Get hex data (from game state, board mapping, or default)
        let hexes;
        if (this.currentGameState && this.currentGameState.hexes && this.currentGameState.hexes.length > 0) {
            hexes = this.currentGameState.hexes;
        } else if (this.boardMapping && this.boardMapping.hexes) {
            hexes = this.boardMapping.hexes;
        } else {
            hexes = GAMEDATA.hexes;
        }

        hexes.forEach(hex => {
            // Get the 6 corners of the current hex
            const corners = this.getHexagonVertices(hex.q, hex.r);
            
            corners.forEach(corner => {
                // Create unique key based on position (rounded to handle floating point)
                const keyX = Math.round(corner.x); 
                const keyY = Math.round(corner.y);
                const key = `${keyX},${keyY}`;
                
                if (!uniqueVerticesMap.has(key)) {
                    uniqueVerticesMap.set(key, {
                        x: corner.x,
                        y: corner.y,
                        adjacent_hexes: [hex.id]
                    });
                } else {
                    // If point exists, add hex to its adjacent list
                    const entry = uniqueVerticesMap.get(key);
                    if (!entry.adjacent_hexes.includes(hex.id)) {
                        entry.adjacent_hexes.push(hex.id);
                    }
                }
            });
        });

        // Convert map to array
        let tempVertices = Array.from(uniqueVerticesMap.values());
        
        // Sort: First by Y (rows), then by X (columns)
        // This attempts to match the server's ID generation order (row by row, left to right)
        tempVertices.sort((a, b) => {
            // Use a tolerance for Y comparison to group vertices into rows
            if (Math.abs(a.y - b.y) > 10) return a.y - b.y; 
            return a.x - b.x;
        });

        // Create final structure with IDs
        this.vertices = tempVertices.map((v, index) => ({
            id: index + 1, // Renumber 1-54
            x: v.x,
            y: v.y,
            game_coords: [], // Not critical for display
            adjacent_points: [], // Will be calculated if needed
            adjacent_hexes: v.adjacent_hexes,
            buildings: []
        }));

        console.log(`Generated ${this.vertices.length} vertices aligned to hex corners`);
    }

    generateVerticesFromServer() {
        // Generate vertices using the server-provided board mapping
        if (!this.boardMapping || !this.boardMapping.points) {
            console.error('No board mapping available from server, using fallback');
            // Create a fallback basic vertex layout
            this.generateFallbackVertices();
            return;
        }
        
        this.vertices = [];
        
        // Use the server-provided point data
        for (const pointData of this.boardMapping.points) {
            const vertex = {
                id: pointData.id,           // Point ID (1-54)
                x: pointData.x,             // Pixel coordinates from server
                y: pointData.y,
                game_coords: pointData.game_coords,  // [row, col] for debugging
                adjacent_points: pointData.adjacent_points || [],
                adjacent_hexes: pointData.adjacent_hexes || [],
                buildings: []  // Will be populated when buildings are added
            };
            
            this.vertices.push(vertex);
        }
        
        console.log(`Generated ${this.vertices.length} vertices from server data`);
    }
    
    generateFallbackVertices() {
        // Generate basic vertices when server mapping is not available
        console.log('Using fallback vertex generation');
        this.vertices = [];
        
        // Create a basic grid of vertices for testing
        let vertexId = 1;
        const rows = [7, 9, 11, 11, 9, 7]; // Standard Catan point distribution
        
        for (let row = 0; row < rows.length; row++) {
            const rowWidth = rows[row];
            for (let col = 0; col < rowWidth; col++) {
                // Simple grid positioning
                const offsetX = -(rowWidth - 1) * this.hexRadius * 0.5 * 0.75;
                const x = this.centerX + offsetX + col * this.hexRadius * 0.75;
                const y = this.centerY + (row - 2.5) * this.hexRadius * 0.866;
                
                this.vertices.push({
                    id: vertexId,
                    x: x,
                    y: y,
                    game_coords: [row, col],
                    adjacent_points: [],
                    adjacent_hexes: [],
                    buildings: []
                });
                
                vertexId++;
            }
        }
        
        console.log(`Generated ${this.vertices.length} fallback vertices`);
    }
    
    // Get vertex by point ID
    getVertexByPointId(pointId) {
        return this.vertices.find(v => v.id === pointId);
    }
    
    // Get vertex by coordinates (for backward compatibility)
    getVertexByCoords(x, y, tolerance = 20) {
        return this.vertices.find(v => {
            const dx = v.x - x;
            const dy = v.y - y;
            return Math.sqrt(dx * dx + dy * dy) < tolerance;
        });
    }
            
    createBoard() {
        // Create the game board with hexes and vertices
        console.log('Creating game board...');
        
        // Clear any existing content
        this.svg.innerHTML = '';
        
        // Create hexes first (either from server data or fallback)
        this.createHexes();
        
        // Create vertices
        this.createVertices();
        
        // Set initial transform
        this.updateTransform();
        
        console.log('Game board created successfully');
    }
    
    createHexes() {
        // Create hexes on the board
        // Use server data if available, otherwise fallback to GAMEDATA
        let hexData;
        if (this.currentGameState && this.currentGameState.hexes && this.currentGameState.hexes.length > 0) {
            hexData = this.currentGameState.hexes;
            console.log('Using hexes from game state');
        } else if (this.boardMapping && this.boardMapping.hexes) {
            hexData = this.boardMapping.hexes;
            console.log('Using hexes from board mapping');
        } else {
            hexData = GAMEDATA.hexes;
            console.log('Using fallback hex data from GAMEDATA');
        }
        
        hexData.forEach(hex => {
            this.createHex(hex);
        });
    }
    
    createBoard() {
        // Clear existing content
        this.svg.innerHTML = '';
        
        // Determine which hex data to use
        let hexData;
        if (this.currentGameState && this.currentGameState.hexes && this.currentGameState.hexes.length > 0) {
            hexData = this.currentGameState.hexes;
            console.log(`Using server hexes: ${hexData.length} hexes`);
        } else {
            hexData = GAMEDATA.hexes;
            console.log(`Using default GAMEDATA hexes: ${hexData.length} hexes`);
        }
        
        // Create hexes
        hexData.forEach(hex => {
            this.createHex(hex);
        });
        
        // Create vertices
        this.createVertices();
        
        // Create buildings only if we don't have current game state
        // (when called directly, not from updateFromGameState)
        if (!this.currentGameState) {
            // Create settlements from GAMEDATA (fallback)
            GAMEDATA.settlements.forEach(settlement => {
                this.createSettlement(settlement);
            });

            // Create cities from GAMEDATA (fallback)
            GAMEDATA.cities.forEach(city => {
                this.createCity(city);
            });

            // Create roads from GAMEDATA (fallback)
            GAMEDATA.roads.forEach(road => {
                this.createRoad(road);
            });
        }
        
        this.updateTransform();
    }
    
    createHex(hex) {
        const vertices = this.getHexagonVertices(hex.q, hex.r);
        const center = this.hexToPixel(hex.q, hex.r);
        
        // Calculate bounding rectangle for the hex
        const minX = Math.min(...vertices.map(v => v.x));
        const maxX = Math.max(...vertices.map(v => v.x));
        const minY = Math.min(...vertices.map(v => v.y));
        const maxY = Math.max(...vertices.map(v => v.y));
        
        // Create group for hex
        const hexGroup = document.createElementNS('http://www.w3.org/2000/svg', 'g');
        
        // Create clipPath for hex
        const clipPath = document.createElementNS('http://www.w3.org/2000/svg', 'clipPath');
        clipPath.setAttribute('id', `clip-${hex.id}`);
        
        const pathData = vertices.map((vertex, index) => {
            const command = index === 0 ? 'M' : 'L';
            return `${command} ${vertex.x.toFixed(2)} ${vertex.y.toFixed(2)}`;
        }).join(' ') + ' Z';
        
        const clipPathElement = document.createElementNS('http://www.w3.org/2000/svg', 'path');
        clipPathElement.setAttribute('d', pathData);
        clipPath.appendChild(clipPathElement);
        
        // Add clipPath to defs
        let defs = this.svg.querySelector('defs');
        if (!defs) {
            defs = document.createElementNS('http://www.w3.org/2000/svg', 'defs');
            this.svg.appendChild(defs);
        }
        defs.appendChild(clipPath);
        
        // Create image that fills the hex
        const image = document.createElementNS('http://www.w3.org/2000/svg', 'image');
        image.setAttribute('href', `static/images/${RESOURCE_FILES[hex.type]}`);
        image.setAttribute('x', minX);
        image.setAttribute('y', minY);
        image.setAttribute('width', maxX - minX);
        image.setAttribute('height', maxY - minY);
        image.setAttribute('preserveAspectRatio', 'xMidYMid slice');
        image.setAttribute('clip-path', `url(#clip-${hex.id})`);
        
        hexGroup.appendChild(image);
        
        // Create hex element (for borders only)
        const pathElement = document.createElementNS('http://www.w3.org/2000/svg', 'path');
        pathElement.setAttribute('d', pathData);
        pathElement.setAttribute('class', `hexagon hex-${hex.type}`);
        pathElement.setAttribute('data-hex-id', hex.id);
        pathElement.style.fill = 'transparent';
        pathElement.style.cursor = 'pointer';
        
        // Add click event to show hex ID
        pathElement.addEventListener('click', (e) => {
            e.stopPropagation();
            this.showHexId(hex.id, center.x, center.y);
        });
        
        hexGroup.appendChild(pathElement);
        this.svg.appendChild(hexGroup);
        
        // Add hex number (if not desert)
        if (hex.number !== null) {
            const numberElement = document.createElementNS('http://www.w3.org/2000/svg', 'text');
            numberElement.setAttribute('x', center.x);
            numberElement.setAttribute('y', center.y);
            numberElement.textContent = hex.number;
            numberElement.setAttribute('class', hex.number === 6 || hex.number === 8 ? 'hex-number red' : 'hex-number');
            this.svg.appendChild(numberElement);
        }
        
        // Add robber if present
        if (hex.has_robber || hex.robber) {  // Support both formats for backward compatibility
            this.createRobber(center.x, center.y, hex.id);
        }
    }
    
    createRobber(x, y, hexId) {
        // Create robber group
        const robberGroup = document.createElementNS('http://www.w3.org/2000/svg', 'g');
        robberGroup.setAttribute('class', 'robber');
        robberGroup.setAttribute('data-hex-id', hexId);
        
        // Create robber circle
        const circle = document.createElementNS('http://www.w3.org/2000/svg', 'circle');
        circle.setAttribute('cx', x);
        circle.setAttribute('cy', y);
        circle.setAttribute('r', 18);
        
        // Create robber text
        const text = document.createElementNS('http://www.w3.org/2000/svg', 'text');
        text.setAttribute('x', x);
        text.setAttribute('y', y);
        text.textContent = 'R';
        text.setAttribute('class', 'robber-text');
        
        robberGroup.appendChild(circle);
        robberGroup.appendChild(text);
        this.svg.appendChild(robberGroup);
    }
    
    createVertices() {
        // Create vertices group
        const verticesGroup = document.createElementNS('http://www.w3.org/2000/svg', 'g');
        verticesGroup.setAttribute('id', 'vertices');
        if (this.showVertices) {
            verticesGroup.classList.add('vertices-visible');
        }
        
        this.vertices.forEach(vertex => {
            // Create vertex circle
            const circle = document.createElementNS('http://www.w3.org/2000/svg', 'circle');
            circle.setAttribute('cx', vertex.x);
            circle.setAttribute('cy', vertex.y);
            circle.setAttribute('r', 8);
            circle.setAttribute('class', 'vertex');
            circle.setAttribute('data-vertex-id', vertex.id);
            
            // Create vertex number text
            const text = document.createElementNS('http://www.w3.org/2000/svg', 'text');
            text.setAttribute('x', vertex.x);
            text.setAttribute('y', vertex.y);
            text.textContent = vertex.id;
            text.setAttribute('class', 'vertex-number');
            
            verticesGroup.appendChild(circle);
            verticesGroup.appendChild(text);
        });
        
        this.svg.appendChild(verticesGroup);
    }
    
    createSettlement(settlement) {
        // Find vertex by ID (handle both string and number IDs)
        const vertexId = parseInt(settlement.vertex);
        const vertex = this.vertices.find(v => v.id === vertexId);
        
        if (!vertex) {
            console.warn(`Could not find vertex ${settlement.vertex} for settlement`);
            return;
        }
        
        // Create settlement polygon (house shape)
        const polygon = document.createElementNS('http://www.w3.org/2000/svg', 'polygon');
        const points = [
            [vertex.x, vertex.y - 12],      // top
            [vertex.x - 8, vertex.y - 4],   // top-left
            [vertex.x - 8, vertex.y + 8],   // bottom-left
            [vertex.x + 8, vertex.y + 8],   // bottom-right
            [vertex.x + 8, vertex.y - 4]    // top-right
        ].map(p => p.join(',')).join(' ');
        
        polygon.setAttribute('points', points);
        polygon.setAttribute('class', `settlement player${settlement.player}`);
        polygon.setAttribute('data-settlement-id', settlement.id);
        polygon.setAttribute('data-vertex-id', settlement.vertex);
        
        this.svg.appendChild(polygon);
    }
    
    createCity(city) {
        // Find vertex by ID (handle both string and number IDs)
        const vertexId = parseInt(city.vertex);
        const vertex = this.vertices.find(v => v.id === vertexId);
        
        if (!vertex) {
            console.warn(`Could not find vertex ${city.vertex} for city`);
            return;
        }
        
        // Create city polygon (larger building)
        const polygon = document.createElementNS('http://www.w3.org/2000/svg', 'polygon');
        const points = [
            [vertex.x, vertex.y - 16],       // top
            [vertex.x - 12, vertex.y - 8],   // top-left
            [vertex.x - 12, vertex.y + 12],  // bottom-left
            [vertex.x + 12, vertex.y + 12],  // bottom-right
            [vertex.x + 12, vertex.y - 8]    // top-right
        ].map(p => p.join(',')).join(' ');
        
        polygon.setAttribute('points', points);
        polygon.setAttribute('class', `city player${city.player}`);
        polygon.setAttribute('data-city-id', city.id);
        polygon.setAttribute('data-vertex-id', city.vertex);
        
        this.svg.appendChild(polygon);
    }
    
    createRoad(road) {
        // Find vertices by ID (handle both string and number IDs)
        const fromId = parseInt(road.from);
        const toId = parseInt(road.to);
        
        const fromVertex = this.vertices.find(v => v.id === fromId);
        const toVertex = this.vertices.find(v => v.id === toId);
        
        if (!fromVertex || !toVertex) {
            console.warn(`Could not find vertices ${road.from}->${road.to} for road`);
            return;
        }
        
        // Create road line
        const line = document.createElementNS('http://www.w3.org/2000/svg', 'line');
        line.setAttribute('x1', fromVertex.x);
        line.setAttribute('y1', fromVertex.y);
        line.setAttribute('x2', toVertex.x);
        line.setAttribute('y2', toVertex.y);
        line.setAttribute('class', `road player${road.player}`);
        line.setAttribute('data-road-id', road.id);
        line.setAttribute('data-from-vertex', road.from);
        line.setAttribute('data-to-vertex', road.to);
        
        this.svg.appendChild(line);
    }
    
    createHarbor(harbor) {
        // Harbor is positioned on an edge between two points
        // We'll place it at the midpoint between the two vertices
        
        // Harbor types: 'wood', 'sheep', 'brick', 'wheat', 'ore', 'any'
        // Harbor ratios: 2 (for specific resource) or 3 (for any resource)
        
        const harborTypeColors = {
            'wood': '#228B22',     // Forest Green
            'sheep': '#90EE90',    // Light Green
            'brick': '#CD5C5C',    // Indian Red
            'wheat': '#FFD700',    // Gold
            'ore': '#696969',      // Dim Gray
            'any': '#4169E1'       // Royal Blue
        };
        
        const harborTypeIcons = {
            'wood': '🌲',
            'sheep': '🐑',
            'brick': '🧱',
            'wheat': '🌾',
            'ore': '⛰️',
            'any': '🏪'
        };
        
        // Find the two vertices for this harbor
        const pointOne = this.getVertexByPointId(harbor.point_one);
        const pointTwo = this.getVertexByPointId(harbor.point_two);
        
        if (!pointOne || !pointTwo) {
            console.warn(`Could not find vertices for harbor ${harbor.id}: points ${harbor.point_one} and ${harbor.point_two}`);
            return;
        }
        
        // Calculate midpoint between the two vertices
        const midX = (pointOne.x + pointTwo.x) / 2;
        const midY = (pointOne.y + pointTwo.y) / 2;
        
        // Calculate direction vector to push harbor outward from the board
        const centerX = this.centerX;
        const centerY = this.centerY;
        const dx = midX - centerX;
        const dy = midY - centerY;
        const dist = Math.sqrt(dx * dx + dy * dy);
        
        // Push harbor 45 pixels outward from the center
        const offsetDist = 45;
        const x = midX + (dx / dist) * offsetDist;
        const y = midY + (dy / dist) * offsetDist;
        
        // Create harbor group
        const harborGroup = document.createElementNS('http://www.w3.org/2000/svg', 'g');
        harborGroup.setAttribute('class', 'harbor');
        harborGroup.setAttribute('data-harbor-id', harbor.id);
        harborGroup.setAttribute('data-harbor-type', harbor.type);
        harborGroup.setAttribute('data-point-one', harbor.point_one);
        harborGroup.setAttribute('data-point-two', harbor.point_two);
        
        // Create harbor circle background
        const circle = document.createElementNS('http://www.w3.org/2000/svg', 'circle');
        circle.setAttribute('cx', x);
        circle.setAttribute('cy', y);
        circle.setAttribute('r', 16);
        circle.setAttribute('fill', harborTypeColors[harbor.type] || '#4169E1');
        circle.setAttribute('stroke', 'white');
        circle.setAttribute('stroke-width', 2.5);
        circle.setAttribute('opacity', '0.95');
        
        // Create harbor icon/text
        const text = document.createElementNS('http://www.w3.org/2000/svg', 'text');
        text.setAttribute('x', x);
        text.setAttribute('y', y + 5);
        text.setAttribute('text-anchor', 'middle');
        text.setAttribute('fill', 'white');
        text.setAttribute('font-size', '14');
        text.textContent = harborTypeIcons[harbor.type] || '🏪';
        
        // Create harbor ratio text (smaller, below the circle)
        const ratioText = document.createElementNS('http://www.w3.org/2000/svg', 'text');
        ratioText.setAttribute('x', x);
        ratioText.setAttribute('y', y + 26);
        ratioText.setAttribute('text-anchor', 'middle');
        ratioText.setAttribute('fill', 'white');
        ratioText.setAttribute('font-size', '8');
        ratioText.setAttribute('font-weight', 'bold');
        ratioText.textContent = `${harbor.ratio}:1`;
        
        // Create lines connecting harbor to both vertices
        const line1 = document.createElementNS('http://www.w3.org/2000/svg', 'line');
        line1.setAttribute('x1', pointOne.x);
        line1.setAttribute('y1', pointOne.y);
        line1.setAttribute('x2', x);
        line1.setAttribute('y2', y);
        line1.setAttribute('stroke', harborTypeColors[harbor.type] || '#4169E1');
        line1.setAttribute('stroke-width', 2.5);
        line1.setAttribute('opacity', '0.7');
        
        const line2 = document.createElementNS('http://www.w3.org/2000/svg', 'line');
        line2.setAttribute('x1', pointTwo.x);
        line2.setAttribute('y1', pointTwo.y);
        line2.setAttribute('x2', x);
        line2.setAttribute('y2', y);
        line2.setAttribute('stroke', harborTypeColors[harbor.type] || '#4169E1');
        line2.setAttribute('stroke-width', 2.5);
        line2.setAttribute('opacity', '0.7');
        
        // Add tooltip
        const title = document.createElementNS('http://www.w3.org/2000/svg', 'title');
        title.textContent = `Harbor: ${harbor.type} (${harbor.ratio}:1 trade)\nPoints: ${harbor.point_one}-${harbor.point_two}`;
        harborGroup.appendChild(title);
        
        // Add lines first (so they appear behind the circle)
        harborGroup.appendChild(line1);
        harborGroup.appendChild(line2);
        harborGroup.appendChild(circle);
        harborGroup.appendChild(text);
        harborGroup.appendChild(ratioText);
        this.svg.appendChild(harborGroup);
        
        console.log(`🏪 Created harbor: ${harbor.type} (${harbor.ratio}:1) at points ${harbor.point_one}-${harbor.point_two}`);
    }
    
    // Update board from game state (called when receiving updates from server)
    updateFromGameState(gameState) {
        console.log('Updating board from game state:', gameState);
        
        // Store the current game state
        this.currentGameState = gameState;
        
        // Don't regenerate vertices - they're already loaded from server in init()
        // this.generateVertices(); // <- This function doesn't exist!
        
        // Clear and rebuild board with new data (but not buildings)
        this.svg.innerHTML = '';
        
        // Create hexes from game state
        if (gameState.hexes && gameState.hexes.length > 0) {
            console.log(`Creating ${gameState.hexes.length} hexes from server data`);
            gameState.hexes.forEach(hex => {
                this.createHex(hex);
            });
        }
        
        // Create vertices
        this.createVertices();
        
        // Add harbors from game state (before buildings so they appear behind)
        if (gameState.harbors && gameState.harbors.length > 0) {
            console.log(`Creating ${gameState.harbors.length} harbors from server data`);
            gameState.harbors.forEach(harbor => {
                this.createHarbor(harbor);
            });
        }
        
        // Add buildings from server data
        this.updateBuildings(gameState);
        this.updateRobberFromGameState(gameState);
        
        // Update transform
        this.updateTransform();
    }
    
    updateBuildings(gameState) {
        // Remove existing buildings
        const existingBuildings = this.svg.querySelectorAll('.settlement, .city, .road');
        existingBuildings.forEach(building => building.remove());
        
        // Add settlements from server data
        if (gameState.settlements && gameState.settlements.length > 0) {
            console.log('Adding settlements:', gameState.settlements);
            gameState.settlements.forEach(settlement => {
                this.createSettlement(settlement);
            });
        }
        
        // Add cities from server data
        if (gameState.cities && gameState.cities.length > 0) {
            console.log('Adding cities:', gameState.cities);
            gameState.cities.forEach(city => {
                this.createCity(city);
            });
        }
        
        // Add roads from server data
        if (gameState.roads && gameState.roads.length > 0) {
            console.log('Adding roads:', gameState.roads);
            gameState.roads.forEach(road => {
                this.createRoad(road);
            });
        }
    }
    
    updateRobberFromGameState(gameState) {
        // Remove existing robber
        const existingRobber = this.svg.querySelector('.robber');
        if (existingRobber) {
            existingRobber.remove();
        }
        
        // Add robber from server data
        if (gameState.hexes) {
            // Find hex with has_robber set to true
            const robberHex = gameState.hexes.find(h => h.has_robber === true);
                
            if (robberHex) {
                // Use axial coordinates from the hex data
                const q = robberHex.axial_coords ? robberHex.axial_coords[0] : robberHex.q;
                const r = robberHex.axial_coords ? robberHex.axial_coords[1] : robberHex.r;
                const center = this.hexToPixel(q, r);
                this.createRobber(center.x, center.y, robberHex.id);
                console.log('🏴‍☠️ Robber placed at hex ID:', robberHex.id, 'position:', robberHex.position);
            } else {
                console.log('No robber found in game state');
            }
        }
    }
    
    updateRobberPosition(newPosition) {
        // Remove existing robber
        const existingRobber = this.svg.querySelector('.robber');
        if (existingRobber) {
            existingRobber.remove();
        }
        
        // Add robber to new position
        const hex = GAMEDATA.hexes.find(h => h.id === newPosition);
        if (hex) {
            const center = this.hexToPixel(hex.q, hex.r);
            this.createRobber(center.x, center.y, hex.id);
        }
    }
    
    // Zoom and pan functionality
    handleZoom(e) {
        e.preventDefault();
        const delta = e.deltaY > 0 ? 0.9 : 1.1;
        this.zoomLevel = Math.max(0.5, Math.min(3, this.zoomLevel * delta));
        this.updateTransform();
    }
    
    startDrag(e) {
        this.isDragging = true;
        this.lastMouseX = e.clientX;
        this.lastMouseY = e.clientY;
    }
    
    handleDrag(e) {
        if (!this.isDragging) return;
        
        const deltaX = e.clientX - this.lastMouseX;
        const deltaY = e.clientY - this.lastMouseY;
        
        this.panX += deltaX;
        this.panY += deltaY;
        
        this.lastMouseX = e.clientX;
        this.lastMouseY = e.clientY;
        
        this.updateTransform();
    }
    
    endDrag() {
        this.isDragging = false;
    }
    
    updateTransform() {
        this.svg.style.transform = `translate(${this.panX}px, ${this.panY}px) scale(${this.zoomLevel})`;
    }
    
    // Control functions
    zoomIn() {
        this.zoomLevel = Math.min(3, this.zoomLevel * 1.2);
        this.updateTransform();
    }
    
    zoomOut() {
        this.zoomLevel = Math.max(0.5, this.zoomLevel * 0.8);
        this.updateTransform();
    }
    
    resetZoom() {
        this.zoomLevel = 1;
        this.panX = 0;
        this.panY = 0;
        this.updateTransform();
    }
    
    toggleVertices() {
        this.showVertices = !this.showVertices;
        const verticesGroup = this.svg.querySelector('#vertices');
        if (verticesGroup) {
            if (this.showVertices) {
                verticesGroup.classList.add('vertices-visible');
            } else {
                verticesGroup.classList.remove('vertices-visible');
            }
        }
        
        // Update button text
        const button = document.getElementById('toggleVertices');
        if (button) {
            button.textContent = this.showVertices ? '🔍' : '📍';
        }
    }
    
    // עדכון vertex IDs בהתבסס על מיפוי אמיתי מהשרת
    updateVertexIDsFromMapping() {
        if (!window.pointMapping || !this.vertices) {
            console.warn('⚠️ לא ניתן לעדכן vertex IDs - חסר מיפוי או vertices');
            return;
        }
        
        console.log('🔄 מעדכן vertex IDs לפי המיפוי האמיתי...');
        
        // עבור על כל vertex ובדוק אם יש לו מיפוי מתאים
        this.vertices.forEach((vertex, index) => {
            // נסה למצוא התאמה במיפוי לפי מיקום יחסי או אינדקס
            // זהו approx - במציאות צריך מיפוי מדויק יותר
            
            // משתמש באינדקס כתוצאת הדמוי
            const mappedPointId = index + 1;
            
            // עדכון ה-ID של הvertex
            vertex.originalId = vertex.id; // שומר את הID המקורי
            vertex.id = mappedPointId; // מעדכן לID הנכון
        });
        
        // עדכון התצוגה אם הvertices מוצגים
        this.refreshVertexDisplay();
        
        console.log('✅ vertex IDs עודכנו בהתבסס על המיפוי');
    }
    
    // רענון תצוגת vertices עם IDs מעודכנים
    refreshVertexDisplay() {
        const verticesGroup = this.svg.querySelector('#vertices');
        if (!verticesGroup) return;
        
        // עדכון הטקסטים עם המספרים החדשים
        const vertexTexts = verticesGroup.querySelectorAll('.vertex-number');
        vertexTexts.forEach((text, index) => {
            if (this.vertices[index]) {
                text.textContent = this.vertices[index].id;
            }
        });
        
        // עדכון ה-data attributes
        const vertexCircles = verticesGroup.querySelectorAll('.vertex');
        vertexCircles.forEach((circle, index) => {
            if (this.vertices[index]) {
                circle.setAttribute('data-vertex-id', this.vertices[index].id);
            }
        });
    }
    
    // Debug functions
    logAllVertices() {
        console.log('All vertices:', this.vertices);
    }
    
    logVertexConnections() {
        // Show examples of connected vertices
        const examples = this.vertices.slice(0, 5);
        examples.forEach(vertex => {
            const connected = this.getConnectedVertices(vertex.id);
            console.log(`Vertex ${vertex.id} connects to vertices: ${connected.join(', ')}`);
        });
    }
    
    getConnectedVertices(vertexId) {
        // This would need implementation based on hex grid logic
        // For now, return empty array
        return [];
    }
    
    // Show hex ID when clicked
    showHexId(hexId, centerX, centerY) {
        // Remove any existing hex ID display
        const existingDisplay = this.svg.querySelector('.hex-id-display');
        if (existingDisplay) {
            existingDisplay.remove();
        }
        
        // Create a group for the display
        const displayGroup = document.createElementNS('http://www.w3.org/2000/svg', 'g');
        displayGroup.setAttribute('class', 'hex-id-display');
        
        // Create background rectangle
        const bg = document.createElementNS('http://www.w3.org/2000/svg', 'rect');
        bg.setAttribute('x', centerX - 40);
        bg.setAttribute('y', centerY - 25);
        bg.setAttribute('width', 80);
        bg.setAttribute('height', 50);
        bg.setAttribute('rx', 5);
        bg.setAttribute('fill', 'rgba(0, 0, 0, 0.8)');
        bg.setAttribute('stroke', '#FFD700');
        bg.setAttribute('stroke-width', 2);
        
        // Create text for "Tile ID:"
        const labelText = document.createElementNS('http://www.w3.org/2000/svg', 'text');
        labelText.setAttribute('x', centerX);
        labelText.setAttribute('y', centerY - 5);
        labelText.setAttribute('text-anchor', 'middle');
        labelText.setAttribute('fill', '#FFD700');
        labelText.setAttribute('font-size', '12');
        labelText.setAttribute('font-weight', 'bold');
        labelText.textContent = 'Tile ID:';
        
        // Create text for hex ID
        const idText = document.createElementNS('http://www.w3.org/2000/svg', 'text');
        idText.setAttribute('x', centerX);
        idText.setAttribute('y', centerY + 15);
        idText.setAttribute('text-anchor', 'middle');
        idText.setAttribute('fill', 'white');
        idText.setAttribute('font-size', '20');
        idText.setAttribute('font-weight', 'bold');
        idText.textContent = hexId;
        
        displayGroup.appendChild(bg);
        displayGroup.appendChild(labelText);
        displayGroup.appendChild(idText);
        this.svg.appendChild(displayGroup);
        
        // Auto-remove after 3 seconds
        setTimeout(() => {
            if (displayGroup.parentNode) {
                displayGroup.remove();
            }
        }, 3000);
        
        // Log to console as well
        console.log(`🎯 Clicked on Tile ID: ${hexId}`);
    }
}