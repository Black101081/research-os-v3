from __future__ import annotations

from typing import Any, Dict, List
from fastapi import APIRouter

router = APIRouter(prefix="/api")

@router.get('/presets')
def get_presets() -> List[Dict[str, Any]]:
    return [
        {
            'name': 'Trend Following (MACD Trend Continuation)',
            'description': 'Captures major directional moves by tracking MACD crossovers and EMA spread alignment under stable regimes.',
            'category': 'Trend',
            'spec': {
                'symbol': 'BTC',
                'strategy_family': 'macd_trend_continuation',
                'parameters': {
                    'fast_period': 12,
                    'slow_period': 26,
                    'signal_period': 9,
                    'min_confidence': 0.65
                },
                'risk_limit': {
                    'max_leverage': 2.0,
                    'max_exposure_usd': 5000.0,
                    'stop_loss_pct': 0.015,
                    'take_profit_pct': 0.03
                }
            }
        },
        {
            'name': 'Mean Reversion (Bollinger Bands Extreme)',
            'description': 'Trades price deviations beyond 2 standard deviations, expecting reversion back to the Bollinger baseline.',
            'category': 'Mean Reversion',
            'spec': {
                'symbol': 'BTC',
                'strategy_family': 'bollinger_bands_reversion',
                'parameters': {
                    'period': 20,
                    'std_dev': 2.0,
                    'zscore_limit': 2.2,
                    'min_volatility': 0.005
                },
                'risk_limit': {
                    'max_leverage': 1.5,
                    'max_exposure_usd': 3000.0,
                    'stop_loss_pct': 0.01,
                    'take_profit_pct': 0.02
                }
            }
        },
        {
            'name': 'Volatility Breakout (Bollinger Squeeze)',
            'description': 'Enters directional breakouts when Bollinger Band Width squeezes to historical lows, indicating imminent volatility expansion.',
            'category': 'Breakout',
            'spec': {
                'symbol': 'BTC',
                'strategy_family': 'bollinger_squeeze_breakout',
                'parameters': {
                    'period': 20,
                    'width_threshold': 0.012,
                    'volume_ratio_trigger': 1.5
                },
                'risk_limit': {
                    'max_leverage': 2.5,
                    'max_exposure_usd': 6000.0,
                    'stop_loss_pct': 0.012,
                    'take_profit_pct': 0.04
                }
            }
        },
        {
            'name': 'Funding Arbitrage (Cross-Exchange Carry)',
            'description': 'Captures low-risk yield by exploiting funding rate differentials on Hyperliquid vs. secondary venues with auto-hedging.',
            'category': 'Arbitrage',
            'spec': {
                'symbol': 'BTC',
                'strategy_family': 'funding_arbitrage_carry',
                'parameters': {
                    'min_rate_differential_bps': 8.0,
                    'rebalance_hours': 8,
                    'hedge_ratio': 1.0
                },
                'risk_limit': {
                    'max_leverage': 3.0,
                    'max_exposure_usd': 10000.0,
                    'stop_loss_pct': 0.005,
                    'take_profit_pct': 0.015
                }
            }
        }
    ]
