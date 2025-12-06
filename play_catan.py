#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PyCatan Game Launcher

Simple script to launch a complete PyCatan game experience.
Run this file to start playing!

Features:
- Interactive player setup
- Multiple interface windows
- Console + Web visualization
- Real-time game updates
"""

from pycatan import RealGame

if __name__ == "__main__":
    print("=" * 60)
    print("Welcome to PyCatan!")
    print("=" * 60)
    print("Starting the complete game experience...")
    print()
    print("What will happen:")
    print("• You'll enter player count and names")
    print("• A separate console will open for game visualization")
    print("• Your web browser will open with the game board")
    print("• You'll play in this main console")
    print()
    
    # Create and run the game
    game = RealGame()
    game.run()