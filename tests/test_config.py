import pytest
from pydantic import ValidationError

from app.config import Settings


@pytest.fixture(autouse=True)
def clear_provider_env(monkeypatch):
    for key in (
        "YIELD_PROVIDER",
        "EXPLANATION_PROVIDER",
        "RISK_PROVIDER",
        "EXTRACTION_PROVIDER",
        "AI_YIELD_PROVIDER",
        "AI_EXPLANATION_PROVIDER",
        "AI_RISK_PROVIDER",
        "AI_EXTRACTION_PROVIDER",
    ):
        monkeypatch.delenv(key, raising=False)


def test_settings_defaults_preserve_current_provider_behavior():
    config = Settings(_env_file=None)

    assert config.AI_YIELD_PROVIDER == "xgboost"
    assert config.AI_EXPLANATION_PROVIDER == "rule_based"
    assert config.AI_RISK_PROVIDER == "rule_based"
    assert config.AI_EXTRACTION_PROVIDER == "rule_based"


def test_short_provider_env_var_overrides_legacy_env_var(monkeypatch):
    monkeypatch.setenv("YIELD_PROVIDER", "stub")
    monkeypatch.setenv("AI_YIELD_PROVIDER", "rule_based")

    config = Settings(_env_file=None)

    assert config.AI_YIELD_PROVIDER == "stub"


def test_settings_normalize_supported_provider_aliases():
    config = Settings(
        _env_file=None,
        YIELD_PROVIDER="ml",
        EXPLANATION_PROVIDER="deterministic",
        EXTRACTION_PROVIDER="manual",
    )

    assert config.AI_YIELD_PROVIDER == "xgboost"
    assert config.AI_EXPLANATION_PROVIDER == "deterministic"
    assert config.AI_EXTRACTION_PROVIDER == "rule_based"


def test_settings_accept_stub_provider_ids():
    config = Settings(
        _env_file=None,
        YIELD_PROVIDER="stub",
        EXPLANATION_PROVIDER="deterministic",
        RISK_PROVIDER="stub",
        EXTRACTION_PROVIDER="stub",
    )

    assert config.AI_YIELD_PROVIDER == "stub"
    assert config.AI_EXPLANATION_PROVIDER == "deterministic"
    assert config.AI_RISK_PROVIDER == "stub"
    assert config.AI_EXTRACTION_PROVIDER == "stub"


@pytest.mark.parametrize(
    ("setting_name", "setting_value", "expected_message"),
    [
        (
            "YIELD_PROVIDER",
            "rule_based",
            "YIELD_PROVIDER='rule_based' is not supported. Allowed values: stub, ml, xgboost",
        ),
        (
            "EXPLANATION_PROVIDER",
            "llm",
            "EXPLANATION_PROVIDER='llm' is not supported. Allowed values: deterministic, rule_based",
        ),
        ("RISK_PROVIDER", "ml", "RISK_PROVIDER='ml' is not supported. Allowed values: rule_based, stub"),
        (
            "EXTRACTION_PROVIDER",
            "llm",
            "EXTRACTION_PROVIDER='llm' is not supported. Allowed values: manual, rule_based, stub",
        ),
    ],
)
def test_invalid_provider_selection_fails_clearly(setting_name, setting_value, expected_message):
    with pytest.raises(ValidationError, match=expected_message):
        Settings(_env_file=None, **{setting_name: setting_value})


def test_faostat_defaults_are_present():
    config = Settings(_env_file=None)

    assert config.FAOSTAT_SOURCE_NAME == "FAOSTAT Crops and Livestock"
    assert "Production_Crops_Livestock" in config.FAOSTAT_BULK_DOWNLOAD_URL
    assert config.FAOSTAT_DEFAULT_LOOKBACK_YEARS == 1
    assert config.FAOSTAT_BATCH_SIZE == 500


@pytest.mark.parametrize(
    ("setting_name", "setting_value", "expected_message"),
    [
        ("FAOSTAT_DEFAULT_LOOKBACK_YEARS", 0, "FAOSTAT_DEFAULT_LOOKBACK_YEARS must be greater than 0"),
        ("FAOSTAT_BATCH_SIZE", 0, "FAOSTAT_BATCH_SIZE must be greater than 0"),
    ],
)
def test_invalid_faostat_settings_fail_clearly(setting_name, setting_value, expected_message):
    with pytest.raises(ValidationError, match=expected_message):
        Settings(_env_file=None, **{setting_name: setting_value})
