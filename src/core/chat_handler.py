import logging
import re
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
    
    def reset_memory(self):
        """Reset chat engine memory to free up context window"""
        if hasattr(self.chat_engine, 'reset'):
            self.chat_engine.reset()
            logger.info("Chat memory reset successfully")
            return True
        return False
    
    def _parse_rate_limit_info(self, error_str: str) -> Dict:
        """
        Parse rate limit information from Groq API error message
        
        Returns dict with: limit_type, current, limit, reset_time, retry_after
        """
        info = {
            "limit_type": None,
            "current": None,
            "limit": None,
            "reset_time": None,
            "retry_after": None,
            "model": None
        }
        
        # Try to extract rate limit type (TPM, RPM, TPD, RPD)
        if "tokens per minute" in error_str.lower() or "tpm" in error_str.lower():
            info["limit_type"] = "TPM"
        elif "requests per minute" in error_str.lower() or "rpm" in error_str.lower():
            info["limit_type"] = "RPM"
        elif "tokens per day" in error_str.lower() or "tpd" in error_str.lower():
            info["limit_type"] = "TPD"
        elif "requests per day" in error_str.lower() or "rpd" in error_str.lower():
            info["limit_type"] = "RPD"
        
        # Try to extract limit value (e.g., "Limit 6000")
        limit_match = re.search(r'limit[:\s]+(\d+[\d,]*)', error_str, re.IGNORECASE)
        if limit_match:
            info["limit"] = limit_match.group(1).replace(",", "")
        
        # Try to extract retry time (e.g., "try again in 42.5s" or "Please retry after 42s")
        retry_match = re.search(r'(?:try again in|retry after|wait)\s*([\d.]+)\s*(?:s|sec|seconds?)?', error_str, re.IGNORECASE)
        if retry_match:
            info["retry_after"] = retry_match.group(1)
        
        # Try to extract reset time
        reset_match = re.search(r'reset[:\s]+([\d.]+\s*(?:s|m|h|sec|min)?)', error_str, re.IGNORECASE)
        if reset_match:
            info["reset_time"] = reset_match.group(1)
        
        return info
    
    def _format_rate_limit_error(self, model_name: str, error_str: str) -> str:
        """
        Format concise rate limit error message
        """
        info = self._parse_rate_limit_info(error_str)
        
        # Build concise error message
        parts = [f"⚠️ **Rate Limit: {model_name}**"]
        
        # Add limit type and value
        if info["limit_type"] and info["limit"]:
            parts.append(f"📊 Limit: {info['limit']} {info['limit_type']}")
        elif info["limit_type"]:
            parts.append(f"📊 Tipe: {info['limit_type']}")
        
        # Add retry time
        if info["retry_after"]:
            parts.append(f"⏱️ Retry: {info['retry_after']}s")
        elif info["reset_time"]:
            parts.append(f"⏱️ Reset: {info['reset_time']}")
        
        return " | ".join(parts)
    
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
        
        current_model_name = model_name or Settings.LLM_MODEL
        
        try:
            logger.info(f"Processing query with model {current_model_name}: {query[:100]}...")
            
            # Get response from chat engine
            response = self.chat_engine.chat(query)
            
            # Extract sources
            sources_data = self._extract_sources(
                response.source_nodes[:Settings.TOP_SOURCES_TO_DISPLAY]
            )
            
            logger.info(f"Query processed successfully with {len(sources_data)} sources")
            return response.response, sources_data, None, None
            
        except Exception as e:
            error_str = str(e)
            
            # Handle rate limiting errors
            if "429" in error_str or "RESOURCE_EXHAUSTED" in error_str or "rate" in error_str.lower():
                is_daily_quota = "tokens per day" in error_str.lower() or "tpd" in error_str.lower()
                
                # Get alternative models
                all_models = Settings.get_all_available_models()
                alternative_models = [m for m in all_models if m["model"] != current_model_name]
                
                # Format concise error message
                error_msg = self._format_rate_limit_error(current_model_name, error_str)
                
                if is_daily_quota and not alternative_models:
                    error_msg = "🚫 **TPD Limit Exceeded** | Semua model habis kuota harian"
                    logger.error("Daily quota exhausted on all models")
                    return None, None, error_msg, None
                
                logger.warning(f"Rate limit on {current_model_name}: {error_str}")
                return None, None, error_msg, alternative_models if alternative_models else None
            
            # Context size overflow error - AUTO-RECOVERY
            elif "context size" in error_str.lower() and "not non-negative" in error_str.lower():
                logger.error(f"Context size overflow: {error_str}")
                
                # Auto-recovery: reset memory and retry once
                logger.info("Attempting auto-recovery by resetting chat memory...")
                self.reset_memory()
                
                try:
                    # Retry the query after memory reset
                    response = self.chat_engine.chat(query)
                    sources_data = self._extract_sources(
                        response.source_nodes[:Settings.TOP_SOURCES_TO_DISPLAY]
                    )
                    logger.info("Query succeeded after memory reset (auto-recovery)")
                    return response.response, sources_data, None, None
                except Exception as retry_e:
                    logger.error(f"Retry after reset also failed: {retry_e}")
                    error_msg = "⚠️ **Context Overflow** | Memory sudah di-reset, tapi masih gagal. Coba pertanyaan lebih singkat."
                    return None, None, error_msg, None
            
            # Other errors - show raw error
            else:
                logger.error(f"Query processing error: {error_str}")
                # Extract just the main error message (first line or first 100 chars)
                short_error = error_str.split('\n')[0][:100]
                return None, None, f"❌ Error: {short_error}", None
    
    def _extract_sources(self, source_nodes) -> List[Dict]:
        """
        Extract source metadata from retrieval nodes
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
