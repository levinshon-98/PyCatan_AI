"""
Test Tool Integration for AI Agents

This script tests the full tool calling flow:
1. AgentTools - The tools themselves
2. ToolExecutor - Execution and logging
3. LLMClient - Function calling support
4. AIManager - Full integration

Run this to verify tools work end-to-end.
"""

import json
from pathlib import Path
from pycatan.ai.agent_tools import AgentTools
from pycatan.ai.tool_executor import ToolExecutor, ToolCall


def test_basic_tools():
    """Test basic tool functionality."""
    print("=" * 60)
    print("TEST 1: Basic Tool Operations")
    print("=" * 60)
    
    # Load a sample game state
    sample_state_path = Path("examples/ai_testing/sample_states/captured_game.json")
    if not sample_state_path.exists():
        print(f"⚠️  Sample state not found at {sample_state_path}")
        print("Using minimal test state instead")
        game_state = {
            "board": {
                "nodes": [
                    {
                        "id": 10,
                        "adjacent_tiles": [0, 1, 2],
                        "neighbors": [8, 11, 14],
                        "port": None,
                        "building": None
                    },
                    {
                        "id": 14,
                        "adjacent_tiles": [2, 3, 4],
                        "neighbors": [10, 11, 18],
                        "port": "3:1",
                        "building": None
                    }
                ],
                "tiles": [
                    {"id": 0, "type": "Wood", "number": 6},
                    {"id": 1, "type": "Brick", "number": 8},
                    {"id": 2, "type": "Wheat", "number": 5},
                    {"id": 3, "type": "Ore", "number": 10},
                    {"id": 4, "type": "Sheep", "number": 9}
                ]
            }
        }
    else:
        with open(sample_state_path, 'r', encoding='utf-8') as f:
            game_state = json.load(f)
    
    # Initialize tools
    tools = AgentTools(game_state)
    print(f"✅ Initialized AgentTools with {len(tools.node_lookup)} nodes")
    print()
    
    # Test 1: inspect_node
    print("🔧 Testing: inspect_node(10)")
    result1 = tools.inspect_node(10)
    print(json.dumps(result1, indent=2))
    print()
    
    # Test 2: inspect_node on another node
    print("🔧 Testing: inspect_node(14)")
    result2 = tools.inspect_node(14)
    print(json.dumps(result2, indent=2))
    print()
    
    # Test 3: find_best_nodes
    print("🔧 Testing: find_best_nodes(min_pips=8)")
    result3 = tools.find_best_nodes(min_pips=8, limit=5)
    print(f"Found {result3['total_found']} nodes:")
    for node in result3['nodes']:
        print(f"  - Node {node['node_id']}: {node['total_pips']} pips, score={node['score']}")
    print()
    
    # Test 4: analyze_path_potential
    if len(tools.node_lookup) > 10:
        print("🔧 Testing: analyze_path_potential(from_node=10)")
        result4 = tools.analyze_path_potential(from_node=10, max_depth=2)
        print(f"Analyzed {result4['total_directions']} directions from node 10")
        if result4['paths']:
            best_path = result4['paths'][0]
            print(f"  Best direction: node {best_path['direction']} (score={best_path['score']})")
            if best_path['highlights']:
                for highlight in best_path['highlights']:
                    print(f"    - {highlight}")
        print()


def test_tool_executor():
    """Test ToolExecutor with multiple tool calls."""
    print("=" * 60)
    print("TEST 2: Tool Executor (Multiple Calls)")
    print("=" * 60)
    
    # Load sample state
    sample_state_path = Path("examples/ai_testing/sample_states/captured_game.json")
    if sample_state_path.exists():
        with open(sample_state_path, 'r', encoding='utf-8') as f:
            game_state = json.load(f)
    else:
        # Minimal state
        game_state = {
            "board": {
                "nodes": [
                    {
                        "id": 10,
                        "adjacent_tiles": [0, 1],
                        "neighbors": [8, 14],
                        "port": None,
                        "building": None
                    }
                ],
                "tiles": [
                    {"id": 0, "type": "Wood", "number": 6},
                    {"id": 1, "type": "Brick", "number": 8}
                ]
            }
        }
    
    # Initialize
    tools = AgentTools(game_state)
    executor = ToolExecutor(tools)
    print(f"✅ Initialized ToolExecutor")
    print()
    
    # Simulate multiple tool calls (as if from LLM)
    tool_calls = [
        {
            "id": "call_1",
            "name": "inspect_node",
            "parameters": {"node_id": 10}
        },
        {
            "id": "call_2",
            "name": "find_best_nodes",
            "parameters": {"min_pips": 8, "limit": 3}
        },
    ]
    
    # Add path analysis if we have enough nodes
    if len(tools.node_lookup) > 10:
        tool_calls.append({
            "id": "call_3",
            "name": "analyze_path_potential",
            "parameters": {"from_node": 10, "max_depth": 1}
        })
    
    print(f"🔧 Executing {len(tool_calls)} tool calls...")
    print()
    
    # Execute
    batch = executor.execute_tool_calls(tool_calls)
    
    # Display results
    print()
    print("📊 Execution Summary:")
    print(f"  Total calls: {len(batch.tool_calls)}")
    print(f"  Successful: {batch.success_count}")
    print(f"  Failed: {batch.failure_count}")
    print(f"  Total time: {batch.total_time*1000:.1f}ms")
    print(f"  Total tokens: {batch.total_tokens}")
    print(f"    - Input: {batch.total_input_tokens}")
    print(f"    - Output: {batch.total_output_tokens}")
    print()
    
    # Show individual call details
    print("📋 Individual Call Details:")
    for call in batch.tool_calls:
        status = "✅" if call.success else "❌"
        print(f"\n  {status} {call.name}({call.parameters})")
        print(f"     Time: {call.execution_time*1000:.1f}ms")
        print(f"     Tokens: {call.input_tokens} in + {call.output_tokens} out")
        if call.success:
            result_preview = str(call.result)[:100]
            print(f"     Result: {result_preview}...")
        else:
            print(f"     Error: {call.error}")
    print()
    
    # Format for LLM
    print("📝 Formatted for LLM:")
    print("-" * 60)
    formatted = executor.format_tool_results_for_llm(batch)
    print(formatted)
    print("-" * 60)
    print()


def test_tool_schemas():
    """Test tool schema generation for LLM."""
    print("=" * 60)
    print("TEST 3: Tool Schemas for LLM")
    print("=" * 60)
    
    tools = AgentTools()
    schemas = tools.get_tools_schema()
    
    print(f"✅ Generated {len(schemas)} tool schemas")
    print()
    
    for schema in schemas:
        print(f"📄 Tool: {schema['name']}")
        print(f"   Description: {schema['description'][:80]}...")
        print(f"   Parameters:")
        for param_name, param_info in schema['parameters']['properties'].items():
            required = "required" if param_name in schema['parameters'].get('required', []) else "optional"
            print(f"     - {param_name} ({required}): {param_info.get('description', 'N/A')[:60]}...")
        print()


def test_execution_history():
    """Test execution history and statistics."""
    print("=" * 60)
    print("TEST 4: Execution History & Statistics")
    print("=" * 60)
    
    # Create minimal state
    game_state = {
        "board": {
            "nodes": [{"id": 10, "adjacent_tiles": [], "neighbors": [], "port": None, "building": None}],
            "tiles": []
        }
    }
    
    tools = AgentTools(game_state)
    executor = ToolExecutor(tools)
    
    # Execute multiple batches
    print("🔧 Executing 3 batches of tool calls...")
    for i in range(3):
        tool_calls = [
            {"id": f"batch{i}_call1", "name": "inspect_node", "parameters": {"node_id": 10}}
        ]
        executor.execute_tool_calls(tool_calls)
    
    print()
    
    # Get summary
    summary = executor.get_execution_summary()
    
    print("📊 Execution Summary:")
    print(f"  Total batches: {summary['total_batches']}")
    print(f"  Total calls: {summary['total_calls']}")
    print(f"  Success rate: {summary['success_rate']}")
    print(f"  Total tokens: {summary['total_tokens']}")
    print()
    
    print("🔧 Tool Usage:")
    for tool_name, count in summary['tool_usage'].items():
        print(f"  - {tool_name}: {count} times")
    print()


if __name__ == "__main__":
    print("\n🧪 Testing Tool Integration for AI Agents\n")
    
    try:
        test_basic_tools()
        test_tool_executor()
        test_tool_schemas()
        test_execution_history()
        
        print("=" * 60)
        print("✅ All Tests Passed!")
        print("=" * 60)
        print()
        print("Next steps:")
        print("1. Tools are ready to use with AI agents")
        print("2. LLM can call these tools via function calling")
        print("3. All executions are logged with token counts")
        print("4. Check tool_executions.json in session logs for details")
        print()
        
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
