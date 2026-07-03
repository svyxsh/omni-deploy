# test_runner.py
import socketserver
import threading
import subprocess
import os
import unittest
import io
from helpers import communicate

IS_BUSY = False
BUSY_LOCK = threading.Lock() # FIX: Added lock for thread safety

class TestRunnerHandler(socketserver.BaseRequestHandler):
    def handle(self):
        global IS_BUSY
        raw_message = self.request.recv(1024).strip().decode('utf-8')
        if not raw_message:
            return

        print(f"recv: {raw_message}")
        parts = raw_message.split(":")
        command_type = parts[0]

        if command_type == "ping":
            self.request.sendall(b"pong")
        elif command_type == "runtest":
            commit_id = parts[1]
            
            # FIX: Use lock to prevent race conditions when checking and updating IS_BUSY
            with BUSY_LOCK:
                is_currently_busy = IS_BUSY
                if not is_currently_busy:
                    IS_BUSY = True
                    
            if is_currently_busy:
                self.request.sendall(b"BUSY")
            else:
                self.request.sendall(b"OK")
                worker = threading.Thread(
                    target=execute_test_suite, 
                    args=(commit_id, self.server.repo_path, self.server.dispatcher_address)
                )
                worker.start()

def execute_test_suite(commit_id, repo_path, dispatcher_address):
    global IS_BUSY
    print(f"running tests for commit: {commit_id[:7]}")
    try:
        # FIX: Added check=True to ensure errors are caught and not silently ignored
        subprocess.run(["git", "clean", "-d", "-f", "-x"], cwd=repo_path, capture_output=True, check=True)
        subprocess.run(["git", "fetch", "origin"], cwd=repo_path, capture_output=True, check=True)
        subprocess.run(["git", "reset", "--hard", commit_id], cwd=repo_path, capture_output=True, check=True)
        
        test_directory = os.path.join(repo_path, "tests")
        suite = unittest.TestLoader().discover(start_dir=test_directory, pattern="test_*.py")
        
        output_buffer = io.StringIO()
        runner = unittest.TextTestRunner(stream=output_buffer, verbosity=2)
        result = runner.run(suite)
        test_results_log = output_buffer.getvalue()
        status = "PASS" if result.wasSuccessful() else "FAIL"
    except Exception as e:
        test_results_log = f"CI Runner Error: {str(e)}"
        status = "FAIL"

    try:
        communicate(dispatcher_address[0], dispatcher_address[1], f"results:{commit_id}:{status}:{test_results_log}")
    finally:
        with BUSY_LOCK:
            IS_BUSY = False

class CustomRunnerServer(socketserver.ThreadingTCPServer):
    def __init__(self, server_address, RequestHandlerClass, repo_path, dispatcher_address):
        super().__init__(server_address, RequestHandlerClass)
        self.repo_path = repo_path
        self.dispatcher_address = dispatcher_address

if __name__ == "__main__":
    # Hardcoded parameters for stability
    RUNNER_CLONE_PATH = "D:/PROJECTS/CI system/test_repo_clone_runner"
    RUNNER_PORT = 8900
    DISPATCHER_ADDRESS = ("localhost", 8888)

    print("starting test runner...")
    if not os.path.exists(RUNNER_CLONE_PATH):
        print(f"error: couldn't find {RUNNER_CLONE_PATH}")
        exit(1)

    runner_server = CustomRunnerServer(( "localhost", RUNNER_PORT), TestRunnerHandler, RUNNER_CLONE_PATH, DISPATCHER_ADDRESS)
    
    try:
        reply = communicate(DISPATCHER_ADDRESS[0], DISPATCHER_ADDRESS[1], f"register:localhost:{RUNNER_PORT}")
        if reply == "OK":
            print("connected to dispatcher")
            runner_server.serve_forever()
    except Exception as e:
        print(f"failed to connect to dispatcher: {e}")
