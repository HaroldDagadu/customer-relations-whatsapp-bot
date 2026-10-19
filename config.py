from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # Server Configuration
    port: int = 8000
    environment: str = "development"

    # LLM Provider: "gemini" or "deepseek"
    llm_provider: str = "gemini"

    # Google Gemini Configuration (LLM + Embeddings)
    google_api_key: str = ""
    gemini_model: str = "gemini-2.5-flash"
    embedding_model: str = "gemini-embedding-001"

    # DeepSeek Configuration (OpenAI-compatible API)
    deepseek_api_key: str = ""
    deepseek_model: str = "deepseek-chat"
    deepseek_base_url: str = "https://api.deepseek.com/v1"

    # ChromaDB Configuration
    chroma_db_dir: str = "./chroma_db"

    # WhatsApp API Configuration
    whatsapp_webhook_verify_token: str = ""
    whatsapp_api_token: str = ""
    whatsapp_phone_number_id: str = ""

    # Payment Gateway Configuration
    paystack_secret_key: str = ""
    paystack_public_key: str = ""
    use_paystack: bool = True

    # WhatsApp Flows Configuration
    registration_flow_id: str = ""
    ticket_flow_id: str = ""
    disable_whatsapp_flows: bool = True

    # Database
    database_url: str = "sqlite:///./whatsapp.db"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

settings = Settings()
