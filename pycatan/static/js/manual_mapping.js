// Manual Mapping Logic
class ManualMapper extends CatanBoard {
    constructor() {
        super();
        this.mapping = {
            hexes: {},
            points: {}
        };
        this.currentId = 1;
        this.mode = 'hex'; // 'hex' or 'point'
        this.history = [];
    }

    async init() {
        await this.initManual();
    }

    async initManual() {
        // Generate visual board from scratch
        this.generateVerticesFromHexes();
        this.createBoard();
        this.setupMappingListeners();
        this.updateUI();
        
        console.log("=== GAME LOGIC EXPECTATIONS ===");
        console.log("Paste the output from 'python print_game_logic.py' here for reference if needed.");
    }

    setupMappingListeners() {
        console.log("Setting up mapping listeners...");
        
        // Use event delegation on the SVG to catch all clicks
        this.svg.addEventListener('click', (e) => {
            console.log("Click detected on:", e.target.tagName, e.target.className);
            
            // Handle Hex Click
            if (this.mode === 'hex') {
                // Check if we clicked the hexagon path directly
                if (e.target.classList.contains('hexagon')) {
                    this.handleHexClick(e.target);
                    return;
                }
                
                // Check if we clicked the image inside the hex group
                if (e.target.tagName === 'image' && e.target.parentNode) {
                    const group = e.target.parentNode;
                    const hexPath = group.querySelector('.hexagon');
                    if (hexPath) {
                        this.handleHexClick(hexPath);
                        return;
                    }
                }
            }
            
            // Handle Point Click
            if (this.mode === 'point') {
                if (e.target.classList.contains('vertex')) {
                    this.handlePointClick(e.target);
                    return;
                }
            }
        });
        
        // Mode switching
        document.querySelectorAll('input[name="mode"]').forEach(radio => {
            radio.addEventListener('change', (e) => {
                this.mode = e.target.value;
                this.currentId = this.getNextId();
                this.updateUI();
            });
        });
    }

    getNextId() {
        const map = this.mode === 'hex' ? this.mapping.hexes : this.mapping.points;
        let id = 1;
        while (map[id]) id++;
        return id;
    }

    handleHexClick(element) {
        // In manual mapping, we use the visual ID (from generateVerticesFromHexes) as a temporary key
        // But wait, generateVerticesFromHexes assigns IDs 1-19 arbitrarily.
        // We want to assign OUR ID (1, 2, 3...) to this visual element.
        
        // The element has data-hex-id which is the visual ID.
        // We want to map: User Chosen ID -> Visual Coordinates (q, r)
        
        // Find the hex data
        const visualId = parseInt(element.getAttribute('data-hex-id'));
        const hexData = this.vertices.find(v => v.adjacent_hexes.includes(visualId)) 
                        ? GAMEDATA.hexes.find(h => h.id === visualId) 
                        : null; // This is tricky, we need to find the hex object
        
        // Actually, we can just find it in GAMEDATA.hexes by ID since createBoard used that
        const hex = GAMEDATA.hexes.find(h => h.id === visualId);
        
        if (this.mapping.hexes[this.currentId]) {
            alert(`Hex ${this.currentId} already mapped!`);
            return;
        }

        // Save mapping
        this.mapping.hexes[this.currentId] = {
            q: hex.q,
            r: hex.r
        };

        // Visual feedback
        element.classList.add('mapped');
        
        // Add text label
        const center = this.hexToPixel(hex.q, hex.r);
        const text = document.createElementNS('http://www.w3.org/2000/svg', 'text');
        text.setAttribute('x', center.x);
        text.setAttribute('y', center.y);
        text.textContent = this.currentId;
        text.setAttribute('class', 'hex-number mapped-text');
        text.setAttribute('pointer-events', 'none');
        this.svg.appendChild(text);

        this.history.push({
            type: 'hex',
            id: this.currentId,
            element: element,
            textElement: text
        });

        this.currentId++;
        this.updateUI();
    }

    handlePointClick(element) {
        const visualId = parseInt(element.getAttribute('data-vertex-id'));
        const vertex = this.vertices.find(v => v.id === visualId);

        if (this.mapping.points[this.currentId]) {
            alert(`Point ${this.currentId} already mapped!`);
            return;
        }

        // Save mapping
        this.mapping.points[this.currentId] = {
            x: vertex.x,
            y: vertex.y
        };

        // Visual feedback
        element.classList.add('mapped');
        
        // Update text
        // Find the text element associated with this vertex
        // It's the next sibling in our DOM structure
        const text = element.nextElementSibling;
        if (text && text.classList.contains('vertex-number')) {
            text.textContent = this.currentId;
            text.classList.add('mapped-text');
            text.style.opacity = 1;
        }

        this.history.push({
            type: 'point',
            id: this.currentId,
            element: element,
            textElement: text,
            originalText: visualId
        });

        this.currentId++;
        this.updateUI();
    }

    undoLast() {
        const last = this.history.pop();
        if (!last) return;

        if (last.type === 'hex') {
            delete this.mapping.hexes[last.id];
            last.element.classList.remove('mapped');
            last.textElement.remove();
            if (this.mode === 'hex') this.currentId = last.id;
        } else {
            delete this.mapping.points[last.id];
            last.element.classList.remove('mapped');
            last.textElement.textContent = last.originalText;
            last.textElement.classList.remove('mapped-text');
            if (this.mode === 'point') this.currentId = last.id;
        }
        this.updateUI();
    }

    getExpectedCoords(id, type) {
        let count = 0;
        
        if (type === 'hex') {
            const rows = [3, 4, 5, 4, 3];
            for (let r = 0; r < rows.length; r++) {
                if (id <= count + rows[r]) {
                    const col = id - count - 1;
                    return `Row ${r}, Col ${col}`;
                }
                count += rows[r];
            }
        } else {
            const rows = [7, 9, 11, 11, 9, 7];
            for (let r = 0; r < rows.length; r++) {
                if (id <= count + rows[r]) {
                    const col = id - count - 1;
                    return `Row ${r}, Col ${col}`;
                }
                count += rows[r];
            }
        }
        return "Done";
    }

    updateUI() {
        console.log("Updating UI", this.currentId, this.mode);
        document.getElementById('nextId').textContent = this.currentId;
        const hint = this.getExpectedCoords(this.currentId, this.mode);
        const hintEl = document.getElementById('coordsHint');
        if (hintEl) {
            hintEl.textContent = hint;
            hintEl.style.color = this.mode === 'hex' ? '#e74c3c' : '#2980b9';
        }
    }

    exportMapping() {
        const output = JSON.stringify(this.mapping, null, 2);
        document.getElementById('output').value = output;
        console.log("Mapping exported:", this.mapping);
    }
}

// Initialize
const mapper = new ManualMapper();

// Global functions for buttons
window.undoLast = () => mapper.undoLast();
window.exportMapping = () => mapper.exportMapping();
