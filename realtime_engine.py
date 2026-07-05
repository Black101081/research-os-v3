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
from factor_math import compute_factors_np, compute_indicators_np


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


def _infer_entry_side(signal_name: str, last_price: float, indicators: dict) -> str:
    if signal_name == 'zscore_recenter':
        z = indicators.get('ZScore_Close', 0.0)
        return 'short' if z >= 1.5 else 'long'
    if signal_name == 'macd_trend_continuation':
        macd = indicators.get('MACD', 0.0)
        sig = indicators.get('MACD_signal', 0.0)
        return 'long' if macd > sig else 'short'
    # bollinger_squeeze_breakout: direction from price vs midband
    mid = indicators.get('BBANDS_mid', 0.0)
    return 'long' if last_price > mid else 'short'


class ResearchEngine:
    def __init__(self, symbols: List[str], max_bars: int = 500, thresholds: Optional[Dict[str, Any]] = None):
        self.thresholds = thresholds or {}
        self.states: Dict[str, SymbolState] = {s: SymbolState(symbol=s, bars=deque(maxlen=max_bars)) for s in symbols}

    def process_message(self, msg: Dict[str, Any]):
        channel = msg.get('channel')
        data = msg.get('data', {})
        if channel == 'trades':
            self._handle_trades(data)
        elif channel == 'candle':
            self._handle_candle(data)
        elif channel == 'bbo':
            self._handle_bbo(data)
        elif channel == 'allMids':
            self._handle_all_mids(data)

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
        
        base_factors = compute_factors_np(closes, volumes)
        state.factors.update(base_factors)
        
        base_indicators = compute_indicators_np(closes, state.factors)
        state.indicators.update(base_indicators)
        
        self._compute_regime(state)
        self._compute_signals(state)
        state.prev_bollinger_width = state.indicators.get('BollingerWidth')
        self._compute_strategies(state)
        self._compute_risk(state)
        self._compute_validation(state, full=(mode == 'bar_close' or not state.validation_packet))

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
        state.signals = evaluate_supported_signals(state.symbol, state.factors, state.indicators, state.regime_state, last_close, state.prev_bollinger_width)

    def _compute_strategies(self, state: SymbolState):
        strategies = {}
        close_count = len(state.closes(include_current=True))
        for signal_name, signal_state in state.signals.items():
            active = bool(signal_state.get('active'))
            logic_ready = bool(active and close_count >= 35 and state.regime_state.get('tradable', False))
            last_price = state.latest_price() or 0.0
            entry_side = _infer_entry_side(signal_name, last_price, state.indicators)
            strategies[signal_name] = {
                'status': 'candidate' if active else 'standby',
                'signal_name': signal_name,
                'symbol': state.symbol,
                'entry_side': entry_side,
                'thesis_state': 'aligned' if active else 'not_triggered',
                'logic_ready': logic_ready,
                'execution_ready': False,
                'last_price': state.latest_price(),
                'updated_at': state.updated_at,
                'regime': state.regime_state.get('regime'),
                'reactive_source': 'live_intrabar' if state.current_bar is not None else 'bar_close',
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
