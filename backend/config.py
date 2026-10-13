"""Runtime configuration loaded from environment variables."""

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Process configuration.

    Defaults are for a local demo. Deployments must override ``api_key`` and
    ``decision_secret``; neither value is a production credential.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    api_key: str = Field(default="dev-only-change-me", alias="API_KEY")
    decision_secret: str = Field(default="dev-only-decision-secret", alias="DECISION_SECRET")
    cors_origins: str = Field(
        default="http://127.0.0.1:8742,http://localhost:8742",
        alias="CORS_ORIGINS",
    )
    audit_db_path: str = Field(default="data/audit.db", alias="AUDIT_DB_PATH")
    sandbox_db_path: str = Field(default="data/sandbox.db", alias="SANDBOX_DB_PATH")
    llm_provider: str = Field(default="mock", alias="LLM_PROVIDER")
    ollama_base_url: str = Field(default="http://127.0.0.1:11434", alias="OLLAMA_BASE_URL")
    ollama_model: str = Field(default="qwen3:4b", alias="OLLAMA_MODEL")
    ollama_temperature: float = Field(default=0.1, alias="OLLAMA_TEMPERATURE")
    w_rule: float = Field(default=0.5, alias="W_RULE")
    w_ml: float = Field(default=0.5, alias="W_ML")
    threshold_approve: int = Field(default=30, alias="THRESHOLD_APPROVE")
    threshold_human: int = Field(default=70, alias="THRESHOLD_HUMAN")
    risk_model_path: str = Field(
        default="backend/ml/artifacts/risk_model.joblib",
        alias="RISK_MODEL_PATH",
    )
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")
    toolemu_enabled: bool = Field(default=False, alias="TOOLEMU_ENABLED")
    toolemu_repo_path: str = Field(default="third_party/ToolEmu", alias="TOOLEMU_REPO_PATH")
    openai_api_key: str = Field(default="", alias="OPENAI_API_KEY")
    openai_base_url: str = Field(default="", alias="OPENAI_BASE_URL")
    eval_seeds: str = Field(default="7,11,19", alias="EVAL_SEEDS")
    results_dir: str = Field(default="results", alias="RESULTS_DIR")
    dataset_path: str = Field(default="data/risk_scenarios.csv", alias="DATASET_PATH")

    def cors_origin_list(self) -> list[str]:
        """Return configured browser origins."""
        return [item.strip() for item in self.cors_origins.split(",") if item.strip()]

    def eval_seed_list(self) -> list[int]:
        """Return comparison seeds parsed from the comma-separated setting."""
        seeds: list[int] = []
        for item in self.eval_seeds.split(","):
            item = item.strip()
            if item:
                seeds.append(int(item))
        return seeds or [7]

    def resolved_model_path(self) -> Path:
        """Return the risk-model path relative to the working directory."""
        return Path(self.risk_model_path)


@lru_cache
def get_settings() -> Settings:
    """Return a cached settings object."""
    return Settings()
