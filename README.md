# Custom Distributed CI/CD Engine

A lightweight, distributed Continuous Integration and Continuous Deployment (CI/CD) system built from scratch in Python. 

## 📖 Acknowledgements & Inspiration
This project's architecture is structurally inspired by and adapted from the chapter **"A Continuous Integration System"** authored by **Malini Das** in the open-source book ***500 Lines or Less*** (part of the *Architecture of Open Source Applications* series). 

While the core architectural concepts of decentralized runners and a central dispatcher belong to the original open-source design by Malini Das, the technical implementation, code optimizations, and multi-threaded concurrency safeguards within this specific repository were uniquely engineered to expand upon those concepts.

## 🏗️ System Architecture
The pipeline operates using standard Python networking (`socketserver`) to facilitate communication across four independent, specialized node scripts:

1. **Repo Observer (`repo_observer.py`)**: Continuously monitors the target repository for new commits. When a change is detected, it alerts the Dispatcher.
2. **Dispatcher (`dispatcher.py`)**: The central hub. It registers available runners, queues incoming commits, and routes jobs to free workers.
3. **Test Runner (`test_runner.py`)**: Checks out the specified commit in an isolated clone and executes the automated test suite using Python's `unittest` framework.
4. **Deploy Runner (`deploy_runner.py`)**: If the Test Runner reports a passing grade, the Dispatcher routes the commit to this node, which checks out the code and executes the repository's deployment scripts.

## ⚙️ Prerequisites
- Python 3.x
- Git installed and added to your system PATH
- A target Git repository (e.g., `test_repo`) located in the root directory.

## 🚀 Usage
You can launch all four components of the system instantly using the built-in Boot Manager.

```bash
python start_system.py
```
*Note: The Boot Manager will ask if you want to spawn external terminals or stream the color-coded output unified in the background.*
