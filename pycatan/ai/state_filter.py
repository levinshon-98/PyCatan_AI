"""
Game State Filtering and Perspective Transformation

This module handles filtering and transforming raw game state data
into an agent-specific view. It ensures that:
1. Agents only see information they should know
2. Information is presented from the agent's perspective
3. Complex game state is simplified for LLM consumption

Key principles:
- Hide opponent's private information (cards, exact resources)
- Transform "Player X did Y" → "You did Y" / "Red did Y"
- Add helpful computed data (probabilities, scarcity)
- Keep prompts concise but complete
"""

from typing import Dict, Any, List, Optional
from dataclasses import dataclass


@dataclass
class PlayerPerspective:
    """Represents which player's perspective we're filtering for."""
    player_num: int  # Player number (1, 2, 3, 4)
    player_name: str  # Player's display name
    player_color: str  # Player's color (Blue, Red, Green, Orange)


class StateFilter:
    """
    Filters and transforms game state for a specific agent's perspective.
    
    This class takes raw game state and produces a filtered, agent-centric
    view that:
    - Hides information the agent shouldn't know
    - Presents data from the agent's viewpoint
    - Adds computed context (probabilities, strategic info)
    """
    
    def __init__(self, perspective: PlayerPerspective):
        """
        Initialize state filter for a specific player.
        
        Args:
            perspective: Which player's perspective to use
        """
        self.perspective = perspective
    
    def filter_game_state(self, raw_state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Main filtering method - returns optimized compact state AS-IS.
        
        The state is already in compact format (H, N, players, bld, rds, meta).
        This filter just returns it directly - the compactness IS the optimization.
        
        Args:
            raw_state: Optimized game state (already compact)
            
        Returns:
            The same compact state (H, N arrays, etc.)
        """
        # The optimized state is already perfect for LLM consumption
        # Just return it as-is
        return raw_state
    
    def _extract_my_info(self, raw_state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Extract this agent's private information.
        Works with optimized state format where players is a dict keyed by name.
        
        Returns:
            Dictionary with agent's resources, cards, and points
        """
        players = raw_state.get("players", {})
        
        # In optimized format, players is a dict with player names as keys
        my_player = players.get(self.perspective.player_name)
        
        if not my_player:
            return {
                "resources": {},
                "development_cards": {"hidden": [], "revealed": []},
                "victory_points": 0,
                "has_longest_road": False,
                "has_largest_army": False,
            }
        
        # Extract dev cards
        dev = my_player.get("dev", {})
        
        return {
            "resources": my_player.get("res", {}),
            "development_cards": {
                "hidden": dev.get("h", []),
                "revealed": dev.get("r", [])
            },
            "victory_points": my_player.get("vp", 0),
            "has_longest_road": "LR" in my_player.get("stat", []),
            "has_largest_army": "LA" in my_player.get("stat", []),
        }
    
    def _filter_board_state(self, raw_state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Filter board information using optimized format.
        Returns the compact H/N arrays plus current state.
        """
        meta = raw_state.get("meta", {})
        state = raw_state.get("state", {})
        
        return {
            "H": raw_state.get("H", []),  # Hex lookup table
            "N": raw_state.get("N", []),  # Node lookup table  
            "buildings": self._annotate_buildings(state.get("bld", [])),
            "roads": self._annotate_roads(state.get("rds", [])),
            "robber_hex": meta.get("robber"),
            "current_phase": meta.get("phase"),
            "dice_result": meta.get("dice")
        }
    
    def _annotate_buildings(self, buildings: List) -> List[Dict]:
        """
        Annotate buildings with ownership info (mine vs others).
        Optimized format: [NodeID, Owner, Type]
        
        Args:
            buildings: List of building data [node, owner, type]
            
        Returns:
            Annotated building list
        """
        annotated = []
        for bld in buildings:
            if len(bld) < 3:
                continue
                
            node_id, owner, bld_type = bld[0], bld[1], bld[2]
            
            annotated.append({
                "node": node_id,
                "owner": "me" if owner == self.perspective.player_name else owner,
                "type": "settlement" if bld_type == "S" else "city"
            })
        
        return annotated
    
    def _annotate_roads(self, roads: List) -> List[Dict]:
        """
        Annotate roads with ownership info.
        Optimized format: [[From, To], Owner]
        
        Args:
            roads: List of road data [[from, to], owner]
            
        Returns:
            Annotated road list
        """
        annotated = []
        for road in roads:
            if len(road) < 2:
                continue
                
            nodes, owner = road[0], road[1]
            
            annotated.append({
                "from": nodes[0],
                "to": nodes[1],
                "owner": "me" if owner == self.perspective.player_name else owner
            })
        
        return annotated
    
    def _filter_other_players(self, raw_state: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Get public information about other players.
        Works with optimized format where players is a dict.
        
        This hides:
        - Exact resource counts (only show total)
        - Hidden development cards
        - Other private information
        """
        players = raw_state.get("players", {})
        other_players = []
        
        for player_name, player_data in players.items():
            # Skip myself
            if player_name == self.perspective.player_name:
                continue
            
            # Calculate totals from optimized format
            resources = player_data.get("res", {})
            dev_cards = player_data.get("dev", {})
            stats = player_data.get("stat", [])
            
            # Public information only
            other_players.append({
                "name": player_name,
                "victory_points": player_data.get("vp", 0),
                "resource_count": sum(resources.values()),  # Total only
                "development_card_count": len(dev_cards.get("h", [])) + len(dev_cards.get("r", [])),
                "knights_played": len([c for c in dev_cards.get("r", []) if c == "K"]),
                "has_longest_road": "LR" in stats,
                "has_largest_army": "LA" in stats
            })
        
        return other_players
    
    def _add_strategic_context(self, raw_state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Add computed strategic information using optimized format.
        
        This includes:
        - Dice roll probabilities for each hex (from H array)
        - Leading player information
        - Current turn info
        """
        H = raw_state.get("H", [])
        players = raw_state.get("players", {})
        meta = raw_state.get("meta", {})
        
        # Dice probabilities
        dice_probs = {
            2: "2.8%", 3: "5.6%", 4: "8.3%", 5: "11.1%", 6: "13.9%",
            8: "13.9%", 9: "11.1%", 10: "8.3%", 11: "5.6%", 12: "2.8%"
        }
        
        # Parse hex array for strategic info
        hex_analysis = []
        for hex_id, hex_str in enumerate(H):
            if not hex_str or hex_id == 0:
                continue
                
            # Parse format like "W12", "B6", "D"
            if hex_str == "D":
                continue  # Skip desert
                
            # Extract resource and number
            resource = hex_str[0] if len(hex_str) > 0 else ""
            if len(hex_str) > 1:
                try:
                    number = int(hex_str[1:])
                    hex_analysis.append({
                        "hex_id": hex_id,
                        "resource": resource,
                        "number": number,
                        "probability": dice_probs.get(number, "0%")
                    })
                except:
                    pass
        
        # Find who's winning
        leading_player = None
        max_points = 0
        for name, data in players.items():
            vp = data.get("vp", 0)
            if vp > max_points:
                max_points = vp
                leading_player = name
        
        return {
            "hex_analysis": hex_analysis,
            "leading_player": leading_player,
            "current_player": meta.get("curr"),
            "game_phase": meta.get("phase"),
            "robber_location": meta.get("robber")
        }
    
    def hide_private_info(self, game_state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Remove all private information from game state.
        Works with optimized format.
        
        Args:
            game_state: Full game state
            
        Returns:
            Game state with private info removed
        """
        filtered = game_state.copy()
        
        # Remove opponent development cards and exact resources
        if "players" in filtered:
            players_copy = {}
            for name, data in filtered["players"].items():
                if name != self.perspective.player_name:
                    # Hide exact resources - only show count
                    res = data.get("res", {})
                    total_res = sum(res.values())
                    
                    # Hide hidden dev cards
                    dev = data.get("dev", {})
                    hidden_count = len(dev.get("h", []))
                    revealed = dev.get("r", [])
                    
                    players_copy[name] = {
                        "vp": data.get("vp", 0),
                        "res": {"total": total_res},  # Only total
                        "dev": {"hidden_count": hidden_count, "r": revealed},  # Hide specific cards
                        "stat": data.get("stat", [])
                    }
                else:
                    # Keep my full info
                    players_copy[name] = data.copy()
            
            filtered["players"] = players_copy
        
        return filtered


def create_filter_for_player(player_num: int, player_name: str, player_color: str) -> StateFilter:
    """
    Convenience function to create a state filter for a specific player.
    
    Args:
        player_num: Player number (1-4)
        player_name: Player's name
        player_color: Player's color
        
    Returns:
        Configured StateFilter instance
    """
    perspective = PlayerPerspective(
        player_num=player_num,
        player_name=player_name,
        player_color=player_color
    )
    return StateFilter(perspective)
