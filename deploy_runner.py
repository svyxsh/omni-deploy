# deploy_runner.py
import socketserver
import threading
import subprocess
import os
import sys
from helpers import communicate

IS_BUSY = False
BUSY_LOCK = threading.Lock()

class DeployRunnerHandler(socketserver.BaseRequestHandler):
    def handle(self):
        global IS_BUSY
        raw_message = self.request.recv(1024).strip().decode('utf-8')
        if not raw_message:
            return

        print(f"\n[DEPLOYER INBOUND] -> {raw_message}")
        parts = raw_message.split(":")
        command_type = parts[0]

        if command_type == "ping":
            self.request.sendall(b"pong")
        elif command_type == "deploy":
            commit_id = parts[1]
            
            with BUSY_LOCK:
                is_currently_busy = IS_BUSY
                if not is_currently_busy:
                    IS_BUSY = True
                    
            if is_currently_busy:
                self.request.sendall(b"BUSY")
            else:
                self.request.sendall(b"OK")
                worker = threading.Thread(
                    target=execute_deployment, 
                    args=(commit_id, self.server.repo_path, self.server.dispatcher_address)
                )
                worker.start()

def execute_deployment(commit_id, repo_path, dispatcher_address):
    global IS_BUSY
    print(f"[WORKER] Starting deployment workflow for commit: {commit_id[:7]}")
    try:
        subprocess.run(["git", "clean", "-d", "-f", "-x"], cwd=repo_path, capture_output=True, check=True)
        subprocess.run(["git", "fetch", "origin"], cwd=repo_path, capture_output=True, check=True)
        subprocess.run(["git", "reset", "--hard", commit_id], cwd=repo_path, capture_output=True, check=True)
        
        deploy_script = os.path.join(repo_path, "deploy.py")
        if os.path.exists(deploy_script):
            result = subprocess.run([sys.executable, "deploy.py"], cwd=repo_path, capture_output=True, text=True)
            deploy_results_log = result.stdout + "\n" + result.stderr
            if result.returncode != 0:
                deploy_results_log = f"Deploy script failed with code {result.returncode}:\n{deploy_results_log}"
        else:
            deploy_results_log = "No deploy.py script found in repository. Skipping execution."
            
    except Exception as e:
        deploy_results_log = f"CI Deployer Error: {str(e)}"

    try:
        communicate(dispatcher_address[0], dispatcher_address[1], f"deploy_results:{commit_id}:{deploy_results_log}")
    finally:
        with BUSY_LOCK:
            IS_BUSY = False

class CustomDeployerServer(socketserver.ThreadingTCPServer):
    def __init__(self, server_address, RequestHandlerClass, repo_path, dispatcher_address):
        super().__init__(server_address, RequestHandlerClass)
        self.repo_path = repo_path
        self.dispatcher_address = dispatcher_address

if __name__ == "__main__":
    # Hardcoded parameters for stability
    DEPLOYER_CLONE_PATH = "D:/PROJECTS/CI system/test_repo_clone_deployer"
    DEPLOYER_PORT = 8901
    DISPATCHER_ADDRESS = ("localhost", 8888)

    print("=== DEPLOY RUNNER DIAGNOSTIC BOOT ===")
    if not os.path.exists(DEPLOYER_CLONE_PATH):
        print(f"[FAIL] Path could not be found: {DEPLOYER_CLONE_PATH}")
        print("Please clone the repo into this path to run the deployer.")
        exit(1)

    deployer_server = CustomDeployerServer(( "localhost", DEPLOYER_PORT), DeployRunnerHandler, DEPLOYER_CLONE_PATH, DISPATCHER_ADDRESS)
    
    try:
        reply = communicate(DISPATCHER_ADDRESS[0], DISPATCHER_ADDRESS[1], f"deploy_register:localhost:{DEPLOYER_PORT}")
        if reply == "OK":
            print("[SUCCESS] Check-in confirmed with Dispatcher.")
            deployer_server.serve_forever()
    except Exception as e:
        print(f"[CRITICAL] Connection to Dispatcher failed: {e}")
