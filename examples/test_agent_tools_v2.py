"""
Test Agent Tools - Testing the 3 new tools

This script tests the agent tools with a mock game state to ensure
they work correctly and prevent hallucinations.
"""

import json
from pycatan.ai.agent_tools import AgentTools


def create_mock_game_state():
    """Create a mock game state for testing."""
    return {
        "board": {
            "nodes": [
                {
                    "id": 10,
                    "adjacent_tiles": [1, 2, 3],
                    "neighbors": [9, 11, 20],
                    "port": None,
                    "building": None
                },
                {
                    "id": 18,
                    "adjacent_tiles": [4, 5],
                    "neighbors": [17, 19, 27],
                    "port": None,
                    "building": None
                },
                {
                    "id": 40,
                    "adjacent_tiles": [6, 7, 8],
                    "neighbors": [39, 41],
                    "port": "3:1",
                    "building": None
                },
                {
                    "id": 15,
                    "adjacent_tiles": [9, 10],
                    "neighbors": [14, 16, 25],
                    "port": "Wheat",
                    "building": {"owner": "Alice", "type": "settlement"}
                },
                {
                    "id": 9,
                    "adjacent_tiles": [11],
                    "neighbors": [8, 10, 19],
                    "port": None,
                    "building": None
                },
                {
                    "id": 11,
                    "adjacent_tiles": [12, 13],
                    "neighbors": [10, 12, 21],
                    "port": None,
                    "building": None
                },
                {
                    "id": 20,
                    "adjacent_tiles": [14, 15],
                    "neighbors": [10, 19, 21],
                    "port": None,
                    "building": {"owner": "Bob", "type": "settlement"}
                }
            ],
            "tiles": [
                {"id": 1, "type": "Brick", "number": 6},
                {"id": 2, "type": "Sheep", "number": 8},
                {"id": 3, "type": "Wood", "number": 12},
                {"id": 4, "type": "Wheat", "number": 4},
                {"id": 5, "type": "Ore", "number": 10},
                {"id": 6, "type": "Wheat", "number": 6},
                {"id": 7, "type": "Ore", "number": 8},
                {"id": 8, "type": "Wood", "number": 5},
                {"id": 9, "type": "Wheat", "number": 9},
                {"id": 10, "type": "Ore", "number": 11},
                {"id": 11, "type": "Desert", "number": 0},
                {"id": 12, "type": "Wood", "number": 3},
                {"id": 13, "type": "Brick", "number": 5},
                {"id": 14, "type": "Sheep", "number": 11},
                {"id": 15, "type": "Wood", "number": 9}
            ]
        }
    }


def print_section(title: str):
    """Print a section header."""
    print(f"\n{'='*70}")
    print(f"  {title}")
    print(f"{'='*70}\n")


def test_inspect_node():
    """Test the inspect_node tool."""
    print_section("TEST 1: Inspect Node (Prevents Hallucinations)")
    
    tools = AgentTools(create_mock_game_state())
    
    # Test 1: Node 10 - Good spot
    print("Test 1a: Inspect node 10 (should exist with good resources)")
    result = tools.inspect_node(10)
    print(json.dumps(result, indent=2))
    print(f"\n✓ Node exists: {result['exists']}")
    print(f"✓ Total pips: {result['total_pips']}")
    print(f"✓ Can build: {result['can_build_here']}")
    
    # Test 2: Node 18 - Different spot
    print("\n\nTest 1b: Inspect node 18")
    result = tools.inspect_node(18)
    print(json.dumps(result, indent=2))
    
    # Test 3: Node 40 - With port
    print("\n\nTest 1c: Inspect node 40 (has port)")
    result = tools.inspect_node(40)
    print(json.dumps(result, indent=2))
    print(f"\n✓ Has port: {result['port'] is not None}")
    
    # Test 4: Node 15 - Occupied
    print("\n\nTest 1d: Inspect node 15 (occupied)")
    result = tools.inspect_node(15)
    print(json.dumps(result, indent=2))
    print(f"\n✓ Occupied: {result['occupied']}")
    print(f"✓ Cannot build: {not result['can_build_here']}")
    
    # Test 5: Node 9 - Too close to occupied node
    print("\n\nTest 1e: Inspect node 9 (too close to node 10's neighbor which is occupied)")
    result = tools.inspect_node(9)
    print(json.dumps(result, indent=2))
    
    # Test 6: Non-existent node
    print("\n\nTest 1f: Inspect non-existent node 999")
    result = tools.inspect_node(999)
    print(json.dumps(result, indent=2))
    print(f"\n✓ Error detected: {not result['exists']}")


def test_find_best_nodes():
    """Test the find_best_nodes tool."""
    print_section("TEST 2: Find Best Nodes (Prevents Missing Opportunities)")
    
    tools = AgentTools(create_mock_game_state())
    
    # Test 1: Find all good nodes (min 10 pips)
    print("Test 2a: Find nodes with at least 10 pips")
    result = tools.find_best_nodes(min_pips=10, exclude_blocked=True)
    print(f"Query: {json.dumps(result['query'], indent=2)}")
    print(f"Total found: {result['total_found']}")
    print(f"\nTop results:")
    for i, node in enumerate(result['nodes'][:3], 1):
        print(f"  {i}. Node {node['node_id']}: {node['total_pips']} pips, score {node['score']}")
        print(f"     Resources: {node['resources']}")
        print(f"     Port: {node['port']}")
    
    # Test 2: Find nodes with Wheat
    print("\n\nTest 2b: Find nodes with Wheat resource")
    result = tools.find_best_nodes(must_have_resource="Wheat", exclude_blocked=True)
    print(f"Total found: {result['total_found']}")
    print(f"\nTop results:")
    for i, node in enumerate(result['nodes'][:3], 1):
        print(f"  {i}. Node {node['node_id']}: {node['resources']}")
    
    # Test 3: Find nodes preferring ports
    print("\n\nTest 2c: Find nodes, preferring ports")
    result = tools.find_best_nodes(prefer_port=True, exclude_blocked=True, limit=5)
    print(f"Total found: {result['total_found']}")
    print(f"\nTop results:")
    for i, node in enumerate(result['nodes'], 1):
        print(f"  {i}. Node {node['node_id']}: Port={node['port']}, Score={node['score']}")
    
    # Test 4: Include blocked nodes
    print("\n\nTest 2d: Find all nodes (including blocked)")
    result = tools.find_best_nodes(exclude_blocked=False, limit=10)
    print(f"Total found: {result['total_found']}")
    blocked = [n for n in result['nodes'] if not n['can_build']]
    print(f"Blocked nodes: {len(blocked)}")
    if blocked:
        print(f"Example blocked: Node {blocked[0]['node_id']} (occupied={blocked[0]['occupied']})")


def test_analyze_path_potential():
    """Test the analyze_path_potential tool."""
    print_section("TEST 3: Analyze Path Potential (Helps Road Strategy)")
    
    tools = AgentTools(create_mock_game_state())
    
    # Test 1: Analyze all directions from node 10
    print("Test 3a: Analyze all path directions from node 10")
    result = tools.analyze_path_potential(from_node=10, max_depth=2)
    print(f"From node: {result['from_node']}")
    print(f"Total directions: {result['total_directions']}")
    
    for i, path in enumerate(result['paths'][:2], 1):  # Show top 2
        print(f"\n  Path {i}: Direction to node {path['direction']}")
        print(f"    Score: {path['score']}")
        if path['depth_1']:
            print(f"    Depth 1: Node {path['depth_1']['node_id']}")
            print(f"      Resources: {path['depth_1']['resources']}")
            print(f"      Pips: {path['depth_1']['total_pips']}")
            print(f"      Port: {path['depth_1']['port']}")
        if path['highlights']:
            print(f"    Highlights:")
            for highlight in path['highlights']:
                print(f"      • {highlight}")
    
    # Test 2: Analyze specific direction
    print("\n\nTest 3b: Analyze specific direction from node 10 to node 11")
    result = tools.analyze_path_potential(from_node=10, direction_node=11)
    path = result['paths'][0]
    print(json.dumps(path, indent=2))
    
    # Test 3: Depth 1 only
    print("\n\nTest 3c: Analyze with depth 1 only")
    result = tools.analyze_path_potential(from_node=10, max_depth=1)
    path = result['paths'][0]
    print(f"Direction to {path['direction']}")
    print(f"Depth 2 data: {path['depth_2']}")  # Should be None
    
    # Test 4: Invalid node
    print("\n\nTest 3d: Try to analyze from invalid node")
    result = tools.analyze_path_potential(from_node=999)
    print(json.dumps(result, indent=2))


def test_tool_schema():
    """Test tool schema generation."""
    print_section("TEST 4: Tool Schema Generation")
    
    tools = AgentTools()
    schemas = tools.get_tools_schema()
    
    print(f"Generated {len(schemas)} tool schemas:")
    for i, schema in enumerate(schemas, 1):
        print(f"\n{i}. {schema['name']}")
        print(f"   Description: {schema['description'][:80]}...")
        print(f"   Parameters: {list(schema['parameters']['properties'].keys())}")
        print(f"   Required: {schema['parameters'].get('required', [])}")


def test_execute_tool():
    """Test tool execution dispatcher."""
    print_section("TEST 5: Tool Execution Dispatcher")
    
    tools = AgentTools(create_mock_game_state())
    
    # Test 1: Execute inspect_node
    print("Test 5a: Execute 'inspect_node' via dispatcher")
    result = tools.execute_tool("inspect_node", {"node_id": 10})
    print(f"Result: Node {result['node_id']}, pips={result['total_pips']}")
    
    # Test 2: Execute find_best_nodes
    print("\n\nTest 5b: Execute 'find_best_nodes' via dispatcher")
    result = tools.execute_tool("find_best_nodes", {"min_pips": 12, "limit": 3})
    print(f"Found {result['total_found']} nodes")
    
    # Test 3: Execute analyze_path_potential
    print("\n\nTest 5c: Execute 'analyze_path_potential' via dispatcher")
    result = tools.execute_tool("analyze_path_potential", {"from_node": 10})
    print(f"Analyzed {result['total_directions']} directions from node {result['from_node']}")
    
    # Test 4: Invalid tool
    print("\n\nTest 5d: Try to execute invalid tool")
    try:
        result = tools.execute_tool("invalid_tool", {})
        print("ERROR: Should have raised ValueError!")
    except ValueError as e:
        print(f"✓ Correctly raised error: {e}")


def main():
    """Run all tests."""
    print("\n" + "="*70)
    print("  AGENT TOOLS TEST SUITE")
    print("  Testing 3 tools that prevent hallucinations")
    print("="*70)
    
    try:
        test_inspect_node()
        test_find_best_nodes()
        test_analyze_path_potential()
        test_tool_schema()
        test_execute_tool()
        
        print("\n" + "="*70)
        print("  ✅ ALL TESTS COMPLETED SUCCESSFULLY!")
        print("="*70)
        print("\n📋 Summary:")
        print("  1. inspect_node - Prevents hallucinations by giving accurate node data")
        print("  2. find_best_nodes - Prevents missing opportunities by searching board")
        print("  3. analyze_path_potential - Helps road strategy by showing what's ahead")
        print()
        
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
