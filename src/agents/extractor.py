import logging
import importlib
from typing import Optional, Type, Dict, Any, List
from pydantic import BaseModel

from src.core.llm_client import get_llm_client, LLMClient
from src.core.normalizer import normalize_extraction
from src.core.validator import Validator
from src.agents.parser_agent import ParserAgent

logger = logging.getLogger(__name__)

class Extractor:
    """Generic multi-agent orchestrator that loops through sub-domains."""

    def __init__(self, llm_client: Optional[LLMClient] = None):
        self.llm_client = llm_client or get_llm_client()
        try:
            from src.auto_generated import config
            self.config = config
            self.sub_domain_names = getattr(config, "SUB_DOMAIN_NAMES", [])
        except ImportError:
            logger.warning("Could not import src.auto_generated.config")
            self.config = None
            self.sub_domain_names = []
            
        self.validator = Validator(self.config)

    def _load_prompt(self, sub_domain_name: str) -> str:
        try:
            with open(f"src/auto_generated/prompts/{sub_domain_name}.md", "r", encoding="utf-8") as f:
                return f.read()
        except FileNotFoundError:
            logger.error(f"Prompt for {sub_domain_name} not found.")
            return f"Extract information for {sub_domain_name}."

    def _get_model_class(self, sub_domain_name: str) -> Type[BaseModel]:
        # e.g., 'feedstock' -> 'FeedstockExtraction'
        class_name = "".join(word.capitalize() for word in sub_domain_name.split("_")) + "Extraction"
        try:
            models_module = importlib.import_module("src.auto_generated.models")
            return getattr(models_module, class_name)
        except (ImportError, AttributeError) as e:
            logger.error(f"Model class {class_name} not found: {e}")
            raise

    def extract_experiment(self, experiment_text: str, paper_id: int, experiment_id: int) -> Dict[str, Any]:
        """Extracts data for a single experiment across all sub-domains."""
        if len(experiment_text) < 20:
            logger.warning(f"Experiment {experiment_id} in paper {paper_id} text too short.")
            return {}

        try:
            from src.auto_generated.prompts.user_templates import SUBDOMAIN_USER_TEMPLATE
            user_template = SUBDOMAIN_USER_TEMPLATE
        except ImportError:
            user_template = "Extract from this text:\n\n{experiment_text}"

        formatted_text = user_template.format(experiment_text=experiment_text)

        sub_domain_results = {}
        for sub_domain in self.sub_domain_names:
            prompt = self._load_prompt(sub_domain)
            model_class = self._get_model_class(sub_domain)

            extracted_obj = self.llm_client.extract(
                response_model=model_class,
                system_prompt=prompt,
                user_message=formatted_text
            )

            if extracted_obj:
                raw_dict = extracted_obj.model_dump()
                normalized_dict = normalize_extraction(raw_dict, self.config)
                sub_domain_results[sub_domain] = normalized_dict
            else:
                sub_domain_results[sub_domain] = None

        extraction = sub_domain_results.copy()
        validation_result = self.validator.validate(extraction, sub_domain_results)

        full_extraction = {
            "metadata": {
                "paper_id": paper_id,
                "experiment_id": experiment_id
            },
            "sub_domain_results": sub_domain_results,
            "validation": validation_result,
            "overall_confidence": validation_result.get("overall_confidence", 1),
        }

        return full_extraction

    def extract_paper(self, paper_content: str, paper_id: int, parser_agent: ParserAgent) -> List[Dict[str, Any]]:
        """Parses a paper for experiments and extracts data from each."""
        parser_output = parser_agent.parse(paper_content, paper_id)
        if not parser_output or not hasattr(parser_output, 'experiments'):
            return []

        results = []
        for i, experiment in enumerate(parser_output.experiments):
            # ExperimentMetadata has no full text — use the full paper content
            # enriched with the brief_description as context hint
            brief = getattr(experiment, 'brief_description', '')
            key_params = getattr(experiment, 'key_parameters', '')
            context_hint = f"Experiment {i+1}: {brief}. Key parameters: {key_params}"
            exp_text = f"{context_hint}\n\n---\n\n{paper_content}"

            result = self.extract_experiment(exp_text, paper_id, i + 1)
            if result:
                results.append(result)

        return results
