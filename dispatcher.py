import socketserver
import os 
import threading

# --- Global State ---
# These lists manage the state of the CI system.
# ACTIVE_RUNNERS: A list of (host, port) tuples for runners that are available.
# PENDING_COMMITS: A list of commit IDs waiting to be tested.
ACTIVE_RUNNERS = []
PENDING_COMMITS = []
ACTIVE_DEPLOYERS = []
PENDING_DEPLOYMENTS = []
class DispatcherHandler(socketserver.BaseRequestHandler):
    """
    The request handler class for our server.
    It is instantiated once per connection to the server, and must
    override the handle() method to implement communication to the
    client.
    """
    def handle(self):
        # self.request is the TCP socket connected to the client
        raw_message = ""
        while True:
            chunk = self.request.recv(1024)
            if not chunk:
                break
            raw_message += chunk.decode('utf-8')
            
        raw_message = raw_message.strip()
        if not raw_message:
            return
        
        print(f"\n[NETWORK INBOUND] -> {raw_message}")
        
        # Messages are expected in the format "command:payload1:payload2:..."
        parts = raw_message.split(":")
        command_type = parts[0]
        payload = parts[1:]

        # Route the command to the appropriate handler method
        if command_type == "status":
            self.request.sendall(b"OK")
        
        elif command_type == "register":
            self.handle_runner_registration(payload)
        
        elif command_type == "dispatch":
            self.handle_new_commit(payload)

        elif command_type == "results":
            self.handle_test_results(payload)

        elif command_type == "deploy_register":
            self.handle_deployer_registration(payload)
            
        elif command_type == "deploy_results":
            self.handle_deploy_results(payload)

    def handle_runner_registration(self, payload):
        """Handles a 'register' command from a new runner."""
        runner_host , runner_port = payload[0] , int(payload[1])
        runner_address = (runner_host, runner_port)

        # Add the runner to the pool if it's not already there
        if runner_address not in ACTIVE_RUNNERS:
            ACTIVE_RUNNERS.append(runner_address)
            print(f"[POOL UPDATE] Registered free runner at {runner_host}:{runner_port}")

        self.request.sendall(b"OK")

    def handle_deployer_registration(self, payload):
        deployer_host, deployer_port = payload[0], int(payload[1])
        deployer_address = (deployer_host, deployer_port)

        if deployer_address not in ACTIVE_DEPLOYERS:
            ACTIVE_DEPLOYERS.append(deployer_address)
            print(f"[POOL UPDATE] Registered free deployer at {deployer_host}:{deployer_port}")

        self.request.sendall(b"OK")

    def handle_new_commit(self, payload):
        """Handles a 'dispatch' command, indicating a new commit to be tested."""
        commit_id = payload[0]
        print(f"[QUEUE] Commit flagged by observer : {commit_id[:7]}")

        # Add the commit to the queue of pending jobs
        PENDING_COMMITS.append(commit_id)
        self.request.sendall(b"OK")

        # Start a new thread to try and allocate the job immediately
        threading.Thread(target=allocate_jobs_to_runners).start()

    def handle_test_results(self,payload):
        """Handles a 'results' command, receiving test logs from a runner."""
        commit_id = payload[0]
        status = payload[1]
        # Re-join the rest of the payload in case the logs contained ':'
        raw_logs = ":".join(payload[2:])

        print(f"[RESULTS] Storing completed test run logs for {commit_id[:7]} (Status: {status})")

        # Create a directory to store test results if it doesn't exist
        os.makedirs("test_results", exist_ok=True)
        file_path = os.path.join("test_results", f"commit_{commit_id}.txt")
        
        # Write the received logs to a file named after the commit ID
        with open(file_path , "w") as log_file:
            log_file.write(raw_logs)

        self.request.sendall(b"OK")

        if status == "PASS":
            print(f"[DEPLOY QUEUE] Commit {commit_id[:7]} passed tests. Queuing for deployment.")
            PENDING_DEPLOYMENTS.append(commit_id)
            threading.Thread(target=allocate_jobs_to_deployers).start()

    def handle_deploy_results(self, payload):
        commit_id = payload[0]
        raw_logs = ":".join(payload[1:])
        print(f"[DEPLOY RESULTS] Deployment logs for {commit_id[:7]}:\n{raw_logs}")
        self.request.sendall(b"OK")
   
def allocate_jobs_to_runners():
    """
    A standalone function to allocate pending jobs to available runners.
    This runs in a separate thread and is triggered when a new commit arrives.
    """

    # If there's nothing to build, or no machines to build it on, sit tight
    if not PENDING_COMMITS or not ACTIVE_RUNNERS:
        return

    # This is a simple First-In-First-Out (FIFO) queue
    current_commit = PENDING_COMMITS[0]
    from helpers import communicate # Keeps connection utilities decoupled

    # Iterate through a copy of the list to allow safe removal during iteration
    for runner in list(ACTIVE_RUNNERS):
        host, port = runner
        try:
            # Connect and ask the runner to execute this specific target commit
            reply = communicate(host, port, f"runtest:{current_commit}")
            
            if reply == "OK":
                # The runner accepted the job
                print(f"[JOB DISPATCHED] Assigned commit {current_commit[:7]} to runner on port {port}")
                PENDING_COMMITS.pop(0) # Remove from wait list
                # Since the job is assigned, we can stop looking for a runner
                break
                
            elif reply == "BUSY":
                # The runner is busy, try the next one
                print(f"[LOAD BALANCER] Runner on port {port} is working. Checking next...")
                continue
                
        except Exception:
            # If communication fails, assume the runner has crashed or is unreachable
            print(f"[CRASH DETECTED] Runner on port {port} dropped. Purging from active pool.")
            ACTIVE_RUNNERS.remove(runner)

def allocate_jobs_to_deployers():
    if not PENDING_DEPLOYMENTS or not ACTIVE_DEPLOYERS:
        return

    current_commit = PENDING_DEPLOYMENTS[0]
    from helpers import communicate

    for deployer in list(ACTIVE_DEPLOYERS):
        host, port = deployer
        try:
            reply = communicate(host, port, f"deploy:{current_commit}")
            if reply == "OK":
                print(f"[JOB DISPATCHED] Assigned deployment of {current_commit[:7]} to deployer on port {port}")
                PENDING_DEPLOYMENTS.pop(0)
                break
            elif reply == "BUSY":
                print(f"[LOAD BALANCER] Deployer on port {port} is working. Checking next...")
                continue
        except Exception:
            print(f"[CRITICAL] Deployer on port {port} dropped. Purging from active pool.")
            ACTIVE_DEPLOYERS.remove(deployer)


if __name__ == "__main__":
    # --- Server Initialization ---
    SERVER_HOST, SERVER_PORT = "localhost", 8888
    
    # ThreadingTCPServer creates a new thread for each incoming connection.
    # This allows the dispatcher to handle multiple runners and observers concurrently.
    dispatcher_server = socketserver.ThreadingTCPServer(
        (SERVER_HOST, SERVER_PORT), 
        DispatcherHandler
    )
    
    print(f"=== Custom CI Engine Central Dispatcher Live ===")
    print(f"Listening for connections on {SERVER_HOST}:{SERVER_PORT}...")
    
    # Start the server and listen for connections indefinitely
    try:
        dispatcher_server.serve_forever()
    except KeyboardInterrupt:
        # Allow a clean shutdown with Ctrl+C
        print("\nShutting down central dispatcher hub safely.")
        dispatcher_server.server_close()
    
