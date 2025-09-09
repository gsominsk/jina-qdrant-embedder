import os
from fastapi import FastAPI
from pydantic import BaseModel
from typing import List, Union

# pip install transformers torch
from transformers import AutoTokenizer, AutoModel
import torch
import numpy as np
from torch.nn import functional as F

app = FastAPI()

# Получаем имя модели из переменной окружения, с дефолтным значением
MODEL_NAME = os.environ.get("MODEL_NAME", "jinaai/jina-embeddings-v2-base-code")

# Загружаем модель и токенизатор
tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME, trust_remote_code=True)
model = AutoModel.from_pretrained(MODEL_NAME, trust_remote_code=True)

def mean_pooling(model_output, attention_mask):
    token_embeddings = model_output[0]
    input_mask_expanded = attention_mask.unsqueeze(-1).expand(token_embeddings.size()).float()
    return torch.sum(token_embeddings * input_mask_expanded, 1) / torch.clamp(input_mask_expanded.sum(1), min=1e-9)

def normalize(vectors):
    return F.normalize(torch.tensor(vectors), p=2, dim=1).numpy()

class EmbeddingsRequest(BaseModel):
    model: str
    input: Union[str, List[str]]

@app.get("/health")
def health():
    return {"status": "ok"}

@app.post("/v1/embeddings")
def create_embeddings(req: EmbeddingsRequest):
    inputs = req.input if isinstance(req.input, list) else [req.input]
    
    # Токенизация
    encoded_input = tokenizer(inputs, padding=True, truncation=True, return_tensors='pt')
    
    # Получение эмбеддингов
    with torch.no_grad():
        model_output = model(**encoded_input)
    
    # Mean Pooling и нормализация
    embeddings = mean_pooling(model_output, encoded_input['attention_mask'])
    normalized_embeddings = normalize(embeddings)
    
    data = []
    for i, embedding in enumerate(normalized_embeddings):
        data.append({
            "object": "embedding",
            "index": i,
            "embedding": embedding.tolist()
        })
        
    return {
        "object": "list",
        "data": data,
        "model": req.model or "jina-code-v2"
    }