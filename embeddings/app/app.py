import os
import logging
import asyncio
import psutil
import threading
import time
import gc
import tracemalloc
import sys
import ctypes
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, Response
from pydantic import BaseModel
from typing import List, Union
from collections import deque

# pip install transformers torch
from transformers import AutoTokenizer, AutoModel
import torch
import numpy as np
from torch.nn import functional as F

# Настройка логирования
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class Stats:
    def __init__(self):
        self.requests_processed = 0
        self.total_wait_time = 0.0
        self.max_wait_time = 0.0
        self.max_queue_depth = 0
        self.lock = asyncio.Lock()

    async def update(self, wait_time, queue_depth):
        async with self.lock:
            self.requests_processed += 1
            self.total_wait_time += wait_time
            if wait_time > self.max_wait_time:
                self.max_wait_time = wait_time
            if queue_depth > self.max_queue_depth:
                self.max_queue_depth = queue_depth

    async def get_and_reset(self):
        async with self.lock:
            stats = {
                "requests_processed": self.requests_processed,
                "avg_wait_time": self.total_wait_time / self.requests_processed if self.requests_processed > 0 else 0,
                "max_wait_time": self.max_wait_time,
                "max_queue_depth": self.max_queue_depth
            }
            self.requests_processed = 0
            self.total_wait_time = 0.0
            self.max_wait_time = 0.0
            self.max_queue_depth = 0
            return stats


# Получаем имя модели из переменной окружения, с дефолтным значением
MODEL_NAME = os.environ.get("MODEL_NAME", "jinaai/jina-embeddings-v2-base-code")

# Загружаем модель и токенизатор
tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME, trust_remote_code=True)

# Определяем устройство для вычислений (MPS для Apple Silicon GPU или CPU)
if torch.backends.mps.is_available():
    device = torch.device("mps")
    logger.info("Using Apple MPS (GPU) for computations.")
else:
    device = torch.device("cpu")
    logger.info("MPS not available, using CPU for computations.")

model = AutoModel.from_pretrained(MODEL_NAME, trust_remote_code=True).to(device)


# Размер микробатча для обработки
MICRO_BATCH_SIZE = int(os.environ.get("MICRO_BATCH_SIZE", "16"))

def mean_pooling(model_output, attention_mask):
    token_embeddings = model_output[0]
    input_mask_expanded = attention_mask.unsqueeze(-1).expand(token_embeddings.size()).float()
    return torch.sum(token_embeddings * input_mask_expanded, 1) / torch.clamp(input_mask_expanded.sum(1), min=1e-9)

def normalize(vectors):
    return F.normalize(vectors, p=2, dim=1)

class EmbeddingsRequest(BaseModel):
    model: str
    input: Union[str, List[str]]


# --- Memory Profiling ---
def log_memory_usage():
    """Logs memory usage at regular intervals."""
    process = psutil.Process(os.getpid())
    while True:
        mem_info = process.memory_info()
        # Log memory usage in MB
        logger.info(f"Memory Usage: RSS={mem_info.rss / 1024 / 1024:.2f} MB, VMS={mem_info.vms / 1024 / 1024:.2f} MB")
        time.sleep(15)  # Log every 15 seconds

async def log_stats_periodically(stats: Stats, interval: int = 30):
    """Logs aggregated stats at regular intervals."""
    while True:
        await asyncio.sleep(interval)
        current_stats = await stats.get_and_reset()
        if current_stats["requests_processed"] > 0:
            logger.info(
                f"STATS (last {interval}s): "
                f"Processed={current_stats['requests_processed']}, "
                f"AvgWait={current_stats['avg_wait_time']:.2f}s, "
                f"MaxWait={current_stats['max_wait_time']:.2f}s, "
                f"MaxQueue={current_stats['max_queue_depth']}"
            )

async def periodic_memory_cleanup(app: FastAPI, idle_threshold: int = 60, check_interval: int = 15):
    """
    Monitors application idle time and, if idle for `idle_threshold` seconds,
    runs garbage collection, empties PyTorch cache, and attempts to release
    memory back to the OS on Linux/macOS.
    """
    # Check if malloc_trim is available and load it once
    libc = None
    try:
        if sys.platform in ["linux", "darwin"]:
            libc = ctypes.CDLL("libc.so.6" if sys.platform == "linux" else "libc.dylib")
    except (OSError, AttributeError):
        logger.warning("Could not load C library or find malloc_trim. Memory trimming will be disabled.")
        libc = None

    logger.info(f"Idle cleanup configured: Threshold={idle_threshold}s, Check Interval={check_interval}s.")

    while True:
        await asyncio.sleep(check_interval)

        time_since_last_activity = time.monotonic() - app.state.last_activity_time
        
        if time_since_last_activity > idle_threshold:
            logger.info(f"App has been idle for {time_since_last_activity:.0f}s. Triggering aggressive cleanup.")

            # 1. Python's garbage collection
            gc.collect()
            logger.info("Garbage collection finished.")

            # 2. PyTorch cache cleanup
            if torch.backends.mps.is_available():
                torch.mps.empty_cache()
                logger.info("PyTorch MPS cache emptied.")
            elif torch.cuda.is_available():
                torch.cuda.empty_cache()
                logger.info("PyTorch CUDA cache emptied.")

            # 3. Force release of memory to the OS (Linux/macOS only)
            if libc and hasattr(libc, 'malloc_trim'):
                try:
                    result = libc.malloc_trim(0)
                    if result == 1:
                        logger.info("malloc_trim succeeded: memory released to OS.")
                    else:
                        logger.info("malloc_trim executed, but no memory was released.")
                except Exception as e:
                    logger.error(f"Error calling malloc_trim: {e}")
            
            # Sleep for a longer duration after a cleanup to avoid constant checks when idle
            await asyncio.sleep(idle_threshold - check_interval)

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manages application startup and shutdown events."""
    # --- Startup Logic ---
    # Start memory logger
    logger.info("Starting memory logger thread.")
    thread = threading.Thread(target=log_memory_usage, daemon=True)
    thread.start()

    # Start tracemalloc
    logger.info("Starting tracemalloc.")
    tracemalloc.start()
    # --- End Tracemalloc ---

    # --- Concurrency Limiter ---
    # Calculation for semaphore value based on 8GB Docker RAM limit:
    # Total RAM: 8GB
    # Safety Margin (for OS, Docker, etc.): ~1.5GB
    # Available for App: 8 - 1.5 = 6.5GB
    # App Base Usage (idle): ~1GB
    # Available for Requests: 6.5 - 1 = 5.5GB
    # Estimated Memory per Concurrent Request: ~0.5GB (conservative estimate)
    # Max Concurrent Requests: 5.5GB / 0.5GB = 11
    # We choose a value of 8, which was calculated based on available system RAM.
    # Устанавливаем значение семафора из переменной окружения, по умолчанию 4.
    # Это число определяет, сколько запросов могут ОДНОВРЕМЕННО обрабатываться моделью.
    SEMAPHORE_VALUE = int(os.environ.get("SEMAPHORE_VALUE", "4"))
    app.state.semaphore = asyncio.Semaphore(SEMAPHORE_VALUE)
    logger.info(f"Semaphore initialized with a value of {SEMAPHORE_VALUE}")

    # Initialize stats collector
    app.state.stats = Stats()
    app.state.last_activity_time = time.monotonic() # For idle-based cleanup
    
    # Start background tasks
    logger.info("Starting periodic stats logger.")
    stats_task = asyncio.create_task(log_stats_periodically(app.state.stats))
    
    logger.info("Starting idle-based memory cleanup task.")
    cleanup_task = asyncio.create_task(periodic_memory_cleanup(app, idle_threshold=60, check_interval=15))

    yield

    # --- Shutdown Logic ---
    logger.info("Shutting down background tasks...")
    stats_task.cancel()
    cleanup_task.cancel()
    try:
        await stats_task
    except asyncio.CancelledError:
        logger.info("Stats logger task cancelled.")
    try:
        await cleanup_task
    except asyncio.CancelledError:
        logger.info("Memory cleanup task cancelled.")


app = FastAPI(lifespan=lifespan)

@app.middleware("http")
async def garbage_collection_middleware(request: Request, call_next):
    response = await call_next(request)
    gc.collect()
    return response

@app.get("/health")
def health():
    return {"status": "ok"}

@app.post("/v1/embeddings")
async def create_embeddings(request: Request):
    # Update activity timestamp for idle cleanup logic
    request.app.state.last_activity_time = time.monotonic()
    loop = asyncio.get_running_loop()

    # Get current queue size BEFORE waiting
    queue_depth = 0
    if hasattr(request.app.state.semaphore, '_waiters') and request.app.state.semaphore._waiters is not None:
        queue_depth = len(request.app.state.semaphore._waiters)

    start_time = time.monotonic()
    async with request.app.state.semaphore:
        # Read and parse the request body AFTER acquiring the semaphore
        try:
            body = await request.json()
            req = EmbeddingsRequest.model_validate(body)
        except Exception:
            logger.error("Failed to parse request body or client disconnected.", exc_info=True)
            # Handle parsing error appropriately
            # 499 Client Closed Request is a non-standard status code used by nginx
            return Response(status_code=499, content="Client Closed Request")

        wait_time = time.monotonic() - start_time
        num_inputs = len(req.input) if isinstance(req.input, list) else 1
        logger.info(f"Request with {num_inputs} inputs waited {wait_time:.2f}s (queue: {queue_depth}). Processing now.")

        # Update stats
        await request.app.state.stats.update(wait_time, queue_depth)

        # Run blocking code in executor
        final_embeddings = await loop.run_in_executor(
            None,
            _blocking_encode,
            req.input
        )
    
    logger.info("Finished processing all batches. Preparing response.")
    # Convert the entire tensor to a list of lists in one go for efficiency.
    all_embeddings_list = final_embeddings.tolist()

    # Use a list comprehension for faster creation of the response structure.
    data = [
        {
            "object": "embedding",
            "index": i,
            "embedding": embedding_list
        }
        for i, embedding_list in enumerate(all_embeddings_list)
    ]
    
    response_data = {
        "object": "list",
        "data": data,
        "model": req.model or "jina-code-v2"
    }

    # Явное освобождение памяти
    del final_embeddings
    del data
    gc.collect()

    return response_data

def _blocking_encode(inputs_data: Union[str, List[str]]):
    snapshot1 = tracemalloc.take_snapshot()

    inputs = inputs_data if isinstance(inputs_data, list) else [inputs_data]
    num_inputs = len(inputs)
    logger.info(f"Received embedding request with {num_inputs} inputs for blocking encode.")

    embedding_dim = model.config.hidden_size
    final_embeddings = torch.empty((num_inputs, embedding_dim), dtype=torch.float32, device='cpu')

    with torch.no_grad():
        num_batches = (num_inputs + MICRO_BATCH_SIZE - 1) // MICRO_BATCH_SIZE
        for i in range(0, num_inputs, MICRO_BATCH_SIZE):
            batch_num = (i // MICRO_BATCH_SIZE) + 1
            logger.info(f"Processing batch {batch_num}/{num_batches} in executor...")
            
            batch = inputs[i:i+MICRO_BATCH_SIZE]
            
            # Перемещаем тензоры на выбранное устройство (GPU/CPU)
            encoded_input = tokenizer(batch, padding=True, truncation=True, return_tensors='pt').to(device)
            
            model_output = model(**encoded_input)
            embeddings = mean_pooling(model_output, encoded_input['attention_mask'])
            normalized_embeddings = normalize(embeddings)
            
            end_index = i + len(batch)
            # Копируем результат обратно на CPU для сборки и отправки
            final_embeddings[i:end_index, :] = normalized_embeddings.cpu()

            # Clean up tensors to free memory
            del batch, encoded_input, model_output, embeddings, normalized_embeddings
            if torch.backends.mps.is_available():
                torch.mps.empty_cache()
            elif torch.cuda.is_available():
                torch.cuda.empty_cache()
            
    # Explicitly trigger garbage collection to free up memory after processing
    gc.collect()

    snapshot2 = tracemalloc.take_snapshot()
    top_stats = snapshot2.compare_to(snapshot1, 'lineno')
    logger.info("[Tracemalloc] Top 10 memory differences:")
    for stat in top_stats[:10]:
        logger.info(f"[Tracemalloc] {stat}")

    return final_embeddings