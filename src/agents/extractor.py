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

    def extract_experiment(
        self,
        experiment_text: str,
        paper_id: int,
        experiment_id: int,
        total_experiments: int = 0,
    ) -> Dict[str, Any]:
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

        total_str = f"/{total_experiments}" if total_experiments else ""

        sub_domain_results = {}
        for sub_domain in self.sub_domain_names:
            prompt = self._load_prompt(sub_domain)
            model_class = self._get_model_class(sub_domain)
            label = f"Exp {experiment_id}{total_str} | {sub_domain}"

            extracted_obj = self.llm_client.extract(
                response_model=model_class,
                system_prompt=prompt,
                user_message=formatted_text,
                label=label,
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

        total = len(parser_output.experiments)
        results = []
        for i, experiment in enumerate(parser_output.experiments):

            # ── Build a rich, surgical context block for subdomain agents ─────
            # Each field was extracted by the parser — use them as precise pointers
            # so subdomain agents don't have to search the entire 12,000-token paper.
            exp_num     = getattr(experiment, 'experiment_number', i + 1)
            brief       = getattr(experiment, 'brief_description', '') or ''
            catalyst    = getattr(experiment, 'catalyst_name', None) or 'not specified'
            reactant    = getattr(experiment, 'reactant', None) or 'not specified'
            temp        = getattr(experiment, 'main_temperature', None) or 'not specified'
            pressure    = getattr(experiment, 'main_pressure', None) or 'not specified'
            products    = getattr(experiment, 'products_mentioned', None) or 'not specified'
            key_section = getattr(experiment, 'key_section', None) or 'see full paper below'
            key_params  = getattr(experiment, 'key_parameters', '') or ''

            context_hint = (
                f"{'='*60}\n"
                f"TARGET EXPERIMENT: #{exp_num} of {total}\n"
                f"{'='*60}\n"
                f"Description    : {brief}\n"
                f"Catalyst/System: {catalyst}\n"
                f"Reactant       : {reactant}\n"
                f"Temperature    : {temp}\n"
                f"Pressure       : {pressure}\n"
                f"Products noted : {products}\n"
                f"Paper location : {key_section}\n"
                f"Key parameters : {key_params}\n"
                f"{'='*60}\n"
                f"CRITICAL INSTRUCTIONS:\n"
                f"  1. Extract data ONLY for the experiment described above.\n"
                f"  2. If the paper contains multiple experiments, IGNORE all others.\n"
                f"  3. Focus especially on the section/table referenced in 'Paper location'.\n"
                f"  4. If a field is not mentioned for THIS specific experiment, return null.\n"
                f"  5. Never mix values from a different experiment into this one.\n"
                f"{'='*60}\n"
                f"\nFULL PAPER TEXT (for reference):\n"
            )
            exp_text = f"{context_hint}{paper_content}"

            result = self.extract_experiment(exp_text, paper_id, exp_num, total_experiments=total)
            if result:
                results.append(result)

        return results

