# Active Context

This file tracks the project's current status, including recent changes, current goals, and open questions.
2025-09-08 21:17:27 - Log of updates made.

*

## Current Focus

* Initializing Memory Bank structure  
* Defining project scope for MCP server research  

## Recent Changes

* Created productContext.md  
* Switched to Architect mode  

## Open Questions/Issues

* Which embedding providers to prioritize?  
* What vector database to use?  
2025-09-08 21:20:17 - Memory Bank initialization complete. Switching to research phase.
[2025-09-09 20:32:51] - Successfully deployed a custom embedding service using FastAPI and `transformers`. The service is now fully functional.
[2025-09-14 12:56:57] - **Focus:** Finalizing the debugging and optimization of the `jina-openai` embedding service.
**Recent Changes:**
- Identified and resolved OOM kill issue by implementing an `asyncio.Semaphore`.
- Tuned the semaphore value to 8 for optimal performance and stability.
- Confirmed via logs that memory usage is now stable under load (~4.4GB peak).
- Updated `decisionLog.md` with the final resolution.
**Next Steps:** Update the project `README.md` with a summary of the problem and solution.
[2025-09-14 17:16:36] - [Current Focus] Verifying the fix for a persistent, slow memory leak that occurs during indexing. A new middleware for aggressive garbage collection has been implemented. Awaiting final test run.
[2025-09-14 17:16:36] - [Recent Changes] Added a FastAPI middleware to trigger `gc.collect()` after each HTTP request to resolve a memory leak related to request/response objects.