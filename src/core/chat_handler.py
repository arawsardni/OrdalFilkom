"""Chat processing and response handling"""
import logging
import time
from typing import Tuple, List, Dict, Optional

from src.config.settings import Settings

logger = logging.getLogger(__name__)


class ChatHandler:
    """Handles chat interactions and response processing"""
    
    def __init__(self, chat_engine):
        """
        Initialize chat handler
        
        Args:
            chat_engine: LlamaIndex chat engine instance
        """
        self.chat_engine = chat_engine
    
    def process_query(
        self, 
        query: str, 
        max_retries: int = None
    ) -> Tuple[Optional[str], Optional[List[Dict]], Optional[str]]:
        """
        Process user query with retry logic and model fallback for rate limiting
        
        Args:
            query: User's question
            max_retries: Maximum retry attempts (uses Settings default if None)
        
        Returns:
            tuple: (response_text, sources_data, error_message)
                - response_text: LLM's answer or None if error
                - sources_data: List of source metadata dicts or None
                - error_message: Error description or None if successful
        """
        if max_retries is None:
            max_retries = Settings.MAX_RETRIES
        
        retry_count = 0
        current_model_index = -1  # -1 means primary model, 0+ means fallback model
        
        while retry_count < max_retries:
            try:
                logger.info(f"Processing query (attempt {retry_count + 1}/{max_retries}): {query[:100]}...")
                
                # Get response from chat engine
                response = self.chat_engine.chat(query)
                
                # Extract sources
                sources_data = self._extract_sources(
                    response.source_nodes[:Settings.TOP_SOURCES_TO_DISPLAY]
                )
                
                logger.info(f"Query processed successfully with {len(sources_data)} sources")
                return response.response, sources_data, None
                
            except Exception as e:
                error_str = str(e)
                
                # Handle rate limiting errors
                if "429" in error_str or "RESOURCE_EXHAUSTED" in error_str or "rate" in error_str.lower():
                    retry_count += 1
                    
                    # Try fallback model if available
                    if current_model_index < len(Settings.FALLBACK_MODELS) - 1:
                        current_model_index += 1
                        fallback_model, tpm_limit, description = Settings.FALLBACK_MODELS[current_model_index]
                        
                        logger.warning(
                            f"Rate limit hit on primary model. "
                            f"Switching to fallback model: {fallback_model} ({description})"
                        )
                        
                        try:
                            # Switch to fallback model
                            from llama_index.llms.groq import Groq
                            from llama_index.core import Settings as LISettings
                            
                            LISettings.llm = Groq(
                                model=fallback_model,
                                api_key=Settings.get_groq_api_key(),
                                temperature=Settings.LLM_TEMPERATURE
                            )
                            
                            # Update chat engine's LLM
                            self.chat_engine._llm = LISettings.llm
                            
                            # Retry immediately with new model
                            continue
                            
                        except Exception as fallback_error:
                            logger.error(f"Fallback model switch failed: {fallback_error}")
                    
                    # If no more fallbacks or retry limit reached
                    if retry_count < max_retries and current_model_index >= len(Settings.FALLBACK_MODELS) - 1:
                        wait_time = Settings.RETRY_WAIT_BASE * retry_count
                        logger.warning(
                            f"All fallback models exhausted. Waiting {wait_time}s before retry "
                            f"({retry_count}/{max_retries})"
                        )
                        time.sleep(wait_time)
                        continue
                    elif retry_count >= max_retries:
                        error_msg = "Server atau kuota sedang penuh. Silakan coba lagi nanti."
                        logger.error(f"Max retries exceeded: {error_str}")
                        return None, None, error_msg
                else:
                    # Non-rate-limit error
                    logger.error(f"Query processing error: {error_str}")
                    return None, None, f"Terjadi kesalahan: {error_str}"
        
        return None, None, "Max retries exceeded"
    
    def _extract_sources(self, source_nodes) -> List[Dict]:
        """
        Extract source metadata from retrieval nodes
        
        Args:
            source_nodes: List of retrieved nodes from vector store
        
        Returns:
            List of dicts with file_name, page, category, score
        """
        sources_data = []
        
        for node in source_nodes:
            source_info = {
                'file_name': node.metadata.get('file_name', 'Unknown'),
                'page': node.metadata.get('page_label', 'Unknown'),
                'category': node.metadata.get('category', 'Unknown'),
                'score': f"{node.score:.0%}" if node.score is not None else "N/A"
            }
            sources_data.append(source_info)
        
        return sources_data
