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
    DATABASE_ECHO: bool = False
    DATABASE_POOL_PRE_PING: bool = True
    DATABASE_POOL_SIZE: int = 5
    DATABASE_MAX_OVERFLOW: int = 10
    DATABASE_POOL_TIMEOUT_SECONDS: int = 30
    DATABASE_CONNECT_TIMEOUT_SECONDS: int = 10
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
    NASA_POWER_SOURCE_NAME: str = "NASA POWER Daily"
    NASA_POWER_BASE_URL: str = "https://power.larc.nasa.gov/api/temporal/daily/point"
    NASA_POWER_COMMUNITY: str = "AG"
    NASA_POWER_TIMEOUT_SECONDS: float = 60.0
    NASA_POWER_DEFAULT_LOOKBACK_DAYS: int = 30
    NASA_POWER_TIME_STANDARD: str = "UTC"
    FAOSTAT_SOURCE_NAME: str = "FAOSTAT Crops and Livestock"
    FAOSTAT_BULK_DOWNLOAD_URL: str = (
        "https://fenixservices.fao.org/faostat/static/bulkdownloads/"
        "Production_Crops_Livestock_E_All_Data_(Normalized).zip"
    )
    FAOSTAT_TIMEOUT_SECONDS: float = 120.0
    FAOSTAT_DEFAULT_LOOKBACK_YEARS: int = 1
    FAOSTAT_BATCH_SIZE: int = 500
    FAOSTAT_DEFAULT_COUNTRIES: str = ""
    FAOSTAT_DEFAULT_CROPS: str = ""

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

    @field_validator("NASA_POWER_DEFAULT_LOOKBACK_DAYS")
    @classmethod
    def validate_nasa_power_lookback_days(cls, value: int) -> int:
        """Ensure the default NASA POWER date window is positive."""

        if value <= 0:
            raise ValueError("NASA_POWER_DEFAULT_LOOKBACK_DAYS must be greater than 0")
        return value

    @field_validator("FAOSTAT_DEFAULT_LOOKBACK_YEARS")
    @classmethod
    def validate_faostat_lookback_years(cls, value: int) -> int:
        """Ensure the default FAOSTAT year window is positive."""

        if value <= 0:
            raise ValueError("FAOSTAT_DEFAULT_LOOKBACK_YEARS must be greater than 0")
        return value

    @field_validator("FAOSTAT_BATCH_SIZE")
    @classmethod
    def validate_faostat_batch_size(cls, value: int) -> int:
        """Ensure the FAOSTAT raw payload batch size is positive."""

        if value <= 0:
            raise ValueError("FAOSTAT_BATCH_SIZE must be greater than 0")
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
