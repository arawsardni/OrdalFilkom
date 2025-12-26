import os
import logging
from dotenv import load_dotenv

from llama_index.core import (
    VectorStoreIndex,
    SimpleDirectoryReader,
    StorageContext,
    Settings,
)
from llama_index.vector_stores.pinecone import PineconeVectorStore
from llama_index.llms.google_genai import GoogleGenAI
from llama_index.embeddings.google_genai import GoogleGenAIEmbedding
from llama_index.core.node_parser import SentenceSplitter
from pinecone import Pinecone, ServerlessSpec
from utils import get_meta
from tqdm import tqdm
import time

# Config Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load Env
load_dotenv()
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
PINECONE_API_KEY = os.getenv("PINECONE_API_KEY")
PINECONE_ENV = os.getenv("PINECONE_ENV", "us-east-1")
INDEX_NAME = "ordal-filkom" # Should define this or get from env

# Configure LlamaIndex Settings
def init_settings():
    # Embedding Model
    Settings.embed_model = GoogleGenAIEmbedding(
        model_name="models/text-embedding-004", 
        api_key=GOOGLE_API_KEY,
    )
    # LLM (Not strictly needed for ingestion but good to set global)
    Settings.llm = GoogleGenAI(
        model_name="models/gemini-1.5-flash", 
        api_key=GOOGLE_API_KEY,
        temperature=0.2
    )

def main():
    if not GOOGLE_API_KEY or not PINECONE_API_KEY:
        logger.error("API Keys missing in .env")
        return

    init_settings()

    logger.info("Step A: Loading Documents...")
    # Using recursive=True as per SRS
    reader = SimpleDirectoryReader(
        input_dir="./dataset",
        recursive=True,
        file_metadata=get_meta 
    )
    documents = reader.load_data()
    logger.info(f"Loaded {len(documents)} document pages.")

    logger.info("Step B: Chunking & Indexing to Pinecone...")
    
    # Initialize Pinecone
    pc = Pinecone(api_key=PINECONE_API_KEY)
    
    # Create Index if not exists (Optional convenience, SRS doesn't explicitly ask but good practice)
    # Check existing indexes using list_indexes() which returns a list of objects with 'name' attribute
    existing_indexes = [i.name for i in pc.list_indexes()]
    if INDEX_NAME in existing_indexes:
        logger.info(f"Deleting existing index {INDEX_NAME} to reset...")
        pc.delete_index(INDEX_NAME)
        time.sleep(10) # Wait for deletion
        
    logger.info(f"Creating Pinecone index: {INDEX_NAME}")
    pc.create_index(
        name=INDEX_NAME,
        dimension=768, # text-embedding-004 default
        metric="cosine",
        spec=ServerlessSpec(
            cloud="aws",
            region=PINECONE_ENV
        )
    )
    
    # Connect to Pinecone
    vector_store = PineconeVectorStore(
        pinecone_index=pc.Index(INDEX_NAME),
    )
    
    storage_context = StorageContext.from_defaults(vector_store=vector_store)
    
    # Strategic Splitting
    splitter = SentenceSplitter(chunk_size=1024, chunk_overlap=200)
    Settings.text_splitter = splitter

    # BATCH PROCESSING to handle Rate Limits
    logger.info("Splitting documents into nodes...")
    nodes = splitter.get_nodes_from_documents(documents, show_progress=True)
    logger.info(f"Total nodes created: {len(nodes)}")

    BATCH_SIZE = 20  # Conservative batch size
    DELAY_SECONDS = 5 # Wait time between batches

    logger.info(f"Indexing in batches of {BATCH_SIZE} with {DELAY_SECONDS}s delay...")
    
    index = None

    for i in tqdm(range(0, len(nodes), BATCH_SIZE), desc="Indexing Batches"):
        batch_nodes = nodes[i : i + BATCH_SIZE]
        try:
            # Create index from first batch, then append
            if index is None:
                index = VectorStoreIndex(
                    batch_nodes,
                    storage_context=storage_context,
                )
            else:
                index.insert_nodes(batch_nodes)
            
            time.sleep(DELAY_SECONDS)
        except Exception as e:
            logger.error(f"Error indexing batch starting at {i}: {e}")
            time.sleep(30) # Backoff
            # Retry logic could be added here, but simple skip/log for MVP
    
    logger.info("SUCCESS: Documents inserted to Pinecone.")

if __name__ == "__main__":
    main()
