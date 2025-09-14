import os
import logging
import asyncio
import psutil
import threading
import time
import gc
import tracemalloc
from fastapi import FastAPI, Request
from pydantic import BaseModel
from typing import List, Union

# pip install transformers torch
from transformers import AutoTokenizer, AutoModel
import torch
import numpy as np
from torch.nn import functional as F

# Настройка логирования
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

app = FastAPI()

@app.middleware("http")
async def garbage_collection_middleware(request: Request, call_next):
    response = await call_next(request)
    gc.collect()
    return response

# Получаем имя модели из переменной окружения, с дефолтным значением
MODEL_NAME = os.environ.get("MODEL_NAME", "jinaai/jina-embeddings-v2-base-code")

# Загружаем модель и токенизатор
tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME, trust_remote_code=True)
model = AutoModel.from_pretrained(MODEL_NAME, trust_remote_code=True)

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

@app.on_event("startup")
async def startup_event():
    """Start the memory logger on app startup."""
    logger.info("Starting memory logger thread.")
    thread = threading.Thread(target=log_memory_usage, daemon=True)
    thread.start()

    # --- Tracemalloc ---
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
    SEMAPHORE_VALUE = 8
    app.state.semaphore = asyncio.Semaphore(SEMAPHORE_VALUE)
    logger.info(f"Semaphore initialized with a value of {SEMAPHORE_VALUE}")
# --- End Memory Profiling ---


@app.get("/health")
def health():
    return {"status": "ok"}

@app.post("/v1/embeddings")
async def create_embeddings(req: EmbeddingsRequest, fastapi_req: Request):
    loop = asyncio.get_event_loop()

    async with app.state.semaphore:
        logger.info("Semaphore acquired. Processing request.")
        # Запускаем блокирующий код в отдельном потоке
        final_embeddings = await loop.run_in_executor(
            None,
            _blocking_encode,
            req.input
        )
    
    logger.info("Finished processing all batches. Preparing response.")
    data = []
    for i, embedding in enumerate(final_embeddings):
        data.append({
            "object": "embedding",
            "index": i,
            "embedding": embedding.tolist()
        })
    
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
    final_embeddings = torch.empty((num_inputs, embedding_dim), dtype=torch.float32)

    with torch.no_grad():
        num_batches = (num_inputs + MICRO_BATCH_SIZE - 1) // MICRO_BATCH_SIZE
        for i in range(0, num_inputs, MICRO_BATCH_SIZE):
            batch_num = (i // MICRO_BATCH_SIZE) + 1
            logger.info(f"Processing batch {batch_num}/{num_batches} in executor...")
            
            batch = inputs[i:i+MICRO_BATCH_SIZE]
            
            encoded_input = tokenizer(batch, padding=True, truncation=True, return_tensors='pt')
            model_output = model(**encoded_input)
            embeddings = mean_pooling(model_output, encoded_input['attention_mask'])
            normalized_embeddings = normalize(embeddings)
            
            end_index = i + len(batch)
            final_embeddings[i:end_index, :] = normalized_embeddings

            # Clean up tensors to free memory
            del batch, encoded_input, model_output, embeddings, normalized_embeddings
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
            
    # Explicitly trigger garbage collection to free up memory after processing
    gc.collect()

    snapshot2 = tracemalloc.take_snapshot()
    top_stats = snapshot2.compare_to(snapshot1, 'lineno')
    logger.info("[Tracemalloc] Top 10 memory differences:")
    for stat in top_stats[:10]:
        logger.info(f"[Tracemalloc] {stat}")

    return final_embeddings