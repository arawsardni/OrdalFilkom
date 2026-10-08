import logging
from llama_index.core import VectorStoreIndex, Settings, PromptTemplate
from llama_index.vector_stores.pinecone import PineconeVectorStore
from llama_index.llms.groq import Groq
from pinecone import Pinecone

from src.config.settings import Settings as AppSettings
from src.config.prompts import QA_PROMPT_TEMPLATE
from src.core.embeddings import PineconeEmbedding

logger = logging.getLogger(__name__)


class RAGEngine:    
    def __init__(self):
        self.chat_engine = None
        self.index = None
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
        
        # LLM
        Settings.llm = Groq(
            model=AppSettings.LLM_MODEL,
            api_key=AppSettings.get_groq_api_key(),
            temperature=AppSettings.LLM_TEMPERATURE
        )
        logger.info(f"LLM configured: {AppSettings.LLM_MODEL}")
        
        # Connect to Pinecone
        pc = Pinecone(api_key=AppSettings.get_pinecone_api_key())
        vector_store = PineconeVectorStore(
            pinecone_index=pc.Index(AppSettings.INDEX_NAME)
        )
        logger.info(f"Connected to Pinecone index: {AppSettings.INDEX_NAME}")
        
        # Load index from vector store
        index = VectorStoreIndex.from_vector_store(vector_store=vector_store)
        self.index = index
        
        # Create chat engine with custom prompt
        qa_prompt = PromptTemplate(QA_PROMPT_TEMPLATE)
        self.chat_engine = index.as_chat_engine(
            chat_mode="context",
            text_qa_template=qa_prompt,
            similarity_top_k=AppSettings.SIMILARITY_TOP_K
        )
        
        logger.info("RAG engine initialized successfully")
    
    def get_engine(self):
        return self.chat_engine
    
    def get_retriever(self, top_k=None):
        """Retriever with the same config as the chat engine (used by eval)"""
        return self.index.as_retriever(similarity_top_k=top_k or AppSettings.SIMILARITY_TOP_K)
    
    def reset_memory(self):
        """Reset chat engine memory to free up context window"""
        if self.chat_engine and hasattr(self.chat_engine, 'reset'):
            self.chat_engine.reset()
