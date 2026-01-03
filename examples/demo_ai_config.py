"""
Quick demo showing how the AI configuration system works.

This script demonstrates:
1. How API keys are loaded from environment variables
2. How to use config files
3. The difference between config_example.yaml and config_dev.yaml
4. How to create custom agent configurations
"""

import os
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from pycatan.ai.config import AIConfig, load_config


def demo_api_key_loading():
    """Demo 1: How API keys are loaded from environment variables."""
    print("\n" + "="*80)
    print("DEMO 1: API Key Loading from Environment")
    print("="*80)
    
    print("\n1. API keys are stored in the .env file (NOT in Git)")
    print("   Example .env file:")
    print("   ┌─────────────────────────────────────┐")
    print("   │ GEMINI_API_KEY=AIzaSyC...your_key  │")
    print("   │ OPENAI_API_KEY=sk-...your_key      │")
    print("   └─────────────────────────────────────┘")
    
    print("\n2. The config system reads from environment variables:")
    config = AIConfig()
    
    print(f"   Provider: {config.llm.provider}")
    print(f"   Env var name: {config.llm.api_key_env_var}")
    
    # Try to get API key
    try:
        api_key = config.get_api_key()
        # Hide most of the key for security
        masked_key = api_key[:10] + "..." + api_key[-4:] if len(api_key) > 14 else "***"
        print(f"   ✓ API key loaded: {masked_key}")
        print(f"   ✓ Full length: {len(api_key)} characters")
    except ValueError as e:
        print(f"   ✗ No API key found: {e}")
        print("\n   👉 To fix this:")
        print("      1. Copy .env.example to .env")
        print("      2. Add your API key to .env")
        print("      3. The .env file will NOT be committed to Git")


def demo_config_files():
    """Demo 2: Different types of config files."""
    print("\n" + "="*80)
    print("DEMO 2: Configuration Files Explained")
    print("="*80)
    
    print("\n📁 THREE types of config files:")
    
    print("\n1️⃣  config_example.yaml - DOCUMENTATION")
    print("   ├─ Purpose: Shows ALL possible settings with explanations")
    print("   ├─ Git: ✅ Committed (it's documentation)")
    print("   ├─ Usage: Read it to understand options")
    print("   └─ Don't use directly - copy and customize it")
    
    print("\n2️⃣  config_dev.yaml - DEFAULT FOR DEVELOPMENT")
    print("   ├─ Purpose: Ready-to-use config for development")
    print("   ├─ Git: ✅ Committed (team shares same defaults)")
    print("   ├─ Usage: Just load it and start coding!")
    print("   └─ Example: AIConfig.from_file('pycatan/ai/config_dev.yaml')")
    
    print("\n3️⃣  your_custom_config.yaml - YOUR PERSONAL AGENT")
    print("   ├─ Purpose: Your custom agent configuration")
    print("   ├─ Git: ❌ NOT committed (optional)")
    print("   ├─ Usage: Create when you want custom behavior")
    print("   └─ Example: Copy config_example.yaml and modify")
    
    print("\n💡 WORKFLOW:")
    print("   • During development: Use config_dev.yaml")
    print("   • Want custom agent: Copy config_example.yaml → my_agent.yaml")
    print("   • API keys: Always in .env (never in YAML files)")


def demo_default_config():
    """Demo 3: Using the default development config."""
    print("\n" + "="*80)
    print("DEMO 3: Using the Default Development Config")
    print("="*80)
    
    print("\n▶ Loading config_dev.yaml...")
    config_path = project_root / "pycatan" / "ai" / "config_dev.yaml"
    
    if config_path.exists():
        config = AIConfig.from_file(str(config_path))
        
        print(f"\n✓ Loaded successfully!")
        print(f"\n📋 Configuration Details:")
        print(f"   Agent Name: {config.agent_name}")
        print(f"   Provider: {config.llm.provider}")
        print(f"   Model: {config.llm.model_name}")
        print(f"   Temperature: {config.llm.temperature}")
        print(f"   Personality: {config.agent.personality}")
        print(f"   Risk Tolerance: {config.agent.risk_tolerance}")
        print(f"   Debug Mode: {config.debug.debug_mode}")
        
        print(f"\n⚙️ Strategic Focus:")
        print(f"   Settlements: {config.agent.focus_on_settlements}")
        print(f"   Cities: {config.agent.focus_on_cities}")
        print(f"   Roads: {config.agent.focus_on_roads}")
        print(f"   Dev Cards: {config.agent.focus_on_dev_cards}")
        
        print(f"\n💬 Social Behavior:")
        print(f"   Trade Willingness: {config.agent.trade_willingness}")
        print(f"   Chat Frequency: {config.agent.chat_frequency}")
        print(f"   Chattiness: {config.agent.chattiness}")
    else:
        print(f"✗ Config file not found: {config_path}")


def demo_custom_config():
    """Demo 4: Creating a custom agent configuration."""
    print("\n" + "="*80)
    print("DEMO 4: Creating Custom Agent Configuration")
    print("="*80)
    
    print("\n▶ Creating an 'Aggressive Trader' agent...")
    
    # Start with default config
    config = AIConfig()
    
    # Customize for aggressive trading
    config.agent_name = "Aggressive Trader"
    config.agent.personality = "trading"
    config.agent.risk_tolerance = 0.8  # High risk
    config.agent.trade_willingness = 0.9  # Trades a lot
    config.agent.trade_fairness = 0.6  # Slightly unfair trades
    config.agent.focus_on_settlements = 0.8  # Expand quickly
    config.agent.chat_frequency = 0.7  # Very chatty
    config.agent.chattiness = "chatty"
    config.llm.temperature = 0.8  # More creative
    
    print("\n✓ Custom config created!")
    print(f"\n📋 Agent Profile:")
    print(f"   Name: {config.agent_name}")
    print(f"   Personality: {config.agent.personality}")
    print(f"   Risk Tolerance: {config.agent.risk_tolerance} (HIGH)")
    print(f"   Trade Willingness: {config.agent.trade_willingness} (VERY HIGH)")
    print(f"   Trade Fairness: {config.agent.trade_fairness} (Slightly unfair)")
    print(f"   Chattiness: {config.agent.chattiness}")
    print(f"   Temperature: {config.llm.temperature} (Creative)")
    
    # Save to file
    custom_file = project_root / "aggressive_trader_config.yaml"
    config.to_file(str(custom_file))
    print(f"\n💾 Saved to: {custom_file.name}")
    print("   (This file will NOT be committed to Git)")
    
    # Clean up
    custom_file.unlink()
    print("   (Cleaned up demo file)")


def demo_security():
    """Demo 5: Security features."""
    print("\n" + "="*80)
    print("DEMO 5: Security Features")
    print("="*80)
    
    print("\n🔒 What's Protected:")
    print("   ✅ .env file → NOT in Git")
    print("   ✅ Your custom *.yaml configs → NOT in Git")
    print("   ✅ Agent memory files → NOT in Git")
    print("   ✅ Game state logs → NOT in Git")
    
    print("\n📤 What's Committed:")
    print("   ✅ .env.example → Template (no secrets)")
    print("   ✅ config_example.yaml → Documentation")
    print("   ✅ config_dev.yaml → Default settings")
    print("   ✅ Python code → No secrets in code")
    
    print("\n⚠️ Remember:")
    print("   • NEVER commit your .env file")
    print("   • NEVER put API keys in YAML files")
    print("   • NEVER hardcode API keys in Python code")
    print("   • Each developer has their own .env file")


def main():
    """Run all demos."""
    print("\n" + "="*80)
    print("🎓 AI CONFIGURATION SYSTEM - INTERACTIVE DEMO")
    print("="*80)
    print("\nThis demo explains how the configuration system works")
    print("and shows you the difference between the config files.")
    
    demo_api_key_loading()
    demo_config_files()
    demo_default_config()
    demo_custom_config()
    demo_security()
    
    print("\n" + "="*80)
    print("✅ DEMO COMPLETE!")
    print("="*80)
    print("\n📚 Next Steps:")
    print("   1. Read: docs/AI_SETUP.md (complete setup guide)")
    print("   2. Read: QUICKSTART_API.md (2-minute setup)")
    print("   3. Look at: pycatan/ai/config_example.yaml (all options)")
    print("   4. Use: pycatan/ai/config_dev.yaml (start coding!)")
    print("\n💡 Quick Start:")
    print("   from pycatan.ai.config import AIConfig")
    print("   config = AIConfig.from_file('pycatan/ai/config_dev.yaml')")
    print("   api_key = config.get_api_key()  # From .env file")
    print("\n" + "="*80)


if __name__ == "__main__":
    main()
