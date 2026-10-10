import logging
from llama_index.core import QueryBundle, VectorStoreIndex, Settings
from llama_index.core.vector_stores import FilterOperator, MetadataFilter, MetadataFilters
from llama_index.vector_stores.pinecone import PineconeVectorStore
from llama_index.llms.groq import Groq
from pinecone import Pinecone

from src.config.settings import Settings as AppSettings
from src.core.embeddings import PineconeEmbedding
from src.utils.catalog import load_catalog

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
        """Top-k chunks, plus faculty/program rules on the same topic when university rules show up.

        Faculty and program rules take precedence over the university's general guide
        (docs/PRODUCT.md), but the university guide is long and often outranks them, so when it
        appears a second search excluding it adds the best faculty/program chunks. University
        sources are then moved last so the LLM leads with the stronger rule; the rest keep their
        retrieval order (a program's curriculum only outranks the faculty for that program).
        """
        query = QueryBundle(query, embedding=Settings.embed_model.get_query_embedding(query))
        nodes = self.retriever.retrieve(query)
        university_files = [name for name, info in load_catalog().items() if info.get("issuer") == "universitas"]
        if university_files and any(n.metadata.get("file_name") in university_files for n in nodes):
            filters = MetadataFilters(filters=[
                MetadataFilter(key="file_name", value=university_files, operator=FilterOperator.NIN)
            ])
            seen = {n.node.node_id for n in nodes}
            extra = self.index.as_retriever(
                similarity_top_k=AppSettings.FACULTY_RULES_TOP_K, filters=filters
            ).retrieve(query)
            nodes += [n for n in extra if n.node.node_id not in seen]
        return sorted(nodes, key=lambda n: n.metadata.get("file_name") in university_files)

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
