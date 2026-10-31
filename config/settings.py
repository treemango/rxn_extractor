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

class LLMConfig:
    # Path to the GGUF model file downloaded in the 'models' directory
    MODEL_PATH = os.getenv("MODEL_PATH", "models/Qwen2.5-14B-Instruct-Q4_K_M.gguf")
    
    # -1 means offload all layers to the GPU
    NUM_GPU_LAYERS = int(os.getenv("NUM_GPU_LAYERS", "-1"))
    
    # 8192 is safe for the 14B model on a V100 GPU
    NUM_CTX = int(os.getenv("NUM_CTX", "8192"))
    
    # How long to wait for generation (not as strictly needed for in-process, but keeping for compatibility)
    TIMEOUT = int(os.getenv("LLM_TIMEOUT", "600"))

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
llm_config = LLMConfig()
extraction_config = ExtractionConfig()
api_config = APIConfig()
batch_config = BatchConfig()
logging_config = LoggingConfig()
