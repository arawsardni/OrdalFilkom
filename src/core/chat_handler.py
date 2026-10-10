import logging
import re
from typing import Tuple, List, Dict, Optional

from llama_index.core.llms import ChatMessage, MessageRole

from src.config.settings import Settings
from src.config.prompts import SYSTEM_PROMPT
from src.core.citations import build_sources_block, resolve_citations, strip_citations

logger = logging.getLogger(__name__)


class ChatHandler:
    """Answers a question from retrieved sources, with [n] citations resolved to document pages.

    The handler is shared by every session (st.cache_resource), so it keeps no conversation
    state: each call receives that session's chat history.
    """

    def __init__(self, engine):
        """
        Args:
            engine: RAGEngine (retrieval + LLM clients)
        """
        self.engine = engine
        # Context and citation checks of the last successful answer, read by scripts/eval.py
        self.last_nodes = []
        self.last_invalid_citations = 0

    def _retrieval_query(self, query: str, history: Optional[List[Dict]]) -> str:
        """Short follow-ups ("kalau tingkat fakultas?") don't name their topic, so they are
        retrieved together with the previous question"""
        previous = [m["content"] for m in (history or []) if m["role"] == "user"]
        if previous and len(query.split()) <= Settings.FOLLOW_UP_MAX_WORDS:
            return f"{previous[-1]} {query}"
        return query

    def _build_messages(self, query: str, nodes, history: Optional[List[Dict]]) -> List[ChatMessage]:
        system = SYSTEM_PROMPT.replace("{sources}", build_sources_block(nodes))
        messages = [ChatMessage(role=MessageRole.SYSTEM, content=system)]
        # Recent turns only, without their citation markers (those numbers referred to older sources)
        for message in (history or [])[-Settings.HISTORY_TURNS * 2:]:
            role = MessageRole.USER if message["role"] == "user" else MessageRole.ASSISTANT
            content = strip_citations(message["content"])[:Settings.HISTORY_MAX_CHARS]
            messages.append(ChatMessage(role=role, content=content))
        messages.append(ChatMessage(role=MessageRole.USER, content=query))
        return messages

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
        history: Optional[List[Dict]] = None
    ) -> Tuple[Optional[str], Optional[List[Dict]], Optional[str], Optional[List[Dict]]]:
        """
        Answer a question with the user-selected model

        Args:
            query: User's question
            model_name: LLM model to use (None = use default from Settings)
            history: Earlier messages of this session ({"role", "content"}), oldest first

        Returns:
            tuple: (response_text, cited_sources, error_message, model_options)
        """
        current_model_name = model_name or Settings.LLM_MODEL

        try:
            logger.info(f"Processing query with model {current_model_name}: {query[:100]}...")

            nodes = self.engine.retrieve(self._retrieval_query(query, history))
            response = self.engine.get_llm(current_model_name).chat(self._build_messages(query, nodes, history))
            answer, sources, invalid = resolve_citations(response.message.content or "", nodes)
            self.last_nodes = nodes
            self.last_invalid_citations = invalid

            logger.info(f"Query answered citing {len(sources)} pages ({invalid} invalid citations)")
            return answer, sources, None, None
            
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
            
            # Other errors - show raw error
            else:
                logger.error(f"Query processing error: {error_str}")
                # Extract just the main error message (first line or first 100 chars)
                short_error = error_str.split('\n')[0][:100]
                return None, None, f"❌ Error: {short_error}", None
