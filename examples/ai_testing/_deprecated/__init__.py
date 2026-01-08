"""
⚠️ DEPRECATED FILES - OLD AI TESTING INFRASTRUCTURE

This folder contains the OLD AI testing files that have been replaced
by the new unified AI system in pycatan/ai/.

These files are kept for reference but should NOT be used for new development.

Old Files (in this folder):
- generate_prompts_from_state.py - Old prompt generation (replaced by AIManager)
- play_with_prompts.py - Old game runner (replaced by play_with_ai.py)
- test_ai_live.py - Old LLM tester (replaced by AIManager)
- request_tracker.py - Old request tracking (replaced by AILogger)
- test_optimized_prompts.py - Old prompt testing
- test_new_structure.py - Old structure tests
- example_get_latest_prompt.py - Old prompt retrieval

New System (use these instead):
- play_with_ai.py (in examples/ai_testing/) - New unified entry point
- pycatan/ai/ai_manager.py - Central AI coordinator
- pycatan/ai/ai_user.py - AI player wrapper
- pycatan/ai/ai_logger.py - Logging system
- pycatan/ai/agent_state.py - Agent state management

Migration:
The new system provides:
1. Cleaner separation of concerns
2. Better event tracking ("what happened" based on real events)
3. Unified logging with session management
4. Support for both manual and automatic LLM modes
5. Better parameter conversion between AI and GameManager

To run a game with AI:
    python examples/ai_testing/play_with_ai.py

For more information, see:
- .github/instructions/AI_REFACTOR_PLAN.md
- .github/instructions/AI_ARCHITECTURE.md
"""

__deprecated__ = True
__version__ = "1.0.0 (deprecated)"

import warnings
warnings.warn(
    "This module is deprecated. Use pycatan.ai instead.",
    DeprecationWarning,
    stacklevel=2
)
