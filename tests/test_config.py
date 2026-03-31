import os
import tempfile
from pathlib import Path

import yaml

from src.config import load_config, AppConfig


def _write_config(tmp_dir: Path, overrides: dict | None = None) -> Path:
    base = {
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
            "min_signals_required": 2,
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
            "scan_interval_minutes": 5,
            "market_hours_only": True,
        },
        "notifications": {
            "sms_enabled": True,
            "email_enabled": True,
            "sms_events": ["fill", "stop_loss"],
            "email_events": ["daily_summary"],
        },
    }
    if overrides:
        base.update(overrides)
    config_path = tmp_dir / "config.yaml"
    config_path.write_text(yaml.dump(base))
    return config_path


def test_load_config_returns_app_config():
    with tempfile.TemporaryDirectory() as tmp:
        path = _write_config(Path(tmp))
        cfg = load_config(str(path))
        assert isinstance(cfg, AppConfig)


def test_load_config_symbols():
    with tempfile.TemporaryDirectory() as tmp:
        path = _write_config(Path(tmp))
        cfg = load_config(str(path))
        assert cfg.symbols == ["SPY", "QQQ"]


def test_load_config_swing_values():
    with tempfile.TemporaryDirectory() as tmp:
        path = _write_config(Path(tmp))
        cfg = load_config(str(path))
        assert cfg.swing.target_dte == [7, 10]
        assert cfg.swing.min_premium == 0.50
        assert cfg.swing.spread_width == {"SPY": 5, "QQQ": 3}


def test_load_config_exhaustion_values():
    with tempfile.TemporaryDirectory() as tmp:
        path = _write_config(Path(tmp))
        cfg = load_config(str(path))
        assert cfg.exhaustion.enabled is True
        assert cfg.exhaustion.profit_target_pct == 20
        assert cfg.exhaustion.min_signals_required == 2


def test_load_config_risk_values():
    with tempfile.TemporaryDirectory() as tmp:
        path = _write_config(Path(tmp))
        cfg = load_config(str(path))
        assert cfg.risk.daily_income_target == 500
        assert cfg.risk.max_concurrent_spreads == 10


def test_load_config_env_vars(monkeypatch):
    monkeypatch.setenv("ALPACA_API_KEY", "test_key")
    monkeypatch.setenv("ALPACA_API_SECRET", "test_secret")
    monkeypatch.setenv("ALPACA_PAPER", "true")
    monkeypatch.setenv("MONGODB_URI", "mongodb://localhost:27017")
    monkeypatch.setenv("MONGODB_DB_NAME", "test_db")
    with tempfile.TemporaryDirectory() as tmp:
        path = _write_config(Path(tmp))
        cfg = load_config(str(path))
        assert cfg.alpaca_api_key == "test_key"
        assert cfg.alpaca_api_secret == "test_secret"
        assert cfg.alpaca_paper is True
        assert cfg.mongodb_uri == "mongodb://localhost:27017"
