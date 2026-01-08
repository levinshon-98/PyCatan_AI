#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
LLM Logger Console - Displays real-time LLM communication logs

This runs in a separate console window and shows:
- Prompts sent to Gemini
- Responses received
- Errors and timing
"""

import sys
import time
import os
from pathlib import Path

# Configure for Windows
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

# Color codes for Windows console
class Colors:
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    END = '\033[0m'
    BOLD = '\033[1m'

def print_header():
    """Print welcome header."""
    print("=" * 70)
    print(f"{Colors.CYAN}[LLM LOGGER] Real-time Gemini Communication{Colors.END}")
    print("=" * 70)
    print()
    print("This window shows all communication with the LLM.")
    print("Keep it open while playing!")
    print()
    print("=" * 70)
    print()

def watch_log_file(log_file: Path):
    """Watch a log file and print new lines."""
    print(f"[WATCHING] {log_file}")
    print("-" * 70)
    
    # Wait for file to exist
    while not log_file.exists():
        time.sleep(0.5)
    
    # Start from end of file
    with open(log_file, 'r', encoding='utf-8', errors='replace') as f:
        # Go to end
        f.seek(0, 2)
        
        while True:
            line = f.readline()
            if line:
                # Color code based on content
                if '[SEND]' in line or '[PROMPT]' in line:
                    print(f"{Colors.BLUE}{line.rstrip()}{Colors.END}")
                elif '[RECV]' in line or '[RESPONSE]' in line:
                    print(f"{Colors.GREEN}{line.rstrip()}{Colors.END}")
                elif '[ERROR]' in line or 'Error' in line:
                    print(f"{Colors.RED}{line.rstrip()}{Colors.END}")
                elif '[LLM]' in line:
                    print(f"{Colors.YELLOW}{line.rstrip()}{Colors.END}")
                else:
                    print(line.rstrip())
            else:
                time.sleep(0.1)

def main():
    """Main entry point."""
    print_header()
    
    # Find session directory - use absolute path from script location
    script_dir = Path(__file__).parent.absolute()
    base_dir = script_dir / "my_games"
    
    print(f"[DEBUG] Script dir: {script_dir}")
    print(f"[DEBUG] Base dir: {base_dir}")
    print(f"[DEBUG] Base dir exists: {base_dir.exists()}")
    
    # Look for current session file
    current_session_file = base_dir / "current_session.txt"
    
    session_name = None
    log_file = None
    
    if current_session_file.exists():
        session_name = current_session_file.read_text().strip()
        print(f"[DEBUG] Session name from file: {session_name}")
        # Handle both full path and just session name
        if Path(session_name).is_absolute():
            log_file = Path(session_name) / "llm_communication.log"
        else:
            log_file = base_dir / session_name / "llm_communication.log"
        print(f"[DEBUG] Log file path: {log_file}")
        print(f"[DEBUG] Log file exists: {log_file.exists()}")
    else:
        print(f"[DEBUG] No current_session.txt at {current_session_file}")
        # Find most recent session
        sessions = sorted(base_dir.glob("session_*"), key=lambda p: p.stat().st_mtime, reverse=True)
        print(f"[DEBUG] Found sessions: {[s.name for s in sessions]}")
        if sessions:
            log_file = sessions[0] / "llm_communication.log"
    
    if log_file is None or not log_file.parent.exists():
        print("[!] No sessions found. Start a game first!")
        print(f"[?] Looking in: {base_dir}")
        input("Press Enter to exit...")
        return
    
    print(f"[LOG FILE] {log_file}")
    print()
    
    try:
        watch_log_file(log_file)
    except KeyboardInterrupt:
        print("\n[STOPPED] Logger closed.")

if __name__ == "__main__":
    main()
