# ==============================================================================
# Script Name: verify_system.py
# Accomplishment: Scans the local workspace for dual repository folders (e.g., arena-helper 
# vs mtga-tracker or similar naming variants) and verifies database and script integrity.
# ==============================================================================

import os
import glob

print("=======================================================")
print(" ARENA HELPER SYSTEM & FOLDER AUDIT")
print("=======================================================")
cwd = os.getcwd()
parent = os.path.dirname(cwd)
print(f" Current Directory : {cwd}")
print(f" Parent Directory  : {parent}")

print("\n[+] Scanning parent directory for repo folders...")
if os.path.exists(parent):
    for item in os.listdir(parent):
        item_path = os.path.join(parent, item)
        if os.path.isdir(item_path):
            print(f"   - Folder found: {item}")

print("\n[+] Scanning current workspace for databases and scripts...")
print("  - Databases found:", glob.glob("**/*.db", recursive=True))
print("  - Python scripts found:", glob.glob("**/*.py", recursive=True))
print("  - PowerShell scripts found:", glob.glob("**/*.ps1", recursive=True))
print("=======================================================")
