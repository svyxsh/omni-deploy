# repo_observer.py
import os
import time
import subprocess
from helpers import communicate

def run_git_command(command, repo_path):
    try:
        result = subprocess.run(command, cwd=repo_path, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=True)
        return result.stdout.strip()
    except subprocess.CalledProcessError as e:
        print(f"oops, git command failed: {' '.join(command)}")
        raise e

def poll_repository(repo_path, dispatcher_host, dispatcher_port):
    print(f"monitoring {repo_path} for new commits...")
    while True:
        try:
            run_git_command(["git", "fetch", "origin"], repo_path)
            latest_remote_hash = run_git_command(["git", "rev-parse", "origin/master"], repo_path)
            current_local_hash = run_git_command(["git", "rev-parse", "HEAD"], repo_path)
            
            if latest_remote_hash != current_local_hash:
                print(f"found new commit: {latest_remote_hash[:7]}")
                run_git_command(["git", "reset", "--hard", "origin/master"], repo_path)
                
                message = f"dispatch:{latest_remote_hash}"
                dispatcher_response = communicate(dispatcher_host, dispatcher_port, message)
                
                if dispatcher_response == "OK":
                    print("dispatcher got the job!")
        except Exception as error:
            print(f"something went wrong in the loop: {error}")
        time.sleep(5)

if __name__ == "__main__":
    # Hardcoded direct path execution for bulletproof running on Windows
    TARGET_CLONE_PATH = "D:/PROJECTS/CI system/test_repo_clone_obs"
    DISPATCHER_HOST = "localhost"
    DISPATCHER_PORT = 8888
    
    print("starting repo observer...")
    if os.path.exists(TARGET_CLONE_PATH):
        print("all set, monitoring started.")
        poll_repository(TARGET_CLONE_PATH, DISPATCHER_HOST, DISPATCHER_PORT)
    else:
        print(f"error: clone path doesn't exist: {TARGET_CLONE_PATH}")