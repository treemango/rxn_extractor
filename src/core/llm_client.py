import json
import logging
import sys
import os
from typing import Optional, Type, TypeVar

from pydantic import BaseModel, ValidationError

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)

class LLMClient:
    """llama-cpp-python client for fully offline, in-process LLM inference."""

    def __init__(
        self,
        model_path: str,
        n_gpu_layers: int = -1,
        num_ctx: int = 8192,
        timeout: int = 600,
        initial_temperature: float = 0.6,
        temperature_increment: float = 0.1,
    ):
        self.model_path = model_path
        self.n_gpu_layers = n_gpu_layers
        self.num_ctx = num_ctx
        self.timeout = timeout
        self.initial_temperature = initial_temperature
        self.temperature_increment = temperature_increment
        
        self.llm = None
        self._validate_connection()

    def _validate_connection(self):
        """Check that the model file exists and initialize llama-cpp-python."""
        logger.info(f"Loading local model from {self.model_path} ...")
        
        if not os.path.exists(self.model_path):
            logger.error(
                f"\n{'='*60}\n"
                f"  MODEL FILE NOT FOUND: '{self.model_path}'\n"
                f"  Please download the .gguf model file into the models/ directory.\n"
                f"{'='*60}"
            )
            sys.exit(1)
            
        try:
            from llama_cpp import Llama
            # Initialize the model
            self.llm = Llama(
                model_path=self.model_path,
                n_gpu_layers=self.n_gpu_layers,
                n_ctx=self.num_ctx,
                verbose=False # Set to True if you want C-level debug logs from llama.cpp
            )
            logger.info(f"✓ Model '{self.model_path}' loaded successfully into memory/GPU.")
        except ImportError:
            logger.error("llama-cpp-python is not installed. Please install it.")
            sys.exit(1)
        except Exception as e:
            logger.error(f"Failed to load model with llama-cpp-python: {e}")
            sys.exit(1)

        # Health check
        logger.info(f"Sending a simple health-check prompt to verify inference...")
        try:
            response = self.llm.create_chat_completion(
                messages=[{"role": "user", "content": "Hello! Please reply with exactly the word 'READY' and nothing else."}],
                temperature=0.1,
                max_tokens=10
            )
            reply = response["choices"][0]["message"]["content"].strip()
            logger.info(f"✓ Health check passed. Model replied: '{reply}'")
        except Exception as e:
            logger.error(f"  ✗ Health check failed. Inference error: {e}")
            sys.exit(1)

    @staticmethod
    def _extract_json(text: str) -> dict:
        """4-tier JSON recovery strategy."""
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass
        if "```json" in text:
            try:
                content = text.split("```json")[1].split("```")[0].strip()
                return json.loads(content)
            except (IndexError, json.JSONDecodeError):
                pass
        if "```" in text:
            try:
                for block in text.split("```")[1::2]:
                    try:
                        return json.loads(block.strip())
                    except json.JSONDecodeError:
                        continue
            except Exception:
                pass
        try:
            start, end = text.find("{"), text.rfind("}")
            if start != -1 and end > start:
                return json.loads(text[start : end + 1])
        except json.JSONDecodeError:
            pass
        raise json.JSONDecodeError("Could not extract JSON from text", text, 0)

    def extract(
        self,
        response_model: Type[T],
        system_prompt: str,
        user_message: str,
        max_retries: int = 3,
        initial_temperature: Optional[float] = None,
        label: str = "",
    ) -> Optional[T]:
        """Extract structured JSON matching a Pydantic model via llama-cpp-python."""
        temperature = initial_temperature if initial_temperature is not None \
            else self.initial_temperature

        required_keys = list(response_model.model_fields.keys())
        keys_str = ', '.join(f'"{k}"' for k in required_keys)
        augmented_system = (
            "IMPORTANT: You MUST respond in English only. "
            "Regardless of the language of the input text, "
            "all your output — including field values — must be in English.\n\n"
            f"{system_prompt}\n\n"
            f"## REQUIRED OUTPUT KEYS\n"
            f"Your JSON response MUST be an object containing ONLY these top-level keys:\n"
            f"  {keys_str}\n"
            f"Return ONLY the JSON object. No markdown fences, no explanation, no other text."
        )

        prompt_chars = len(augmented_system) + len(user_message)
        prompt_tokens_est = prompt_chars // 4  # rough estimate
        
        logger.info(
            f"  → Inferencing locally | model={os.path.basename(self.model_path)} | "
            f"~{prompt_tokens_est} tokens | ctx_limit={self.num_ctx} | temp={temperature}"
        )

        # Defensive dynamic truncation: leave at least 2048 tokens for completion output.
        # This guarantees that even massive 100-page papers will NEVER overflow or crash llama.cpp.
        max_prompt_tokens = max(1024, self.num_ctx - 2048)
        if prompt_tokens_est > max_prompt_tokens:
            max_user_chars = max(1000, (max_prompt_tokens - (len(augmented_system) // 4)) * 4)
            logger.warning(
                f"\n{'!'*60}\n"
                f"  [CONTEXT PROTECT] Prompt is ~{prompt_tokens_est} tokens (limit: {max_prompt_tokens}).\n"
                f"  Truncating user text from {len(user_message)} to {max_user_chars} chars to prevent overflow.\n"
                f"{'!'*60}"
            )
            user_message = user_message[:max_user_chars] + "\n\n[... truncated by extractor to fit context window ...]"
            prompt_tokens_est = (len(augmented_system) + len(user_message)) // 4
        elif prompt_tokens_est > self.num_ctx * 0.85:
            logger.warning(
                f"  ⚠ Prompt is using {prompt_tokens_est/self.num_ctx*100:.0f}% of "
                f"num_ctx ({self.num_ctx})."
            )

        messages = [
            {"role": "system", "content": augmented_system},
            {"role": "user", "content": user_message},
        ]

        for attempt in range(1, max_retries + 1):
            try:
                logger.info(f"  [Attempt {attempt}/{max_retries}] Generating response (temp={temperature})...")
                
                # We use response_format={"type": "json_object"} to constrain output
                # llama-cpp-python supports this if the model is capable
                response = self.llm.create_chat_completion(
                    messages=messages,
                    temperature=temperature,
                    response_format={"type": "json_object"}
                )
                
                content = response["choices"][0]["message"]["content"]
                response_tokens_est = len(content) // 4
                
                logger.info(f"  ✓ Response generated (~{response_tokens_est} tokens). Parsing...")
                
                label_line = f"  [{label}]" if label else ""
                logger.info(
                    f"\n{'─'*60}\n"
                    f"{label_line}\n"
                    f"  [DEBUG] LLM RAW OUTPUT (attempt {attempt}):\n"
                    f"{content}\n"
                    f"{'─'*60}"
                )
                
                parsed = self._extract_json(content)

                expected_keys = set(response_model.model_fields.keys())
                returned_keys = set(parsed.keys())
                if not expected_keys.intersection(returned_keys):
                    wrong_keys = list(returned_keys)[:5]
                    logger.warning(
                        f"  ✗ Attempt {attempt}: Model returned wrong JSON structure.\n"
                        f"    Expected keys like: {list(expected_keys)[:5]}\n"
                        f"    Got keys: {wrong_keys}\n"
                        f"    Retrying with higher temperature..."
                    )
                    temperature = round(temperature + self.temperature_increment, 2)
                    continue

                result = response_model(**parsed)
                logger.info(f"  ✓ Attempt {attempt}: Parsed successfully.")
                return result
                
            except json.JSONDecodeError as e:
                logger.warning(f"  ✗ Attempt {attempt}: JSON parse error: {e}")
            except ValidationError as e:
                expected_fields = list(response_model.model_fields.keys())
                logger.warning(
                    f"\n{'─'*60}\n"
                    f"  [DEBUG] SCHEMA MISMATCH on attempt {attempt}:\n"
                    f"  Expected model : {response_model.__name__}\n"
                    f"  Expected fields: {expected_fields}\n"
                    f"  Validation errors:\n{e}\n"
                    f"{'─'*60}"
                )
            except Exception as e:
                logger.warning(f"  ✗ Attempt {attempt}: Request error: {e}")
            temperature = round(temperature + self.temperature_increment, 2)

        logger.error("  ✗ All extraction attempts failed for this sub-domain.")
        return None

_client: Optional[LLMClient] = None

def get_llm_client() -> LLMClient:
    """Returns a singleton LLMClient using settings from config/settings.py."""
    global _client
    if _client is None:
        try:
            from config.settings import llm_config, extraction_config
            model_path           = llm_config.MODEL_PATH
            n_gpu_layers         = llm_config.NUM_GPU_LAYERS
            timeout              = llm_config.TIMEOUT
            num_ctx              = llm_config.NUM_CTX
            initial_temperature  = extraction_config.TEMPERATURE
            temperature_increment = extraction_config.TEMPERATURE_INCREMENT
        except Exception:
            model_path           = "models/Qwen2.5-14B-Instruct-Q4_K_M.gguf"
            n_gpu_layers         = -1
            timeout              = 600
            num_ctx              = 8192
            initial_temperature  = 0.6
            temperature_increment = 0.1
        _client = LLMClient(
            model_path=model_path,
            n_gpu_layers=n_gpu_layers,
            timeout=timeout,
            num_ctx=num_ctx,
            initial_temperature=initial_temperature,
            temperature_increment=temperature_increment,
        )
    return _client

def reset_client():
    """Resets the singleton (useful after config changes)."""
    global _client
    _client = None
