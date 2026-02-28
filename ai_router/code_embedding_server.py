from fastapi import FastAPI, HTTPException
from typing import Union, List
from pydantic import BaseModel
import uvicorn
import logging

from raphael.ai_router.embeddings import EmbeddingRouter, EmbeddingLayer

app = FastAPI(title="Code Embedding Service", version="1.0.0")
# We only use the CODE layer for this node
router = EmbeddingRouter()
logger = logging.getLogger("code_embedding_server")


class EmbedRequest(BaseModel):
    text: Union[str, List[str]]


@app.post("/api/embed/code")
async def embed_code(request: EmbedRequest):
    try:
        # Force routing to the Intelligence layer (CODE)
        results = await router.embed(request.text, EmbeddingLayer.CODE)
        return {"embeddings": results}
    except Exception as e:
        logger.error(f"Failed to generate code embeddings: {e}")
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    uvicorn.run("raphael.ai_router.code_embedding_server:app", host="0.0.0.0", port=9200)
