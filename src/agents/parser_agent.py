import logging
from typing import Optional

from src.core.llm_client import get_llm_client, LLMClient
from src.auto_generated.models import ParserOutput

logger = logging.getLogger(__name__)

class ParserAgent:
    """Parser agent that identifies experiments in a paper."""

    def __init__(self, llm_client: Optional[LLMClient] = None):
        self.llm_client = llm_client or get_llm_client()
        
        try:
            with open("src/auto_generated/prompts/parser.md", "r", encoding="utf-8") as f:
                self.system_prompt = f.read()
        except FileNotFoundError:
            logger.warning("Parser system prompt not found. Using default.")
            self.system_prompt = "You are a parser. Extract experiments from the text."
            
        try:
            from src.auto_generated.prompts.user_templates import PARSER_USER_TEMPLATE
            self.user_template = PARSER_USER_TEMPLATE
        except ImportError:
            self.user_template = "Parse this text:\n\n{paper_content}"

    def parse(self, paper_content: str, paper_id: int = 0) -> Optional[ParserOutput]:
        """Parses the paper content to find experiments."""
        if len(paper_content) < 100:
            logger.warning(f"Paper {paper_id} content too short ({len(paper_content)} chars).")
            return None
            
        user_message = self.user_template.format(paper_content=paper_content)
        
        result = self.llm_client.extract(
            response_model=ParserOutput,
            system_prompt=self.system_prompt,
            user_message=user_message
        )
        
        if result:
            experiments_count = len(result.experiments) if hasattr(result, 'experiments') else 0
            avg_conf = 0.0
            if experiments_count > 0:
                confs = [getattr(e, 'confidence', getattr(e, 'confidence_score', 3))
                         for e in result.experiments]
                avg_conf = sum(confs) / len(confs)
            logger.info(f"Paper {paper_id}: Found {experiments_count} experiments. Avg Confidence: {avg_conf:.2f}")
            return result
        else:
            logger.error(f"Paper {paper_id}: Failed to parse experiments.")
            return None
