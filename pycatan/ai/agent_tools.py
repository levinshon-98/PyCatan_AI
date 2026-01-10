"""
Agent Tools - Helper functions for LLM AI Agents

This module provides tools that the LLM can use to help make better decisions.
These tools are designed to PREVENT HALLUCINATIONS by providing processed information
rather than forcing the LLM to interpret raw data structures.

Tools available:
1. inspect_node - Get detailed info about a specific node (prevents hallucinations)
2. find_best_nodes - Search for nodes by criteria (prevents missing opportunities)
3. analyze_path_potential - Analyze road building potential (helps with strategy)
"""

from typing import Dict, Any, List, Optional, Set, Tuple


# Pip values (dots on tiles): represents probability of each dice number
PIP_VALUES = {
    2: 1, 3: 2, 4: 3, 5: 4, 6: 5,
    8: 5, 9: 4, 10: 3, 11: 2, 12: 1
}


class AgentTools:
    """
    Collection of helper tools for AI agents.
    
    These tools are designed to PREVENT HALLUCINATIONS by providing
    the LLM with processed, accurate information rather than forcing
    it to interpret complex data structures (Arrays N and H).
    
    Key principle: The LLM asks questions, the tools provide answers.
    """
    
    def __init__(self, game_state: Optional[Dict[str, Any]] = None):
        """
        Initialize agent tools with game state.
        
        Args:
            game_state: Current game state dictionary (from state_optimizer)
        """
        self.game_state = game_state or {}
        self._update_internal_structures()
    
    def update_game_state(self, game_state: Dict[str, Any]):
        """
        Update the game state (called each turn).
        
        Args:
            game_state: New game state dictionary
        """
        self.game_state = game_state
        self._update_internal_structures()
    
    def _update_internal_structures(self):
        """
        Build internal lookup structures from game state for fast queries.
        
        Supports the COMPACT format from state_optimizer:
        - H: Array of hex data. H[id] = "W12" (Wood, number 12)
        - N: Array of node data. N[id] = [[neighbors], [hex_ids], port?]
        - state: {"bld": [[node, owner, type], ...], "rds": [[[from,to], owner], ...]}
        
        Resource codes: W=Wood, B=Brick, S=Sheep, Wh=Wheat, O=Ore, D=Desert
        Port codes: ?3=Any 3:1, W2=Wood 2:1, etc.
        """
        # Resource code mapping (compact -> full name)
        RES_DECODE = {"W": "Wood", "B": "Brick", "S": "Sheep", "Wh": "Wheat", "O": "Ore", "D": "Desert"}
        
        # Extract compact arrays
        self.H = self.game_state.get("H", [])  # Hex array
        self.N = self.game_state.get("N", [])  # Node array  
        self.state = self.game_state.get("state", {})  # Buildings & roads
        
        # Build hex lookup: hex_id -> {type, number}
        self.tile_lookup: Dict[int, Dict[str, Any]] = {}
        for hex_id, hex_val in enumerate(self.H):
            if hex_val:  # Skip empty entries
                # Parse "W12" -> type="Wood", number=12
                # Or "D" -> type="Desert", number=0
                resource_code = ""
                number = 0
                
                # Handle "Wh" (2 char) vs "W" (1 char)
                if hex_val.startswith("Wh"):
                    resource_code = "Wh"
                    num_str = hex_val[2:]
                elif len(hex_val) >= 1:
                    resource_code = hex_val[0]
                    num_str = hex_val[1:]
                
                if num_str.isdigit():
                    number = int(num_str)
                
                self.tile_lookup[hex_id] = {
                    "type": RES_DECODE.get(resource_code, resource_code),
                    "number": number
                }
        
        # Build buildings lookup from state.bld: [[node, owner, type], ...]
        self.buildings: Dict[int, Dict[str, Any]] = {}  # node_id -> building info
        for bld in self.state.get("bld", []):
            if len(bld) >= 3:
                node_id, owner, bld_type = bld[0], bld[1], bld[2]
                self.buildings[node_id] = {
                    "owner": owner,
                    "type": "settlement" if bld_type == "S" else "city"
                }
        
        # Build node lookup: node_id -> node_data (converted from compact format)
        self.node_lookup: Dict[int, Dict[str, Any]] = {}
        for node_id, node_val in enumerate(self.N):
            if node_val is not None:  # Skip null entries (index 0 is often null)
                # N[id] = [[neighbors], [hex_ids], port?]
                neighbors = node_val[0] if len(node_val) > 0 else []
                hex_ids = node_val[1] if len(node_val) > 1 else []
                port = node_val[2] if len(node_val) > 2 else None
                
                # Check if this node has a building
                building = self.buildings.get(node_id)
                
                self.node_lookup[node_id] = {
                    "id": node_id,
                    "neighbors": neighbors,
                    "adjacent_tiles": hex_ids,
                    "port": port,
                    "building": building
                }
        
        # For backwards compatibility
        self.nodes = list(self.node_lookup.values())
        self.tiles = list(self.tile_lookup.values())
    
    
    # ========== TOOL 1: Inspect Node (Prevents Hallucinations) ==========
    
    def inspect_node(self, node_id: int, reasoning: str = "") -> Dict[str, Any]:
        """
        Get detailed, processed information about a specific node.
        
        CRITICAL: This prevents hallucinations!
        Instead of the LLM trying to interpret Arrays N and H, it asks this tool
        for accurate information about a specific node.
        
        Args:
            node_id: The node ID to inspect (e.g., 10, 18, 40)
            reasoning: LLM's explanation for why it's inspecting this node
            
        Returns:
            Dictionary with complete node information
        """
        # Check if node exists
        if node_id not in self.node_lookup:
            return {
                "node_id": node_id,
                "exists": False,
                "error": f"Node {node_id} does not exist on the board",
                "llm_reasoning": reasoning
            }
        
        node = self.node_lookup[node_id]
        
        # Extract resources and calculate pips
        resources = {}
        resources_detailed = []  # List of all resources with their numbers
        total_pips = 0
        
        adjacent_tiles = node.get("adjacent_tiles", [])
        for tile_id in adjacent_tiles:
            if tile_id in self.tile_lookup:
                tile = self.tile_lookup[tile_id]
                resource = tile.get("type", "")
                number = tile.get("number", 0)
                
                # Skip desert
                if resource.lower() != "desert" and number > 0:
                    # Add to detailed list
                    resources_detailed.append({
                        "type": resource,
                        "number": number,
                        "pips": PIP_VALUES.get(number, 0)
                    })
                    # Keep aggregated format for backwards compatibility
                    if resource not in resources:
                        resources[resource] = []
                    resources[resource].append(number)
                    total_pips += PIP_VALUES.get(number, 0)
        
        # Check for port
        port = node.get("port")
        if port:
            # Normalize port format
            if isinstance(port, dict):
                port = port.get("type", None)
        
        # Check if occupied
        building = node.get("building")
        occupied = building is not None
        occupied_by = None
        building_type = None
        
        if building:
            occupied_by = building.get("owner", "Unknown")
            building_type = building.get("type", "settlement")
        
        # Get neighbors
        neighbors = node.get("neighbors", [])
        
        # Check if can build here
        can_build_here = not occupied
        blocked_reason = None
        
        if occupied:
            blocked_reason = f"Occupied by {occupied_by}'s {building_type}"
        else:
            # Check distance rule (no buildings within 1 edge)
            for neighbor_id in neighbors:
                if neighbor_id in self.node_lookup:
                    neighbor_building = self.node_lookup[neighbor_id].get("building")
                    if neighbor_building:
                        can_build_here = False
                        neighbor_owner = neighbor_building.get("owner", "someone")
                        blocked_reason = f"Too close to {neighbor_owner}'s building at node {neighbor_id}"
                        break
        
        return {
            "node_id": node_id,
            "exists": True,
            "resources": resources,  # {"Wheat": [9, 6, 9], "Ore": [5]}
            "resources_detailed": resources_detailed,  # [{"type": "Wheat", "number": 9, "pips": 4}, ...]
            "total_pips": total_pips,
            "port": port,
            "neighbors": neighbors,
            "occupied": occupied,
            "occupied_by": occupied_by,
            "building_type": building_type,
            "can_build_here": can_build_here,
            "blocked_reason": blocked_reason,
            "llm_reasoning": reasoning
        }
    
    
    # ========== TOOL 2: Find Best Nodes (Prevents Missing Opportunities) ==========
    
    def find_best_nodes(
        self,
        reasoning: str = "",
        min_pips: int = 0,
        must_have_resource: Optional[str] = None,
        exclude_blocked: bool = True,
        prefer_port: bool = False,
        limit: int = 10
    ) -> Dict[str, Any]:
        """
        Search for the best nodes on the board based on criteria.
        
        CRITICAL: This prevents missing opportunities!
        Instead of the LLM trying to visually scan Arrays N and H, it asks this
        tool to find the best positions that match specific criteria.
        
        Args:
            reasoning: LLM's explanation for this search strategy
            min_pips: Minimum total pip value (e.g., 10 for high-probability spots)
            must_have_resource: Required resource type (e.g., "Wheat", "Ore")
            exclude_blocked: Skip nodes that can't be built on
            prefer_port: Sort port nodes higher
            limit: Maximum number of results to return
            
        Returns:
            Dictionary with search results
        """
        matching_nodes = []
        
        # Search all nodes
        for node_id, node in self.node_lookup.items():
            # Get node info using inspect_node
            info = self.inspect_node(node_id)
            
            if not info.get("exists"):
                continue
            
            # Apply filters
            if exclude_blocked and not info.get("can_build_here"):
                continue
            
            total_pips = info.get("total_pips", 0)
            if total_pips < min_pips:
                continue
            
            resources = info.get("resources", {})
            if must_have_resource:
                # Case-insensitive resource check
                has_resource = False
                for res in resources.keys():
                    if res.lower() == must_have_resource.lower():
                        has_resource = True
                        break
                if not has_resource:
                    continue
            
            # Calculate score
            score = total_pips
            
            # Resource diversity bonus
            score += len(resources) * 0.5
            
            # Port bonus
            if info.get("port"):
                score += 2.0
                if info.get("port") != "3:1":
                    score += 0.5  # Specialized port
            
            matching_nodes.append({
                "node_id": node_id,
                "resources": resources,  # {"Wheat": [9, 6, 9], "Ore": [5]}
                "resources_detailed": info.get("resources_detailed", []),  # Full details
                "total_pips": total_pips,
                "port": info.get("port"),
                "neighbors": info.get("neighbors", []),
                "score": round(score, 1),
                "can_build": info.get("can_build_here", False),
                "occupied": info.get("occupied", False)
            })
        
        # Sort by score (and prefer ports if requested)
        if prefer_port:
            matching_nodes.sort(
                key=lambda n: (n["port"] is not None, n["score"]),
                reverse=True
            )
        else:
            matching_nodes.sort(key=lambda n: n["score"], reverse=True)
        
        # Limit results
        total_found = len(matching_nodes)
        matching_nodes = matching_nodes[:limit]
        
        return {
            "llm_reasoning": reasoning,
            "query": {
                "min_pips": min_pips,
                "must_have_resource": must_have_resource,
                "exclude_blocked": exclude_blocked,
                "prefer_port": prefer_port
            },
            "total_found": total_found,
            "nodes": matching_nodes
        }
    
    
    # ========== TOOL 3: Analyze Path Potential (Helps with Road Strategy) ==========
    
    def analyze_path_potential(
        self,
        from_node: int,
        reasoning: str = "",
        direction_node: Optional[int] = None,
        max_depth: int = 2
    ) -> Dict[str, Any]:
        """
        Analyze the potential of building roads in a direction.
        
        CRITICAL: This helps with road-building strategy!
        Instead of the LLM guessing where roads lead, this tool shows exactly
        what opportunities exist 1-2 steps ahead (ports, high-value nodes, etc.)
        
        Args:
            from_node: Starting node ID
            reasoning: LLM's explanation for analyzing this path
            direction_node: Target direction (neighbor node ID), or None to check all directions
            max_depth: How many steps ahead to look (1 or 2)
            
        Returns:
            Dictionary with path analysis
        """
        # Get starting node info
        from_info = self.inspect_node(from_node, reasoning="Internal call for path analysis")
        if not from_info.get("exists"):
            return {
                "error": f"Starting node {from_node} does not exist",
                "from_node": from_node,
                "llm_reasoning": reasoning
            }
        
        neighbors = from_info.get("neighbors", [])
        
        # If specific direction given, only analyze that one
        if direction_node is not None:
            if direction_node not in neighbors:
                return {
                    "error": f"Node {direction_node} is not a neighbor of {from_node}",
                    "from_node": from_node,
                    "neighbors": neighbors,
                    "llm_reasoning": reasoning
                }
            neighbors = [direction_node]
        
        paths = []
        
        for neighbor_id in neighbors:
            path_analysis = {
                "direction": neighbor_id,
                "depth_1": None,
                "depth_2": None,
                "highlights": [],
                "score": 0.0
            }
            
            # Depth 1: Immediate neighbor
            depth_1_info = self.inspect_node(neighbor_id, reasoning="Internal call for path analysis depth 1")
            if depth_1_info.get("exists"):
                path_analysis["depth_1"] = {
                    "node_id": neighbor_id,
                    "resources": depth_1_info.get("resources", {}),
                    "total_pips": depth_1_info.get("total_pips", 0),
                    "port": depth_1_info.get("port"),
                    "can_build": depth_1_info.get("can_build_here", False),
                    "occupied": depth_1_info.get("occupied", False)
                }
                
                # Score based on depth 1
                score = depth_1_info.get("total_pips", 0) * 1.0  # Full weight
                
                # Highlights
                if depth_1_info.get("port"):
                    path_analysis["highlights"].append(
                        f"Port ({depth_1_info['port']}) at depth 1"
                    )
                    score += 3.0
                
                if depth_1_info.get("total_pips", 0) >= 12:
                    path_analysis["highlights"].append("High-value node at depth 1")
                
                if depth_1_info.get("can_build_here"):
                    path_analysis["highlights"].append("Can build settlement at depth 1")
                    score += 1.0
                
                # Depth 2: Look ahead one more step
                if max_depth >= 2:
                    depth_2_neighbors = depth_1_info.get("neighbors", [])
                    reachable_nodes = []
                    best_node = None
                    best_pips = 0
                    
                    for depth_2_id in depth_2_neighbors:
                        if depth_2_id == from_node:  # Don't go back
                            continue
                        
                        depth_2_info = self.inspect_node(depth_2_id, reasoning="Internal call for path analysis depth 2")
                        if depth_2_info.get("exists"):
                            node_data = {
                                "node_id": depth_2_id,
                                "total_pips": depth_2_info.get("total_pips", 0),
                                "port": depth_2_info.get("port"),
                                "can_build": depth_2_info.get("can_build_here", False)
                            }
                            reachable_nodes.append(node_data)
                            
                            # Track best
                            pips = depth_2_info.get("total_pips", 0)
                            if pips > best_pips:
                                best_pips = pips
                                best_node = depth_2_id
                            
                            # Highlights at depth 2
                            if depth_2_info.get("port"):
                                path_analysis["highlights"].append(
                                    f"Port ({depth_2_info['port']}) at depth 2 (node {depth_2_id})"
                                )
                                score += 1.5
                            
                            if pips >= 12:
                                path_analysis["highlights"].append(
                                    f"High-value node at depth 2 (node {depth_2_id}, {pips} pips)"
                                )
                    
                    path_analysis["depth_2"] = {
                        "reachable_nodes": reachable_nodes,
                        "best_node": best_node,
                        "best_pips": best_pips
                    }
                    
                    # Add partial score for depth 2 (50% weight)
                    score += best_pips * 0.5
                
                path_analysis["score"] = round(score, 1)
            
            paths.append(path_analysis)
        
        # Sort by score
        paths.sort(key=lambda p: p["score"], reverse=True)
        
        return {
            "llm_reasoning": reasoning,
            "from_node": from_node,
            "total_directions": len(paths),
            "paths": paths
        }
    
    
    # ========== Tool Registration for LLM ==========
    
    def get_tools_schema(self) -> List[Dict[str, Any]]:
        """
        Get tool definitions in a format suitable for LLM function calling.
        
        These schemas can be passed to LLM APIs like OpenAI's function calling,
        Anthropic's tool use, or Google Gemini's function declarations.
        
        Returns:
            List of tool definition dictionaries
        """
        return [
            {
                "name": "inspect_node",
                "description": "Get detailed information about a specific node on the board. USE THIS to verify node data instead of trying to interpret Arrays N and H yourself - this prevents hallucinations!",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "reasoning": {
                            "type": "string",
                            "description": "Explain WHY you're inspecting this specific node. What are you trying to verify or learn?"
                        },
                        "node_id": {
                            "type": "integer",
                            "description": "The node ID to inspect (e.g., 10, 18, 40)"
                        }
                    },
                    "required": ["reasoning", "node_id"]
                }
            },
            {
                "name": "find_best_nodes",
                "description": "Search for the best available nodes matching specific criteria. USE THIS instead of manually scanning the board - prevents missing opportunities!",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "reasoning": {
                            "type": "string",
                            "description": "Explain your search strategy. What kind of position are you looking for and why?"
                        },
                        "min_pips": {
                            "type": "integer",
                            "description": "Minimum total pip value (probability). Good nodes have 10+, excellent have 12+",
                            "default": 0
                        },
                        "must_have_resource": {
                            "type": "string",
                            "description": "Required resource type (e.g., 'Wheat', 'Ore', 'Brick', 'Wood', 'Sheep')",
                            "nullable": True
                        },
                        "exclude_blocked": {
                            "type": "boolean",
                            "description": "Skip nodes that cannot be built on (occupied or too close to other buildings)",
                            "default": True
                        },
                        "prefer_port": {
                            "type": "boolean",
                            "description": "Prioritize nodes with port access",
                            "default": False
                        },
                        "limit": {
                            "type": "integer",
                            "description": "Maximum number of results to return",
                            "default": 10
                        }
                    },
                    "required": ["reasoning"]
                }
            },
            {
                "name": "analyze_path_potential",
                "description": "Analyze where a road path leads and what opportunities exist ahead. USE THIS to plan road building - shows ports and valuable nodes 1-2 steps away!",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "reasoning": {
                            "type": "string",
                            "description": "Explain your road-building strategy. Why analyze this path? What are you hoping to reach?"
                        },
                        "from_node": {
                            "type": "integer",
                            "description": "Starting node ID (where you currently have a settlement/road)"
                        },
                        "direction_node": {
                            "type": "integer",
                            "description": "Specific neighbor to analyze, or omit to see all directions",
                            "nullable": True
                        },
                        "max_depth": {
                            "type": "integer",
                            "description": "How many steps ahead to look (1 or 2)",
                            "default": 2
                        }
                    },
                    "required": ["reasoning", "from_node"]
                }
            }
        ]
    
    
    def execute_tool(
        self,
        tool_name: str,
        parameters: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Execute a tool by name with given parameters.
        
        This is the dispatcher for when the LLM calls a tool.
        
        Args:
            tool_name: Name of the tool to execute
            parameters: Parameters for the tool (as a dictionary)
            
        Returns:
            Tool execution result
            
        Raises:
            ValueError: If tool name is unknown
        """
        if tool_name == "inspect_node":
            return self.inspect_node(**parameters)
        elif tool_name == "find_best_nodes":
            return self.find_best_nodes(**parameters)
        elif tool_name == "analyze_path_potential":
            return self.analyze_path_potential(**parameters)
        else:
            raise ValueError(
                f"Unknown tool: {tool_name}. "
                f"Available tools: inspect_node, find_best_nodes, analyze_path_potential"
            )
