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
        paper_content: str,
        context_hint: str,
        paper_id: int,
        experiment_id: int,
        total_experiments: int = 0,
    ) -> Dict[str, Any]:
        """Extracts data for a single experiment across all sub-domains.

        paper_content and context_hint are kept separate so the paper can be
        sent as the shared KV-cache prefix (identical across all 4 sub-domain
        calls for this experiment), while context_hint becomes part of the
        small per-call question.
        """
        if len(paper_content) < 20:
            logger.warning(f"Experiment {experiment_id} in paper {paper_id} text too short.")
            return {}

        total_str = f"/{total_experiments}" if total_experiments else ""

        sub_domain_results = {}
        for sub_domain in self.sub_domain_names:
            # Load the domain's system prompt (rules, field definitions, examples)
            domain_prompt = self._load_prompt(sub_domain)
            model_class   = self._get_model_class(sub_domain)
            label         = f"Exp {experiment_id}{total_str} | {sub_domain}"

            # Build the question: domain instructions + experiment pointer.
            # This is the ONLY part that changes between the 4 sub-domain calls
            # on the same experiment. The paper stays as the cached prefix.
            question_prompt = (
                f"{domain_prompt}\n\n"
                f"{context_hint}"
            )

            extracted_obj = self.llm_client.extract_with_prefix(
                response_model=model_class,
                paper_content=paper_content,   # ← shared cache prefix
                question_prompt=question_prompt,
                label=label,
            )

            if extracted_obj:
                raw_dict        = extracted_obj.model_dump()
                normalized_dict = normalize_extraction(raw_dict, self.config)
                sub_domain_results[sub_domain] = normalized_dict
            else:
                sub_domain_results[sub_domain] = None

        extraction       = sub_domain_results.copy()
        validation_result = self.validator.validate(extraction, sub_domain_results)

        return {
            "metadata": {
                "paper_id":      paper_id,
                "experiment_id": experiment_id,
            },
            "sub_domain_results": sub_domain_results,
            "validation":         validation_result,
            "overall_confidence": validation_result.get("overall_confidence", 1),
        }

    def extract_paper(self, paper_content: str, paper_id: int, parser_agent: ParserAgent) -> List[Dict[str, Any]]:
        """Parses a paper for experiments and extracts data from each."""
        parser_output = parser_agent.parse(paper_content, paper_id)
        if not parser_output or not hasattr(parser_output, 'experiments'):
            return []

        total   = len(parser_output.experiments)
        results = []

        for i, experiment in enumerate(parser_output.experiments):

            # ── Build the experiment pointer (the small per-call question part) ──
            # These fields were extracted by the parser — they act as a surgical
            # pointer so the subdomain model knows exactly which experiment to focus
            # on without needing to re-read section headings to disambiguate.
            exp_num     = getattr(experiment, 'experiment_number', i + 1)
            brief       = getattr(experiment, 'brief_description', '') or ''
            catalyst    = getattr(experiment, 'catalyst_name', None) or 'not specified'
            reactant    = getattr(experiment, 'reactant', None) or 'not specified'
            temp        = getattr(experiment, 'main_temperature', None) or 'not specified'
            pressure    = getattr(experiment, 'main_pressure', None) or 'not specified'
            products    = getattr(experiment, 'products_mentioned', None) or 'not specified'
            key_section = getattr(experiment, 'key_section', None) or 'see full paper'
            key_params  = getattr(experiment, 'key_parameters', '') or ''

            # NOTE: "FULL PAPER TEXT" line removed — the paper is now sent as its
            # own message (the cached prefix), not concatenated here.
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
            )

            result = self.extract_experiment(
                paper_content=paper_content,   # ← paper passed separately for KV cache
                context_hint=context_hint,
                paper_id=paper_id,
                experiment_id=exp_num,
                total_experiments=total,
            )
            if result:
                results.append(result)

        return results
