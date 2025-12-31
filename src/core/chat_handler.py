import logging
import time
from typing import Tuple, List, Dict, Optional

from src.config.settings import Settings

logger = logging.getLogger(__name__)


class ChatHandler:    
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
        model_name: str = None,
        max_retries: int = None
    ) -> Tuple[Optional[str], Optional[List[Dict]], Optional[str], Optional[List[Dict]]]:
        """
        Process user query with user-selected model and fallback options
        
        Args:
            query: User's question
            model_name: LLM model to use (None = use default from Settings)
            max_retries: Maximum retry attempts (uses Settings default if None)
        
        Returns:
            tuple: (response_text, sources_data, error_message, model_options)
                - response_text: LLM's answer or None if error
                - sources_data: List of source metadata dicts or None
                - error_message: Error description or None if successful
                - model_options: List of alternative models on rate limit, None otherwise
        """
        if max_retries is None:
            max_retries = Settings.MAX_RETRIES
        
        # Switch to user-selected model if provided
        if model_name and model_name != Settings.LLM_MODEL:
            try:
                from llama_index.llms.groq import Groq
                from llama_index.core import Settings as LISettings
                
                LISettings.llm = Groq(
                    model=model_name,
                    api_key=Settings.get_groq_api_key(),
                    temperature=Settings.LLM_TEMPERATURE
                )
                self.chat_engine._llm = LISettings.llm
                logger.info(f"Using user-selected model: {model_name}")
            except Exception as e:
                logger.error(f"Failed to switch to model {model_name}: {e}")
        
        current_model_name = model_name or Settings.LLM_MODEL  # Track current model
        rate_limit_encountered = False  # Track if we've hit rate limit before
        
        try:
            logger.info(f"Processing query with model {current_model_name}: {query[:100]}...")
            
            # Get response from chat engine
            response = self.chat_engine.chat(query)
            
            # Extract sources
            sources_data = self._extract_sources(
                response.source_nodes[:Settings.TOP_SOURCES_TO_DISPLAY]
            )
            
            logger.info(f"Query processed successfully with {len(sources_data)} sources")
            return response.response, sources_data, None, None  # No model options on success
            
        except Exception as e:
            error_str = str(e)
            
            # Handle rate limiting errors FIRST
            # (because quota exhaustion can cause misleading "context size" errors)
            if "429" in error_str or "RESOURCE_EXHAUSTED" in error_str or "rate" in error_str.lower():
                # Check if this is a daily quota exhaustion (tokens per day limit)
                is_daily_quota = "tokens per day" in error_str.lower() or "tpd" in error_str.lower()
                
                rate_limit_encountered = True
                
                # Get alternative models (exclude currently used model)
                all_models = Settings.get_all_available_models()
                alternative_models = [m for m in all_models if m["model"] != current_model_name]
                
                # If daily quota, check if there are alternatives available
                if is_daily_quota:
                    if alternative_models:
                        # Return alternative models for user to choose
                        error_msg = (
                            f"⚠️ **Rate limit pada model: {current_model_name}**\n\n"
                            "Kuota harian model saat ini telah habis. "
                            "Silakan pilih model alternatif untuk mencoba lagi."
                        )
                        logger.warning(f"Daily quota exhausted on {current_model_name}. Offering alternatives.")
                        return None, None, error_msg, alternative_models
                    else:
                        # No alternatives available - all quota exhausted
                        error_msg = (
                            "🚫 **Kuota harian sudah habis!**\n\n"
                            "Maaf, semua model telah mencapai batas kuota API harian. "
                            "Silakan coba lagi besok.\n\n"
                            "_Terima kasih atas pengertiannya :)._"
                        )
                        logger.error("Daily quota exhausted on all available models")
                        return None, None, error_msg, None
                else:
                    # Temporary rate limit (RPM/TPM) - offer retry with alternative models
                    if alternative_models:
                        error_msg = (
                            f"⚠️ **Rate limit pada model:  {current_model_name}**\n\n"
                            "Model saat ini sedang sibuk. "
                            "Silakan pilih model alternatif atau coba lagi nanti."
                        )
                        logger.warning(f"Rate limit on {current_model_name}. Offering alternatives.")
                        return None, None, error_msg, alternative_models
                    else:
                        error_msg = "⚠️ Server sedang sibuk. Silakan coba lagi dalam beberapa saat."
                        logger.error(f"Rate limit hit, no alternatives: {error_str}")
                        return None, None, error_msg, None
            
            # Check for context size overflow error
            # BUT if we've previously hit rate limit, this might be a false "context size" error
            # caused by quota exhaustion on the fallback model
            elif "context size" in error_str.lower() and "not non-negative" in error_str.lower():
                if rate_limit_encountered:
                    # This is likely a quota issue disguised as context size error
                    logger.error(f"Context size error after rate limit (likely quota exhausted): {error_str}")
                    error_msg = (
                        "🚫 **Kuota harian sudah habis!**\n\n"
                        "Maaf, sistem telah mencapai batas kuota API harian. "
                        "Silakan coba lagi besok.\n\n"
                        "_Terima kasih atas pengertiannya :)._"
                    )
                    return None, None, error_msg, None
                else:
                    # Genuine context size issue
                    logger.error(f"Context size overflow: {error_str}")
                    error_msg = (
                        "⚠️ Maaf, pertanyaan Anda terlalu kompleks atau dokumen yang relevan terlalu besar. "
                        "Silakan coba dengan pertanyaan yang lebih singkat atau spesifik."
                    )
                    return None, None, error_msg, None
            else:
                # Non-rate-limit error
                logger.error(f"Query processing error: {error_str}")
                return None, None, f"Terjadi kesalahan: {error_str}", None
    
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
