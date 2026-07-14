
import os
from dataclasses import dataclass
from dotenv import load_dotenv
from functools import lru_cache
load_dotenv()

PLACEHOLDER_AZURE_OPENAI_ENDPOINTS = {
    "https://your-resource.openai.azure.com",
    "https://your-resource.openai.azure.com/",
}

def _as_int(name: str, default: int) -> int:
    value = os.getenv(name)
    if value is None or value == "":
        return default
    return int(value)


def _as_float(name: str, default: float) -> float:
    value = os.getenv(name)
    if value is None or value == "":
        return default
    return float(value)


def _as_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None or value == "":
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}

@dataclass(frozen=True)
class Settings:
    azure_openai_api_key: str
    azure_openai_endpoint: str
    azure_openai_deployment: str
    azure_openai_api_version: str
    default_result_record_count: int
    max_features_for_answer: int
    query_timeout_seconds: int
    agent_max_tool_rounds: int
    llm_temperature: float
    openai_verify_ssl: bool
    openai_ca_bundle: str | None
    mcp_config_path: str = os.getenv("MCP_CONFIG", "app/mcp_client/mcp_config.json")

    @property
    def use_azure_openai(self) -> bool:
        return bool(
            self.azure_openai_endpoint
            and self.azure_openai_endpoint not in PLACEHOLDER_AZURE_OPENAI_ENDPOINTS
        )

    @property
    def portal_token_enabled(self) -> bool:
        return bool(
            self.esri_portal_url
            and self.esri_portal_username
            and self.esri_portal_password
        )

    def validate_required(self) -> None:
        missing = []
        if not self.azure_openai_api_key:
            missing.append("AZURE_OPENAI_API_KEY")
        if not self.azure_openai_deployment:
            missing.append("AZURE_OPENAI_DEPLOYMENT")
        if not self.azure_openai_api_version:
            missing.append("AZURE_OPENAI_API_VERSION")

        if missing:
            joined = ", ".join(missing)
            raise ValueError(f"Missing required environment variables: {joined}")
        
@lru_cache(maxsize=1)
def get_settings() -> Settings:
    settings = Settings(
        azure_openai_api_key=os.getenv("AZURE_OPENAI_API_KEY", ""),
        azure_openai_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT", "").rstrip("/"),
        azure_openai_deployment=os.getenv("AZURE_OPENAI_DEPLOYMENT", ""),
        azure_openai_api_version=os.getenv(
            "AZURE_OPENAI_API_VERSION",
            "2024-12-01-preview",
        ),
        default_result_record_count=_as_int("DEFAULT_RESULT_RECORD_COUNT", 25),
        max_features_for_answer=_as_int("MAX_FEATURES_FOR_ANSWER", 10),
        query_timeout_seconds=_as_int("QUERY_TIMEOUT_SECONDS", 30),
        agent_max_tool_rounds=_as_int("AGENT_MAX_TOOL_ROUNDS", 4),
        llm_temperature=_as_float("LLM_TEMPERATURE", 0.0),
        openai_verify_ssl=_as_bool("OPENAI_VERIFY_SSL", True),
        openai_ca_bundle=os.getenv("OPENAI_CA_BUNDLE") or None,
    )
    settings.validate_required()
    return settings