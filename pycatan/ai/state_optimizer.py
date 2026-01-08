"""
State Optimizer - Compact Game State Representation

Converts verbose game state to a compact, LLM-optimized format.
This significantly reduces token usage while maintaining all essential information.

Format:
- H (Hexes): Array indexed by hex ID containing resource type + number
- N (Nodes): Array indexed by node ID with neighbors, adjacent hexes, and port info
- state: Buildings and roads with owner info
- players: Compact player data with resources, dev cards, and stats
- meta: Game metadata (current player, phase, robber position, dice)

NOTE: This is the same code as in play_and_capture.py - kept in sync for consistency.
"""

from typing import Dict, Any, List, Optional


def game_state_to_dict(game_state) -> Dict[str, Any]:
    """
    Convert GameState object to captured_game.json format.
    
    This replicates WebVisualization._convert_game_state logic
    to produce the format that optimize_state_for_ai expects.
    
    Args:
        game_state: GameState object from GameManager
        
    Returns:
        Dictionary in captured_game.json format
    """
    from pycatan.config.board_definition import board_definition
    
    # If already a dict, return as-is
    if isinstance(game_state, dict):
        return game_state
    
    # Resource type mapping (internal -> web)
    TILE_TYPE_MAP = {
        'forest': 'wood',
        'hills': 'brick',
        'pasture': 'sheep',
        'fields': 'wheat',
        'mountains': 'ore',
        'desert': 'desert'
    }
    
    result = {
        'hexes': [],
        'settlements': [],
        'cities': [],
        'roads': [],
        'harbors': [],
        'players': [],
        'points': [],
        'current_player': getattr(game_state, 'current_player', 0),
        'current_phase': game_state.game_phase.name if hasattr(game_state.game_phase, 'name') else str(game_state.game_phase),
        'dice_result': getattr(game_state, 'dice_rolled', None),
    }
    
    # Convert board data
    if hasattr(game_state, 'board_state') and game_state.board_state:
        board = game_state.board_state
        
        # Convert hexes/tiles
        if hasattr(board, 'tiles') and board.tiles:
            for tile in board.tiles:
                if isinstance(tile, dict):
                    tile_type = tile.get('type', 'desert')
                    # Map internal type names to standard names
                    mapped_type = TILE_TYPE_MAP.get(tile_type, tile_type)
                    
                    result['hexes'].append({
                        'id': tile.get('id', 0),
                        'type': mapped_type,
                        'number': tile.get('token'),
                        'has_robber': tile.get('has_robber', False)
                    })
        
        # Convert harbors
        if hasattr(board, 'harbors') and board.harbors:
            for i, harbor in enumerate(board.harbors):
                if isinstance(harbor, dict):
                    result['harbors'].append({
                        'id': i + 1,
                        'type': harbor.get('resource', 'any'),
                        'ratio': harbor.get('ratio', 3),
                        'point_one': harbor.get('point_one', 0),
                        'point_two': harbor.get('point_two', 0)
                    })
        
        # Convert buildings
        if hasattr(board, 'buildings') and board.buildings:
            for point_id, info in board.buildings.items():
                if isinstance(info, dict):
                    b_type = info.get('type', 'settlement')
                    owner = info.get('owner', 0)
                    entry = {
                        'id': f"b_{point_id}",
                        'vertex': point_id,
                        'player': owner + 1  # Convert to 1-based
                    }
                    if b_type == 'settlement':
                        result['settlements'].append(entry)
                    elif b_type == 'city':
                        result['cities'].append(entry)
        
        # Convert roads
        if hasattr(board, 'roads') and board.roads:
            for road in board.roads:
                if isinstance(road, dict):
                    result['roads'].append({
                        'from': road.get('start_point_id', 0),
                        'to': road.get('end_point_id', 0),
                        'player': road.get('owner', 0) + 1
                    })
    
    # Convert players
    if hasattr(game_state, 'players_state') and game_state.players_state:
        for p in game_state.players_state:
            # Get cards list (handle enums)
            cards_list = []
            if hasattr(p, 'cards'):
                for card in p.cards:
                    if isinstance(card, str):
                        cards_list.append(card)
                    else:
                        card_name = card.name if hasattr(card, 'name') else str(card)
                        if "." in card_name:
                            card_name = card_name.split(".")[-1]
                        cards_list.append(card_name.lower())
            
            # Get dev cards list
            dev_cards_list = []
            if hasattr(p, 'dev_cards'):
                for card in p.dev_cards:
                    if isinstance(card, str):
                        dev_cards_list.append(card)
                    else:
                        card_name = card.name if hasattr(card, 'name') else str(card)
                        if "." in card_name:
                            card_name = card_name.split(".")[-1]
                        dev_cards_list.append(card_name)
            
            result['players'].append({
                'id': p.player_id,
                'name': p.name,
                'victory_points': p.victory_points,
                'cards_list': cards_list,
                'dev_cards_list': dev_cards_list,
                'has_longest_road': p.has_longest_road,
                'has_largest_army': p.has_largest_army,
                'knights_played': p.knights_played
            })
    
    # Get points from board_definition (static structure - always correct!)
    for point_id in board_definition.get_all_point_ids():
        point_def = board_definition.points.get(point_id)
        if point_def:
            result['points'].append({
                'point_id': point_id,
                'adjacent_points': point_def.adjacent_points,
                'adjacent_hexes': point_def.adjacent_hexes
            })
    
    return result


def optimize_state_for_ai(input_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    ממיר את מצב המשחק למבנה אופטימלי עבור AI.
    מדחס את המידע ומסיר דופליקציות.
    
    This function expects game state in the format produced by web_visualization
    or captured_game.json (with hexes, points, harbors, players, etc.)
    """
    # טיפול בעטיפה אם קיימת
    data = input_data['state'] if 'state' in input_data else input_data
    
    # מילוני קיצור
    RES_MAP = {"wood": "W", "brick": "B", "sheep": "S", "wheat": "Wh", "ore": "O", "desert": "D"}
    TYPE_MAP = {"settlement": "S", "city": "C"}
    
    # 1. יצירת מערך הקסים (H)
    hexes = data.get('hexes', [])
    if hexes:
        max_hex_id = max([h['id'] for h in hexes], default=0)
        hex_array = [""] * (max_hex_id + 1)
        
        robber_hex = None
        for h in hexes:
            if h.get('has_robber'): 
                robber_hex = h['id']
            t = RES_MAP.get(h['type'], "?")
            # אם יש מספר מוסיפים אותו, אחרת (מדבר) רק את הסוג
            num = h.get('number') or h.get('token')  # Support both 'number' and 'token'
            val = f"{t}{num}" if num else t
            hex_array[h['id']] = val
    else:
        hex_array = []
        robber_hex = None

    # 2. מיפוי נמלים
    port_map = {}
    for p in data.get('harbors', []):
        harbor_type = p.get('type') or p.get('resource', 'any')  # Support both formats
        t = RES_MAP.get(harbor_type, "Any") if harbor_type != "any" else "?"
        code = f"{t}{p['ratio']}"
        port_map[p['point_one']] = code
        port_map[p['point_two']] = code

    # 3. יצירת מערך צמתים (N)
    points = data.get('points', [])
    if points:
        max_point_id = max([p['point_id'] for p in points], default=0)
        nodes_array = [None] * (max_point_id + 1)
        
        for p in points:
            # המבנה: [ [שכנים], [הקסים], נמל? ]
            val = [p['adjacent_points'], p['adjacent_hexes']]
            if p['point_id'] in port_map:
                val.append(port_map[p['point_id']])
            nodes_array[p['point_id']] = val
    else:
        nodes_array = []

    # 4. עיבוד שחקנים
    players = {}
    pid_to_name = {}
    for pl in data.get('players', []):
        name = pl['name']
        pid_to_name[pl['id']] = name
        
        # ספירת משאבים
        res_list = pl.get('cards_list', [])
        res_compact = {}
        if res_list:
            for r in set(res_list):
                r_key = RES_MAP.get(r.lower(), r)
                res_compact[r_key] = res_list.count(r)
        
        p_obj = {"vp": pl['victory_points'], "res": res_compact}
        
        # קלפי פיתוח
        knights = pl.get('knights_played', 0)
        hidden = pl.get('dev_cards_list', [])
        if knights > 0 or hidden:
            p_obj["dev"] = {}
            if hidden: 
                p_obj["dev"]["h"] = hidden
            if knights: 
                p_obj["dev"]["r"] = ["K"] * knights
        
        # דגלים מיוחדים (LR / LA)
        flags = []
        if pl.get('has_longest_road'):
            flags.append("LR")  # Longest Road
        if pl.get('has_largest_army'):
            flags.append("LA")  # Largest Army
        
        if flags:
            p_obj["stat"] = flags
            
        players[name] = p_obj

    # 5. מצב הלוח (בניינים ודרכים)
    bld = []
    for b in data.get('settlements', []):
        owner_id = b.get('player', 1) - 1  # המרה מ-1-based ל-0-based
        owner = pid_to_name.get(owner_id, "?")
        bld.append([b['vertex'], owner, "S"])
    
    for b in data.get('cities', []):
        owner_id = b.get('player', 1) - 1  # המרה מ-1-based ל-0-based
        owner = pid_to_name.get(owner_id, "?")
        bld.append([b['vertex'], owner, "C"])

    rds = []
    for r in data.get('roads', []):
        owner_id = r.get('player', 1) - 1  # המרה מ-1-based ל-0-based
        owner = pid_to_name.get(owner_id, "?")
        rds.append([[r['from'], r['to']], owner])
    
    # המרת ID של השחקן הנוכחי לשם
    curr_id = data.get('current_player')
    curr_name = pid_to_name.get(curr_id, str(curr_id) if curr_id is not None else None)

    # החזרת המילון המעובד
    return {
        "meta": {
            "curr": curr_name, 
            "phase": data.get('current_phase'), 
            "robber": robber_hex,
            "dice": data.get('dice_result')
        },
        "H": hex_array,
        "N": nodes_array,
        "state": {"bld": bld, "rds": rds},
        "players": players
    }


def format_with_legend(optimized_state: Dict[str, Any]) -> str:
    """
    Format optimized state with explanatory legend for LLM.
    
    Args:
        optimized_state: Output from optimize_state_for_ai
        
    Returns:
        Formatted string with legend + JSON
    """
    import json
    
    legend = """1. LOOKUP TABLES:
   • "H" (Hexes): Array where Index = HexID. Value = Resource+Num.
     Example: H[1]="W12" -> Hex 1 is Wood 12.
   • "N" (Nodes): Array where Index = NodeID.
     Format: [ [Neighbors], [HexIDs], Port? ]
     Logic: To find yield of Node 10, check N[10]. Get HexIDs (e.g. [1,5]). Look up H[1] and H[5].

2. CODES: W=Wood, B=Brick, S=Sheep, Wh=Wheat, O=Ore, D=Desert.
          ?3=Any 3:1 port, X2=Specific Resource 2:1 port.

3. STATE: "bld"=[NodeID, Owner, Type], "rds"=[[From,To], Owner].

4. PLAYERS: "res"={Resource:Count}, "dev"={"h":[Hidden Cards], "r":[Revealed] (K=Knight)}, 
            "stat"=["LR" (Longest Road), "LA" (Largest Army)].

5. ROBBER: Located at HexID specified in "meta.robber". H[id] is blocked.

JSON:
"""
    
    sections = [
        f'"meta":{json.dumps(optimized_state["meta"], separators=(",", ":"))}',
        f'"H":{json.dumps(optimized_state["H"], separators=(",", ":"))}',
        f'"N":{json.dumps(optimized_state["N"], separators=(",", ":"))}',
        f'"state":{json.dumps(optimized_state["state"], separators=(",", ":"))}',
        f'"players":{json.dumps(optimized_state["players"], separators=(",", ":"))}'
    ]
    json_content = "{\n  " + ",\n  ".join(sections) + "\n}"
    
    return legend + json_content
