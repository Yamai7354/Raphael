from fastapi import FastAPI, HTTPException
from typing import Union, List
from pydantic import BaseModel
import uvicorn
import logging

from ai_router.embeddings import EmbeddingRouter, EmbeddingLayer
from ai_router.node_manager import NodeRegistration, NodeRole, NodeHealth

app = FastAPI(title="Embedding Router Service", version="1.0.0")
router = EmbeddingRouter()
logger = logging.getLogger("embedding_server")


class EmbedRequest(BaseModel):
    text: Union[str, List[str]]
    layer: EmbeddingLayer


@app.post("/api/embed")
async def embed(request: EmbedRequest):
    try:
        results = await router.embed(request.text, request.layer)
        return {"embeddings": results}
    except Exception as e:
        logger.error(f"Failed to generate embeddings: {e}")
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    uvicorn.run("ai_router.embedding_server:app", host="0.0.0.0", port=9100)
