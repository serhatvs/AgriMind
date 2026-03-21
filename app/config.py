from dataclasses import dataclass
from typing import ClassVar, Self

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings


@dataclass(frozen=True, slots=True)
class ProviderSettingSpec:
    """Describe how a provider setting is loaded, normalized, and validated."""

    short_field: str
    canonical_field: str
    allowed_values: tuple[str, ...]
    aliases: dict[str, str]


class Settings(BaseSettings):
    DATABASE_URL: str = "postgresql://postgres:postgres@localhost:5432/agrimind"
    APP_NAME: str = "AgriMind"
    DEBUG: bool = False
    API_V1_PREFIX: str = "/api/v1"
    YIELD_PROVIDER: str | None = None
    EXPLANATION_PROVIDER: str | None = None
    RISK_PROVIDER: str | None = None
    EXTRACTION_PROVIDER: str | None = None
    AI_SUITABILITY_PROVIDER: str = "rule_based"
    AI_RISK_PROVIDER: str = "rule_based"
    AI_EXPLANATION_PROVIDER: str = "rule_based"
    AI_RANKING_AUGMENTATION_PROVIDER: str = "rule_based"
    AI_YIELD_PROVIDER: str = "xgboost"
    AI_ASSISTANT_PROVIDER: str = "openai"
    AI_EXTRACTION_PROVIDER: str = "rule_based"
    YIELD_MODEL_DIR: str = "artifacts/yield_model"
    OPENAI_API_KEY: str | None = None
    OPENAI_MODEL: str = "gpt-4.1-mini"
    OPENAI_BASE_URL: str = "https://api.openai.com/v1"
    OPENAI_TIMEOUT_SECONDS: float = 20.0

    _PROVIDER_SETTING_SPECS: ClassVar[dict[str, ProviderSettingSpec]] = {
        "yield": ProviderSettingSpec(
            short_field="YIELD_PROVIDER",
            canonical_field="AI_YIELD_PROVIDER",
            allowed_values=("stub", "ml", "xgboost"),
            aliases={
                "stub": "stub",
                "ml": "xgboost",
                "xgboost": "xgboost",
            },
        ),
        "explanation": ProviderSettingSpec(
            short_field="EXPLANATION_PROVIDER",
            canonical_field="AI_EXPLANATION_PROVIDER",
            allowed_values=("deterministic", "rule_based"),
            aliases={
                "deterministic": "deterministic",
                "rule_based": "rule_based",
            },
        ),
        "risk": ProviderSettingSpec(
            short_field="RISK_PROVIDER",
            canonical_field="AI_RISK_PROVIDER",
            allowed_values=("rule_based", "stub"),
            aliases={
                "rule_based": "rule_based",
                "stub": "stub",
            },
        ),
        "extraction": ProviderSettingSpec(
            short_field="EXTRACTION_PROVIDER",
            canonical_field="AI_EXTRACTION_PROVIDER",
            allowed_values=("manual", "rule_based", "stub"),
            aliases={
                "manual": "rule_based",
                "rule_based": "rule_based",
                "stub": "stub",
            },
        ),
    }

    @field_validator("DEBUG", mode="before")
    @classmethod
    def parse_debug(cls, value):
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            normalized = value.strip().lower()
            if normalized in {"1", "true", "yes", "on", "debug", "dev", "development"}:
                return True
            if normalized in {"0", "false", "no", "off", "release", "prod", "production", ""}:
                return False
        return value

    @model_validator(mode="after")
    def normalize_provider_settings(self) -> Self:
        """Resolve provider aliases into canonical AI_* settings."""

        for spec in self._PROVIDER_SETTING_SPECS.values():
            resolved_value = self._resolve_provider_setting(spec)
            setattr(self, spec.canonical_field, resolved_value)
        return self

    def _resolve_provider_setting(self, spec: ProviderSettingSpec) -> str:
        short_value = getattr(self, spec.short_field)
        legacy_value = getattr(self, spec.canonical_field)

        if short_value is not None:
            source_name = spec.short_field
            source_value = short_value
        else:
            source_name = spec.canonical_field
            source_value = legacy_value

        normalized_value = self._normalize_provider_value(source_name, source_value, spec)
        resolved_value = spec.aliases.get(normalized_value)
        if resolved_value is None:
            allowed_values = ", ".join(spec.allowed_values)
            raise ValueError(
                f"{source_name}={normalized_value!r} is not supported. Allowed values: {allowed_values}"
            )
        return resolved_value

    @staticmethod
    def _normalize_provider_value(
        source_name: str,
        source_value: str,
        spec: ProviderSettingSpec,
    ) -> str:
        if not isinstance(source_value, str):
            raise ValueError(f"{source_name} must be a string provider id")

        normalized_value = source_value.strip().lower()
        if normalized_value:
            return normalized_value

        allowed_values = ", ".join(spec.allowed_values)
        raise ValueError(f"{source_name} cannot be blank. Allowed values: {allowed_values}")

    model_config = {"env_file": ".env", "extra": "ignore"}


settings = Settings()
