from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """应用配置。"""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = Field(default="景区导览服务AI数字人", alias="APP_NAME")
    app_env: str = Field(default="development", alias="APP_ENV")
    app_debug: bool = Field(default=True, alias="APP_DEBUG")
    database_url: str = Field(
        default="postgresql+psycopg://scenic_user:scenic_password@localhost:5432/scenic_ai_guide",
        alias="DATABASE_URL",
    )
    chroma_persist_dir: str = Field(default="./data/vector_store/chroma", alias="CHROMA_PERSIST_DIR")
    llm_provider: str = Field(default="deepseek", alias="LLM_PROVIDER")
    deepseek_api_key: str | None = Field(default=None, alias="DEEPSEEK_API_KEY")
    deepseek_base_url: str = Field(default="https://api.deepseek.com", alias="DEEPSEEK_BASE_URL")
    deepseek_model: str = Field(default="deepseek-v4-flash", alias="DEEPSEEK_MODEL")
    qwen_api_key: str | None = Field(default=None, alias="QWEN_API_KEY")
    qwen_base_url: str | None = Field(default="https://dashscope.aliyuncs.com/compatible-mode/v1", alias="QWEN_BASE_URL")
    qwen_model: str = Field(default="qwen-plus", alias="QWEN_MODEL")
    multimodal_provider: str = Field(default="qwen-vl", alias="MULTIMODAL_PROVIDER")
    multimodal_model: str = Field(default="qwen-vl-plus", alias="MULTIMODAL_MODEL")
    asr_model_size: str = Field(default="small", alias="ASR_MODEL_SIZE")
    asr_device: str = Field(default="cpu", alias="ASR_DEVICE")
    asr_compute_type: str = Field(default="int8", alias="ASR_COMPUTE_TYPE")
    tts_provider: str = Field(default="browser", alias="TTS_PROVIDER")
    azure_speech_key: str | None = Field(default=None, alias="AZURE_SPEECH_KEY")
    azure_speech_region: str | None = Field(default=None, alias="AZURE_SPEECH_REGION")


@lru_cache
def get_settings() -> Settings:
    return Settings()
