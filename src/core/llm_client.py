import json
import logging
from typing import Optional, Type, TypeVar

import httpx
from pydantic import BaseModel, ValidationError

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)


class LLMClient:
    """Ollama LLM client using /api/chat with JSON mode."""

    def __init__(self, base_url: str, model: str, timeout: int, num_ctx: int = 32768):
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout = timeout
        self.num_ctx = num_ctx
        self.client = httpx.Client(base_url=self.base_url, timeout=self.timeout)
        self._validate_connection()

    def _validate_connection(self):
        try:
            response = self.client.get("/api/tags")
            response.raise_for_status()
            models = [m.get("name") for m in response.json().get("models", [])]
            logger.info(f"Ollama connected. Available models: {models}")
            if self.model not in models:
                logger.warning(
                    f"Model '{self.model}' not found locally. "
                    f"Run: ollama pull {self.model}"
                )
        except Exception as e:
            logger.error(f"Failed to connect to Ollama at {self.base_url}: {e}")

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
        initial_temperature: float = 0.3,
    ) -> Optional[T]:
        """Extract structured JSON matching a Pydantic model via Ollama /api/chat."""
        temperature = initial_temperature

        # Inject schema so the model knows exact required fields
        schema = json.dumps(response_model.model_json_schema(), indent=2)
        augmented_system = (
            f"{system_prompt}\n\n"
            f"## REQUIRED OUTPUT SCHEMA\n"
            f"Your response MUST be valid JSON conforming to this schema:\n"
            f"```json\n{schema}\n```\n"
            f"Return ONLY the JSON object. No markdown fences, no explanation."
        )

        messages = [
            {"role": "system", "content": augmented_system},
            {"role": "user", "content": user_message},
        ]

        for attempt in range(1, max_retries + 1):
            try:
                payload = {
                    "model": self.model,
                    "messages": messages,
                    "stream": False,
                    "format": "json",  # forces valid JSON output from Ollama
                    "options": {
                        "temperature": temperature,
                        "num_ctx": self.num_ctx,  # override Ollama's default 2048 truncation
                    },
                }
                response = self.client.post("/api/chat", json=payload)
                response.raise_for_status()
                content = response.json()["message"]["content"]
                logger.debug(f"Attempt {attempt} raw (first 200): {content[:200]}")
                result = response_model(**self._extract_json(content))
                logger.info(f"Attempt {attempt}: Success (temp={temperature})")
                return result
            except json.JSONDecodeError as e:
                logger.warning(f"Attempt {attempt}: JSON error: {e} (temp={temperature})")
            except ValidationError as e:
                logger.warning(f"Attempt {attempt}: Validation error: {e} (temp={temperature})")
            except Exception as e:
                logger.warning(f"Attempt {attempt}: Request error: {e} (temp={temperature})")
            temperature += 0.2

        logger.error("All extraction attempts failed.")
        return None


_client: Optional[LLMClient] = None


def get_llm_client() -> LLMClient:
    """Returns a singleton LLMClient using settings from config/settings.py."""
    global _client
    if _client is None:
        try:
            from config.settings import ollama_config
            base_url = ollama_config.base_url
            model    = ollama_config.OLLAMA_MODEL
            timeout  = ollama_config.OLLAMA_TIMEOUT
            num_ctx  = ollama_config.OLLAMA_NUM_CTX
        except Exception:
            base_url = "http://localhost:11434"
            model    = "qwen2.5:14b-instruct-q4_K_M"
            timeout  = 180
            num_ctx  = 32768
        _client = LLMClient(base_url=base_url, model=model, timeout=timeout, num_ctx=num_ctx)
    return _client


def reset_client():
    """Resets the singleton (useful after config changes)."""
    global _client
    _client = None
