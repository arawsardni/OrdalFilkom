import os
import sys
import logging
from pathlib import Path
from dotenv import load_dotenv
import nest_asyncio

# Apply nest_asyncio for LlamaParse async operations
nest_asyncio.apply()

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from llama_index.core import (
    VectorStoreIndex,
    StorageContext,
    Settings,
    Document,
)
from llama_index.vector_stores.pinecone import PineconeVectorStore
from llama_index.llms.google_genai import GoogleGenAI
from llama_index.embeddings.google_genai import GoogleGenAIEmbedding
from llama_index.core.node_parser import HierarchicalNodeParser, get_leaf_nodes
from llama_parse import LlamaParse
from pinecone import Pinecone, ServerlessSpec
from src.utils.metadata import get_meta
from tqdm import tqdm
import time

# Config Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load Env
load_dotenv()
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
PINECONE_API_KEY = os.getenv("PINECONE_API_KEY")
LLAMA_CLOUD_API_KEY = os.getenv("LLAMA_CLOUD_API_KEY")
PINECONE_ENV = os.getenv("PINECONE_ENV", "us-east-1")
INDEX_NAME = "ordal-filkom"

# Configure LlamaIndex Settings
def init_settings():
    # Embedding Model
    Settings.embed_model = GoogleGenAIEmbedding(
        model_name="models/text-embedding-004", 
        api_key=GOOGLE_API_KEY,
    )
    Settings.llm = GoogleGenAI(
        model_name="models/gemini-1.5-flash", 
        api_key=GOOGLE_API_KEY,
        temperature=0.2
    )

def main():
    if not GOOGLE_API_KEY or not PINECONE_API_KEY:
        logger.error("API Keys missing in .env")
        return
    
    if not LLAMA_CLOUD_API_KEY:
        logger.error("LLAMA_CLOUD_API_KEY missing in .env - required for PDF parsing")
        return

    init_settings()

    logger.info("Loading Documents with LlamaParse...")
    
    # Initialize LlamaParse
    parser = LlamaParse(
        api_key=LLAMA_CLOUD_API_KEY,
        result_type="markdown",  # Preserves tables as markdown
        verbose=True,
        language="id",  # Indonesian
        num_workers=4, 
        parsing_instruction="""
        This is an Indonesian academic document (curriculum, handbook, or guideline).
        Please:
        - Extract all text content with proper structure
        - Convert all tables to markdown format (IMPORTANT for course/SKS data)
        - Preserve document hierarchy (headings, sections, subsections)
        - For diagrams/images with text, provide brief descriptions
        - Maintain bullet points and numbered lists
        """
    )
    
    # Get all PDF files
    pdf_files = [str(p) for p in Path("./dataset").rglob("*.pdf")]
    logger.info(f"Found {len(pdf_files)} PDF files")
    
    # Parse with LlamaParse
    logger.info("⏳ Parsing PDFs with LlamaParse (this may take 5-15 minutes)...")
    logger.info("Quality improvement: Tables preserved, diagrams described")
    
    # Parse each file separately to maintain file-to-document mapping
    documents = []
    for pdf_file in tqdm(pdf_files, desc="Parsing PDFs"):
        try:
            parsed_docs = parser.load_data(pdf_file)
            
            # Get metadata for this file
            file_metadata = get_meta(pdf_file)
            
            # Add metadata to each document from this file
            for page_idx, doc in enumerate(parsed_docs):
                # LlamaParse returns empty metadata, so we need to add everything
                doc.metadata.update(file_metadata)
                
                # Add page_label (LlamaParse docs are typically one per page or whole doc)
                # Use page index + 1 for 1-indexed page numbers
                doc.metadata['page_label'] = str(page_idx + 1)
                
                documents.append(doc)
                
        except Exception as e:
            logger.error(f"Failed to parse {pdf_file}: {e}")
            continue
    
    logger.info(f"Parsed {len(documents)} document pages with enhanced extraction")

    logger.info("Chunking & Indexing to Pinecone...")
    
    # Initialize Pinecone
    pc = Pinecone(api_key=PINECONE_API_KEY)
    
    # Create Index if not exists 

    # Check existing indexes using list_indexes() which returns a list of objects with 'name' attribute
    existing_indexes = [i.name for i in pc.list_indexes()]
    if INDEX_NAME in existing_indexes:
        logger.info(f"Deleting existing index {INDEX_NAME} to reset...")
        pc.delete_index(INDEX_NAME)
        time.sleep(10)
        
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
    
    
    # HYBRID CHUNKING STRATEGY
    logger.info("Initializing HYBRID chunking...")
    
    chunk_sizes = [2048, 512, 128]
    
    # Hierarchical parsing for structure
    node_parser = HierarchicalNodeParser.from_defaults(
        chunk_sizes=chunk_sizes
    )
    
    logger.info(f"Chunk hierarchy: {chunk_sizes}")
    logger.info("Creating hierarchical nodes...")
    
    all_nodes = node_parser.get_nodes_from_documents(documents, show_progress=True)
    leaf_nodes = get_leaf_nodes(all_nodes)
    
    logger.info(f"Hierarchical: {len(all_nodes)} total, {len(leaf_nodes)} leaf nodes")
    
    # Semantic refinement for coherence
    USE_SEMANTIC = True 
    
    if USE_SEMANTIC:
        logger.info("Applying semantic refinement...")
        
        from llama_index.core.node_parser import SemanticSplitterNodeParser
        from llama_index.core import Document as LlamaDocument
        import re
        
        semantic_parser = SemanticSplitterNodeParser(
            buffer_size=1,
            breakpoint_percentile_threshold=95,
            embed_model=Settings.embed_model
        )
        
        # Helper functions for guardrails
        def contains_markdown_table(text):
            """Check if text contains markdown table"""
            return '|' in text and '---' in text
        
        def has_heading(text):
            """Check if text starts with markdown heading"""
            return text.strip().startswith('#')
        
        def contains_policy_keywords(text):
            """Check if text contains normative policy keywords"""
            policy_words = ['wajib', 'harus', 'dikecualikan', 'tidak berlaku jika', 
                          'syarat', 'ketentuan', 'peraturan', 'kecuali']
            return any(word in text.lower() for word in policy_words)
        
        nodes = []
        skipped_table = 0
        skipped_heading = 0
        skipped_policy = 0
        refined = 0
        
        for node in tqdm(leaf_nodes, desc="Semantic refinement"):
            node_text = node.text
            
            # Table Lock - Don't split tables
            if contains_markdown_table(node_text):
                nodes.append(node)
                skipped_table += 1
                continue
            
            # Heading-aware - Don't split if starts with heading
            if has_heading(node_text):
                nodes.append(node)
                skipped_heading += 1
                continue
            
            # Policy-safe - Don't split normative clauses
            if contains_policy_keywords(node_text) and len(node_text) < 1000:
                # Keep policy clauses atomic if reasonably sized
                nodes.append(node)
                skipped_policy += 1
                continue
            
            # Only refine large, safe-to-split chunks
            if len(node_text) > 600:
                try:
                    temp_doc = LlamaDocument(text=node_text, metadata=node.metadata)
                    chunks = semantic_parser.get_nodes_from_documents([temp_doc])
                    
                    if len(chunks) > 1:
                        # Semantic split successful
                        nodes.extend(chunks)
                        refined += 1
                    else:
                        nodes.append(node)
                except:
                    nodes.append(node)
            else:
                nodes.append(node)
        
        logger.info(f"\nSemantic refinement complete:")
    else:
        nodes = leaf_nodes
    
    logger.info(f"\nHYBRID PARSING COMPLETE:")
    logger.info(f"Final chunks: {len(nodes)}")
    
    # Create storage context for Pinecone
    storage_context = StorageContext.from_defaults(vector_store=vector_store)

    BATCH_SIZE = 20  
    DELAY_SECONDS = 5

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
    
    logger.info("SUCCESS: Documents inserted to Pinecone.")

if __name__ == "__main__":
    main()
