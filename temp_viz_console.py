
# -*- coding: utf-8 -*-
import sys
import time
import os

log_file = r"C:\git\PyCatan_AI\game_viz.log"

print("PyCatan - Game Visualization Console")
print("=" * 50)
print("This window shows real-time game state updates.")
print("Keep this window open while playing!")
print("=" * 50)
print(f"Reading from: {log_file}")

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
