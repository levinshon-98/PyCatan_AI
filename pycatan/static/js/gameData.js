// נתוני המשחק - אובייקט GAMEDATA (ברירת מחדל כאשר אין חיבור לשרת)
const GAMEDATA = {
    // משושים (19 משושים ברמת קושי רגילה)
    hexes: [
        // שורה עליונה (3 משושים)
        { id: 1, q: 0, r: -2, type: 'wood', number: 11, robber: false },
        { id: 2, q: 1, r: -2, type: 'sheep', number: 12, robber: false },
        { id: 3, q: 2, r: -2, type: 'wheat', number: 9, robber: false },
        
        // שורה שנייה (4 משושים)
        { id: 4, q: -1, r: -1, type: 'brick', number: 4, robber: false },
        { id: 5, q: 0, r: -1, type: 'ore', number: 6, robber: false },
        { id: 6, q: 1, r: -1, type: 'sheep', number: 5, robber: false },
        { id: 7, q: 2, r: -1, type: 'wheat', number: 10, robber: false },
        
        // שורה אמצעית (5 משושים)
        { id: 8, q: -2, r: 0, type: 'wood', number: 3, robber: false },
        { id: 9, q: -1, r: 0, type: 'brick', number: 11, robber: false },
        { id: 10, q: 0, r: 0, type: 'desert', number: null, robber: true },
        { id: 11, q: 1, r: 0, type: 'wheat', number: 4, robber: false },
        { id: 12, q: 2, r: 0, type: 'ore', number: 8, robber: false },
        
        // שורה רביעית (4 משושים)
        { id: 13, q: -2, r: 1, type: 'ore', number: 8, robber: false },
        { id: 14, q: -1, r: 1, type: 'sheep', number: 10, robber: false },
        { id: 15, q: 0, r: 1, type: 'wood', number: 9, robber: false },
        { id: 16, q: 1, r: 1, type: 'brick', number: 3, robber: false },
        
        // שורה תחתונה (3 משושים)
        { id: 17, q: -2, r: 2, type: 'wheat', number: 2, robber: false },
        { id: 18, q: -1, r: 2, type: 'sheep', number: 5, robber: false },
        { id: 19, q: 0, r: 2, type: 'ore', number: 6, robber: false }
    ],

    // יישובים - מתחילים ריקים
    settlements: [],

    // ערים - מתחילים ריקות  
    cities: [],

    // דרכים - מתחילים ריקות
    roads: [],

    // מיקום השודד הנוכחי
    robberPosition: 10,
    
    // שחקנים (תוסף חדש)
    players: [
        { id: 0, name: 'שחקן 1', victory_points: 2, total_cards: 5 },
        { id: 1, name: 'שחקן 2', victory_points: 3, total_cards: 7 },
        { id: 2, name: 'שחקן 3', victory_points: 1, total_cards: 4 },
        { id: 3, name: 'שחקן 4', victory_points: 2, total_cards: 6 }
    ],
    
    // מידע נוכחי על המשחק
    current_player: 0,
    current_phase: 'ACTION',
    dice_result: [3, 4]
};

// מיפוי סוגי משאבים לקבצי התמונות
const RESOURCE_FILES = {
    'wood': 'Forest.png',
    'brick': 'Hills.png', 
    'sheep': 'Pasture.png',
    'wheat': 'Fields.png',
    'ore': 'Mountains.png',
    'desert': 'Desert.png'
};

// מיפוי תכונות Tile ל-Hex בפורמט שלנו
function tileToHex(tile) {
    const tileTypeMap = {
        'FOREST': 'wood',
        'HILLS': 'brick',
        'PASTURE': 'sheep', 
        'FIELDS': 'wheat',
        'MOUNTAINS': 'ore',
        'DESERT': 'desert'
    };
    
    return {
        id: tile.id || tile.position,
        q: tile.position ? tile.position[0] : 0,
        r: tile.position ? tile.position[1] : 0, 
        type: tileTypeMap[tile.type] || 'desert',
        number: tile.token,
        robber: tile.has_robber || false
    };
}

// המרת GameState מPyCatan לפורמט שלנו
function convertGameState(pyGameState) {
    const converted = {
        hexes: [],
        settlements: [],
        cities: [],
        roads: [],
        players: [],
        robberPosition: null,
        current_player: pyGameState.current_player || 0,
        current_phase: pyGameState.current_phase || 'ACTION',
        dice_result: pyGameState.dice_result || null
    };
    
    // המר משושים
    if (pyGameState.board && pyGameState.board.tiles) {
        converted.hexes = pyGameState.board.tiles.map((tile, index) => tileToHex({
            ...tile,
            id: index + 1
        }));
    }
    
    // המר שחקנים
    if (pyGameState.players) {
        converted.players = pyGameState.players.map((player, index) => ({
            id: index,
            name: player.name || `שחקן ${index + 1}`,
            victory_points: player.victory_points || 0,
            total_cards: (player.cards && player.cards.length) || 0
        }));
    }
    
    // המר מבנים
    if (pyGameState.buildings) {
        pyGameState.buildings.forEach(building => {
            if (building.type === 'settlement') {
                converted.settlements.push({
                    id: building.id,
                    vertex: building.point_id,
                    player: building.player + 1
                });
            } else if (building.type === 'city') {
                converted.cities.push({
                    id: building.id,
                    vertex: building.point_id,
                    player: building.player + 1
                });
            }
        });
    }
    
    // המר דרכים
    if (pyGameState.roads) {
        converted.roads = pyGameState.roads.map((road, index) => ({
            id: index + 1,
            from: road.start_point_id,
            to: road.end_point_id,
            player: road.player + 1
        }));
    }
    
    return converted;
}