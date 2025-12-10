"""
Web-based visualization for PyCatan using Flask server.
Provides real-time board updates and interactive web interface.
"""

import json
import threading
import time
from datetime import datetime
from typing import Dict, Any, Optional, List
from queue import Queue, Empty
import webbrowser

try:
    from flask import Flask, render_template, jsonify, Response
    FLASK_AVAILABLE = True
except ImportError:
    FLASK_AVAILABLE = False
    print("Warning: Flask not installed. Web visualization will not work.")
    print("Install with: pip install flask")

from .visualization import Visualization
from .actions import Action, ActionResult, GameState
from .board_definition import board_definition


class WebVisualization(Visualization):
    """
    Web-based visualization using Flask server.
    Provides real-time updates via Server-Sent Events (SSE).
    """
    
    def __init__(self, port: int = 5000, auto_open: bool = True, debug: bool = False):
        """
        Initialize web visualization.
        
        Args:
            port: Port number for Flask server
            auto_open: Whether to automatically open browser
            debug: Enable Flask debug mode
        """
        super().__init__(name="WebVisualization")
        
        if not FLASK_AVAILABLE:
            raise ImportError("Flask is required for WebVisualization. Install with: pip install flask")
        
        self.port = port
        self.auto_open = auto_open
        self.debug = debug
        
        # Flask app setup
        self.app = Flask(__name__, 
                        static_folder='static', 
                        template_folder='templates')
        
        # Disable Flask logging
        import logging
        log = logging.getLogger('werkzeug')
        log.setLevel(logging.ERROR)
        self.app.logger.disabled = True
        
        self._setup_routes()
        
        # Game state management
        self.current_game_state = None
        self.action_history: List[Dict[str, Any]] = []
        self.event_history: List[Dict[str, Any]] = []  # Track all events (turn starts, dice rolls, etc.)
        
        # SSE (Server-Sent Events) for real-time updates
        self.sse_clients: List[Queue] = []
        self.server_thread = None
        self.running = False
    
    # Implementation of abstract methods from Visualization
    def display_action(self, action: Action, result: ActionResult) -> None:
        """Display action via web interface notification."""
        self.notify_action(action, result)
    
    def display_turn_start(self, player_name: str, turn_number: int) -> None:
        """Display turn start via web interface."""
        self._broadcast_to_clients({
            'type': 'turn_start',
            'payload': {
                'player_name': player_name,
                'turn_number': turn_number,
                'message': f"Turn {turn_number}: {player_name}'s turn begins"
            }
        })
    
    def display_dice_roll(self, player_name: str, dice_values: List[int], total: int) -> None:
        """Display dice roll via web interface."""
        self._broadcast_to_clients({
            'type': 'dice_roll',
            'payload': {
                'player_name': player_name,
                'dice_values': dice_values,
                'total': total,
                'message': f"{player_name} rolled {dice_values} (total: {total})"
            }
        })
    
    def display_resource_distribution(self, distributions: Dict[str, List[str]]) -> None:
        """Display resource distribution via web interface."""
        self._broadcast_to_clients({
            'type': 'resource_distribution',
            'payload': {
                'distributions': distributions,
                'message': "Resources distributed"
            }
        })
    
    def display_game_state(self, game_state: GameState) -> None:
        """Display full game state via web interface."""
        self.update_full_state(game_state)
    
    def display_message(self, message: str, level: str = "INFO") -> None:
        """Display message via web interface."""
        self._broadcast_to_clients({
            'type': 'message',
            'payload': {
                'message': message,
                'level': level,
                'timestamp': datetime.now().strftime("%H:%M:%S")
            }
        })
    
    def display_error(self, error: str) -> None:
        """Display error via web interface."""
        self.display_message(error, "ERROR")
        
    def _setup_routes(self):
        """Setup Flask routes for the web interface."""
        
        @self.app.route('/')
        def index():
            """Main game board page."""
            return render_template('index.html')
        
        @self.app.route('/api/game-state')
        def get_game_state():
            """Get current game state as JSON."""
            try:
                if self.current_game_state:
                    # current_game_state is already in converted format
                    return jsonify(self.current_game_state)

                # No state available - return a safe, empty JSON structure
                return jsonify({
                    'hexes': [],
                    'settlements': [],
                    'cities': [],
                    'roads': [],
                    'players': [],
                    'current_player': 0,
                    'current_phase': 'WAITING',
                    'robber_position': None
                })
            except Exception as e:
                # Catch conversion errors and return JSON error (prevents HTML 500 page)
                print(f"[ERROR] Failed to prepare game state JSON: {e}")
                try:
                    return jsonify({'error': str(e)}), 500
                except Exception:
                    # As a last resort, return minimal JSON
                    return jsonify({'error': 'internal_error'}), 500
        
        @self.app.route('/api/actions')
        def get_action_history():
            """Get action history."""
            return jsonify(self.action_history)
        
        @self.app.route('/api/board_mapping')
        def get_board_mapping():
            """Get complete board mapping including hexes and points."""
            return jsonify(board_definition.export_for_web())
        
        @self.app.route('/api/point_mapping')
        def get_point_mapping():
            """Get point mapping for backward compatibility."""
            return jsonify(board_definition.export_point_mapping())
        
        @self.app.route('/api/events')
        def sse_events():
            """Server-Sent Events endpoint for real-time updates."""
            def event_generator():
                # Create new client queue
                client_queue = Queue()
                self.sse_clients.append(client_queue)
                
                try:
                    # Send initial game state
                    if self.current_game_state:
                        initial_data = json.dumps({
                            'type': 'game_update', 
                            'payload': self.current_game_state  # Already converted in update_full_state
                        })
                        yield f"data: {initial_data}\n\n"
                    
                    # Send event history (all previous events including actions)
                    all_events = []
                    
                    # Combine action history and other events
                    for action_data in self.action_history:
                        all_events.append(('action_executed', action_data))
                    
                    for event_data in self.event_history:
                        all_events.append((event_data.get('type', 'event'), event_data))
                    
                    # Sort by timestamp and send
                    all_events.sort(key=lambda x: x[1].get('timestamp', ''), reverse=False)
                    
                    for event_type, event_data in all_events:
                        event_json = json.dumps({
                            'type': event_type,
                            'payload': event_data
                        })
                        yield f"data: {event_json}\n\n"
                    
                    # Listen for updates
                    while True:
                        try:
                            # Wait for new events with timeout
                            event_data = client_queue.get(timeout=30)
                            event_json = json.dumps(event_data)
                            yield f"data: {event_json}\n\n"
                        except Empty:
                            # Send heartbeat to keep connection alive
                            heartbeat_data = json.dumps({'type': 'heartbeat'})
                            yield f"data: {heartbeat_data}\n\n"
                            
                except GeneratorExit:
                    # Client disconnected
                    pass
                finally:
                    # Remove client queue when disconnected
                    if client_queue in self.sse_clients:
                        self.sse_clients.remove(client_queue)
            
            # Server-Sent Events requires the 'text/event-stream' content type
            return Response(event_generator(),
                            mimetype='text/event-stream',
                            headers={
                                'Cache-Control': 'no-cache',
                                'Connection': 'keep-alive',
                                'Access-Control-Allow-Origin': '*',
                                'Content-Type': 'text/event-stream'
                            })
        
        @self.app.route('/manual_mapping')
        def manual_mapping():
            """Page for manually mapping the board."""
            return render_template('manual_mapping.html')
    
    def _convert_game_state(self, game_state: GameState) -> Dict[str, Any]:
        """
        Convert PyCatan GameState to web-friendly format.
        
        Args:
            game_state: PyCatan GameState object
            
        Returns:
            Dictionary in format expected by web interface
        """
        # If it's already a dict, just return it
        if isinstance(game_state, dict):
            return game_state
        
        web_state = {
            'hexes': [],
            'settlements': [],
            'cities': [],
            'roads': [],
            'players': [],
            'current_player': getattr(game_state, 'current_player', 0),
            'current_phase': getattr(game_state, 'game_phase', 'ACTION').name if hasattr(getattr(game_state, 'game_phase', None), 'name') else str(getattr(game_state, 'game_phase', 'ACTION')),
            'robber_position': None,
            'dice_result': getattr(game_state, 'dice_rolled', None)
        }
        
        # Convert board data
        if hasattr(game_state, 'board_state') and game_state.board_state:
            # Convert hexes/tiles
            if hasattr(game_state.board_state, 'tiles'):
                web_state['hexes'] = self._convert_hexes(game_state.board_state.tiles)
            
            # Find robber position
            web_state['robber_position'] = self._find_robber_position(game_state.board_state)
        
        # Convert players
        if hasattr(game_state, 'players_state') and game_state.players_state:
            web_state['players'] = self._convert_players(game_state.players_state)
        
        # Convert buildings and roads
        # Check board_state first (preferred)
        if hasattr(game_state, 'board_state') and hasattr(game_state.board_state, 'buildings'):
            settlements, cities = self._convert_buildings(game_state.board_state.buildings)
            web_state['settlements'] = settlements
            web_state['cities'] = cities
            
            if hasattr(game_state.board_state, 'roads'):
                web_state['roads'] = self._convert_roads(game_state.board_state.roads)
                
        # Fallback to direct attributes (legacy)
        elif hasattr(game_state, 'buildings'):
            settlements, cities = self._convert_buildings(game_state.buildings)
            web_state['settlements'] = settlements
            web_state['cities'] = cities
            
            if hasattr(game_state, 'roads'):
                web_state['roads'] = self._convert_roads(game_state.roads)
        
        return web_state
    
    def _convert_coords_to_point_id(self, coords) -> int:
        """
        Convert internal coordinates [row, index] to user-friendly point ID (1-54).
        
        Args:
            coords: List or tuple with [row, index] coordinates
            
        Returns:
            int: Point ID (1-54), or 0 if conversion fails
        """
        if not coords or len(coords) < 2:
            return 0
            
        try:
            row, index = coords[0], coords[1]
            point_id = board_definition.game_coords_to_point_id(row, index)
            return point_id if point_id else 0
        except (ValueError, TypeError, IndexError):
            return 0
    
    def _convert_point_id_to_coords(self, point_id: int) -> List[int]:
        """
        Convert user-friendly point ID (1-54) to internal coordinates.
        
        Args:
            point_id: Point ID (1-54)
            
        Returns:
            List[int]: [row, index] coordinates, or [0, 0] if conversion fails
        """
        try:
            coords = board_definition.point_id_to_game_coords(point_id)
            return list(coords) if coords else [0, 0]
        except (ValueError, TypeError):
            return [0, 0]
    
    def _convert_hexes(self, tiles) -> List[Dict[str, Any]]:
        """Convert board tiles to web hex format using BoardDefinition."""
        tile_type_map = {
            'forest': 'wood',
            'hills': 'brick', 
            'pasture': 'sheep',
            'fields': 'wheat',
            'mountains': 'ore',
            'desert': 'desert'
        }
        
        hexes = []
        for tile in tiles:
            # Game already provides the needed information thanks to BoardDefinition
            if isinstance(tile, dict):
                # Use axial coordinates directly from Game if available
                if 'axial_coords' in tile:
                    q, r = tile['axial_coords']
                else:
                    # Fallback to board_definition conversion
                    hex_id = tile.get('id')
                    axial_coords = board_definition.hex_id_to_axial_coords(hex_id) if hex_id else (0, 0)
                    q, r = axial_coords

                hex_data = {
                    'id': tile.get('id', 1),
                    'q': q,
                    'r': r, 
                    'type': tile_type_map.get(tile.get('type', 'desert'), 'desert'),
                    'number': tile.get('token'),
                    'has_robber': tile.get('has_robber', False),  # Keep consistent with Game
                    'position': tile.get('position', [0, 0]),  # Add position for debugging
                    'axial_coords': [q, r]  # Add axial coords explicitly
                }
                hexes.append(hex_data)
        
        return hexes
    
    def _find_robber_position(self, board_state) -> Optional[int]:
        """Find which hex has the robber."""
        if hasattr(board_state, 'robber_position'):
            return board_state.robber_position
        return None
    
    def _convert_players(self, players) -> List[Dict[str, Any]]:
        """Convert player data to web format."""
        web_players = []
        for i, player in enumerate(players):
            player_name = getattr(player, 'name', f'Player {i + 1}')
            
            # Get cards list (convert enums to strings)
            cards_list = []
            if hasattr(player, 'cards'):
                for card in player.cards:
                    # Handle ResCard enum
                    card_name = card.name if hasattr(card, 'name') else str(card)
                    # Clean up "ResCard.Wood" -> "Wood"
                    if "." in card_name:
                        card_name = card_name.split(".")[-1]
                    cards_list.append(card_name)
            
            # Get dev cards list
            dev_cards_list = []
            if hasattr(player, 'dev_cards'):
                for card in player.dev_cards:
                    # Handle DevCard enum
                    card_name = card.name if hasattr(card, 'name') else str(card)
                    if "." in card_name:
                        card_name = card_name.split(".")[-1]
                    dev_cards_list.append(card_name)
            
            player_data = {
                'id': i,
                'name': player_name,
                'victory_points': getattr(player, 'victory_points', 0),
                'total_cards': len(getattr(player, 'cards', [])),
                'cards_list': cards_list,
                'dev_cards_list': dev_cards_list,
                'settlements': len(getattr(player, 'settlements', [])),
                'cities': len(getattr(player, 'cities', [])),
                'roads': len(getattr(player, 'roads', [])),
                'longest_road': getattr(player, 'longest_road_length', 0),
                'knights': getattr(player, 'knight_cards', 0)
            }
            web_players.append(player_data)
        
        return web_players
    
    def _convert_buildings(self, buildings) -> tuple:
        """
        Convert buildings to settlements and cities for web display.
        Game now provides buildings with point IDs directly.
        """
        settlements = []
        cities = []
        
        # Handle dictionary format from Game.get_full_state (point_id: info)
        if isinstance(buildings, dict):
            for point_id, info in buildings.items():
                building_data = {
                    'id': f"b_{point_id}",
                    'vertex': point_id,  # Already a point ID (1-54)
                    'player': info.get('owner', 0) + 1  # 1-based for web
                }
                
                b_type = info.get('type', 'settlement')
                if b_type == 'settlement':
                    settlements.append(building_data)
                elif b_type == 'city':
                    cities.append(building_data)
                    
        # Handle list format (legacy)
        elif isinstance(buildings, list):
            for i, building in enumerate(buildings):
                point_id = getattr(building, 'point_id', 0)
                
                building_data = {
                    'id': i + 1,
                    'vertex': point_id,  # Point ID (1-54) for web display
                    'player': getattr(building, 'player', 0) + 1  # 1-based for web
                }
                
                if getattr(building, 'type', None) == 'settlement':
                    settlements.append(building_data)
                elif getattr(building, 'type', None) == 'city':
                    cities.append(building_data)
        
        return settlements, cities
    
    def _convert_roads(self, roads) -> List[Dict[str, Any]]:
        """
        Convert roads to web format.
        Game now provides roads with point IDs directly.
        """
        web_roads = []
        
        for i, road in enumerate(roads):
            # Handle dict format from Game.get_full_state
            if isinstance(road, dict):
                road_data = {
                    'id': i + 1,
                    'from': road.get('start_point_id', 0),
                    'to': road.get('end_point_id', 0),
                    'player': road.get('owner', 0) + 1
                }
                web_roads.append(road_data)
                
            # Handle tuple format (legacy): (start_pos, end_pos, owner)
            elif isinstance(road, tuple) and len(road) >= 3:
                start_pos, end_pos, owner = road[0], road[1], road[2]
                start_id = self._convert_coords_to_point_id(start_pos)
                end_id = self._convert_coords_to_point_id(end_pos)
                
                road_data = {
                    'id': i + 1,
                    'from': start_id,
                    'to': end_id,
                    'player': owner + 1
                }
                web_roads.append(road_data)
                
            # Handle object format (legacy)
            else:
                start_point = getattr(road, 'start_point_id', 0)
                end_point = getattr(road, 'end_point_id', 0)
                
                road_data = {
                    'id': i + 1,
                    'from': start_point,  # Point ID (1-54) for web display
                    'to': end_point,      # Point ID (1-54) for web display  
                    'player': getattr(road, 'player', 0) + 1  # 1-based for web
                }
                web_roads.append(road_data)
        
        return web_roads
    
    def _broadcast_to_clients(self, event_data: Dict[str, Any]):
        """Send event to all connected SSE clients."""
        disconnected_clients = []
        
        for client_queue in self.sse_clients:
            try:
                client_queue.put_nowait(event_data)
            except:
                # Mark client as disconnected
                disconnected_clients.append(client_queue)
        
        # Remove disconnected clients
        for client in disconnected_clients:
            if client in self.sse_clients:
                self.sse_clients.remove(client)
    
    def notify_action(self, action: Action, result: ActionResult):
        """Notify web clients of action execution."""
        timestamp = datetime.now().strftime("%H:%M:%S")
        
        # Get player name from action parameters (added by GameManager)
        player_name = action.parameters.get('player_name', f'Player {action.player_id + 1}') if hasattr(action, 'parameters') and action.parameters else f'Player {action.player_id + 1}'
        
        # Generate a better message for the web log
        message = result.error_message
        if result.success:
            action_name = action.action_type.name
            if action_name == 'BUILD_SETTLEMENT':
                message = f"{player_name} built a settlement"
            elif action_name == 'BUILD_CITY':
                message = f"{player_name} built a city"
            elif action_name == 'BUILD_ROAD':
                message = f"{player_name} built a road"
            elif action_name == 'BUY_DEV_CARD':
                message = f"{player_name} bought a development card"
            elif action_name == 'ROLL_DICE':
                message = f"{player_name} rolled dice"
            elif action_name == 'END_TURN':
                message = f"{player_name} ended turn"
            elif action_name == 'TRADE_BANK':
                message = f"{player_name} traded with bank"
            elif action_name == 'TRADE_PLAYER':
                message = f"{player_name} traded with player"
            else:
                message = f"{player_name} performed {action_name}"

        action_data = {
            'timestamp': timestamp,
            'action_type': action.action_type.name,
            'player': action.player_id,
            'success': result.success,
            'message': message
        }
        
        # Add to history
        self.action_history.append(action_data)
        
        # Keep only last 100 actions
        if len(self.action_history) > 100:
            self.action_history = self.action_history[-100:]
        
        # Broadcast to web clients
        self._broadcast_to_clients({
            'type': 'action_executed',
            'payload': action_data
        })
    
    def update_full_state(self, game_state: GameState):
        """Update full game state and broadcast to web clients."""
        # Convert to web format first
        web_state = self._convert_game_state(game_state)
        
        # Store the converted state instead of the original
        self.current_game_state = web_state
        
        # Broadcast to web clients
        self._broadcast_to_clients({
            'type': 'game_update',
            'payload': web_state
        })

    # ===== ConsoleVisualization Interface Compatibility =====
    # Adding methods to match ConsoleVisualization interface
    
    def display_game_state(self, game_state) -> None:
        """Display game state (ConsoleVisualization interface)."""
        # Handle both dict and GameState object formats
        if isinstance(game_state, dict):
            # Convert dict format to web format
            web_state = self._convert_dict_to_web_format(game_state)
        else:
            # Assume it's a GameState object - use the proper conversion
            web_state = self._convert_game_state(game_state)
            
        # Update internal state
        self.current_game_state = web_state
        
        # Broadcast to web clients
        self._broadcast_to_clients({
            'type': 'state_updated',
            'payload': web_state
        })
    
    def display_action(self, action: Action, result: ActionResult) -> None:
        """Display action result (ConsoleVisualization interface)."""
        self.notify_action(action, result)
    
    def display_turn_start(self, player_name: str, turn_number: int) -> None:
        """Display turn start notification (ConsoleVisualization interface)."""
        timestamp = datetime.now().strftime("%H:%M:%S")
        
        message_data = {
            'timestamp': timestamp,
            'type': 'turn_start',
            'player_name': player_name,
            'turn_number': turn_number,
            'message': f"Turn {turn_number}: {player_name}'s turn begins"
        }
        
        # Add to event history
        self.event_history.append(message_data)
        # Keep only last 100 events
        if len(self.event_history) > 100:
            self.event_history = self.event_history[-100:]
        
        # Broadcast to web clients
        self._broadcast_to_clients({
            'type': 'turn_start',
            'payload': message_data
        })
    
    def display_dice_roll(self, player_name: str, dice_values: List[int], total: int) -> None:
        """Display dice roll results (ConsoleVisualization interface)."""
        timestamp = datetime.now().strftime("%H:%M:%S")
        
        dice_data = {
            'timestamp': timestamp,
            'player_name': player_name,
            'dice_values': dice_values,
            'total': total,
            'message': f"{player_name} rolled {dice_values} = {total}"
        }
        
        # Add to event history
        self.event_history.append(dice_data)
        if len(self.event_history) > 100:
            self.event_history = self.event_history[-100:]
        
        # Broadcast to web clients
        self._broadcast_to_clients({
            'type': 'dice_roll',
            'payload': dice_data
        })
    
    def display_resource_distribution(self, distributions: Dict[str, List[str]]) -> None:
        """Display resource distribution (ConsoleVisualization interface)."""
        timestamp = datetime.now().strftime("%H:%M:%S")
        
        distribution_data = {
            'timestamp': timestamp,
            'distributions': distributions,
            'message': "Resources distributed to players"
        }
        
        # Add to event history
        self.event_history.append(distribution_data)
        if len(self.event_history) > 100:
            self.event_history = self.event_history[-100:]
        
        # Broadcast to web clients
        self._broadcast_to_clients({
            'type': 'resource_distribution',
            'payload': distribution_data
        })
    
    def display_error(self, message: str) -> None:
        """Display error message (ConsoleVisualization interface)."""
        timestamp = datetime.now().strftime("%H:%M:%S")
        
        error_data = {
            'timestamp': timestamp,
            'type': 'error',
            'message': message
        }
        
        # Broadcast to web clients
        self._broadcast_to_clients({
            'type': 'error',
            'payload': error_data
        })
    
    def display_message(self, message: str) -> None:
        """Display general message (ConsoleVisualization interface)."""
        timestamp = datetime.now().strftime("%H:%M:%S")
        
        message_data = {
            'timestamp': timestamp,
            'type': 'info',
            'message': message
        }
        
        # Broadcast to web clients
        self._broadcast_to_clients({
            'type': 'message',
            'payload': message_data
        })
    
    def _convert_dict_to_web_format(self, game_state: Dict[str, Any]) -> Dict[str, Any]:
        """Convert dict game state to web format."""
        web_format = {
            'current_player': game_state.get('current_player', 0),
            'turn_number': game_state.get('turn_number', 1),
            'game_phase': game_state.get('game_phase', 'NORMAL_PLAY'),
            'turn_phase': game_state.get('turn_phase', 'PLAYER_ACTIONS'),
            'current_phase': game_state.get('current_phase', 'ACTION'),
            'players': game_state.get('players', []),
            'dice_roll': game_state.get('dice_roll') or game_state.get('last_dice_roll'),
            'dice_result': game_state.get('dice_result'),
            'board': game_state.get('board', {}),
            'robber_position': game_state.get('robber_position', [2, 2]),
            # Add the missing fields that are important!
            'hexes': game_state.get('hexes', []),
            'settlements': game_state.get('settlements', []),
            'cities': game_state.get('cities', []),
            'roads': game_state.get('roads', [])
        }
        
        return web_format
    
    def start_server(self):
        """Start Flask server in background thread."""
        if self.running:
            print("Web server already running")
            return
        
        self.running = True
        
        def run_server():
            try:
                print(f"Starting PyCatan web visualization on port {self.port}")
                print(f"Access the game at: http://localhost:{self.port}")
                
                self.app.run(
                    host='0.0.0.0',
                    port=self.port,
                    debug=self.debug,
                    use_reloader=False,  # Disable reloader to prevent issues
                    threaded=True
                )
            except Exception as e:
                print(f"Error starting web server: {e}")
                self.running = False
        
        self.server_thread = threading.Thread(target=run_server, daemon=True)
        self.server_thread.start()
        
        # Wait a moment for server to start
        time.sleep(2)
        
        # Open browser if requested
        if self.auto_open and self.running:
            try:
                webbrowser.open(f'http://localhost:{self.port}')
                print("Browser opened automatically")
            except Exception as e:
                print(f"Could not open browser automatically: {e}")
                print(f"Please open http://localhost:{self.port} manually")
    
    def stop_server(self):
        """Stop the Flask server."""
        self.running = False
        
        # Clear SSE clients
        self.sse_clients.clear()
        
        print("Web visualization server stopped")
    
    def __enter__(self):
        """Context manager entry."""
        self.start_server()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.stop_server()


# Convenience function for quick setup
def create_web_visualization(port: int = 5000, auto_open: bool = True, debug: bool = False) -> WebVisualization:
    """
    Create and start a WebVisualization instance.
    
    Args:
        port: Port number for Flask server
        auto_open: Whether to automatically open browser
        debug: Enable Flask debug mode
        
    Returns:
        WebVisualization instance with server started
    """
    web_viz = WebVisualization(port=port, auto_open=auto_open, debug=debug)
    web_viz.start_server()
    return web_viz