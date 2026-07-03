import subprocess
import time
import sys
import os
import threading
from datetime import datetime

# Windows-specific flag to open a new command prompt window
CREATE_NEW_CONSOLE = 0x00000010

# ANSI Color Codes for terminal formatting
COLORS = {
    "DISPATCHER": "\033[36m",      # Cyan
    "TEST_RUNNER": "\033[32m",     # Green
    "DEPLOY_RUNNER": "\033[33m",   # Yellow
    "REPO_OBSERVER": "\033[35m",   # Magenta
    "RESET": "\033[0m"
}

scripts_to_launch = [
    "dispatcher.py",
    "test_runner.py",
    "deploy_runner.py",
    "repo_observer.py"
]

def stream_output(process, prefix):
    """Reads lines from the process stdout and prints them with a color-coded prefix."""
    color = COLORS.get(prefix, "")
    reset = COLORS["RESET"]
    prefix_padded = f"{prefix:<13}"
    
    for line in iter(process.stdout.readline, b''):
        raw_text = line.decode('utf-8', errors='replace').rstrip()
        timestamp = datetime.now().strftime("%H:%M:%S")
        print(f"{color}[{timestamp}] {prefix_padded} |{reset} {raw_text}")

print("starting CI/CD system boot manager...")

choice = input("open in separate external windows? (y/n): ").strip().lower()
separate_windows = choice == 'y'

processes = []

for script_name in scripts_to_launch:
    if not os.path.exists(script_name):
        print(f"error: couldn't find {script_name}!")
        continue

    prefix = script_name.split('.')[0].upper()

    if separate_windows:
        print(f"launching {script_name} externally...")
        p = subprocess.Popen(
            [sys.executable, script_name],
            creationflags=CREATE_NEW_CONSOLE
        )
        processes.append(p)
    else:
        print(f"launching {script_name}...")
        # We pass '-u' to force Python to flush its print statements immediately
        p = subprocess.Popen(
            [sys.executable, "-u", script_name], 
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT
        )
        processes.append(p)
        # Start a thread to read the output continuously
        t = threading.Thread(target=stream_output, args=(p, prefix), daemon=True)
        t.start()
    
    time.sleep(1)

print("\nall systems dispatched.")
if separate_windows:
    print("you should see 4 new terminal windows.")
else:
    print("streaming logs below... press Ctrl+C to stop.")
    try:
        # Keep the main script alive to continue streaming output
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nshutting down CI/CD components...")
        for p in processes:
            p.terminate()
        print("done.")
