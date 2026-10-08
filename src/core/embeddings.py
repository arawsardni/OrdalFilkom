from typing import Any, List

from llama_index.core.base.embeddings.base import BaseEmbedding
from llama_index.core.bridge.pydantic import PrivateAttr
from pinecone import Pinecone


class PineconeEmbedding(BaseEmbedding):
    """LlamaIndex embedding backed by Pinecone's hosted inference API."""

    dimension: int = 768
    _pc: Pinecone = PrivateAttr()

    def __init__(self, model_name: str, api_key: str, dimension: int = 768, **kwargs: Any):
        # Pinecone's embed endpoint accepts at most 96 inputs per call
        kwargs.setdefault("embed_batch_size", 96)
        super().__init__(model_name=model_name, dimension=dimension, **kwargs)
        self._pc = Pinecone(api_key=api_key)

    @classmethod
    def class_name(cls) -> str:
        return "PineconeEmbedding"

    def _embed(self, texts: List[str], input_type: str) -> List[List[float]]:
        result = self._pc.inference.embed(
            model=self.model_name,
            inputs=texts,
            parameters={"input_type": input_type, "truncate": "END", "dimension": self.dimension},
        )
        return [item.values for item in result.data]

    def _get_query_embedding(self, query: str) -> List[float]:
        return self._embed([query], "query")[0]

    def _get_text_embedding(self, text: str) -> List[float]:
        return self._embed([text], "passage")[0]

    def _get_text_embeddings(self, texts: List[str]) -> List[List[float]]:
        return self._embed(texts, "passage")

    async def _aget_query_embedding(self, query: str) -> List[float]:
        return self._get_query_embedding(query)
