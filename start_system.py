import subprocess
import time
import sys
import os
import threading

# Windows-specific flag to open a new command prompt window
CREATE_NEW_CONSOLE = 0x00000010

# ANSI Color Codes for terminal formatting
COLORS = {
    "DISPATCHER": "\033[94m",      # Blue
    "TEST_RUNNER": "\033[92m",     # Green
    "DEPLOY_RUNNER": "\033[93m",   # Yellow
    "REPO_OBSERVER": "\033[95m",   # Magenta
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
    
    for line in iter(process.stdout.readline, b''):
        raw_text = line.decode('utf-8', errors='replace').rstrip()
        # Colorize just the prefix box to make the terminal easy to read
        print(f"{color}[{prefix}]{reset} {raw_text}")

print("=== CI/CD System Boot Manager ===")

choice = input("Do you want to open these in separate external windows? (y/n): ").strip().lower()
separate_windows = choice == 'y'

processes = []

for script_name in scripts_to_launch:
    if not os.path.exists(script_name):
        print(f"[ERROR] Could not find {script_name} in the current directory!")
        continue

    prefix = script_name.split('.')[0].upper()

    if separate_windows:
        print(f"Launching {script_name} in a new external terminal...")
        p = subprocess.Popen(
            [sys.executable, script_name],
            creationflags=CREATE_NEW_CONSOLE
        )
        processes.append(p)
    else:
        print(f"Launching {script_name} in the background...")
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

print("\nAll systems have been dispatched!")
if separate_windows:
    print("You should now see 4 new terminal windows.")
else:
    print("Output will stream below. Press Ctrl+C to safely kill all background processes.")
    try:
        # Keep the main script alive to continue streaming output
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nShutting down all CI/CD components...")
        for p in processes:
            p.terminate()
        print("Shutdown complete.")
