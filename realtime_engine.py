from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from statistics import mean, pstdev
from typing import Deque, Dict, List, Optional, Any

from regime_engine import classify_regime
from signal_orchestrator import evaluate_supported_signals
from validation_bridge import build_validation_packet
from risk_engine import build_risk_packet_v1
from reactivity_diff import build_reactivity_diff_v1
from factor_math import (
    compute_factors_np,
    compute_indicators_np,
    rsi_np,
    atr_np,
    compute_divergence,
    flow_imbalance_np,
    macd_history_np,
    rsi_history_np
)
from multi_tf_state import MultiTFEngine
from asset_tf_fitness import is_fitness_ok, fitness_summary, get_fitness
from quality_gate_models import QualityGateConfig, QualifiedSignal, GateRejection
from quality_gate import QualityGate
from tf_indicator_engine import compute_all_tf_indicators


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def ema(values: List[float], period: int) -> Optional[float]:
    if not values:
        return None
    alpha = 2 / (period + 1)
    result = values[0]
    for value in values[1:]:
        result = value * alpha + result * (1 - alpha)
    return result


def safe_std(values: List[float]) -> float:
    if len(values) < 2:
        return 0.0
    return pstdev(values)


def ts_to_datetime(value: Any) -> datetime:
    if isinstance(value, datetime):
        return value.astimezone(timezone.utc) if value.tzinfo else value.replace(tzinfo=timezone.utc)
    if isinstance(value, str):
        try:
            dt = datetime.fromisoformat(value.replace('Z', '+00:00'))
            return dt.astimezone(timezone.utc) if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
        except Exception:
            return datetime.now(timezone.utc)
    if isinstance(value, (int, float)):
        if value > 1e12:
            return datetime.fromtimestamp(value / 1000, tz=timezone.utc)
        return datetime.fromtimestamp(value, tz=timezone.utc)
    return datetime.now(timezone.utc)


def ts_to_iso(value: Any) -> str:
    return ts_to_datetime(value).isoformat()


def minute_bucket_iso(value: Any) -> str:
    dt = ts_to_datetime(value)
    return dt.replace(second=0, microsecond=0).isoformat()


@dataclass
class Bar:
    ts: str
    open: float
    high: float
    low: float
    close: float
    volume: float


@dataclass
class SymbolState:
    symbol: str
    bars: Deque[Bar] = field(default_factory=lambda: deque(maxlen=500))
    current_bar: Optional[Bar] = None
    current_bar_source: Optional[str] = None
    last_trade: Optional[float] = None
    last_trade_ts: Optional[str] = None
    bid: Optional[float] = None
    ask: Optional[float] = None
    mid: Optional[float] = None
    trade_prices: Deque[float] = field(default_factory=lambda: deque(maxlen=200))
    trade_sizes: Deque[float] = field(default_factory=lambda: deque(maxlen=200))
    trade_sides: Deque[str] = field(default_factory=lambda: deque(maxlen=200))
    trade_times: Deque[float] = field(default_factory=lambda: deque(maxlen=200))
    factors: Dict[str, float] = field(default_factory=dict)
    indicators: Dict[str, float] = field(default_factory=dict)
    regime_state: Dict[str, Any] = field(default_factory=dict)
    signals: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    strategies: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    risk_packets: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    validation_packet: Dict[str, Any] = field(default_factory=dict)
    reactivity_events: Deque[Dict[str, Any]] = field(default_factory=lambda: deque(maxlen=100))
    updated_at: Optional[str] = None
    last_bar_ts: Optional[str] = None
    prev_bollinger_width: Optional[float] = None

    def __post_init__(self):
        self._cache = {}

    def append_or_replace_bar(self, bar: Bar):
        if self.bars and self.bars[-1].ts == bar.ts:
            self.bars[-1] = bar
        else:
            self.bars.append(bar)
        if self.current_bar and self.current_bar.ts == bar.ts:
            self.current_bar = None
            self.current_bar_source = None
        self.last_bar_ts = bar.ts
        self.updated_at = now_iso()

    def update_trade(self, px: float, size: float = 0.0, side: Optional[str] = None, trade_ts: Any = None):
        self.last_trade = px
        self.last_trade_ts = ts_to_iso(trade_ts)
        self.trade_prices.append(px)
        self.trade_sizes.append(float(size or 0.0))
        self.trade_sides.append(str(side or ''))
        self.trade_times.append(ts_to_datetime(trade_ts).timestamp() * 1000)
        self.updated_at = now_iso()

    def update_bbo(self, bid: Optional[float], ask: Optional[float]):
        self.bid = bid
        self.ask = ask
        if bid is not None and ask is not None:
            self.mid = (bid + ask) / 2
        self.updated_at = now_iso()

    def closes(self, include_current: bool = False) -> List[float]:
        closes = [b.close for b in self.bars]
        if include_current and self.current_bar is not None:
            if self.bars and self.bars[-1].ts == self.current_bar.ts:
                closes[-1] = self.current_bar.close
            else:
                closes.append(self.current_bar.close)
        return closes

    def volumes(self, include_current: bool = False) -> List[float]:
        volumes = [b.volume for b in self.bars]
        if include_current and self.current_bar is not None:
            if self.bars and self.bars[-1].ts == self.current_bar.ts:
                volumes[-1] = self.current_bar.volume
            else:
                volumes.append(self.current_bar.volume)
        return volumes

    def latest_close(self) -> Optional[float]:
        if self.current_bar is not None:
            return self.current_bar.close
        if self.bars:
            return self.bars[-1].close
        return self.last_trade

    def latest_price(self) -> Optional[float]:
        return self.last_trade or self.latest_close() or self.mid


def _infer_entry_side(signal_name: str, last_price: float, indicators: dict, template_family: str | None = None) -> str:
    family = template_family or signal_name
    if 'zscore' in family or 'mean_reversion' in family:
        z = indicators.get('ZScore_Close', 0.0)
        return 'short' if z >= 1.5 else 'long'
    if 'macd' in family or 'continuation' in family:
        macd = indicators.get('MACD', 0.0)
        sig = indicators.get('MACD_signal', 0.0)
        return 'long' if macd > sig else 'short'
    mid = indicators.get('BBANDS_mid', 0.0)
    return 'long' if last_price > mid else 'short'


class ResearchEngine:
    def __init__(self, symbols: List[str], max_bars: int = 500, thresholds: Optional[Dict[str, Any]] = None):
        self.thresholds = thresholds or {}
        self.states: Dict[str, SymbolState] = {s: SymbolState(symbol=s, bars=deque(maxlen=max_bars)) for s in symbols}
        self._paper_broker = None  # Set externally after init
        # Build asset_config from thresholds or derive from symbols list
        asset_config = (thresholds or {}).get("asset_config", {})
        if not asset_config:
            # Legacy fallback — wrap old symbols list
            for sym in symbols:
                asset_config[sym] = {
                    "candle_intervals": ["1m"],
                    "role": "anchor" if sym == "BTC" else "major",
                }
        max_bars_per_tf = (thresholds or {}).get("runtime", {}).get(
            "max_bars_per_tf", {"1m": 500, "5m": 300, "15m": 200, "1h": 100}
        )
        self._mtf = MultiTFEngine(asset_config, max_bars_per_tf)
        self._asset_config = asset_config
        # Initialize Orchestrator and Quality Gate
        from signal_orchestrator import SignalOrchestrator
        self._orchestrator = SignalOrchestrator(mtf_engine=self._mtf, paper_broker=None)
        self._quality_gate = self._orchestrator._quality_gate
        # Crypto-native history buffers (per symbol)
        from collections import deque as _deque
        self._funding_history: dict = {
            sym: _deque(maxlen=48)   # 48 data points ≈ 16 days (funding every 8h)
            for sym in self._mtf.symbols()
        }
        self._oi_history: dict = {
            sym: _deque(maxlen=200)   # 200 samples of OI snapshots
            for sym in self._mtf.symbols()
        }
        self._last_entry_time: Dict[str, float] = {}   # symbol → unix timestamp
        self._last_sl_time: Dict[str, float] = {}       # symbol → unix timestamp
        self.entry_cooldown_seconds: int = 300          # 5 minutes between entries
        self.sl_cooldown_seconds: int = 600             # 10 minutes after a stop loss

    def process_message(self, msg: Dict[str, Any]):
        channel = msg.get('channel')
        data = msg.get('data', {})
        if channel == 'trades':
            self._handle_trades(data)
        elif channel == 'candle':
            # Also forward to MultiTFEngine for all intervals
            self._mtf.handle_candle(data)
            self._handle_candle(data)   # existing handler (handles 1m SymbolState)
            return                       # avoid double-call, wrap existing call
        elif channel == 'bbo':
            self._handle_bbo(data)
        elif channel == 'allMids':
            self._handle_all_mids(data)
        elif channel == 'l2Book':
            self._mtf.handle_l2book(data)
        elif channel == 'activeAssetCtx':
            self._mtf.handle_active_asset_ctx(data)
            symbol = data.get("coin")
            ctx = data.get("ctx", {})
            if symbol and ctx:
                fr = ctx.get("funding")
                oi = ctx.get("openInterest")
                if fr is not None:
                    try:
                        if symbol not in self._funding_history:
                            from collections import deque as _deque
                            self._funding_history[symbol] = _deque(maxlen=48)
                        self._funding_history[symbol].append(float(fr))
                    except (TypeError, ValueError):
                        pass
                if oi is not None:
                    try:
                        if symbol not in self._oi_history:
                            from collections import deque as _deque
                            self._oi_history[symbol] = _deque(maxlen=200)
                        self._oi_history[symbol].append(float(oi))
                    except (TypeError, ValueError):
                        pass

    def _get_state(self, symbol: str) -> Optional[SymbolState]:
        return self.states.get(symbol)

    def _state_view(self, state: SymbolState) -> Dict[str, Any]:
        return {
            'current_bar': asdict(state.current_bar) if state.current_bar else None,
            'factors': dict(state.factors),
            'indicators': dict(state.indicators),
            'regime_state': dict(state.regime_state),
            'signals': {k: dict(v) for k, v in state.signals.items()},
            'strategies': {k: dict(v) for k, v in state.strategies.items()},
            'risk_packets': {k: dict(v) for k, v in state.risk_packets.items()},
            'validation_packet': dict(state.validation_packet),
        }

    def _record_reactivity(self, state: SymbolState, message_type: str, before: Dict[str, Any]):
        after = self._state_view(state)
        reactive_source = 'live_intrabar' if state.current_bar is not None else 'bar_close'
        diff = build_reactivity_diff_v1(state.symbol, message_type, before, after, reactive_source=reactive_source)
        state.reactivity_events.append(diff)

    def _handle_trades(self, data: Any):
        trades = data if isinstance(data, list) else data.get('trades', []) if isinstance(data, dict) else []
        before_by_symbol: Dict[str, Dict[str, Any]] = {}
        touched = []
        for t in trades:
            symbol = t.get('coin') or t.get('symbol') or t.get('s')
            px = t.get('px') or t.get('price') or t.get('p')
            sz = t.get('sz') or t.get('size') or t.get('q') or 0.0
            side = t.get('side') or t.get('S')
            ts = t.get('time') or t.get('t')
            state = self._get_state(symbol)
            if state and px is not None:
                if symbol not in before_by_symbol:
                    before_by_symbol[symbol] = self._state_view(state)
                    touched.append(symbol)
                self._update_forming_bar_from_trade(state, float(px), float(sz or 0.0), ts)
                state.update_trade(float(px), float(sz or 0.0), side, ts)
        for symbol in touched:
            self._refresh_state(symbol, mode='tick')
            self._record_reactivity(self.states[symbol], 'trades', before_by_symbol[symbol])

    def _handle_candle(self, data: Dict[str, Any]):
        candle = data.get('candle') if isinstance(data, dict) and 'candle' in data else data
        if not isinstance(candle, dict):
            return
        symbol = candle.get('coin') or candle.get('symbol') or candle.get('s')
        state = self._get_state(symbol)
        if not state:
            return
        before = self._state_view(state)
        bar = Bar(
            ts=ts_to_iso(candle.get('t') or candle.get('time')),
            open=float(candle.get('o', candle.get('open', 0.0))),
            high=float(candle.get('h', candle.get('high', 0.0))),
            low=float(candle.get('l', candle.get('low', 0.0))),
            close=float(candle.get('c', candle.get('close', 0.0))),
            volume=float(candle.get('v', candle.get('volume', 0.0))),
        )
        state.append_or_replace_bar(bar)
        self._refresh_state(symbol, mode='bar_close')
        self._record_reactivity(state, 'candle', before)

        # After bar has been appended to both, compute all tf indicators
        sym_state = self._mtf.get(symbol) if symbol else None
        if sym_state:
            # Extract best bid/ask from BBO if available
            bbo_state = self.states.get(symbol)
            best_bid = getattr(bbo_state, "best_bid", 0.0) if bbo_state else 0.0
            best_ask = getattr(bbo_state, "best_ask", 0.0) if bbo_state else 0.0

            compute_all_tf_indicators(
                sym_state=sym_state,
                funding_history=list(self._funding_history.get(symbol, [])),
                oi_history=list(self._oi_history.get(symbol, [])),
                best_bid=best_bid,
                best_ask=best_ask,
            )

    def _handle_bbo(self, data: Dict[str, Any]):
        symbol = data.get('coin') or data.get('symbol') or data.get('s')
        state = self._get_state(symbol)
        if not state:
            return
        before = self._state_view(state)
        bid = data.get('bid') or data.get('b')
        ask = data.get('ask') or data.get('a')
        if isinstance(bid, list):
            bid = bid[0].get('px') if bid else None
        if isinstance(ask, list):
            ask = ask[0].get('px') if ask else None
        state.update_bbo(float(bid) if bid is not None else None, float(ask) if ask is not None else None)
        self._refresh_state(symbol, mode='tick')
        self._record_reactivity(state, 'bbo', before)

    def _handle_all_mids(self, data: Dict[str, Any]):
        if not isinstance(data, dict):
            return
        mids = data.get('mids', data)
        if not isinstance(mids, dict):
            return
        for symbol, mid in mids.items():
            state = self._get_state(symbol)
            if state and mid is not None:
                before = self._state_view(state)
                state.mid = float(mid)
                state.updated_at = now_iso()
                self._refresh_state(symbol, mode='tick')
                self._record_reactivity(state, 'allMids', before)

    def _update_forming_bar_from_trade(self, state: SymbolState, px: float, size: float, trade_ts: Any):
        bucket_ts = minute_bucket_iso(trade_ts)
        if state.current_bar is None or state.current_bar.ts != bucket_ts:
            state.current_bar = Bar(ts=bucket_ts, open=px, high=px, low=px, close=px, volume=size)
        else:
            state.current_bar.high = max(state.current_bar.high, px)
            state.current_bar.low = min(state.current_bar.low, px)
            state.current_bar.close = px
            state.current_bar.volume += size
        state.current_bar_source = 'trade'
        state.updated_at = now_iso()

    def _refresh_state(self, symbol: str, mode: str = 'tick'):
        state = self.states[symbol]
        include_current = mode in {'tick', 'intrabar'}
        self._compute_micro_factors(state)
        
        closes = state.closes(include_current=include_current)
        volumes = state.volumes(include_current=include_current)
        
        highs = [b.high for b in list(state.bars)]
        lows = [b.low for b in list(state.bars)]
        if include_current and state.current_bar is not None:
            if state.bars and state.bars[-1].ts == state.current_bar.ts:
                highs[-1] = state.current_bar.high
                lows[-1] = state.current_bar.low
            else:
                highs.append(state.current_bar.high)
                lows.append(state.current_bar.low)
        
        import numpy as np
        
        base_factors = compute_factors_np(closes, volumes[:-1] if include_current else volumes)
        state.factors.update(base_factors)
        
        state.prev_bollinger_width = state.indicators.get('BollingerWidth')
        base_indicators = compute_indicators_np(closes, state.factors)
        state.indicators.update(base_indicators)
        
        sizes = list(state.trade_sizes)
        sides = list(state.trade_sides)
        state.factors['trade_flow_imbalance_50'] = flow_imbalance_np(sizes, sides, 50)
        
        if sizes:
            mean_sz = mean(sizes[-20:]) if len(sizes) >= 20 else mean(sizes)
            large_trades_sum = sum(sz for sz in sizes[-20:] if sz > 1.5 * mean_sz)
            total_trades_sum = sum(sizes[-20:])
            state.factors['large_trade_ratio'] = large_trades_sum / total_trades_sum if total_trades_sum else 0.0
        else:
            state.factors['large_trade_ratio'] = 0.0
            
        btc_state = self.states.get('BTC')
        if btc_state:
            state.factors['btc_ret_1'] = btc_state.factors.get('ret_1', 0.0)
            if state.symbol != 'BTC':
                btc_closes = [b.close for b in list(btc_state.bars)[-20:]]
                asset_closes = [b.close for b in list(state.bars)[-20:]]
                if len(btc_closes) == len(asset_closes) and len(btc_closes) >= 5:
                    btc_rets = np.diff(btc_closes) / btc_closes[:-1]
                    asset_rets = np.diff(asset_closes) / asset_closes[:-1]
                    if btc_rets.std() > 0 and asset_rets.std() > 0:
                        corr = np.corrcoef(btc_rets, asset_rets)[0, 1]
                        state.factors['market_correlation_20'] = float(corr) if not np.isnan(corr) else 0.0
                    else:
                        state.factors['market_correlation_20'] = 0.0
                else:
                    state.factors['market_correlation_20'] = 0.0
            else:
                state.factors['market_correlation_20'] = 1.0
        else:
            state.factors['btc_ret_1'] = 0.0
            state.factors['market_correlation_20'] = 0.0
            
        upper = state.indicators.get('BBANDS_upper', 0.0)
        lower = state.indicators.get('BBANDS_lower', 0.0)
        close = closes[-1] if closes else 0.0
        state.indicators['bb_pct_b'] = (close - lower) / (upper - lower) if (upper - lower) else 0.5
        state.indicators['rsi_14'] = rsi_np(closes, 14)
        
        mid = state.indicators.get('BBANDS_mid', 0.0)
        state.indicators['price_vs_sma20'] = (close / mid) - 1.0 if mid else 0.0
        
        if len(closes) >= 20:
            arr_closes = np.asarray(closes, dtype=np.float64)
            std5 = arr_closes[-5:].std()
            std20 = arr_closes[-20:].std()
            state.indicators['volatility_ratio_5_20'] = std5 / std20 if std20 else 1.0
        else:
            state.indicators['volatility_ratio_5_20'] = 1.0
            
        atr_val = atr_np(highs, lows, closes, 14)
        state.indicators['atr_pct_14'] = atr_val / close if close else 0.0
        
        macd_history = list(macd_history_np(closes)) if len(closes) >= 35 else [state.indicators.get('MACD', 0.0)] * len(closes)
        rsi_history = list(rsi_history_np(closes)) if len(closes) > 14 else [state.indicators.get('rsi_14', 50.0)] * len(closes)

        state.indicators['momentum_divergence'] = compute_divergence(
            closes, macd_history, fractal_window=2, max_lookback=30
        )
        state.indicators['rsi_divergence'] = compute_divergence(
            closes, rsi_history, fractal_window=2, max_lookback=30
        )
        
        state.indicators['trade_flow_imbalance_20'] = state.factors.get('trade_flow_imbalance_20', 0.0)
        state.indicators['trade_flow_imbalance_50'] = state.factors.get('trade_flow_imbalance_50', 0.0)
        state.indicators['large_trade_ratio'] = state.factors.get('large_trade_ratio', 0.0)
        state.indicators['btc_ret_1'] = state.factors.get('btc_ret_1', 0.0)
        state.indicators['market_correlation_20'] = state.factors.get('market_correlation_20', 0.0)
        
        self._compute_regime(state)
        self._compute_signals(state)
        self._compute_strategies(state)
        self._compute_risk(state)
        self._dispatch_paper_trades(state)
        self._compute_validation(state, full=(mode == 'bar_close' or not state.validation_packet))

    def _dispatch_paper_trades(self, state: SymbolState):
        """Update PnL tick + SL/TP checks, then dispatch new paper trades."""
        if not hasattr(self, '_paper_broker') or self._paper_broker is None:
            return

        last_price = state.latest_price()
        if not last_price:
            return

        # ── FIX 1: Always call process_tick so PnL updates in real-time ──
        self._paper_broker.process_tick(state.symbol, last_price, state.updated_at)

        # Track closed trades to notify Quality Gate
        recent_trades = self._paper_broker.trade_history[-3:] if self._paper_broker.trade_history else []
        if not hasattr(self, '_processed_trades'):
            self._processed_trades = set()
        for t in recent_trades:
            trade_key = f"{t.get('symbol')}_{t.get('exit_time')}_{t.get('pnl')}"
            if trade_key not in self._processed_trades:
                self._processed_trades.add(trade_key)
                sig_id = t.get("signal_id")
                if sig_id:
                    self.on_trade_closed(sig_id, t.get("pnl", 0.0))

            if (t.get('symbol') == state.symbol
                    and t.get('reason') == 'Stop Loss'):
                import time as _time2
                last_recorded = self._last_sl_time.get(state.symbol, 0.0)
                try:
                    trade_ts = __import__('datetime').datetime.fromisoformat(
                        t['exit_time'].replace('Z', '+00:00')
                    ).timestamp()
                except Exception:
                    trade_ts = _time2.time()
                if trade_ts > last_recorded:
                    self._last_sl_time[state.symbol] = trade_ts

        for strategy_name, strategy_state in state.strategies.items():
            if not strategy_state.get('execution_ready'):
                continue

            symbol = state.symbol

            # Skip if already in position for this symbol
            if symbol in self._paper_broker.positions:
                continue

            direction = strategy_state.get('entry_side', 'long')

            signal_info = state.signals.get(strategy_name, {})
            if signal_info.get('direction') == 'signal_only':
                continue

            risk_packet = state.risk_packets.get(strategy_name, {})
            quantity = risk_packet.get('target_quantity', 0.0)
            if quantity <= 0:
                equity = self._paper_broker.equity
                position_value = equity * 0.10
                quantity = round(position_value / last_price, 6)

            if quantity <= 0:
                continue

            # Fetch TF-specific indicators
            signal_interval = strategy_state.get('signal_interval', '1m')
            mtf_sym = self._mtf.get(symbol)
            tf_state = mtf_sym.get_tf(signal_interval) if mtf_sym else None
            tf_indicators = tf_state.indicators if tf_state else state.indicators

            # SL từ signal info (Tầng 3), then fallback to risk packet, then ATR fallback
            stop_loss = signal_info.get('stop_loss') if isinstance(signal_info, dict) else getattr(signal_info, 'stop_loss', None)
            if not stop_loss or stop_loss == 0.0:
                stop_loss = risk_packet.get('stop_policy', {}).get('initial_stop_price')

            # ── FIX 2: ATR-based SL fallback khi risk packet không có SL ──
            if stop_loss is None or stop_loss == 0.0:
                atr_val = tf_indicators.get('atr_14_pct')
                if atr_val is not None:
                    atr_pct = atr_val / 100.0
                else:
                    atr_pct = tf_indicators.get('atr_pct_14', 0.02)
                sl_pct = max(0.01, atr_pct * 1.5)
                if direction == 'long':
                    stop_loss = round(last_price * (1 - sl_pct), 6)
                else:
                    stop_loss = round(last_price * (1 + sl_pct), 6)

            # TP từ signal info (Tầng 3), then fallback to risk packet, then fallback Bollinger Width
            take_profit = signal_info.get('take_profit') if isinstance(signal_info, dict) else getattr(signal_info, 'take_profit', None)
            if not take_profit or take_profit == 0.0:
                take_profit = risk_packet.get('take_profit_price')
            if take_profit is None or take_profit == 0.0:
                bb_val = tf_indicators.get('bb_width_20')
                if bb_val is not None:
                    bb_width = bb_val / 100.0
                else:
                    bb_width = tf_indicators.get('BollingerWidth', 0.03)
                tp_pct = max(0.01, bb_width)
                take_profit = last_price * (1 + tp_pct) if direction == 'long' else last_price * (1 - tp_pct)

            # Cooldown gate
            import time as _time
            now_ts = _time.time()

            # Gate 1: general entry cooldown
            last_entry = self._last_entry_time.get(symbol, 0.0)
            if now_ts - last_entry < self.entry_cooldown_seconds:
                continue

            # Gate 2: extra cooldown after stop loss
            last_sl = self._last_sl_time.get(symbol, 0.0)
            if now_ts - last_sl < self.sl_cooldown_seconds:
                continue

            # MTF alignment gate on execution path (defense-in-depth)
            if self._mtf:
                mtf_sym_state = self._mtf.get(symbol)
                if mtf_sym_state:
                    alignment = mtf_sym_state.mtf_alignment(["5m", "15m", "1h"])
                    if direction == "long" and alignment < -0.5:
                        import logging as _log
                        _log.getLogger(__name__).debug(
                            f"[MTF Block] {symbol} LONG skipped — alignment={alignment:.2f} (strongly bearish)"
                        )
                        continue
                    if direction == "short" and alignment > 0.5:
                        import logging as _log
                        _log.getLogger(__name__).debug(
                            f"[MTF Block] {symbol} SHORT skipped — alignment={alignment:.2f} (strongly bullish)"
                        )
                        continue

            from signal_models import SignalResult
            sig_id = signal_info.get("signal_id") or f"{symbol}_{strategy_name}_spec"
            family = signal_info.get("template_family") or signal_info.get("family") or "continuation"
            interval = signal_info.get("interval") or signal_interval
            asset_role = signal_info.get("asset_role") or ("anchor" if symbol == "BTC" else "major")
            fired = signal_info.get("fired", True)
            sig_direction = signal_info.get("direction", direction)
            confidence = signal_info.get("confidence_score") or signal_info.get("confirmation_score", 0.70)
            rr = signal_info.get("risk_reward_ratio") or 2.0

            signal_obj = SignalResult(
                signal_id=sig_id,
                symbol=symbol,
                family=family,
                interval=interval,
                asset_role=asset_role,
                fired=fired,
                direction=sig_direction,
                entry_price=last_price,
                stop_loss=stop_loss,
                take_profit=take_profit,
                confidence_score=confidence,
                risk_reward_ratio=rr,
            )

            success = self._emit_signal(signal_obj)

            if success:
                self._last_entry_time[symbol] = _time.time()
                import logging
                logging.getLogger(__name__).info(
                    f"[PaperTrade] OPENED {direction.upper()} {symbol} "
                    f"qty={quantity} price={last_price} SL={stop_loss} TP={take_profit} via {strategy_name}"
                )

    def _compute_micro_factors(self, state: SymbolState):
        prices = list(state.trade_prices)
        sizes = list(state.trade_sizes)
        sides = list(state.trade_sides)
        if len(prices) >= 2 and prices[-2]:
            state.factors['tick_ret_1'] = (prices[-1] / prices[-2]) - 1
        if len(prices) >= 5 and prices[-5]:
            state.factors['tick_ret_5'] = (prices[-1] / prices[-5]) - 1
        window_prices = prices[-20:]
        if len(window_prices) >= 2:
            center = mean(window_prices)
            dev = safe_std(window_prices)
            state.factors['trade_zscore_20'] = ((window_prices[-1] - center) / dev) if dev else 0.0
            state.factors['micro_volatility_20'] = dev / center if center else 0.0
        window_sizes = sizes[-20:]
        window_sides = sides[-20:]
        if window_sizes:
            signed = 0.0
            for sz, side in zip(window_sizes, window_sides):
                if side == 'B':
                    signed += sz
                elif side == 'A':
                    signed -= sz
            total = sum(window_sizes)
            state.factors['trade_flow_imbalance_20'] = (signed / total) if total else 0.0
            state.factors['trade_size_mean_20'] = mean(window_sizes)
        if state.mid and state.last_trade:
            state.factors['last_trade_minus_mid_bps'] = ((state.last_trade - state.mid) / state.mid) * 10000 if state.mid else 0.0
        if state.bid and state.ask and state.mid:
            state.factors['spread_bps'] = ((state.ask - state.bid) / state.mid) * 10000 if state.mid else 0.0
        latest_close = state.latest_close()
        if latest_close is not None and state.bars:
            prev_close = state.bars[-1].close
            if prev_close:
                state.factors['live_ret_from_last_close'] = (latest_close / prev_close) - 1

    def _compute_regime(self, state: SymbolState):
        state.regime_state = classify_regime(state.factors, state.indicators)

    def _compute_signals(self, state: SymbolState):
        last_close = state.latest_close()
        sym_state = self._mtf.get(state.symbol) if hasattr(self, '_mtf') else None
        state.signals = evaluate_supported_signals(
            state.symbol,
            state.factors,
            state.indicators,
            state.regime_state,
            last_close,
            state.prev_bollinger_width,
            sym_state=sym_state
        )

    def _compute_strategies(self, state: SymbolState):
        strategies = {}
        close_count = len(state.closes(include_current=True))
        for signal_name, signal_state in state.signals.items():
            active = bool(signal_state.get('active'))
            direction = signal_state.get('direction', 'both')
            is_signal_only = (direction == 'signal_only')
            
            status = 'candidate' if (active and not is_signal_only) else 'standby'
            # 1. Asset role + signal family
            asset_role = self._asset_config.get(state.symbol, {}).get("role", "major")
            signal_family = signal_state.get("template_family", "breakout")

            # 2. Primary TF for this signal (prefer m5 if available, else m1)
            mtf_sym = self._mtf.get(state.symbol)
            available_intervals = list(
                self._asset_config.get(state.symbol, {}).get("candle_intervals", ["1m"])
            )
            # Pick best interval for this signal family (prefer higher TF for quality)
            TF_PRIORITY = {"1h": 0, "15m": 1, "5m": 2, "1m": 3}
            sorted_intervals = sorted(
                available_intervals,
                key=lambda x: TF_PRIORITY.get(x, 99)
            )
            signal_interval = sorted_intervals[0] if sorted_intervals else "1m"

            # 3. Bars count on the signal's primary TF
            tf_state = mtf_sym.get_tf(signal_interval) if mtf_sym else None
            tf_bars = len(tf_state.bars) if tf_state else close_count

            # 4. Fitness gate
            fitness_ok = is_fitness_ok(signal_family, asset_role, signal_interval, tf_bars)

            # 5. Min bars for MACD validity — always 35 on any TF
            bars_ok = close_count >= 35

            # 6. HTF bias alignment gate
            # Signals must not trade against strong HTF trend
            mtf_alignment_ok = True
            htf_bias = "n/a"
            htf_to_check = "15m" if "15m" in available_intervals else (
                            "5m"  if "5m"  in available_intervals else None)
            if htf_to_check and mtf_sym:
                htf_bias = mtf_sym.htf_bias(htf_to_check)
                entry_side_guess = signal_state.get("direction", "both")
                if entry_side_guess == "long" and htf_bias == "bearish":
                    mtf_alignment_ok = False
                elif entry_side_guess == "short" and htf_bias == "bullish":
                    mtf_alignment_ok = False

            logic_ready = bool(
                active
                and not is_signal_only
                and bars_ok
                and state.regime_state.get("tradable", False)
                and fitness_ok
                and mtf_alignment_ok
            )
            
            tf_indicators = tf_state.indicators if tf_state else state.indicators
            last_price = state.latest_price() or 0.0
            entry_side = _infer_entry_side(signal_name, last_price, tf_indicators, signal_state.get('template_family'))
            
            invalidated = bool(signal_state.get('invalidated'))
            thesis_state = 'invalidated' if invalidated else ('aligned' if active else 'not_triggered')
            
            strategies[signal_name] = {
                'status': status,
                'signal_name': signal_name,
                'symbol': state.symbol,
                'entry_side': entry_side,
                'thesis_state': thesis_state,
                'logic_ready': logic_ready,
                'execution_ready': False,
                'last_price': state.latest_price(),
                'updated_at': state.updated_at,
                'regime': state.regime_state.get('regime'),
                'reactive_source': 'live_intrabar' if state.current_bar is not None else 'bar_close',
                'fitness_score': get_fitness(signal_family, asset_role, signal_interval)["score"],
                'signal_interval': signal_interval,
                'htf_bias': htf_bias,
                'mtf_alignment_ok': mtf_alignment_ok,
                'fitness_ok': fitness_ok,
            }
        state.strategies = strategies

    def _compute_risk(self, state: SymbolState):
        packets = {}
        state_payload = {
            'symbol': state.symbol,
            'last_trade': state.last_trade,
            'last_price': state.latest_price(),
            'factors': state.factors,
            'indicators': state.indicators,
            'regime_state': state.regime_state,
        }
        risk_config = self.thresholds.get('risk_config_v1', {})
        # Build live portfolio_state from actual broker state
        if self._paper_broker is not None:
            broker_summary = self._paper_broker.get_summary()
            portfolio_state = {
                'balance': broker_summary.get('balance', 10000.0),
                'account_equity': broker_summary.get('equity', 10000.0),
                'active_positions_count': broker_summary.get('active_positions_count', 0),
                'gross_exposure': sum(
                    p.get('quantity', 0) * p.get('current_price', 0)
                    for p in broker_summary.get('positions', [])
                ),
                'net_exposure': 0.0,
                'session_realized_pnl': sum(
                    t.get('pnl', 0) for t in broker_summary.get('trade_history', [])
                ),
                'symbol_exposure': {
                    p['symbol']: p.get('quantity', 0) * p.get('current_price', 0)
                    for p in broker_summary.get('positions', [])
                },
                'trade_history': broker_summary.get('trade_history', []),
            }
        else:
            portfolio_state = self.thresholds.get('portfolio_state', {})
        for strategy_name, strategy_state in state.strategies.items():
            packet = build_risk_packet_v1(state.symbol, state_payload, strategy_name, strategy_state, risk_config=risk_config, portfolio_state=portfolio_state)
            packets[strategy_name] = packet
            strategy_state['risk_status'] = packet['risk_status']
            strategy_state['execution_ready'] = bool(strategy_state.get('logic_ready') and packet.get('allow_entry'))
            strategy_state['risk_rejection_reasons'] = packet.get('rejection_reasons', [])
        state.risk_packets = packets

    def _compute_validation(self, state: SymbolState, full: bool = False):
        state_payload = {
            'symbol': state.symbol,
            'factors': state.factors,
            'indicators': state.indicators,
            'regime_state': state.regime_state,
            'signals': state.signals,
            'strategies': state.strategies,
            'risk_packets': state.risk_packets,
            'current_bar': asdict(state.current_bar) if state.current_bar else None,
        }
        if full or not state.validation_packet:
            try:
                packet = build_validation_packet(state.symbol, state_payload)
                state.validation_packet = packet if isinstance(packet, dict) else {'symbol': state.symbol, 'status': 'validation_non_dict'}
            except TypeError:
                state.validation_packet = {'symbol': state.symbol, 'status': 'validation_signature_mismatch'}
        state.validation_packet['updated_at'] = state.updated_at
        state.validation_packet['live_reactive'] = state.current_bar is not None
        state.validation_packet['risk_statuses'] = {k: v.get('risk_status') for k, v in state.risk_packets.items()}

    def snapshot(self) -> Dict[str, Any]:
        payload = {}
        for symbol, state in self.states.items():
            payload[symbol] = {
                'symbol': state.symbol,
                'updated_at': state.updated_at,
                'last_trade': state.last_trade,
                'last_trade_ts': state.last_trade_ts,
                'bid': state.bid,
                'ask': state.ask,
                'mid': state.mid,
                'last_bar_ts': state.last_bar_ts,
                'current_bar': asdict(state.current_bar) if state.current_bar else None,
                'bars': [asdict(b) for b in list(state.bars)[-50:]],
                'factors': state.factors,
                'indicators': state.indicators,
                'regime_state': state.regime_state,
                'signals': state.signals,
                'strategies': state.strategies,
                'risk_packets': state.risk_packets,
                'validation_packet': state.validation_packet,
                'recent_reactivity': list(state.reactivity_events),
            }
        return payload

    def _emit_signal(self, signal: "SignalResult") -> bool:
        """
        Run signal through QualityGate via SignalOrchestrator before forwarding to paper_broker.
        Only QualifiedSignal objects reach the broker.
        GateRejection objects are logged and discarded.
        """
        if hasattr(self, "_orchestrator") and self._orchestrator:
            self._orchestrator._paper_broker = self._paper_broker
            try:
                self._orchestrator._emit_signal(signal)
                return True   # ← luôn return True nếu không crash
            except Exception as e:
                import logging
                logging.getLogger(__name__).error(
                    f"[EMIT_SIGNAL_ERROR] {signal.symbol}: {e}"
                )
                return False
        return False

    def on_trade_closed(self, signal_id: str, pnl_usd: float = 0.0) -> None:
        """Called when a trade closes."""
        self._quality_gate.on_signal_closed(signal_id)
        current_equity = self._quality_gate._cfg.sizing.account_equity
        self._quality_gate.update_account_equity(current_equity + pnl_usd)
