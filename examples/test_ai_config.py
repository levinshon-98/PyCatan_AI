"""
Test script for AI Configuration System

This script tests the configuration management functionality:
1. Create default configuration
2. Save to file
3. Load from file
4. Validate configuration
5. Test different personalities
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from pycatan.ai.config import AIConfig, load_config


def test_default_config():
    """Test creating and using default configuration."""
    print("\n" + "="*80)
    print("TEST 1: Default Configuration")
    print("="*80)
    
    config = AIConfig()
    print(f"\n✓ Created default config:\n{config}")
    
    # Validate
    try:
        config.validate()
        print("✓ Configuration is valid")
    except ValueError as e:
        print(f"✗ Validation failed: {e}")
        return False
    
    return True


def test_save_and_load():
    """Test saving and loading configuration."""
    print("\n" + "="*80)
    print("TEST 2: Save and Load Configuration")
    print("="*80)
    
    # Create custom config
    config = AIConfig()
    config.agent_name = "Test Agent"
    config.agent.personality = "aggressive"
    config.agent.risk_tolerance = 0.8
    config.llm.temperature = 0.9
    
    # Save to file
    test_file = "test_config.yaml"
    config.to_file(test_file)
    print(f"✓ Saved configuration to {test_file}")
    
    # Load from file
    loaded_config = AIConfig.from_file(test_file)
    print(f"✓ Loaded configuration from {test_file}")
    
    # Verify values
    assert loaded_config.agent_name == "Test Agent", "Agent name mismatch"
    assert loaded_config.agent.personality == "aggressive", "Personality mismatch"
    assert loaded_config.agent.risk_tolerance == 0.8, "Risk tolerance mismatch"
    assert loaded_config.llm.temperature == 0.9, "Temperature mismatch"
    
    print("✓ All values match correctly")
    
    # Clean up
    Path(test_file).unlink()
    print(f"✓ Cleaned up {test_file}")
    
    return True


def test_personalities():
    """Test creating configs with different personalities."""
    print("\n" + "="*80)
    print("TEST 3: Different Personalities")
    print("="*80)
    
    personalities = {
        "aggressive": {
            "personality": "aggressive",
            "risk_tolerance": 0.8,
            "trade_willingness": 0.7,
            "focus_on_settlements": 0.8
        },
        "defensive": {
            "personality": "defensive",
            "risk_tolerance": 0.3,
            "trade_willingness": 0.3,
            "focus_on_cities": 0.9
        },
        "balanced": {
            "personality": "balanced",
            "risk_tolerance": 0.5,
            "trade_willingness": 0.5
        },
        "trading": {
            "personality": "trading",
            "risk_tolerance": 0.6,
            "trade_willingness": 0.9,
            "chat_frequency": 0.7
        }
    }
    
    for name, settings in personalities.items():
        config = AIConfig()
        config.agent_name = f"{name.capitalize()} Agent"
        
        # Apply settings
        for key, value in settings.items():
            setattr(config.agent, key, value)
        
        # Validate
        config.validate()
        print(f"✓ Created and validated '{name}' personality")
        print(f"  - Risk tolerance: {config.agent.risk_tolerance}")
        print(f"  - Trade willingness: {config.agent.trade_willingness}")
    
    return True


def test_validation():
    """Test configuration validation."""
    print("\n" + "="*80)
    print("TEST 4: Configuration Validation")
    print("="*80)
    
    # Test invalid temperature
    config = AIConfig()
    config.llm.temperature = 3.0  # Invalid (> 2.0)
    
    try:
        config.validate()
        print("✗ Should have caught invalid temperature")
        return False
    except ValueError as e:
        print(f"✓ Correctly caught invalid temperature: {e}")
    
    # Test invalid risk tolerance
    config = AIConfig()
    config.agent.risk_tolerance = 1.5  # Invalid (> 1.0)
    
    try:
        config.validate()
        print("✗ Should have caught invalid risk_tolerance")
        return False
    except ValueError as e:
        print(f"✓ Correctly caught invalid risk_tolerance: {e}")
    
    # Test valid config
    config = AIConfig()
    config.validate()
    print("✓ Valid configuration passes validation")
    
    return True


def test_to_dict_and_back():
    """Test dictionary conversion."""
    print("\n" + "="*80)
    print("TEST 5: Dictionary Conversion")
    print("="*80)
    
    # Create config
    config = AIConfig()
    config.agent_name = "Dict Test Agent"
    config.agent.personality = "trading"
    config.llm.temperature = 0.8
    
    # Convert to dict
    config_dict = config.to_dict()
    print("✓ Converted config to dictionary")
    
    # Create from dict
    new_config = AIConfig.from_dict(config_dict)
    print("✓ Created config from dictionary")
    
    # Verify values
    assert new_config.agent_name == config.agent_name
    assert new_config.agent.personality == config.agent.personality
    assert new_config.llm.temperature == config.llm.temperature
    print("✓ All values preserved correctly")
    
    return True


def main():
    """Run all tests."""
    print("\n" + "="*80)
    print("AI CONFIGURATION SYSTEM - TEST SUITE")
    print("="*80)
    
    tests = [
        ("Default Configuration", test_default_config),
        ("Save and Load", test_save_and_load),
        ("Different Personalities", test_personalities),
        ("Validation", test_validation),
        ("Dictionary Conversion", test_to_dict_and_back)
    ]
    
    results = []
    for name, test_func in tests:
        try:
            result = test_func()
            results.append((name, result))
        except Exception as e:
            print(f"\n✗ Test '{name}' failed with exception: {e}")
            import traceback
            traceback.print_exc()
            results.append((name, False))
    
    # Summary
    print("\n" + "="*80)
    print("TEST SUMMARY")
    print("="*80)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for name, result in results:
        status = "✓ PASS" if result else "✗ FAIL"
        print(f"{status}: {name}")
    
    print(f"\nTotal: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n🎉 All tests passed!")
        return 0
    else:
        print(f"\n❌ {total - passed} test(s) failed")
        return 1


if __name__ == "__main__":
    sys.exit(main())
