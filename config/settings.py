import os
from dotenv import load_dotenv

load_dotenv()

class DatabaseConfig:
    DB_USER = os.getenv("DB_USER", "")
    DB_PASSWORD = os.getenv("DB_PASSWORD", "")
    DB_HOST = os.getenv("DB_HOST", "")
    DB_PORT = os.getenv("DB_PORT", "")
    DB_NAME = os.getenv("DB_NAME", "")
    DB_URL = os.getenv("DB_URL", "sqlite:///rxn_extractor.db")

    @property
    def connection_string(self):
        if self.DB_URL and self.DB_URL != "sqlite:///rxn_extractor.db":
            return self.DB_URL
        if all([self.DB_USER, self.DB_PASSWORD, self.DB_HOST, self.DB_PORT, self.DB_NAME]):
            return f"postgresql://{self.DB_USER}:{self.DB_PASSWORD}@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"
        return "sqlite:///rxn_extractor.db"

class OllamaConfig:
    OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost")
    OLLAMA_PORT = os.getenv("OLLAMA_PORT", "11434")
    OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen2.5:14b-instruct-q4_K_M")
    OLLAMA_TIMEOUT = int(os.getenv("OLLAMA_TIMEOUT", "180"))
    
    MODEL_PRESETS = {
        "qwen2.5-7b": "qwen2.5:7b-instruct-q4_K_M",
        "qwen2.5-14b": "qwen2.5:14b-instruct-q4_K_M",
        "qwen2.5-32b": "qwen2.5:32b-instruct-q4_K_M",
        "qwen2.5-72b": "qwen2.5:72b-instruct-q4_K_M"
    }

    @property
    def base_url(self):
        return f"{self.OLLAMA_HOST}:{self.OLLAMA_PORT}"

class ExtractionConfig:
    MAX_RETRIES = int(os.getenv("MAX_RETRIES", "3"))
    TEMPERATURE = float(os.getenv("TEMPERATURE", "0.3"))
    TEMPERATURE_INCREMENT = float(os.getenv("TEMPERATURE_INCREMENT", "0.2"))
    CONFIDENCE_THRESHOLD = int(os.getenv("CONFIDENCE_THRESHOLD", "3"))
    ENABLE_VALIDATION = os.getenv("ENABLE_VALIDATION", "true").lower() == "true"

class APIConfig:
    API_HOST = os.getenv("API_HOST", "0.0.0.0")
    API_PORT = int(os.getenv("API_PORT", "8000"))
    API_DEBUG = os.getenv("API_DEBUG", "false").lower() == "true"
    CORS_ORIGINS = os.getenv("CORS_ORIGINS", "*").split(",")

class BatchConfig:
    CHECKPOINT_INTERVAL = int(os.getenv("CHECKPOINT_INTERVAL", "50"))
    CONTINUE_ON_ERROR = os.getenv("CONTINUE_ON_ERROR", "true").lower() == "true"

class LoggingConfig:
    LOG_DIR = os.getenv("LOG_DIR", "logs")
    LOG_FILE = os.getenv("LOG_FILE", "rxn_extractor.log")
    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")

# Singleton instances at module level
db_config = DatabaseConfig()
ollama_config = OllamaConfig()
extraction_config = ExtractionConfig()
api_config = APIConfig()
batch_config = BatchConfig()
logging_config = LoggingConfig()
