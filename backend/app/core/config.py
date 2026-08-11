from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    APP_NAME: str = "灵山胜境AI数字人导览系统"
    LLM_API_KEY: str = ""
    LLM_BASE_URL: str = "https://dashscope.aliyuncs.com/compatible-mode"
    LLM_MODEL: str = "qwen-vl-max"
    ASR_MODEL: str = "paraformer-zh"
    TTS_MODEL: str = "cosyvoice-v1"
    MYSQL_HOST: str = "localhost"
    MYSQL_PORT: int = 3306
    MYSQL_USER: str = "root"
    MYSQL_PASSWORD: str = ""
    MYSQL_DATABASE: str = "lingshan_guide"
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    MILVUS_HOST: str = "localhost"
    MILVUS_PORT: int = 19530
    MILVUS_COLLECTION: str = "lingshan_knowledge"

    class Config:
        env_file = ".env"


settings = Settings()
