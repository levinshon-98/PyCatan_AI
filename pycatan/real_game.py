"""
RealGame - Complete Interactive Catan Game Experience

This class orchestrates a full Catan game with multiple interfaces:
- Main console for player input and game commands
- Console visualization for game state display  
- Web browser interface for interactive board view

The game provides a complete, multi-interface gaming experience.
"""

import threading
import time
import webbrowser
from typing import List, Optional
import subprocess
import sys
import os

from .game_manager import GameManager
from .human_user import HumanUser
from .console_visualization import ConsoleVisualization
from .web_visualization import WebVisualization
from .visualization import VisualizationManager


class RealGame:
    """
    Complete interactive Catan game with multiple interfaces.
    
    Features:
    - Player setup (names, count)
    - Main game loop with human input
    - Real-time console visualization
    - Web browser board display
    - Coordinated multi-interface experience
    """
    
    def __init__(self):
        """Initialize the real game manager."""
        self.num_players = 0
        self.player_names = []
        self.users = []
        self.game_manager = None
        self.visualization_manager = None
        self.console_viz = None
        self.web_viz = None
        self.web_thread = None
        self.console_thread = None
        self.is_running = False
        
    def setup_game(self) -> bool:
        """
        Interactive setup for the game.
        Collects number of players and their names.
        
        Returns:
            bool: True if setup successful
        """
        print("🎮 Welcome to PyCatan - Interactive Settlers of Catan!")
        print("=" * 60)
        
        # Get number of players
        while True:
            try:
                self.num_players = int(input("How many players? (2-4): "))
                if 2 <= self.num_players <= 4:
                    break
                else:
                    print("Please enter a number between 2 and 4.")
            except ValueError:
                print("Please enter a valid number.")
        
        print(f"\nGreat! Setting up a game for {self.num_players} players.")
        print("=" * 40)
        
        # Get player names
        self.player_names = []
        for i in range(self.num_players):
            while True:
                name = input(f"Enter name for Player {i + 1}: ").strip()
                if name and len(name) <= 20:
                    self.player_names.append(name)
                    break
                elif not name:
                    print("Name cannot be empty. Please try again.")
                else:
                    print("Name too long (max 20 characters). Please try again.")
        
        print(f"\n✅ Players registered: {', '.join(self.player_names)}")
        
        # Create user objects
        self.users = []
        for i, name in enumerate(self.player_names):
            user = HumanUser(name, i)
            self.users.append(user)
        
        print("✅ Player objects created successfully!")
        return True
    
    def setup_interfaces(self) -> bool:
        """
        Setup all game interfaces (console, web).
        
        Returns:
            bool: True if setup successful
        """
        print("\n🖥️  Setting up game interfaces...")
        print("=" * 40)
        
        try:
            # Define log file for visualization
            self.viz_log_file = os.path.abspath("game_viz.log")
            # Clear existing log file
            with open(self.viz_log_file, 'w', encoding='utf-8') as f:
                f.write("")
                
            # Create console visualization pointing to log file
            self.console_viz = ConsoleVisualization(
                use_colors=True,
                compact_mode=False,
                output_file=self.viz_log_file
            )
            print("✅ Console visualization ready (redirected to separate window)")
            
            # Create web visualization  
            self.web_viz = WebVisualization(
                port=5000,
                auto_open=False,  # We'll open manually
                debug=False
            )
            print("✅ Web visualization ready")
            
            # Create visualization manager
            self.visualization_manager = VisualizationManager()
            self.visualization_manager.add_visualization(self.console_viz)
            self.visualization_manager.add_visualization(self.web_viz)
            
            print("✅ Visualization manager configured")
            
            # Open separate console for visualization (Windows only)
            if os.name == 'nt':  # Windows
                try:
                    self._open_visualization_console()
                    print("✅ Separate visualization console opened")
                except Exception as e:
                    print(f"⚠️  Could not open separate console: {e}")
            
            return True
            
        except Exception as e:
            print(f"❌ Failed to setup interfaces: {e}")
            return False

    def _open_visualization_console(self):
        """Open a separate console window for visualization (Windows only)."""
        if os.name != 'nt':
            return  # Only works on Windows
        
        # Create a Python script that will run in the new console
        # This script tails the log file
        script_content = f'''
# -*- coding: utf-8 -*-
import sys
import time
import os

log_file = r"{self.viz_log_file}"

print("PyCatan - Game Visualization Console")
print("=" * 50)
print("This window shows real-time game state updates.")
print("Keep this window open while playing!")
print("=" * 50)
print(f"Reading from: {{log_file}}")

# Wait for file to exist
while not os.path.exists(log_file):
    time.sleep(0.1)

# Tail the file
with open(log_file, 'r', encoding='utf-8') as f:
    # Go to the end of file
    # f.seek(0, 2) 
    # Actually start from beginning since we just created it
    
    while True:
        line = f.readline()
        if line:
            print(line, end='')
        else:
            time.sleep(0.1)
'''
        
        # Write the script to a temporary file
        temp_script = "temp_viz_console.py"
        with open(temp_script, 'w', encoding='utf-8') as f:
            f.write(script_content)
        
        # Open new console window
        try:
            # Use proper path without extra quotes
            cmd_args = [
                'cmd', '/k', 
                f'python {temp_script}'
            ]
            subprocess.Popen(cmd_args, creationflags=subprocess.CREATE_NEW_CONSOLE)
        except Exception as e:
            print(f"Failed to open console: {e}")
    
    def start_game(self) -> bool:
        """
        Start the actual game with all interfaces.
        
        Returns:
            bool: True if game started successfully
        """
        print("\n🚀 Starting the game...")
        print("=" * 40)
        
        try:
            # Create users if they don't exist
            if not self.users:
                from .human_user import HumanUser
                self.users = []
                for i, name in enumerate(self.player_names):
                    user = HumanUser(name, i)
                    self.users.append(user)
                print(f"✅ Created {len(self.users)} user objects")
            
            # Create GameManager
            self.game_manager = GameManager(
                users=self.users,
                game_config={"enable_visualizations": True},
                random_seed=0
            )
            
            # Set up visualizations with GameManager
            self.game_manager.visualization_manager = self.visualization_manager
            
            # Start the game
            self.game_manager.start_game()
            print("✅ Game engine started")
            
            # Start web server in background thread
            self.web_thread = threading.Thread(
                target=self._run_web_server,
                daemon=True
            )
            self.web_thread.start()
            
            # Give web server time to start
            time.sleep(2)
            
            # Update web interface with initial game state
            if self.web_viz:
                try:
                    self.web_viz.update_full_state(self.game_manager.get_full_state())
                    print("✅ Initial web state updated")
                except Exception as e:
                    print(f"⚠️  Initial web update failed: {e}")
            
            # Open web browser
            print("🌐 Opening web browser for board view...")
            webbrowser.open('http://localhost:5000')
            
            print("✅ Web interface launched")
            
            self.is_running = True
            return True
            
        except Exception as e:
            print(f"❌ Failed to start game: {e}")
            return False
    
    def _run_web_server(self):
        """Run the web visualization server in background thread."""
        try:
            # Suppress Flask/Werkzeug logs
            import logging
            logging.getLogger('werkzeug').setLevel(logging.ERROR)
            logging.getLogger('flask').setLevel(logging.ERROR)
            
            self.web_viz.__enter__()  # Start the server
            # The server runs in its own event loop
        except Exception as e:
            print(f"❌ Web server error: {e}")
    
    def _cleanup(self):
        """Clean up resources when game ends."""
        print("\n🧹 Cleaning up...")
        
        try:
            # Stop game manager
            if self.game_manager:
                self.game_manager.end_game()
            
            # Stop web server
            if self.web_viz:
                self.web_viz.__exit__(None, None, None)
            
            # Clean up temp files
            if os.name == 'nt':  # Windows
                try:
                    if os.path.exists("temp_viz_console.py"):
                        os.remove("temp_viz_console.py")
                except:
                    pass
                
            print("✅ Cleanup completed")
            
        except Exception as e:
            print(f"⚠️  Cleanup error: {e}")
    
    def run(self):
        """
        Run the complete game experience.
        This is the main entry point for starting a full game.
        """
        try:
            # Step 1: Setup game (players, names)
            if not self.setup_game():
                return False
            
            # Step 2: Setup interfaces (console, web)
            if not self.setup_interfaces():
                return False
            
            # Step 3: Start game engine
            if not self.start_game():
                return False
            
            # Step 4: Play the game (delegate to GameManager)
            print("\n🎯 Game Started! Control passed to GameManager.")
            print("=" * 60)
            print("🔥 Multiple interfaces are now active:")
            print("   📱 This console - for entering commands")
            print("   🖥️  Console visualization - for game state display")  
            print("   🌐 Web browser - for interactive board view")
            print("=" * 60)
            
            try:
                self.game_manager.game_loop()
            except KeyboardInterrupt:
                print("\n\n🛑 Game interrupted by user.")
            finally:
                self._cleanup()
            
            return True
            
        except Exception as e:
            print(f"❌ Fatal error: {e}")
            return False


def main():
    """Main entry point for running a complete Catan game."""
    print("🏴‍☠️ Starting PyCatan Real Game Experience...")
    
    real_game = RealGame()
    success = real_game.run()
    
    if success:
        print("\n🎉 Thanks for playing PyCatan!")
    else:
        print("\n😔 Game ended with errors.")
    
    print("👋 Goodbye!")


if __name__ == "__main__":
    main()