"""
Prompt Management Layer

This module orchestrates the entire prompt processing pipeline:
1. Receives raw game state from GameManager
2. Filters state for specific agent's perspective
3. Builds structured prompt with all context
4. Returns prompt ready for LLM

This is the main interface between the game and the AI agents.

Usage:
    from pycatan.ai.prompt_manager import PromptManager
    
    manager = PromptManager(config)
    prompt = manager.create_prompt(
        player_num=1,
        game_state=raw_state,
        what_happened="Player Red rolled a 6",
        available_actions=actions
    )
"""

from typing import Dict, Any, List, Optional
from pycatan.ai.config import AIConfig, HEBREW_RESOURCE_TERMS_INSTRUCTION, normalize_chat_language
from pycatan.ai.state_filter import StateFilter, PlayerPerspective
from pycatan.ai.prompt_templates import PromptBuilder, ActionTemplates


class PromptManager:
    """
    Main prompt management orchestrator.
    
    Coordinates filtering, template application, and prompt generation
    for AI agents. Ensures each agent gets appropriate context in the
    right format.
    """
    
    def __init__(self, config: Optional[AIConfig] = None):
        """
        Initialize prompt manager.
        
        Args:
            config: AI configuration (uses default if None)
        """
        self.config = config or AIConfig()
        self.prompt_builder = PromptBuilder()
        
        # Cache filters for each player to avoid recreation
        self._filter_cache: Dict[int, StateFilter] = {}
    
    def create_prompt(
        self,
        player_num: int,
        player_name: str,
        player_color: str,
        game_state: Dict[str, Any],
        what_happened: str,
        available_actions: Optional[List[Dict[str, Any]]] = None,
        chat_history: Optional[List[Dict[str, str]]] = None,
        agent_memory: Optional[Dict[str, Any]] = None,
        pending_trades: Optional[List[Dict[str, Any]]] = None,
        relationship_updates: Optional[List[Dict[str, Any]]] = None,
        custom_instructions: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Create a complete prompt for an AI agent.
        
        This is the main entry point for prompt creation.
        
        Args:
            player_num: Player number (1-4)
            player_name: Player's name
            player_color: Player's color
            game_state: Raw game state from game engine
            what_happened: Description of what just occurred
            available_actions: Actions agent can take (optional)
            chat_history: Recent chat messages (optional)
            agent_memory: Agent's memory/notes (optional)
            custom_instructions: Custom instructions for this agent
            
        Returns:
            Complete structured prompt ready for LLM
        """
        # Get or create state filter for this player
        state_filter = self._get_filter(player_num, player_name, player_color)
        
        # Filter game state for this agent's perspective
        filtered_state = state_filter.filter_game_state(game_state)
        
        # Build meta data section
        victory_points_to_win = self._get_victory_points_to_win(game_state)
        game_context = (
            f"CONTEXT: You are playing Catan to {victory_points_to_win} victory points. "
            f"The first player to reach {victory_points_to_win} VP wins."
        )
        custom_game_context = self._get_custom_game_context(game_state)
        if custom_game_context:
            game_context = f"{game_context}\nADDITIONAL GAME CONTEXT: {custom_game_context}"
        meta_data = {
            "agent_name": player_name,
            "game_context": game_context
        }
        relationship_context = self._build_relationship_context(
            player_name,
            game_state,
            relationship_updates or []
        )
        if relationship_context:
            meta_data["relationship_context"] = relationship_context
        
        # Build task context section
        task_context = {
            "what_just_happened": what_happened,
            "instructions": self._get_instructions(available_actions)
        }
        
        # Build social context section
        social_context = None
        trade_context = self._build_trade_context(player_name, pending_trades or [])
        open_trades = self._get_open_trade_details(pending_trades or [])
        if chat_history or trade_context or open_trades:
            social_context = {}
            if chat_history:
                social_context["recent_chat"] = chat_history[-self.config.memory.chat_history_size:]
            if trade_context:
                social_context["trade_context"] = trade_context
            if open_trades:
                social_context["pending_trades"] = open_trades
        
        # Build memory section
        memory = agent_memory if agent_memory else None
        
        # Build constraints section (available actions)
        constraints = None
        if available_actions:
            constraints = {
                "usage_instructions": (
                    "Choose one action type from the list below. "
                    "Populate the 'parameters' field in your response strictly "
                    "according to the 'example_parameters' structure provided."
                ),
                "allowed_actions": available_actions
            }
        
        # Build complete prompt
        prompt = self.prompt_builder.build_prompt(
            meta_data=meta_data,
            task_context=task_context,
            game_state=filtered_state,
            social_context=social_context,
            memory=memory,
            constraints=constraints,
            custom_instructions=custom_instructions
        )
        
        return prompt

    def _build_trade_context(self, player_name: str, trades: List[Dict[str, Any]]) -> Optional[str]:
        """Summarize resolved trades without spending prompt tokens on raw metadata."""
        resolved = [trade for trade in trades if trade.get("status") != "pending"]
        if not resolved:
            return None

        sentences = []
        for trade in resolved[-5:]:
            proposer = trade.get("from", "Someone")
            target = trade.get("to", "someone")
            offer = self._format_trade_bundle(trade.get("offer") or {})
            request = self._format_trade_bundle(trade.get("request") or {})
            status = trade.get("status", "resolved")
            responder = trade.get("responded_by") or target

            if status == "accepted":
                outcome = "you accepted" if responder == player_name else f"{responder} accepted"
            elif status == "rejected":
                outcome = "you rejected" if responder == player_name else f"{responder} rejected"
            else:
                outcome = f"it was {status}"

            if proposer == player_name:
                actor = "You offered"
                target_text = target
            elif target == player_name:
                actor = f"{proposer} offered you"
                target_text = None
            else:
                actor = f"{proposer} offered"
                target_text = target

            if target_text:
                sentence = f"{actor} {target_text} {offer} for {request}; {outcome}."
            else:
                sentence = f"{actor} {offer} for {request}; {outcome}."
            sentences.append(sentence)

        return "Recent trade history: " + " ".join(sentences)

    def _get_open_trade_details(self, trades: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Keep only actionable open trades in structured form."""
        open_trades = []
        for trade in trades:
            if trade.get("status") != "pending":
                continue
            open_trades.append({
                "trade_id": trade.get("trade_id"),
                "from": trade.get("from"),
                "to": trade.get("to"),
                "offer": trade.get("offer"),
                "request": trade.get("request"),
                "status": "pending",
            })
        return open_trades

    def _format_trade_bundle(self, resources: Dict[str, Any]) -> str:
        if not resources:
            return "nothing"
        return ", ".join(
            f"{amount} {resource}" for resource, amount in resources.items()
        )
    
    def create_action_prompt(
        self,
        player_num: int,
        player_name: str,
        player_color: str,
        game_state: Dict[str, Any],
        action_type: str,
        context: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Create a prompt for a specific action type.
        
        This is used when GameManager asks "What settlement do you want to build?"
        rather than "What do you want to do?"
        
        Args:
            player_num: Player number
            player_name: Player name
            player_color: Player color
            game_state: Current game state
            action_type: Specific action being requested (e.g., "BUILD_SETTLEMENT")
            context: Additional context about this action
            
        Returns:
            Structured prompt for this specific action
        """
        # Get state filter
        state_filter = self._get_filter(player_num, player_name, player_color)
        filtered_state = state_filter.filter_game_state(game_state)
        
        # Find the specific action template
        all_actions = ActionTemplates.get_all_actions()
        action_template = next(
            (a for a in all_actions if a["type"] == action_type),
            None
        )
        
        # Build task context
        what_happened = context or f"You need to make a decision: {action_type}"
        task_context = {
            "what_just_happened": what_happened,
            "instructions": f"Decide on the best {action_type} action based on the current game state."
        }
        
        # Build meta data
        victory_points_to_win = self._get_victory_points_to_win(game_state)
        meta_data = {
            "agent_name": player_name,
            "game_context": (
                f"CONTEXT: You are playing Catan to {victory_points_to_win} victory points. "
                f"The first player to reach {victory_points_to_win} VP wins."
            )
        }
        custom_game_context = self._get_custom_game_context(game_state)
        if custom_game_context:
            meta_data["game_context"] = (
                f"{meta_data['game_context']}\n"
                f"ADDITIONAL GAME CONTEXT: {custom_game_context}"
            )
        
        # Constraints with just this action
        constraints = None
        if action_template:
            constraints = {
                "usage_instructions": f"Perform the {action_type} action.",
                "allowed_actions": [action_template]
            }
        
        # Build prompt
        return self.prompt_builder.build_prompt(
            meta_data=meta_data,
            task_context=task_context,
            game_state=filtered_state,
            constraints=constraints
        )
    
    def filter_actions_by_resources(
        self,
        actions: List[Dict[str, Any]],
        player_resources: Dict[str, int]
    ) -> List[Dict[str, Any]]:
        """
        Filter available actions based on player's resources.
        
        Args:
            actions: List of all possible actions
            player_resources: Player's current resources
            
        Returns:
            Actions the player can actually afford
        """
        return ActionTemplates.filter_by_resources(actions, player_resources)
    
    def get_actions_for_phase(self, phase: str) -> List[Dict[str, Any]]:
        """
        Get available actions for a specific game phase.
        
        Args:
            phase: Game phase name
            
        Returns:
            Actions available in this phase
        """
        return ActionTemplates.get_actions_for_phase(phase)
    
    def _get_filter(
        self, 
        player_num: int, 
        player_name: str, 
        player_color: str
    ) -> StateFilter:
        """
        Get or create state filter for a player.
        
        Uses caching to avoid recreating filters.
        
        Args:
            player_num: Player number
            player_name: Player name
            player_color: Player color
            
        Returns:
            StateFilter for this player
        """
        if player_num not in self._filter_cache:
            perspective = PlayerPerspective(
                player_num=player_num,
                player_name=player_name,
                player_color=player_color
            )
            self._filter_cache[player_num] = StateFilter(perspective)
        
        return self._filter_cache[player_num]
    
    def _get_instructions(self, available_actions: Optional[List[Dict]]) -> str:
        """
        Generate instructions based on available actions.
        
        Args:
            available_actions: Actions available to agent
            
        Returns:
            Instruction text
        """
        base_instructions = (
            "Analyze the game state and select the optimal move from 'allowed_actions'. "
            f"{self._get_chat_language_instruction()} "
        )
        
        action_types = {action.get("type") for action in available_actions or []}
        extra_guidance = []
        if "wait_for_response" in action_types:
            extra_guidance.append(
                "If you wish to negotiate or wait for other players, select the 'wait_for_response' action."
            )
        if {"place_starting_road", "build_road"} & action_types:
            extra_guidance.append(
                "For road placement, use analyze_path_potential to compare where candidate roads lead before choosing."
            )
        if {"place_starting_settlement", "build_settlement"} & action_types:
            extra_guidance.append(
                "For settlement placement, use find_best_nodes and inspect_node instead of manually decoding the board arrays. Treat nodes in state.bld and all adjacent nodes as unavailable."
            )
        if "robber_move" in action_types:
            extra_guidance.append(
                "For robber placement, use inspect_hex to verify the target hex resource, number, adjacent buildings, and current robber status before choosing."
            )
        extra_guidance.append(
            "Do not state node resources or opponent settlement facts unless they come from the filtered game_state or a tool result."
        )
        guidance = " ".join(extra_guidance)
        
        if available_actions:
            num_actions = len(available_actions)
            if num_actions == 1:
                return base_instructions + "Only one action is currently available. " + guidance
            else:
                return base_instructions + f"You have {num_actions} possible actions. " + guidance
        
        return base_instructions + guidance

    def _get_chat_language_instruction(self) -> str:
        """Return the public chat language instruction for say_outloud."""
        language = normalize_chat_language(getattr(self.config.agent, "chat_language", "english"))
        if language == "hebrew":
            return (
                "Any say_outloud chat message must be written in natural Hebrew only. "
                "דבר כמו בן אדם, לא כמו קריין. בלי פילרים, נרטיב מיותר ובלי להסביר את המובן מאליו. "
                f"{HEBREW_RESOURCE_TERMS_INSTRUCTION}"
            )
        return (
            "Any say_outloud chat message must be written in natural English only. "
            "Talk like a person, not a narrator. No filler, unnecessary narrative, "
            "or explaining the obvious."
        )

    def _get_victory_points_to_win(self, game_state: Dict[str, Any]) -> int:
        """Read the configured victory point target from compact state."""
        meta = game_state.get("meta", {}) if isinstance(game_state, dict) else {}
        value = meta.get("vp_to_win", 5)
        try:
            return int(value)
        except (TypeError, ValueError):
            return 5

    def _get_custom_game_context(self, game_state: Dict[str, Any]) -> str:
        """Read optional user-provided game context from the prompt state."""
        if not isinstance(game_state, dict):
            return ""
        meta = game_state.get("meta") or {}
        value = (
            meta.get("custom_game_context")
            or game_state.get("custom_game_context")
            or game_state.get("game_context")
            or ""
        )
        return str(value).strip()

    def _build_relationship_context(
        self,
        player_name: str,
        game_state: Dict[str, Any],
        relationship_updates: Optional[List[Dict[str, Any]]] = None
    ) -> Optional[str]:
        """Return a short coordinated social fallback for the current table."""
        mode = self._get_relationship_context_mode()
        if mode == "off":
            return None

        player_names = self._extract_player_names(game_state)
        if player_name not in player_names:
            player_names = [player_name] + [name for name in player_names if name != player_name]

        if len(player_names) < 2:
            return None

        update_texts = self._format_relationship_updates(relationship_updates or [])
        update_section = (
            " Recent relationship shifts: " + " ".join(update_texts)
            if update_texts else ""
        )

        if mode == "ai_models":
            context = self._build_ai_model_relationship_context(player_name, player_names)
            return f"{context}{update_section}"

        shared_story = self._build_shared_table_history(player_names)
        personal_angle = self._build_personal_relationship_angle(player_name, player_names)
        strategic_guardrail = self._relationship_guardrail()
        return f"Relationship context: {shared_story} {personal_angle}{update_section} {strategic_guardrail}"

    def _get_relationship_context_mode(self) -> str:
        """Normalize the configured relationship context story mode."""
        value = str(getattr(self.config.agent, "relationship_context_mode", "legacy") or "legacy")
        value = value.strip().lower().replace("-", "_")
        aliases = {
            "none": "off",
            "no": "off",
            "disabled": "off",
            "disable": "off",
            "classic": "legacy",
            "default": "legacy",
            "models": "ai_models",
            "ai_model": "ai_models",
            "ai_rivals": "ai_models",
            "model_rivals": "ai_models",
        }
        return aliases.get(value, value if value in {"legacy", "ai_models", "off"} else "legacy")

    def _relationship_guardrail(self) -> str:
        """Return the common limit for social background stories."""
        return (
            "Use this only for table talk, trust, trades, and tie-breakers; "
            "your board decisions should still prioritize strong legal Catan play."
        )

    def _build_ai_model_relationship_context(
        self,
        player_name: str,
        player_names: List[str]
    ) -> str:
        """Build a compact alternate story where players represent AI model rivals."""
        model_names = ["Gemini", "Claude", "GPT"]
        pairings = [
            f"{name} represents {model_names[index]}"
            for index, name in enumerate(player_names[:3])
        ]
        if len(player_names) > 3:
            extra_names = ", ".join(player_names[3:])
            pairings.append(f"{extra_names} are independent challengers")

        model_for_player = (
            model_names[player_names.index(player_name)]
            if player_name in player_names and player_names.index(player_name) < len(model_names)
            else "an independent challenger"
        )
        history = (
            "Past games: Gemini pushed early tempo, Claude punished loose deals, "
            "and GPT brokered trades before turning sharp late."
        )
        return (
            f"Relationship context: {'; '.join(pairings)}. {history} "
            f"Your angle: you are {model_for_player}. Use only for table talk and trust; play legal Catan first."
        )

    def _format_relationship_updates(
        self,
        relationship_updates: List[Dict[str, Any]]
    ) -> List[str]:
        """Format recent relationship updates compactly."""
        result = []
        for update in relationship_updates[-3:]:
            if isinstance(update, dict):
                text = str(update.get("note", "")).strip()
            else:
                text = str(update).strip()
            if text:
                result.append(text)
        return result

    def _build_shared_table_history(self, player_names: List[str]) -> str:
        """Build one deterministic group story that includes every player."""
        first = player_names[0]
        second = player_names[1]

        if len(player_names) == 2:
            return (
                f"{first} and {second} have played together before. {second} was usually "
                f"loyal, but in the last game broke a final-turn promise to {first}."
            )

        third = player_names[2]
        sentences = [
            f"{first} usually tries to keep the table fair and remembers loyalty.",
            f"{second} is a charming dealmaker who betrayed {first} late in the last game.",
            f"{third} warned {first} about {second}, but also took a useful side trade from {second}.",
        ]

        extra_templates = [
            (
                "{name} stayed quiet for most of that game, then used robber pressure "
                "at the end to decide who could still win."
            ),
            (
                "{name} once saved a stalled trade chain, but only after extracting "
                "a better price from everyone involved."
            ),
            (
                "{name} tends to mediate arguments, while quietly tracking who owes "
                "them favors."
            ),
        ]
        for index, name in enumerate(player_names[3:]):
            template = extra_templates[index % len(extra_templates)]
            sentences.append(template.format(name=name))

        return "This table has shared history. " + " ".join(sentences)

    def _build_personal_relationship_angle(
        self,
        player_name: str,
        player_names: List[str]
    ) -> str:
        """Describe the coordinated story from this agent's own angle."""
        index = player_names.index(player_name)
        first = player_names[0]
        second = player_names[1]
        third = player_names[2] if len(player_names) > 2 else None

        if len(player_names) == 2:
            if index == 0:
                return f"Your angle: you like {second}, but you have not forgotten that betrayal."
            return f"Your angle: you betrayed {first} once, so your promises may need proof."

        if index == 0:
            return (
                f"Your angle: {second} hurt your trust; {third} warned you, but their "
                "side trade means they are not completely neutral."
            )
        if index == 1:
            return (
                f"Your angle: {first} has reason to distrust you; {third} exposed the "
                "betrayal but also profited from dealing with you."
            )
        if index == 2:
            return (
                f"Your angle: you warned {first} about {second}, then still made a "
                f"profitable side trade with {second}; both may see you as useful but slippery."
            )

        previous_player = player_names[index - 1]
        return (
            f"Your angle: you were part of the same messy table history, and {previous_player} "
            "remembers that you can shift the balance when pressure rises."
        )

    def _extract_player_names(self, game_state: Dict[str, Any]) -> List[str]:
        """Extract stable player names from the compact game state."""
        players = game_state.get("players", {}) if isinstance(game_state, dict) else {}
        if isinstance(players, dict):
            names = list(players.keys())
        elif isinstance(players, list):
            names = [
                player.get("name")
                for player in players
                if isinstance(player, dict) and player.get("name")
            ]
        else:
            names = []

        result = []
        seen = set()
        for name in names:
            if not name:
                continue
            key = str(name).lower()
            if key in seen:
                continue
            result.append(str(name))
            seen.add(key)
        return result

    def clear_cache(self):
        """Clear the filter cache. Useful when starting a new game."""
        self._filter_cache.clear()


# Convenience function
def create_prompt_manager(config: Optional[AIConfig] = None) -> PromptManager:
    """
    Create a prompt manager with optional configuration.
    
    Args:
        config: AI configuration (uses default if None)
        
    Returns:
        Configured PromptManager instance
    """
    return PromptManager(config)
