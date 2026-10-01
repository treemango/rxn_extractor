import logging
from typing import Tuple, Optional
from pydantic import BaseModel, Field

from src.core.llm_client import get_llm_client

logger = logging.getLogger(__name__)

class FilterOutput(BaseModel):
    is_relevant: bool = Field(description="True if the paper describes the target reaction, False otherwise")
    reason: str = Field(description="Brief reason explaining the relevance decision")

class FilterAgent:
    """Agent that performs a fast pre-check on the paper abstract/intro to determine relevance."""

    def __init__(self, target_reaction: str, llm_client=None):
        self.target_reaction = target_reaction
        self.llm_client = llm_client or get_llm_client()
        self.system_prompt = (
            "You are an expert chemistry screener. Your job is to determine if a "
            "research paper is relevant to a specific target reaction based on its title, abstract, and introduction. "
            "IMPORTANT: If the paper explicitly focuses on the target reaction, mark it relevant. "
            "If it focuses on a completely different reaction or different primary reactants/products, mark it irrelevant."
        )

    def check_relevance(self, paper_content: str, paper_id: int = 0) -> Tuple[bool, str]:
        """Checks if the paper matches the target reaction using the first 4000 characters."""
        if not self.target_reaction:
            # If no target reaction is defined in YAML, skip the filter (pass everything)
            return True, "No target_reaction specified in YAML. Skipping filter."

        if len(paper_content) < 100:
            return False, "Paper content too short."

        # Take only the first 4000 characters to save compute and context (typically Title + Abstract + Intro)
        text_chunk = paper_content[:4000]

        user_message = (
            f"TARGET REACTION TO MATCH:\n{self.target_reaction}\n\n"
            f"{'='*60}\n"
            f"PAPER TEXT (First section):\n{text_chunk}\n"
            f"{'='*60}\n\n"
            "INSTRUCTION:\n"
            "Does the paper primarily study or investigate the TARGET REACTION?\n"
            "Return a JSON object with 'is_relevant' (boolean) and 'reason' (string)."
        )

        result = self.llm_client.extract(
            response_model=FilterOutput,
            system_prompt=self.system_prompt,
            user_message=user_message,
            label=f"Paper {paper_id} | Relevance Filter"
        )

        if not result:
            logger.warning(f"Paper {paper_id}: Filter agent failed to return a response. Defaulting to True.")
            return True, "Filter agent failure."

        return result.is_relevant, result.reason
