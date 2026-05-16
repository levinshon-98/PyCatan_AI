"""
Web-based visualization for PyCatan using Flask server.
Provides real-time board updates and interactive web interface.
"""

import json
import copy
import threading
import time
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional, List
from queue import Queue, Empty
import webbrowser

try:
    from flask import Flask, render_template, jsonify, Response, request
    FLASK_AVAILABLE = True
except ImportError:
    FLASK_AVAILABLE = False
    print("Warning: Flask not installed. Web visualization will not work.")
    print("Install with: pip install flask")

from .visualization import Visualization
from pycatan.management.actions import Action, ActionResult, GameState
from pycatan.config.board_definition import board_definition
from pycatan.management.log_events import EventType, LogEntry, create_log_entry
from pycatan.ai.session_analysis import build_decision_analysis, build_turn_flow


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
        
        # Get the directory of this file
        import os
        viz_dir = os.path.dirname(os.path.abspath(__file__))
        pycatan_dir = os.path.dirname(viz_dir)  # Go up one level to pycatan/
        
        # Flask app setup with absolute paths
        # Static files are in pycatan/static, templates in visualizations/templates
        self.app = Flask(__name__, 
                        static_folder=os.path.join(pycatan_dir, 'static'), 
                        template_folder=os.path.join(viz_dir, 'templates'))
        
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
        self.log_entries: List[LogEntry] = []  # Structured log entries
        self.chat_history: List[Dict[str, Any]] = []
        self.player_chat_messages: Dict[str, str] = {}

        # Watch-replay timeline support. Snapshots are full UI states that can
        # be restored by the browser scrubber without re-running game logic.
        self.replay_enabled = False
        self.replay_source_session: Optional[str] = None
        self.replay_delay_seconds: float = 2.5
        self.replay_timeline: List[Dict[str, Any]] = []
        self.replay_index: int = 0
        self.replay_speech_prepare_callback = None
        self.replay_speech_play_callback = None
        self.replay_text_lead_seconds: float = 0.25
        
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
    
    def display_chat(self, player_name: str, message: str) -> None:
        """Display chat message (say_outloud) via web interface."""
        # Store the latest chat message for each player
        self.player_chat_messages[player_name] = message

        chat_data = {
            'player_name': player_name,
            'message': message,
            'timestamp': datetime.now().strftime("%H:%M:%S")
        }
        self.chat_history.append(chat_data)
        if len(self.chat_history) > 200:
            self.chat_history = self.chat_history[-200:]

        self._broadcast_to_clients({
            'type': 'player_chat',
            'payload': chat_data
        })
    
    def display_ai_status(self, player_name: str, status: str, details: str = "") -> None:
        """Display AI thinking status via web interface.
        
        Args:
            player_name: Name of the AI player
            status: Status type ('thinking', 'tool_call', 'processing', 'done')
            details: Optional details about what the AI is doing
        """
        # Debug: Log to console
        print(f"[AI_STATUS] {player_name}: {status} - {details[:50] if details else ''}...")
        
        self._broadcast_to_clients({
            'type': 'ai_status',
            'payload': {
                'player_name': player_name,
                'status': status,
                'details': details,
                'timestamp': datetime.now().strftime("%H:%M:%S")
            }
        })
        
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

        @self.app.route('/api/chat')
        def get_chat_history():
            """Get chat history."""
            return jsonify(self.chat_history)

        @self.app.route('/api/current')
        def get_current_ai_session():
            """Get current AI session data for the unified AI analysis tab."""
            try:
                from examples.ai_testing.web_viewer import get_current_session, get_session_data

                current = get_current_session()
                if current is None:
                    return jsonify({"error": "No active session"}), 404

                data = get_session_data(str(current))
                if data is None:
                    return jsonify({"error": "Session not found"}), 404

                return jsonify(data)
            except Exception as exc:
                print(f"[ERROR] Failed to load AI session data: {exc}")
                return jsonify({"error": str(exc)}), 500

        @self.app.route('/api/replay/status')
        def get_replay_status():
            """Get replay timeline metadata for browser controls."""
            return jsonify(self.get_replay_status())

        @self.app.route('/api/replay/seek/<int:index>', methods=['GET', 'POST'])
        def seek_replay(index: int):
            """Restore a replay snapshot and broadcast it to connected clients."""
            speak = str(request.args.get("speak", "")).lower() in {"1", "true", "yes", "on"}
            snapshot = self.seek_replay(index, speak=speak)
            if snapshot is None:
                return jsonify({"error": "Replay snapshot not found"}), 404
            return jsonify(snapshot)

        @self.app.route('/api/replay/analysis/<int:index>')
        def get_replay_analysis(index: int):
            """Get a decision-analysis trace for a replay snapshot."""
            analysis = self.get_replay_analysis(index)
            if analysis is None:
                return jsonify({"error": "Replay analysis not available"}), 404
            return jsonify(analysis)
        
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
        
        @self.app.route('/unified')
        def unified_view():
            """Unified view combining game board and AI analysis."""
            return render_template('unified.html')
    
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
            'harbors': [],
            'players': [],
            'current_player': getattr(game_state, 'current_player', 0),
            'current_phase': getattr(game_state, 'game_phase', 'ACTION').name if hasattr(getattr(game_state, 'game_phase', None), 'name') else str(getattr(game_state, 'game_phase', 'ACTION')),
            'robber_position': None,
            'dice_result': getattr(game_state, 'dice_rolled', None),
            'allowed_actions': getattr(game_state, 'allowed_actions', []),  # Actions available to current player
            # Add board structure information - CRITICAL FOR AI!
            'points': self._get_points_info(),
            'board_graph': self._get_board_graph()
        }
        
        # Convert board data
        if hasattr(game_state, 'board_state') and game_state.board_state:
            # Convert hexes/tiles
            if hasattr(game_state.board_state, 'tiles'):
                web_state['hexes'] = self._convert_hexes(game_state.board_state.tiles)
            
            # Convert harbors
            if hasattr(game_state.board_state, 'harbors'):
                web_state['harbors'] = self._convert_harbors(game_state.board_state.harbors)
            
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
    
    def _convert_harbors(self, harbors) -> List[Dict[str, Any]]:
        """
        Convert harbors to web format.
        
        Args:
            harbors: List of harbor dictionaries from GameState
            
        Returns:
            List of harbor data for web display
        """
        web_harbors = []
        
        if not harbors:
            return web_harbors
        
        for i, harbor in enumerate(harbors):
            if isinstance(harbor, dict):
                # Harbor from Game._get_ports_info (new format)
                harbor_data = {
                    'id': i + 1,
                    'type': harbor.get('resource', 'any'),  # 'wood', 'sheep', 'brick', 'wheat', 'ore', 'any'
                    'ratio': harbor.get('ratio', 3),  # 2 or 3
                    'point_one': harbor.get('point_one', 0),  # Point ID of first vertex
                    'point_two': harbor.get('point_two', 0),  # Point ID of second vertex
                }
                web_harbors.append(harbor_data)
            else:
                # Harbor object (fallback for older code)
                harbor_type = getattr(harbor, 'type', None)
                if harbor_type:
                    # Convert HarborType enum to string
                    type_name = harbor_type.name.lower() if hasattr(harbor_type, 'name') else 'any'
                    ratio = 2 if type_name != 'any' else 3
                    
                    harbor_data = {
                        'id': i + 1,
                        'type': type_name,
                        'ratio': ratio,
                        'point_one': 0,
                        'point_two': 0
                    }
                    web_harbors.append(harbor_data)
        
        return web_harbors
    
    def _get_points_info(self) -> List[Dict[str, Any]]:
        """
        Get complete information about all points on the board.
        CRITICAL FOR AI - provides board structure and connectivity.
        
        Returns:
            List of point definitions with adjacency information
        """
        points_info = []
        
        for point_id in board_definition.get_all_point_ids():
            point_def = board_definition.points.get(point_id)
            if point_def:
                points_info.append({
                    'point_id': point_id,
                    'game_coords': list(point_def.game_coords),
                    'adjacent_points': point_def.adjacent_points,  # Which points connect via roads
                    'adjacent_hexes': point_def.adjacent_hexes,    # Which hexes touch this point
                    'pixel_coords': list(point_def.pixel_coords)   # For visualization
                })
        
        return points_info
    
    def _get_board_graph(self) -> Dict[str, Any]:
        """
        Get the board as a graph structure for AI pathfinding and strategy.
        
        Returns:
            Graph representation with nodes (points) and edges (possible roads)
        """
        # Create adjacency list for quick lookup
        adjacency = {}
        for point_id in board_definition.get_all_point_ids():
            point_def = board_definition.points.get(point_id)
            if point_def:
                adjacency[point_id] = point_def.adjacent_points
        
        # Get hex-to-points mapping for resource strategy
        hex_to_points = {}
        for hex_id in board_definition.get_all_hex_ids():
            hex_def = board_definition.hexes.get(hex_id)
            if hex_def:
                hex_to_points[hex_id] = hex_def.adjacent_points
        
        return {
            'adjacency': adjacency,  # point_id -> [connected_point_ids]
            'hex_to_points': hex_to_points,  # hex_id -> [point_ids_on_hex]
            'total_points': len(board_definition.points),
            'total_hexes': len(board_definition.hexes)
        }
    
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
            
            resources = {
                'wood': 0,
                'brick': 0,
                'sheep': 0,
                'wheat': 0,
                'ore': 0,
            }
            resource_names = {
                'wood': 'wood',
                'lumber': 'wood',
                'brick': 'brick',
                'sheep': 'sheep',
                'wool': 'sheep',
                'wheat': 'wheat',
                'grain': 'wheat',
                'ore': 'ore',
            }
            for card_name in cards_list:
                normalized = resource_names.get(card_name.lower())
                if normalized:
                    resources[normalized] += 1
            
            # Get dev cards list
            dev_cards_list = []
            if hasattr(player, 'dev_cards'):
                for card in player.dev_cards:
                    # Handle DevCard enum
                    card_name = card.name if hasattr(card, 'name') else str(card)
                    if "." in card_name:
                        card_name = card_name.split(".")[-1]
                    dev_cards_list.append(card_name)
            
            # Get chat message if available
            chat_message = None
            if hasattr(self, 'player_chat_messages') and player_name in self.player_chat_messages:
                chat_message = self.player_chat_messages[player_name]
            
            player_data = {
                'id': i,
                'name': player_name,
                'victory_points': getattr(player, 'victory_points', 0),
                'total_cards': len(getattr(player, 'cards', [])),
                'resources': resources,
                'cards_list': cards_list,
                'dev_cards_list': dev_cards_list,
                'settlements': len(getattr(player, 'settlements', [])),
                'cities': len(getattr(player, 'cities', [])),
                'roads': len(getattr(player, 'roads', [])),
                'longest_road': getattr(player, 'longest_road_length', 0),
                'has_longest_road': getattr(player, 'has_longest_road', False),
                'knights': getattr(player, 'knight_cards', 0),
                'knights_played': getattr(player, 'knights_played', getattr(player, 'knight_cards', 0)),
                'has_largest_army': getattr(player, 'has_largest_army', False),
                'chat_message': chat_message  # Add chat message for display
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

    def enable_replay_mode(
        self,
        source_session: str = "",
        delay_seconds: float = 2.5,
        speech_callback=None,
        speech_prepare_callback=None,
        speech_play_callback=None,
        text_lead_seconds: float = 0.25
    ) -> None:
        """Enable browser-controlled replay timeline mode."""
        self.replay_enabled = True
        self.replay_source_session = source_session
        self.replay_delay_seconds = delay_seconds
        self.replay_text_lead_seconds = max(0.0, text_lead_seconds)
        self.replay_speech_prepare_callback = speech_prepare_callback or speech_callback
        self.replay_speech_play_callback = speech_play_callback or speech_callback
        self.replay_timeline = []
        self.replay_index = 0

    def capture_replay_snapshot(
        self,
        label: str = "",
        decision: Optional[Dict[str, Any]] = None
    ) -> None:
        """Capture the current board/log/chat UI state as a seekable snapshot."""
        if not self.replay_enabled:
            return

        snapshot = {
            "index": len(self.replay_timeline),
            "label": label,
            "decision": copy.deepcopy(decision or {}),
            "game_state": copy.deepcopy(self.current_game_state),
            "action_history": copy.deepcopy(self.action_history),
            "chat_history": copy.deepcopy(self.chat_history),
            "timestamp": datetime.now().isoformat(),
        }
        self.replay_timeline.append(snapshot)

    def get_replay_status(self) -> Dict[str, Any]:
        """Return replay metadata and lightweight snapshot labels."""
        return {
            "enabled": self.replay_enabled,
            "source_session": self.replay_source_session,
            "delay_seconds": self.replay_delay_seconds,
            "index": self.replay_index,
            "total": len(self.replay_timeline),
            "snapshots": [
                {
                    "index": item["index"],
                    "label": item.get("label", ""),
                    "decision": item.get("decision", {}),
                    "action_count": len(item.get("action_history") or []),
                    "chat_count": len(item.get("chat_history") or []),
                }
                for item in self.replay_timeline
            ],
        }

    def get_replay_analysis(self, index: int) -> Optional[Dict[str, Any]]:
        """Return AI decision analysis for the snapshot at index."""
        if not self.replay_enabled or not self.replay_timeline:
            return None

        index = max(0, min(index, len(self.replay_timeline) - 1))
        snapshot = self.replay_timeline[index]
        decision = snapshot.get("decision") or {}
        if not decision:
            return {
                "available": False,
                "index": index,
                "total": len(self.replay_timeline),
                "message": "This replay point does not contain an AI decision.",
            }

        latest_action = self._snapshot_latest_action(snapshot)
        analysis = build_decision_analysis(
            Path(self.replay_source_session or "."),
            decision,
            action_result=latest_action,
        )
        analysis["index"] = index
        analysis["total"] = len(self.replay_timeline)
        analysis["replay_label"] = snapshot.get("label", "")
        analysis["turn_flow"] = build_turn_flow(
            Path(self.replay_source_session or "."),
            self._collect_turn_decision_items(index),
        )
        return analysis

    def seek_replay(self, index: int, speak: bool = False) -> Optional[Dict[str, Any]]:
        """Restore a captured replay snapshot and broadcast the restored UI state."""
        if not self.replay_enabled or not self.replay_timeline:
            return None

        index = max(0, min(index, len(self.replay_timeline) - 1))
        previous_index = self.replay_index
        previous_snapshot = (
            self.replay_timeline[previous_index]
            if 0 <= previous_index < len(self.replay_timeline)
            else None
        )
        previous_chat_count = (
            len(self.replay_timeline[previous_index].get("chat_history") or [])
            if 0 <= previous_index < len(self.replay_timeline)
            else 0
        )

        snapshot = self.replay_timeline[index]

        messages_to_speak = []
        if speak and index > previous_index:
            new_messages = (snapshot.get("chat_history") or [])[previous_chat_count:]
            for chat in new_messages:
                player_name = chat.get("player_name")
                message = chat.get("message")
                if player_name and message:
                    messages_to_speak.append((player_name, message))

        def apply_snapshot_state(
            source_snapshot: Dict[str, Any],
            phase: str = "action",
            chat_history: Optional[List[Dict[str, Any]]] = None,
            action_history: Optional[List[Dict[str, Any]]] = None,
            game_state: Optional[Dict[str, Any]] = None
        ) -> Dict[str, Any]:
            self.replay_index = index
            self.current_game_state = copy.deepcopy(
                game_state if game_state is not None else source_snapshot.get("game_state")
            )
            self.action_history = copy.deepcopy(
                action_history if action_history is not None else source_snapshot.get("action_history") or []
            )
            self.chat_history = copy.deepcopy(
                chat_history if chat_history is not None else source_snapshot.get("chat_history") or []
            )

            self.player_chat_messages = {}
            for chat in self.chat_history[-20:]:
                player_name = chat.get("player_name")
                message = chat.get("message")
                if player_name and message:
                    self.player_chat_messages[player_name] = message

            return {
                "index": self.replay_index,
                "total": len(self.replay_timeline),
                "label": source_snapshot.get("label", ""),
                "decision": source_snapshot.get("decision", {}),
                "game_state": self.current_game_state,
                "action_history": self.action_history,
                "chat_history": self.chat_history,
                "delay_seconds": self.replay_delay_seconds,
                "phase": phase,
            }

        # Wait until the audio is available before painting the action. Playback
        # then runs before the final action snapshot is painted, keeping table
        # talk visibly ahead of the game move that belongs to it.
        if messages_to_speak and self.replay_speech_prepare_callback:
            for player_name, message in messages_to_speak:
                self.replay_speech_prepare_callback(player_name, message)

        if messages_to_speak and previous_snapshot:
            speech_payload = apply_snapshot_state(
                snapshot,
                phase="speech",
                chat_history=snapshot.get("chat_history") or [],
                action_history=previous_snapshot.get("action_history") or [],
                game_state=previous_snapshot.get("game_state"),
            )
            self._broadcast_to_clients({
                "type": "replay_seek",
                "payload": speech_payload,
            })
            time.sleep(self.replay_text_lead_seconds)

        if messages_to_speak and self.replay_speech_play_callback:
            for player_name, message in messages_to_speak:
                self.replay_speech_play_callback(player_name, message)

        payload = apply_snapshot_state(snapshot, phase="action")
        self._broadcast_to_clients({
            "type": "replay_seek",
            "payload": payload,
        })

        return payload

    def _snapshot_latest_action(self, snapshot: Dict[str, Any]) -> Dict[str, Any]:
        actions = snapshot.get("action_history") or []
        return copy.deepcopy(actions[-1]) if actions else {}

    def _collect_turn_decision_items(self, index: int) -> List[Dict[str, Any]]:
        """Collect snapshot decisions that belong to the same player turn."""
        if not (0 <= index < len(self.replay_timeline)):
            return []

        target_snapshot = self.replay_timeline[index]
        target_decision = target_snapshot.get("decision") or {}
        target_action = self._snapshot_latest_action(target_snapshot)
        target_turn = target_action.get("turn_number")
        target_player = target_decision.get("player_name")

        items: List[Dict[str, Any]] = []
        for snap in self.replay_timeline:
            decision = snap.get("decision") or {}
            if not decision:
                continue
            action = self._snapshot_latest_action(snap)
            same_turn = (
                target_turn not in (None, 0)
                and action.get("turn_number") == target_turn
            )
            same_setup_player = (
                target_turn in (None, 0)
                and decision.get("player_name") == target_player
                and snap.get("index") == index
            )
            if same_turn or same_setup_player:
                items.append({
                    "snapshot_index": snap.get("index"),
                    "label": snap.get("label", ""),
                    "decision": decision,
                    "action_result": action,
                })

        if not items:
            items.append({
                "snapshot_index": index,
                "label": target_snapshot.get("label", ""),
                "decision": target_decision,
                "action_result": target_action,
            })
        return items
    
    def _map_action_to_event(self, action: Action, result: ActionResult) -> tuple:
        """
        Map ActionType to EventType and extract relevant data.
        Returns: (EventType, data_dict)
        """
        from pycatan.management.actions import ActionType as AT
        
        event_data = {}
        
        # Extract common parameters
        params = action.parameters if hasattr(action, 'parameters') else {}
        
        if action.action_type == AT.BUILD_SETTLEMENT or action.action_type == AT.PLACE_STARTING_SETTLEMENT:
            event_type = EventType.BUILD_SETTLEMENT
            event_data['point'] = params.get('point', '?')
            event_data['is_starting'] = action.action_type == AT.PLACE_STARTING_SETTLEMENT
            if result.success and 'cost' in params:
                event_data['cost'] = params['cost']
        
        elif action.action_type == AT.BUILD_CITY:
            event_type = EventType.BUILD_CITY
            event_data['point'] = params.get('point', '?')
            if result.success and 'cost' in params:
                event_data['cost'] = params['cost']
        
        elif action.action_type == AT.BUILD_ROAD or action.action_type == AT.PLACE_STARTING_ROAD:
            event_type = EventType.BUILD_ROAD
            event_data['points'] = params.get('points', ['?', '?'])
            event_data['is_starting'] = action.action_type == AT.PLACE_STARTING_ROAD
            if result.success and 'cost' in params:
                event_data['cost'] = params['cost']
        
        elif action.action_type == AT.BUY_DEV_CARD:
            event_type = EventType.BUY_DEV_CARD
            event_data['card'] = params.get('card', 'Unknown')
            if result.success:
                event_data['cost'] = ['ORE', 'SHEEP', 'WHEAT']
        
        elif action.action_type == AT.USE_DEV_CARD:
            event_type = EventType.USE_DEV_CARD
            event_data['card'] = params.get('card_type', 'Unknown')
            if 'details' in params:
                event_data['details'] = params['details']
            for key in (
                'resource_type',
                'resource',
                'resources',
                'gained',
                'taken',
                'total_stolen',
                'roads',
                'robber_tile',
                'victim',
                'victim_id',
                'stolen_card',
            ):
                if key in params:
                    event_data[key] = params[key]
        
        elif action.action_type == AT.ROLL_DICE:
            event_type = EventType.DICE_ROLL
            event_data['dice'] = params.get('dice', [0, 0])
            event_data['total'] = sum(event_data['dice'])
        
        elif action.action_type == AT.ROBBER_MOVE:
            event_type = EventType.ROBBER_MOVE
            event_data['tile'] = params.get('tile', '?')
            if 'victim' in params:
                event_data['victim'] = params['victim']
            if 'victim_id' in params:
                event_data['victim_id'] = params['victim_id']
            stolen_card = params.get('stolen_card') or params.get('card')
            if stolen_card:
                event_data['card'] = stolen_card
        
        elif action.action_type == AT.TRADE_BANK:
            event_type = EventType.TRADE_BANK
            event_data['give'] = params.get('give') or params.get('offer', {})
            event_data['receive'] = params.get('receive') or params.get('request', {})
            if 'rate' in params:
                event_data['rate'] = params['rate']
        
        elif action.action_type == AT.TRADE_PROPOSE:
            trade_status = params.get('trade_status')
            if trade_status == 'accepted':
                event_type = EventType.TRADE_EXECUTE
            elif trade_status == 'rejected':
                event_type = EventType.TRADE_RESPONSE
                event_data['response'] = 'REJECT'
            else:
                event_type = EventType.TRADE_PROPOSE
            event_data['to_player'] = params.get('to_player', '?')
            event_data['offer'] = params.get('offer', {})
            event_data['request'] = params.get('request', {})
            if trade_status:
                event_data['trade_status'] = trade_status
            if 'trade_id' in params:
                event_data['trade_id'] = params['trade_id']
        
        elif action.action_type in [AT.TRADE_ACCEPT, AT.TRADE_REJECT]:
            event_type = EventType.TRADE_RESPONSE
            event_data['response'] = 'ACCEPT' if action.action_type == AT.TRADE_ACCEPT else 'REJECT'
        
        elif action.action_type == AT.DISCARD_CARDS:
            event_type = EventType.DISCARD_CARDS
            event_data['cards'] = params.get('cards', [])
            event_data['discarded'] = params.get('discarded', {})
            event_data['count'] = len(event_data['cards'])

        elif action.action_type == AT.STEAL_CARD:
            event_type = EventType.ROBBER_STEAL
            event_data['victim_id'] = params.get('victim_id') or params.get('target_player')
            event_data['victim'] = params.get('victim', '?')
            event_data['card'] = params.get('stolen_card') or params.get('card') or 'unknown'
        
        elif action.action_type == AT.END_TURN:
            event_type = EventType.TURN_END
            # Add player state at end of turn
            if 'player_state' in params:
                ps = params['player_state']
                event_data['vp'] = ps.get('victory_points', 0)
                event_data['cards'] = ps.get('card_count', 0)
                event_data['roads'] = ps.get('roads', 0)
                event_data['settlements'] = ps.get('settlements', 0)
                event_data['cities'] = ps.get('cities', 0)
        
        else:
            # Generic action
            event_type = EventType.ACTION_FAILED if not result.success else EventType.TURN_START
            event_data['action'] = action.action_type.name
        
        return event_type, event_data
    
    def notify_action(self, action: Action, result: ActionResult):
        """Notify web clients of action execution."""
        # Get player name from action parameters (added by GameManager)
        player_name = action.parameters.get('player_name', f'Player {action.player_id + 1}') if hasattr(action, 'parameters') and action.parameters else f'Player {action.player_id + 1}'
        
        # Debug: Print action to console
        status = "✓" if result.success else "✗"
        print(f"[ACTION] {status} {player_name}: {action.action_type.name}")
        
        # Map ActionType to EventType and extract relevant data
        event_type, event_data = self._map_action_to_event(action, result)
        
        # Get turn number from action parameters (added by GameManager)
        turn_number = action.parameters.get('turn_number', 0) if hasattr(action, 'parameters') and action.parameters else 0
        
        # Create structured log entry
        log_entry = create_log_entry(
            event_type=event_type,
            turn=turn_number,
            player_id=action.player_id,
            player_name=player_name,
            data=event_data,
            status="SUCCESS" if result.success else "FAIL",
            error=result.error_message if not result.success else None
        )
        
        # Store log entry
        self.log_entries.append(log_entry)
        if len(self.log_entries) > 100:
            self.log_entries = self.log_entries[-100:]
        
        # Create display data from log entry
        action_data = {
            'timestamp': log_entry.timestamp.strftime("%H:%M:%S.%f")[:-3],
            'turn_number': turn_number,
            'action_type': action.action_type.name,
            'event_type': event_type.value,
            'player': action.player_id,
            'player_name': player_name,
            'success': result.success,
            'message': log_entry.to_human_string(),
            'structured': log_entry.to_log_string(),
            'data': event_data
        }
        
        # Add to history
        self.action_history.append(action_data)
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
    
    def log_event(self, log_entry: LogEntry):
        """
        Log a structured event directly.
        This allows GameManager to send detailed log entries.
        """
        # Store log entry
        self.log_entries.append(log_entry)
        if len(self.log_entries) > 100:
            self.log_entries = self.log_entries[-100:]
        
        # Create display data
        event_data = {
            'timestamp': log_entry.timestamp.strftime("%H:%M:%S.%f")[:-3],
            'event_type': log_entry.event_type.value,
            'turn': log_entry.turn,
            'player_id': log_entry.player_id,
            'player_name': log_entry.player_name,
            'success': log_entry.status == "SUCCESS",
            'status': log_entry.status,
            'message': log_entry.to_human_string(),
            'structured': log_entry.to_log_string(),
            'data': log_entry.data,
            'error': log_entry.error
        }
        
        # Add to BOTH histories so it appears in the action log
        self.event_history.append(event_data)
        if len(self.event_history) > 100:
            self.event_history = self.event_history[-100:]
        
        # Also add to action_history for display in UI
        self.action_history.append(event_data)
        if len(self.action_history) > 100:
            self.action_history = self.action_history[-100:]
        
        # Broadcast to web clients
        self._broadcast_to_clients({
            'type': 'log_event',
            'payload': event_data
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
        # Create structured log entry
        log_entry = create_log_entry(
            event_type=EventType.TURN_START,
            turn=turn_number,
            player_name=player_name,
            data={'phase': 'MAIN'}
        )
        
        # Use the log_event method
        self.log_event(log_entry)
    
    def display_dice_roll(self, player_name: str, dice_values: List[int], total: int) -> None:
        """Display dice roll results (ConsoleVisualization interface)."""
        # Create structured log entry
        log_entry = create_log_entry(
            event_type=EventType.DICE_ROLL,
            turn=0,  # Turn number will be set by GameManager
            player_name=player_name,
            data={
                'dice': dice_values,
                'total': total
            }
        )
        
        # Use the log_event method
        self.log_event(log_entry)
    
    def display_resource_distribution(self, distributions: Dict[str, List[str]]) -> None:
        """Display resource distribution (ConsoleVisualization interface)."""
        # The Visualization contract is {player_name: [resource, ...]}.
        # Older web code treated the key as a resource name, which produced
        # messages like "Player 0: 1xJimmy" when the key was actually a player.
        for player_name, resources in distributions.items():
            if not resources:
                continue
            resource_counts = dict(Counter(str(resource) for resource in resources))
            log_entry = create_log_entry(
                event_type=EventType.RESOURCE_DIST,
                turn=0,  # Turn number will be set by GameManager
                player_name=player_name,
                data={
                    'resources': resource_counts,
                    'total': len(resources)
                }
            )
            self.log_event(log_entry)
        
        # Keep compatibility with old event history format
        timestamp = datetime.now().strftime("%H:%M:%S")
        distribution_data = {
            'timestamp': timestamp,
            'distributions': distributions,
            'message': "Resources distributed to players"
        }
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
    
    def display_winner(self, player_name: str, player_id: int, victory_points: int) -> None:
        """Display game winner announcement."""
        timestamp = datetime.now().strftime("%H:%M:%S")
        
        winner_data = {
            'timestamp': timestamp,
            'player_name': player_name,
            'player_id': player_id,
            'victory_points': victory_points,
            'message': f"🎉 {player_name} has won with {victory_points} victory points! 🎉"
        }
        
        # Get turn number safely (handle both dict and GameState object)
        turn_number = 0
        if self.current_game_state:
            if isinstance(self.current_game_state, dict):
                turn_number = self.current_game_state.get('turn_number', 0)
            else:
                turn_number = getattr(self.current_game_state, 'turn_number', 0)
        
        # Create structured log entry
        log_entry = create_log_entry(
            event_type=EventType.GAME_END,
            turn=turn_number,
            player_id=player_id,
            player_name=player_name,
            data={
                'victory_points': victory_points,
                'winner': player_name
            },
            status="SUCCESS"
        )
        self.log_entries.append(log_entry)
        
        # Add to event history  
        self.event_history.append({
            'type': 'game_end',
            'timestamp': timestamp,
            'data': winner_data
        })
        
        # Broadcast to web clients
        self._broadcast_to_clients({
            'type': 'game_winner',
            'payload': winner_data
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
