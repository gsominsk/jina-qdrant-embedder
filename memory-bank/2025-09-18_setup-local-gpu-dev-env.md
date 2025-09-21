# Task: Setup Local Development Environment for macOS with GPU Acceleration

**Date:** 2025-09-18

**Objective:** To enable the `embeddings` service to use the host macOS GPU (Apple MPS) for accelerated performance during local development, without altering the primary Docker-based architecture.

---

### Analysis

- **Problem:** The `embeddings` service, when run inside a standard Linux Docker container on macOS, cannot access the host's GPU. This is a fundamental limitation of Docker Desktop for Mac.
- **Solution:** A hybrid approach where the `qdrant` database continues to run in Docker for convenience, while the computationally intensive `embeddings` service is run directly on the host macOS to gain access to the GPU.
- **Impact:** This change is additive. It introduces a new, optional workflow for macOS developers and does not modify or break the existing, fully-containerized setup.

---

### Implementation Plan

1.  **Create Python Virtual Environment:**
    -   A `venv` will be created in the project root to isolate Python dependencies.
    -   This prevents conflicts with system-wide packages.

2.  **Install Dependencies:**
    -   All packages listed in `embeddings/app/requirements.txt` will be installed into the `venv`.

3.  **Create Local Run Script (`scripts/run_local.sh`):**
    -   A new shell script will be created to automate the local launch process.
    -   The script will:
        -   Check for and activate the `venv`.
        -   Set any necessary environment variables.
        -   Start the `embeddings` service using `uvicorn`.

4.  **Update Documentation (`README.md`):**
    -   A new section will be added to the main `README.md`.
    -   It will provide clear, step-by-step instructions for macOS users on how to set up and use this local GPU-accelerated development environment.
