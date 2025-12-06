"""
Console-based visualization for PyCatan game.

This module provides a text-based console interface for displaying game state,
actions, and events. It formats the game information in a readable way for
terminal display.
"""

from typing import Dict, Any, List, Optional
from .visualization import Visualization
from .actions import Action, ActionResult, ActionType, GameState
from .card import ResCard, DevCard


class ConsoleVisualization(Visualization):
    """
    Console-based visualization implementation.
    
    Displays game information in a formatted text output suitable for
    terminal/console viewing. Uses colors and formatting when available.
    """
    
    def __init__(self, use_colors: bool = True, compact_mode: bool = False, output_file: Optional[str] = None):
        """
        Initialize the console visualization.
        
        Args:
            use_colors: Whether to use ANSI color codes for formatting
            compact_mode: Whether to use compact display format
            output_file: Optional path to a file to write output to instead of stdout
        """
        super().__init__("Console")
        self.use_colors = use_colors
        self.compact_mode = compact_mode
        self.output_file = output_file
        
        # ANSI color codes (if enabled)
        if self.use_colors:
            self.colors = {
                'reset': '\033[0m',
                'bold': '\033[1m',
                'red': '\033[91m',
                'green': '\033[92m',
                'yellow': '\033[93m',
                'blue': '\033[94m',
                'purple': '\033[95m',
                'cyan': '\033[96m',
                'white': '\033[97m'
            }
        else:
            self.colors = {key: '' for key in ['reset', 'bold', 'red', 'green', 
                                             'yellow', 'blue', 'purple', 'cyan', 'white']}

    def _print(self, text: str = "", end: str = "\n"):
        """Internal print method to handle output destination."""
        if self.output_file:
            try:
                with open(self.output_file, 'a', encoding='utf-8') as f:
                    f.write(str(text) + end)
            except Exception:
                pass # Ignore errors writing to file
        else:
            print(text, end=end)
    
    def _format_header(self, text: str) -> str:
        """Format a header with colors and formatting."""
        return f"\n{self.colors['bold']}{self.colors['cyan']}{'='*50}{self.colors['reset']}\n" \
               f"{self.colors['bold']}{self.colors['cyan']}{text.center(50)}{self.colors['reset']}\n" \
               f"{self.colors['bold']}{self.colors['cyan']}{'='*50}{self.colors['reset']}\n"
    
    def _format_subheader(self, text: str) -> str:
        """Format a subheader with colors."""
        return f"\n{self.colors['bold']}{self.colors['yellow']}{text}{self.colors['reset']}\n" \
               f"{self.colors['yellow']}{'-' * len(text)}{self.colors['reset']}"
    
    def _format_player_name(self, name: str, is_current: bool = False) -> str:
        """Format a player name with highlighting if current."""
        if is_current:
            return f"{self.colors['bold']}{self.colors['green']}► {name}{self.colors['reset']}"
        else:
            return f"{self.colors['white']}{name}{self.colors['reset']}"
    
    def _format_resource_card(self, card: ResCard) -> str:
        """Format a resource card with appropriate color."""
        card_colors = {
            ResCard.Wood: 'green',
            ResCard.Brick: 'red',
            ResCard.Wheat: 'yellow',
            ResCard.Sheep: 'white',
            ResCard.Ore: 'purple'
        }
        color = card_colors.get(card, 'white')
        return f"{self.colors[color]}{card.name}{self.colors['reset']}"
    
    def _format_building(self, building_type: str, count: int) -> str:
        """Format building information."""
        if count == 0:
            return f"{building_type}: {self.colors['red']}0{self.colors['reset']}"
        else:
            return f"{building_type}: {self.colors['green']}{count}{self.colors['reset']}"
    
    def _convert_gamestate_to_dict(self, game_state: Any) -> Dict[str, Any]:
        """Convert GameState object to dictionary format expected by visualization."""
        # If it's already a dict, return it
        if isinstance(game_state, dict):
            return game_state
            
        # It's a GameState object
        state_dict = {
            'turn_number': game_state.turn_number,
            'current_player_index': game_state.current_player,
            'players': []
        }
        
        # Convert players
        for p in game_state.players_state:
            player_dict = {
                'name': p.name,
                'victory_points': p.victory_points,
                'cards': p.cards,
                'dev_cards': p.dev_cards,
                'settlements': len(p.settlements),
                'cities': len(p.cities),
                'roads': len(p.roads)
            }
            state_dict['players'].append(player_dict)
            
        # Find current player name
        current_player_name = "Unknown"
        for p in game_state.players_state:
            if p.player_id == game_state.current_player:
                current_player_name = p.name
                break
        state_dict['current_player_name'] = current_player_name
        
        # Board
        state_dict['board'] = {
            'robber_position': game_state.board_state.robber_position,
            'tiles': game_state.board_state.tiles
        }
        
        return state_dict

    def display_game_state(self, game_state: Any) -> None:
        """Display the complete game state."""
        if not self.enabled:
            return
            
        # Convert GameState object to dict if needed
        game_state = self._convert_gamestate_to_dict(game_state)
        
        self._print(self._format_header("GAME STATE"))
        
        # Turn information
        self._print(f"Turn: {self.colors['bold']}{game_state.get('turn_number', 'N/A')}{self.colors['reset']}")
        self._print(f"Current Player: {self._format_player_name(game_state.get('current_player_name', 'N/A'), True)}")
        
        # Players information
        players = game_state.get('players', [])
        if players:
            self._print(self._format_subheader("PLAYERS"))
            
            for i, player in enumerate(players):
                is_current = i == game_state.get('current_player_index', -1)
                player_name = player.get('name', f'Player {i}')
                
                self._print(f"\n{self._format_player_name(player_name, is_current)}")
                
                # Victory points
                vp = player.get('victory_points', 0)
                vp_color = 'green' if vp >= 10 else 'white'
                self._print(f"  Victory Points: {self.colors[vp_color]}{vp}{self.colors['reset']}")
                
                # Resource cards
                cards = player.get('cards', [])
                card_counts = {}
                for card in cards:
                    card_counts[card] = card_counts.get(card, 0) + 1
                
                if card_counts:
                    self._print(f"  Resources: ", end="")
                    card_strs = []
                    for card_type in [ResCard.Wood, ResCard.Brick, ResCard.Wheat, ResCard.Sheep, ResCard.Ore]:
                        count = card_counts.get(card_type, 0)
                        if count > 0:
                            card_strs.append(f"{self._format_resource_card(card_type)}×{count}")
                    self._print(", ".join(card_strs) if card_strs else "None")
                else:
                    self._print(f"  Resources: None")
                
                # Development cards
                dev_cards = player.get('dev_cards', [])
                if dev_cards:
                    self._print(f"  Dev Cards: {len(dev_cards)}")
                
                # Buildings
                settlements = player.get('settlements', 0)
                cities = player.get('cities', 0) 
                roads = player.get('roads', 0)
                self._print(f"  Buildings: {self._format_building('Settlements', settlements)}, " \
                      f"{self._format_building('Cities', cities)}, " \
                      f"{self._format_building('Roads', roads)}")
        
        # Board information (simplified)
        board = game_state.get('board', {})
        if board:
            self._print(self._format_subheader("BOARD"))
            
            # Robber position
            robber_pos = game_state.get('robber_position')
            if robber_pos:
                self._print(f"Robber Position: {robber_pos}")
            
            # Additional board info could be added here
            if not self.compact_mode:
                tiles = board.get('tiles', [])
                if tiles:
                    self._print(f"Board Tiles: {len(tiles)} tiles configured")
        
        self._print()  # Empty line at end
    
    def display_action(self, action: Action, result: ActionResult) -> None:
        """Display a single action and its result."""
        if not self.enabled:
            return
        
        # Determine result color
        if result.success:
            result_color = 'green'
            result_symbol = '✓'
        else:
            result_color = 'red'
            result_symbol = '✗'
        
        # Format action description
        action_desc = self._get_action_description(action)
        
        self._print(f"{self.colors[result_color]}{result_symbol}{self.colors['reset']} {action_desc}")
        
        if not result.success and result.error_message:
            self._print(f"  {self.colors['red']}Error: {result.error_message}{self.colors['reset']}")
        elif result.success and result.error_message:
            self._print(f"  {self.colors['green']}{result.error_message}{self.colors['reset']}")
    
    def display_turn_start(self, player_name: str, turn_number: int) -> None:
        """Display turn start notification."""
        if not self.enabled:
            return
        
        self._print(f"\n{self.colors['bold']}{self.colors['blue']}>>> Turn {turn_number}: {player_name}'s turn{self.colors['reset']}")
    
    def display_dice_roll(self, player_name: str, dice_values: List[int], total: int) -> None:
        """Display dice roll results."""
        if not self.enabled:
            return
        
        dice_str = " + ".join(str(d) for d in dice_values)
        total_color = 'red' if total == 7 else 'white'
        
        self._print(f"\n{self.colors['bold']}🎲 {player_name} rolled: " \
              f"{dice_str} = {self.colors[total_color]}{total}{self.colors['reset']}")
    
    def display_resource_distribution(self, distributions: Dict[str, List[str]]) -> None:
        """Display resource distribution from dice roll."""
        if not self.enabled:
            return
        
        if not distributions:
            self._print("No resources were distributed.")
            return
        
        self._print("\n📦 Resources distributed:")
        for player_name, resources in distributions.items():
            if resources:
                resource_str = ", ".join(resources)
                self._print(f"  {player_name}: {self.colors['green']}{resource_str}{self.colors['reset']}")
    
    def display_error(self, message: str) -> None:
        """Display error message."""
        if not self.enabled:
            return
        
        self._print(f"{self.colors['red']}❌ Error: {message}{self.colors['reset']}")
    
    def display_message(self, message: str) -> None:
        """Display general information message."""
        if not self.enabled:
            return
        
        self._print(f"{self.colors['cyan']}ℹ️  {message}{self.colors['reset']}")
    
    def _get_action_description(self, action: Action) -> str:
        """Get a human-readable description of an action."""
        player_name = action.parameters.get('player_name', f'Player {action.player_id}')
        
        if action.action_type in [ActionType.BUILD_SETTLEMENT, ActionType.PLACE_STARTING_SETTLEMENT]:
            return f"{player_name} built a settlement"
        elif action.action_type == ActionType.BUILD_CITY:
            return f"{player_name} built a city"
        elif action.action_type in [ActionType.BUILD_ROAD, ActionType.PLACE_STARTING_ROAD]:
            return f"{player_name} built a road"
        elif action.action_type == ActionType.TRADE_BANK:
            given = action.parameters.get('give', 'resources')
            received = action.parameters.get('receive', 'resources')
            return f"{player_name} traded {given} for {received} with bank"
        elif action.action_type == ActionType.TRADE_PROPOSE:
            return f"{player_name} proposed a trade"
        elif action.action_type == ActionType.BUY_DEV_CARD:
            return f"{player_name} bought a development card"
        elif action.action_type == ActionType.USE_DEV_CARD:
            card_type = action.parameters.get('card_type', 'development card')
            return f"{player_name} used {card_type}"
        elif action.action_type == ActionType.END_TURN:
            return f"{player_name} ended their turn"
        elif action.action_type == ActionType.ROLL_DICE:
            return f"{player_name} rolled the dice"
        else:
            return f"{player_name} performed {action.action_type.value}"
    
    def clear_screen(self) -> None:
        """Clear the console screen (platform dependent)."""
        import os
        os.system('cls' if os.name == 'nt' else 'clear')
    
    def set_compact_mode(self, enabled: bool) -> None:
        """Enable or disable compact display mode."""
        self.compact_mode = enabled
    
    def set_colors(self, enabled: bool) -> None:
        """Enable or disable color output."""
        self.use_colors = enabled
        if not enabled:
            self.colors = {key: '' for key in self.colors.keys()}
    
    def display_board_layout(self, game_state: Dict[str, Any]) -> None:
        """
        Display the complete board layout with tiles, numbers and robber position.
        This shows all the hexagonal tiles, their resource types, and dice numbers.
        """
        if not self.enabled:
            return
        
        print(self._format_header("BOARD LAYOUT"))
        
        # Handle both Game objects and dict game states
        if hasattr(game_state, 'board'):
            # This is a Game object - use its board directly
            self._display_real_board_tiles(game_state.board.tiles)
            
            # Get robber position from game if available
            robber_pos = getattr(game_state, 'robber_pos', None)
            if robber_pos:
                print(f"\n{self.colors['red']}🛡️  Robber Position: {robber_pos}{self.colors['reset']}")
        else:
            # This is a dict game_state - try to extract board info
            board = game_state.get('board_state', {}) or game_state.get('board', {})
            tiles = board.get('tiles', [])
            
            if tiles:
                self._display_dict_board_tiles(tiles)
            else:
                print("No board tiles found in game state!")
                print("Note: This display works with full Game objects.")
            
            # Show robber position from dict
            robber_pos = game_state.get('robber_position')
            if robber_pos:
                print(f"\n{self.colors['red']}🛡️  Robber Position: {robber_pos}{self.colors['reset']}")
        
        print()
    
    def _display_real_board_tiles(self, tiles):
        """Display tiles from actual Game.board.tiles structure."""
        print("📋 Board Tiles (by rows):")
        print()
        
        # Group tiles by rows
        tiles_by_row = {}
        tile_count = 0
        
        for row_index, tile_row in enumerate(tiles):
            if not tile_row:  # Skip empty rows
                continue
                
            tiles_by_row[row_index] = []
            for col_index, tile in enumerate(tile_row):
                if tile:  # Only count non-None tiles
                    tile_count += 1
                    tiles_by_row[row_index].append((col_index, tile, tile_count))
        
        # Display each row
        for row in sorted(tiles_by_row.keys()):
            if not tiles_by_row[row]:  # Skip empty rows
                continue
                
            print(f"{self.colors['yellow']}Row {row}:{self.colors['reset']}")
            
            for col, tile, tile_num in tiles_by_row[row]:
                # Get tile information
                tile_type = self._get_tile_type_name(tile)
                tile_number = self._get_tile_number(tile)
                
                # Color coding for tile types
                tile_color = self._get_tile_color(tile_type)
                
                # Format tile display
                tile_display = f"{self.colors[tile_color]}{tile_type:<10}{self.colors['reset']}"
                number_display = f"({tile_number:>2})" if tile_number != 'N/A' else "    "
                
                print(f"  [{tile_num:>2}] {tile_display} {number_display} at [{row},{col}]")
            print()
        
        print(f"Total: {tile_count} tiles on the board")
    
    def _display_dict_board_tiles(self, tiles):
        """Display tiles from dictionary format (fallback)."""
        print("📋 Board Tiles:")
        print()
        
        for i, tile in enumerate(tiles, 1):
            # Handle dict format
            if isinstance(tile, dict):
                tile_type = tile.get('type', 'Unknown')
                tile_number = tile.get('number', 'N/A')
                position = tile.get('position', ['?', '?'])
            else:
                tile_type = 'Unknown'
                tile_number = 'N/A' 
                position = ['?', '?']
            
            # Color coding
            tile_color = self._get_tile_color(tile_type)
            
            # Format display
            tile_display = f"{self.colors[tile_color]}{tile_type:<10}{self.colors['reset']}"
            number_display = f"({tile_number:>2})" if tile_number != 'N/A' else "    "
            
            print(f"  [{i:>2}] {tile_display} {number_display} at {position}")
    
    def _get_tile_type_name(self, tile):
        """Get the tile type name from a tile object."""
        # Try different attribute names
        if hasattr(tile, 'tile_type'):
            tile_type = tile.tile_type
        elif hasattr(tile, 'type'):
            tile_type = tile.type
        else:
            return 'Unknown'
        
        # Handle different formats
        if hasattr(tile_type, 'name'):
            return tile_type.name
        elif hasattr(tile_type, 'value'):
            # Handle enum by value
            type_names = {
                0: 'Desert', 1: 'Fields', 2: 'Pasture', 
                3: 'Mountains', 4: 'Hills', 5: 'Forest'
            }
            return type_names.get(tile_type.value, 'Unknown')
        else:
            return str(tile_type)
    
    def _get_tile_number(self, tile):
        """Get the tile number from a tile object."""
        # Try different attribute names
        if hasattr(tile, 'number') and tile.number is not None:
            return tile.number
        elif hasattr(tile, 'token_num') and tile.token_num is not None:
            return tile.token_num
        else:
            return 'N/A'
    
    def _get_tile_color(self, tile_type):
        """Get the appropriate color for a tile type."""
        tile_colors = {
            'Forest': 'green', 'FOREST': 'green', 'wood': 'green',
            'Hills': 'red', 'HILLS': 'red', 'brick': 'red', 
            'Fields': 'yellow', 'FIELDS': 'yellow', 'wheat': 'yellow',
            'Pasture': 'white', 'PASTURE': 'white', 'sheep': 'white',
            'Mountains': 'purple', 'MOUNTAINS': 'purple', 'ore': 'purple',
            'Desert': 'cyan', 'DESERT': 'cyan', 'desert': 'cyan'
        }
        return tile_colors.get(tile_type, 'white')
    
    def display_points_reference(self) -> None:
        """
        Display the point mapping reference (1-54) organized by board sections.
        This helps players understand which point numbers correspond to which locations.
        """
        if not self.enabled:
            return
        
        print(self._format_header("POINTS REFERENCE (1-54)"))
        
        print("Points are numbered 1-54 and represent intersections where you can build settlements/cities.")
        print(f"{self.colors['yellow']}Use these point numbers when building!{self.colors['reset']}\n")
        
        # Organize points by rows (based on actual Catan board layout - 54 points total)
        points_layout = {
            "Top Row (7 points)": list(range(1, 8)),          # Points 1-7
            "Second Row (9 points)": list(range(8, 17)),      # Points 8-16  
            "Third Row (11 points)": list(range(17, 28)),     # Points 17-27
            "Fourth Row (11 points)": list(range(28, 39)),    # Points 28-38
            "Fifth Row (9 points)": list(range(39, 48)),      # Points 39-47
            "Bottom Row (7 points)": list(range(48, 55))      # Points 48-54
        }
        
        for section_name, points in points_layout.items():
            print(f"{self.colors['cyan']}{section_name}:{self.colors['reset']}")
            
            # Display points in rows of 6 for better readability
            for i in range(0, len(points), 6):
                row_points = points[i:i+6]
                formatted_points = [f"{self.colors['green']}{p:>2}{self.colors['reset']}" for p in row_points]
                print(f"  {' '.join(formatted_points)}")
            print()
        
        print(f"{self.colors['yellow']}💡 Tip: Use 'overview' command to see the full board with both tiles and points!{self.colors['reset']}")
        print()
    
    def display_robber_info(self, game_state: Dict[str, Any]) -> None:
        """
        Display information about the robber's current position and effects.
        """
        if not self.enabled:
            return
        
        print(self._format_header("ROBBER INFORMATION"))
        
        robber_pos = game_state.get('robber_position')
        
        if robber_pos:
            print(f"🛡️  {self.colors['red']}Robber is currently at position: {robber_pos}{self.colors['reset']}")
            
            # Try to find which tile the robber is on
            board = game_state.get('board_state', {}) or game_state.get('board', {})
            tiles = board.get('tiles', [])
            
            robber_tile = None
            for i, tile in enumerate(tiles):
                tile_pos = None
                if hasattr(tile, 'position'):
                    tile_pos = tile.position
                elif isinstance(tile, dict) and 'position' in tile:
                    tile_pos = tile['position']
                
                if tile_pos and list(tile_pos) == robber_pos:
                    robber_tile = tile
                    break
            
            if robber_tile:
                # Get tile type
                if hasattr(robber_tile, 'tile_type'):
                    tile_type = robber_tile.tile_type.name if hasattr(robber_tile.tile_type, 'name') else str(robber_tile.tile_type)
                elif isinstance(robber_tile, dict) and 'type' in robber_tile:
                    tile_type = robber_tile['type']
                else:
                    tile_type = 'Unknown'
                
                # Get tile number
                if hasattr(robber_tile, 'number'):
                    tile_number = robber_tile.number
                elif isinstance(robber_tile, dict) and 'number' in robber_tile:
                    tile_number = robber_tile['number']
                else:
                    tile_number = 'N/A'
                
                print(f"📍 This is a {self.colors['yellow']}{tile_type}{self.colors['reset']} tile with number {self.colors['bold']}{tile_number}{self.colors['reset']}")
                print(f"⚠️  {self.colors['red']}This tile does not produce resources while the robber is there!{self.colors['reset']}")
            
            print(f"\n{self.colors['cyan']}Robber Effects:{self.colors['reset']}")
            print("  • Blocks resource production on the occupied tile")
            print("  • Can steal cards from players with settlements/cities on that tile")
            print("  • Moved when a 7 is rolled or when a Knight card is played")
        else:
            print("🤔 Robber position not found in game state.")
        
        print()
    
    def display_game_overview(self, game_state: Dict[str, Any]) -> None:
        """
        Display a comprehensive overview of the entire game including board, players, and current state.
        This is the "everything at once" view for players who want complete information.
        """
        if not self.enabled:
            return
        
        print(self._format_header("COMPLETE GAME OVERVIEW"))
        
        # Game status
        turn_num = game_state.get('turn_number', 'N/A')
        current_player = game_state.get('current_player_name', 'N/A')
        print(f"🎲 {self.colors['bold']}Turn {turn_num} - {current_player}'s Turn{self.colors['reset']}")
        print()
        
        # Quick board summary
        board = game_state.get('board_state', {}) or game_state.get('board', {})
        tiles = board.get('tiles', [])
        
        if tiles:
            # Count tile types
            tile_counts = {}
            for tile in tiles:
                tile_type = 'Unknown'
                if hasattr(tile, 'tile_type'):
                    tile_type = tile.tile_type.name if hasattr(tile.tile_type, 'name') else str(tile.tile_type)
                elif isinstance(tile, dict) and 'type' in tile:
                    tile_type = tile['type']
                
                tile_counts[tile_type] = tile_counts.get(tile_type, 0) + 1
            
            print(f"{self.colors['cyan']}📋 Board Summary:{self.colors['reset']}")
            for tile_type, count in tile_counts.items():
                print(f"  {tile_type}: {count} tiles")
            print()
        
        # Robber info (condensed)
        robber_pos = game_state.get('robber_position')
        if robber_pos:
            print(f"🛡️  {self.colors['red']}Robber at: {robber_pos}{self.colors['reset']}")
        
        # Players summary
        players = game_state.get('players', [])
        if players:
            print(f"\n{self.colors['cyan']}👥 Players Status:{self.colors['reset']}")
            for i, player in enumerate(players):
                is_current = i == game_state.get('current_player_index', -1)
                player_name = player.get('name', f'Player {i}')
                vp = player.get('victory_points', 0)
                
                indicator = "👑" if is_current else "  "
                vp_indicator = "🏆" if vp >= 10 else f"{vp}VP"
                
                cards_count = len(player.get('cards', []))
                buildings = f"S:{player.get('settlements', 0)} C:{player.get('cities', 0)} R:{player.get('roads', 0)}"
                
                print(f"{indicator} {self.colors['bold'] if is_current else ''}{player_name:<12}{self.colors['reset']} " \
                      f"{vp_indicator:<4} {cards_count:>2}cards {buildings}")
        
        print(f"\n{self.colors['yellow']}💡 Commands:{self.colors['reset']}")
        print("  'points'    - Show detailed point reference (1-54)")
        print("  'board'     - Show detailed board layout") 
        print("  'robber'    - Show robber information")
        print("  'help'      - Show all available commands")
        print()