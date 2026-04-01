from pathlib import Path
from unittest.mock import MagicMock

import yaml

from src.config import _deep_merge, load_config


def _make_full_config() -> dict:
    """Return a complete config dict with all required fields for every dataclass."""
    return {
        "symbols": ["SPY", "QQQ"],
        "swing": {
            "target_dte": [7, 10],
            "short_strike_delta": [0.15, 0.30],
            "spread_width": {"SPY": 5, "QQQ": 3},
            "min_premium": 0.50,
            "iv_rank_threshold": 30,
            "profit_target_pct": 50,
        },
        "exhaustion": {
            "enabled": True,
            "target_dte": [1, 2],
            "spread_width": {"SPY": 5, "QQQ": 3},
            "min_premium": 0.25,
            "profit_target_pct": 20,
            "stop_loss_multiplier": 1.5,
            "time_window_start": "11:00",
            "rsi_overbought": 70,
            "rsi_oversold": 30,
            "intraday_timeframe": "5min",
            "min_signals_required": 3,
            "min_move_from_open_pct": 0.8,
            "strong_move_pct": 1.5,
            "close_by_eod": True,
        },
        "risk": {
            "max_concurrent_spreads": 10,
            "max_risk_per_trade_pct": 5,
            "max_buying_power_usage_pct": 60,
            "stop_loss_multiplier": 2.0,
            "roll_delta_threshold": 0.50,
            "dte_exit": 1,
            "daily_loss_limit": 1000,
            "daily_income_target": 500,
            "max_same_direction_per_symbol": 3,
            "max_portfolio_delta_per_symbol": 0.30,
        },
        "execution": {
            "price_adjustment_interval": 30,
            "price_adjustment_step": 0.01,
            "fill_timeout": 300,
        },
        "schedule": {
            "scan_interval_minutes": 2,
            "market_hours_only": True,
        },
        "notifications": {
            "sms_enabled": True,
            "email_enabled": True,
            "sms_events": ["fill", "stop_loss", "roll", "circuit_breaker", "error"],
            "email_events": ["daily_summary", "weekly_recap"],
        },
    }


# ---- _deep_merge unit tests ------------------------------------------------


def test_deep_merge_overwrites_scalar():
    base = {"a": 1, "b": 2}
    override = {"b": 99}
    result = _deep_merge(base, override)
    assert result == {"a": 1, "b": 99}


def test_deep_merge_recurses_dicts():
    base = {"outer": {"x": 1, "y": 2}}
    override = {"outer": {"y": 42}}
    result = _deep_merge(base, override)
    assert result == {"outer": {"x": 1, "y": 42}}


def test_deep_merge_does_not_mutate_base():
    base = {"outer": {"x": 1, "y": 2}, "keep": "yes"}
    override = {"outer": {"y": 99}}
    _deep_merge(base, override)
    assert base == {"outer": {"x": 1, "y": 2}, "keep": "yes"}


# ---- load_config with db override ------------------------------------------


def test_load_config_uses_db_override(tmp_path: Path):
    # Write a complete YAML config to a temp file
    config_data = _make_full_config()
    config_path = tmp_path / "config.yaml"
    config_path.write_text(yaml.dump(config_data))

    # Mock db that returns a partial override for risk section
    mock_db = MagicMock()
    mock_db.get_settings.return_value = {
        "risk": {"daily_loss_limit": 500},
        "updated_at": "2026-01-01T00:00:00",
    }

    cfg = load_config(str(config_path), db=mock_db)

    # The overridden value should be applied
    assert cfg.risk.daily_loss_limit == 500
    # Values not in the override should remain from the YAML defaults
    assert cfg.risk.max_concurrent_spreads == 10

    # Verify db.get_settings was called and seed_settings was NOT called
    mock_db.get_settings.assert_called_once()
    mock_db.seed_settings.assert_not_called()


def test_load_config_seeds_db_when_no_settings(tmp_path: Path):
    """When db.get_settings() returns None, load_config should seed the DB."""
    config_data = _make_full_config()
    config_path = tmp_path / "config.yaml"
    config_path.write_text(yaml.dump(config_data))

    mock_db = MagicMock()
    mock_db.get_settings.return_value = None

    cfg = load_config(str(config_path), db=mock_db)

    # Config should still load normally from YAML
    assert cfg.risk.daily_loss_limit == 1000
    # seed_settings should have been called with the raw YAML data
    mock_db.seed_settings.assert_called_once()
