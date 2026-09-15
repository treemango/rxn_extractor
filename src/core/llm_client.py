import json
import logging
import sys
from typing import Optional, Type, TypeVar

import httpx
from pydantic import BaseModel, ValidationError

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)


class LLMClient:
    """Ollama LLM client using /api/chat with JSON mode."""

    def __init__(
        self,
        base_url: str,
        model: str,
        timeout: int,
        num_ctx: int = 32768,
        initial_temperature: float = 0.6,
        temperature_increment: float = 0.1,
    ):
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout = timeout
        self.num_ctx = num_ctx
        self.initial_temperature = initial_temperature
        self.temperature_increment = temperature_increment
        self.client = httpx.Client(base_url=self.base_url, timeout=self.timeout)
        self._validate_connection()

    def _validate_connection(self):
        """Check Ollama is reachable and the configured model is downloaded."""
        logger.info(f"Connecting to Ollama at {self.base_url} ...")
        try:
            response = self.client.get("/api/tags", timeout=10)
            response.raise_for_status()
            models = [m.get("name") for m in response.json().get("models", [])]
            logger.info(f"✓ Ollama is running. Available models: {models}")
            if self.model not in models:
                logger.error(
                    f"\n{'='*60}\n"
                    f"  MODEL NOT FOUND: '{self.model}'\n"
                    f"  Ollama has these models: {models}\n"
                    f"  Fix: run   ollama pull {self.model}\n"
                    f"{'='*60}"
                )
                sys.exit(1)  # Hard stop — no point running if model isn't there
            else:
                logger.info(f"✓ Model '{self.model}' is available locally.")
        except httpx.ConnectError:
            logger.error(
                f"\n{'='*60}\n"
                f"  OLLAMA IS NOT RUNNING\n"
                f"  Could not connect to {self.base_url}\n"
                f"  Fix: open a terminal and run   ollama serve\n"
                f"{'='*60}"
            )
            sys.exit(1)  # Hard stop — nothing will work without Ollama
        except Exception as e:
            logger.error(f"Unexpected error connecting to Ollama: {e}")
            sys.exit(1)

        # Execute a quick health check to force the model into RAM and verify inference
        logger.info(f"Sending a simple health-check prompt to verify inference...")
        try:
            payload = {
                "model": self.model,
                "messages": [
                    {
                        "role": "user", 
                        "content": "Hello! Please reply with exactly the word 'READY' and nothing else."
                    }
                ],
                "stream": False,
                # Use a tiny context for the health check to minimize overhead,
                # but use the full configured timeout to allow for the slow HDD load.
                "options": {"num_ctx": 512, "temperature": 0.1} 
            }
            response = self.client.post("/api/chat", json=payload, timeout=self.timeout)
            response.raise_for_status()
            reply = response.json()["message"]["content"].strip()
            logger.info(f"✓ Health check passed. Model replied: '{reply}'")
        except httpx.TimeoutException:
            logger.error(f"  ✗ Health check timed out after {self.timeout}s.")
            sys.exit(1)
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
    ) -> Optional[T]:
        """Extract structured JSON matching a Pydantic model via Ollama /api/chat."""
        temperature = initial_temperature if initial_temperature is not None \
            else self.initial_temperature

        # Instead of injecting the full Pydantic JSON schema (which uses technical
        # vocabulary like $defs / anyOf / properties that confuses small models),
        # just list the required top-level key names in plain English.
        # The concrete examples already in the system prompt show the exact format.
        required_keys = list(response_model.model_fields.keys())
        keys_str = ', '.join(f'"{k}"' for k in required_keys)
        augmented_system = (
            # Hard language override — must come first so it takes priority
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
            f"  → Sending to Ollama | model={self.model} | "
            f"~{prompt_tokens_est} tokens | temp={temperature} | "
            f"num_ctx={self.num_ctx} | timeout={self.timeout}s"
        )

        # ── Context overflow guard ────────────────────────────────────────────
        # If the prompt is larger than num_ctx, Ollama silently truncates from
        # the END of the paper — exactly where Results/Tables usually live.
        # This is the #1 cause of "0 experiments found" on large papers.
        if prompt_tokens_est > self.num_ctx:
            overage = prompt_tokens_est - self.num_ctx
            logger.error(
                f"\n{'!'*60}\n"
                f"  CONTEXT OVERFLOW: Prompt is ~{prompt_tokens_est} tokens but\n"
                f"  OLLAMA_NUM_CTX={self.num_ctx}. Ollama will silently cut the\n"
                f"  last ~{overage} tokens (likely the Results/Tables section).\n"
                f"  Fix: increase OLLAMA_NUM_CTX to at least {prompt_tokens_est + 512}\n"
                f"  in your .env file, then restart.\n"
                f"{'!'*60}"
            )
        elif prompt_tokens_est > self.num_ctx * 0.90:
            logger.warning(
                f"  ⚠ Prompt is using {prompt_tokens_est/self.num_ctx*100:.0f}% of "
                f"num_ctx ({self.num_ctx}). Close to the limit."
            )

        messages = [
            {"role": "system", "content": augmented_system},
            {"role": "user", "content": user_message},
        ]

        for attempt in range(1, max_retries + 1):
            try:
                logger.info(
                    f"  [Attempt {attempt}/{max_retries}] Waiting for response "
                    f"(temp={temperature}) — this may take several minutes on CPU..."
                )
                payload = {
                    "model": self.model,
                    "messages": messages,
                    "stream": False,
                    "format": "json",  # forces valid JSON output from Ollama
                    "options": {
                        "temperature": temperature,
                        "num_ctx": self.num_ctx,
                    },
                }
                response = self.client.post("/api/chat", json=payload)
                response.raise_for_status()
                content = response.json()["message"]["content"]
                response_tokens_est = len(content) // 4
                logger.info(
                    f"  ✓ Response received (~{response_tokens_est} tokens). Parsing..."
                )
                # --- DEBUG: always print full LLM output ---
                logger.info(
                    f"\n{'─'*60}\n"
                    f"  [DEBUG] LLM RAW OUTPUT (attempt {attempt}):\n"
                    f"{content}\n"
                    f"{'─'*60}"
                )
                parsed = self._extract_json(content)

                # Guard: check if the model returned a completely wrong structure.
                # If NONE of the expected fields are present, the model ignored the
                # schema entirely (e.g. returned abstract/keywords/references).
                # Treat this as a failed attempt so the retry ladder kicks in.
                expected_keys = set(response_model.model_fields.keys())
                returned_keys = set(parsed.keys())
                if not expected_keys.intersection(returned_keys):
                    wrong_keys = list(returned_keys)[:5]  # show first 5 wrong keys
                    logger.warning(
                        f"  ✗ Attempt {attempt}: Model returned wrong JSON structure.\n"
                        f"    Expected keys like: {list(expected_keys)[:5]}\n"
                        f"    Got keys: {wrong_keys}\n"
                        f"    The model likely summarized the paper instead of extracting experiments.\n"
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
                # --- DEBUG: print what Pydantic expected vs what it got ---
                expected_fields = list(response_model.model_fields.keys())
                logger.warning(
                    f"\n{'─'*60}\n"
                    f"  [DEBUG] SCHEMA MISMATCH on attempt {attempt}:\n"
                    f"  Expected model : {response_model.__name__}\n"
                    f"  Expected fields: {expected_fields}\n"
                    f"  Validation errors:\n{e}\n"
                    f"{'─'*60}"
                )
            except httpx.TimeoutException:
                logger.error(
                    f"  ✗ Attempt {attempt}: TIMED OUT after {self.timeout}s. "
                    f"The model is too slow for this context size on your hardware. "
                    f"Try reducing OLLAMA_NUM_CTX in .env, or use a smaller model."
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
            from config.settings import ollama_config, extraction_config
            base_url             = ollama_config.base_url
            model                = ollama_config.OLLAMA_MODEL
            timeout              = ollama_config.OLLAMA_TIMEOUT
            num_ctx              = ollama_config.OLLAMA_NUM_CTX
            initial_temperature  = extraction_config.TEMPERATURE
            temperature_increment = extraction_config.TEMPERATURE_INCREMENT
        except Exception:
            base_url             = "http://localhost:11434"
            model                = "qwen2.5:14b-instruct-q4_K_M"
            timeout              = 180
            num_ctx              = 32768
            initial_temperature  = 0.6
            temperature_increment = 0.1
        _client = LLMClient(
            base_url=base_url,
            model=model,
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
