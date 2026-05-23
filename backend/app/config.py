from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # DeepSeek
    deepseek_api_key: str = ""
    deepseek_base_url: str = "https://api.deepseek.com/v1"
    deepseek_model: str = "deepseek-chat"

    # TEI
    tei_embedding_url: str = "http://localhost:8888"
    tei_reranker_url: str = "http://localhost:8889"

    # Qdrant
    qdrant_url: str = "http://localhost:6333"
    qdrant_api_key: str = ""

    # App
    app_host: str = "0.0.0.0"
    app_port: int = 8000

    # Paths
    data_raw_dir: str = "data/raw"
    data_processed_dir: str = "data/processed"

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
