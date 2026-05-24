from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # DeepSeek
    deepseek_api_key: str = ""
    deepseek_base_url: str = "https://api.deepseek.com/v1"
    deepseek_model: str = "deepseek-chat"

    # LLM 参数
    llm_temperature: float = 0.15
    llm_max_tokens: int = 4096

    # TEI
    tei_embedding_url: str = "http://localhost:8888"
    tei_reranker_url: str = "http://localhost:8889"

    # Qdrant
    qdrant_url: str = "http://localhost:6333"
    qdrant_api_key: str = ""

    # 检索参数
    reranker_score_threshold: float = 0.15
    dense_top: int = 30
    sparse_top: int = 30

    # App
    app_host: str = "0.0.0.0"
    app_port: int = 8000

    # Paths
    data_raw_dir: str = "data/raw"
    data_processed_dir: str = "data/processed"

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
