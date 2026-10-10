import logging
from llama_index.core import VectorStoreIndex, Settings
from llama_index.vector_stores.pinecone import PineconeVectorStore
from llama_index.llms.groq import Groq
from pinecone import Pinecone

from src.config.settings import Settings as AppSettings
from src.core.embeddings import PineconeEmbedding

logger = logging.getLogger(__name__)


class RAGEngine:
    """Retrieval over the Pinecone index plus Groq LLM clients. Answer generation lives in ChatHandler."""

    def __init__(self):
        self.index = None
        self.retriever = None
        self._llms = {}
        self._validate_api_keys()
        self._initialize()

    def _validate_api_keys(self):
        pinecone_key = AppSettings.get_pinecone_api_key()
        groq_key = AppSettings.get_groq_api_key()

        if not all([pinecone_key, groq_key]):
            raise ValueError("Missing required API keys. Check your .env file.")

    def _initialize(self):
        logger.info("Initializing RAG engine...")

        # Embedding model
        Settings.embed_model = PineconeEmbedding(
            model_name=AppSettings.EMBEDDING_MODEL,
            api_key=AppSettings.get_pinecone_api_key(),
            dimension=AppSettings.EMBEDDING_DIM
        )
        logger.info(f"Embedding model configured: {AppSettings.EMBEDDING_MODEL}")

        # Connect to Pinecone
        pc = Pinecone(api_key=AppSettings.get_pinecone_api_key())
        vector_store = PineconeVectorStore(
            pinecone_index=pc.Index(AppSettings.INDEX_NAME)
        )
        logger.info(f"Connected to Pinecone index: {AppSettings.INDEX_NAME}")

        # Load index from vector store
        self.index = VectorStoreIndex.from_vector_store(vector_store=vector_store)
        self.retriever = self.get_retriever()

        logger.info("RAG engine initialized successfully")

    def get_retriever(self, top_k=None):
        return self.index.as_retriever(similarity_top_k=top_k or AppSettings.SIMILARITY_TOP_K)

    def retrieve(self, query: str):
        return self.retriever.retrieve(query)

    def get_llm(self, model_name=None):
        """Groq client for the given model (default: Settings.LLM_MODEL), created once per model"""
        model_name = model_name or AppSettings.LLM_MODEL
        if model_name not in self._llms:
            self._llms[model_name] = Groq(
                model=model_name,
                api_key=AppSettings.get_groq_api_key(),
                temperature=AppSettings.LLM_TEMPERATURE
            )
            logger.info(f"LLM configured: {model_name}")
        return self._llms[model_name]
