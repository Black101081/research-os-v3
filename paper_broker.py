from __future__ import annotations

import logging
from datetime import datetime, UTC
from typing import Dict, Any, List

import database as db

logger = logging.getLogger(__name__)


class PaperBroker:
    def __init__(self, initial_balance: float = 10000.0):
        db.init_db()

        saved = db.load_broker_state()
        if saved:
            self.balance = saved["balance"]
            self.equity  = saved["equity"]
            logger.info(f"[PaperBroker] Restored from DB: balance={self.balance}")
        else:
            self.balance = initial_balance
            self.equity  = initial_balance

        self.positions: Dict[str, Dict[str, Any]] = db.load_positions()
        self.trade_history: List[Dict[str, Any]] = db.load_trade_history()
        self._last_equity_save = None  # will be set on first tick

        from collections import deque
        self._qualified_signals: deque = deque(maxlen=200)
        self._qs_by_id: dict = {}

        logger.info(
            f"[PaperBroker] Loaded {len(self.positions)} positions, "
            f"{len(self.trade_history)} trades from DB"
        )

    def process_tick(self, symbol: str, current_price: float, current_time: str):
        if symbol in self.positions:
            pos = self.positions[symbol]
            direction   = pos["direction"]
            entry_price = pos["entry_price"]
            quantity    = pos["quantity"]

            if direction == "long":
                unrealized = (current_price - entry_price) * quantity
            else:
                unrealized = (entry_price - current_price) * quantity

            pos["current_price"]   = current_price
            pos["unrealized_pnl"]  = round(unrealized, 4)

            sl_price = pos.get("stop_loss")
            tp_price = pos.get("take_profit")
            trigger_close = False
            close_reason  = ""

            if direction == "long":
                if sl_price and current_price <= sl_price:
                    trigger_close = True
                    close_reason  = "Stop Loss"
                elif tp_price and current_price >= tp_price:
                    trigger_close = True
                    close_reason  = "Take Profit"
            else:
                if sl_price and current_price >= sl_price:
                    trigger_close = True
                    close_reason  = "Stop Loss"
                elif tp_price and current_price <= tp_price:
                    trigger_close = True
                    close_reason  = "Take Profit"

            if trigger_close:
                self.close_position(symbol, current_price, current_time, close_reason)
            else:
                db.save_position(pos)

        unrealized_total = sum(p["unrealized_pnl"] for p in self.positions.values())
        self.equity = round(self.balance + unrealized_total, 4)
        db.save_broker_state(self.balance, self.equity)

        # Throttle: save equity point every 60 seconds max
        now_ts = datetime.now(UTC).isoformat()
        last_eq = getattr(self, '_last_equity_save', None)
        if last_eq is None or (datetime.now(UTC) - datetime.fromisoformat(last_eq)).seconds >= 60:
            db.save_equity_point(
                balance=self.balance,
                equity=self.equity,
                open_positions=len(self.positions),
                unrealized_pnl=unrealized_total
            )
            self._last_equity_save = now_ts

    def execute_order(
        self,
        symbol: str,
        direction: str,
        quantity: float,
        price: float,
        stop_loss: float | None = None,
        take_profit: float | None = None,
        time_str: str | None = None,
        signal_source: str = "unknown",
        extra: dict = None,
    ) -> bool:
        if symbol in self.positions:
            db.save_order_log(symbol, direction, quantity, price,
                              stop_loss, take_profit, signal_source,
                              accepted=False, reject_reason="Position already open")
            return False
        if quantity <= 0 or price <= 0:
            db.save_order_log(symbol, direction, quantity, price,
                              stop_loss, take_profit, signal_source,
                              accepted=False, reject_reason="Invalid quantity or price")
            return False

        cost = quantity * price
        if cost > self.balance * 2.0:
            db.save_order_log(symbol, direction, quantity, price,
                              stop_loss, take_profit, signal_source,
                              accepted=False,
                              reject_reason=f"Insufficient margin: cost={cost:.2f} balance={self.balance:.2f}")
            logger.warning(f"Simulated order failed: Insufficient margin for {symbol}")
            return False

        entry_fee    = cost * 0.0005
        self.balance = round(self.balance - entry_fee, 4)

        pos = {
            "symbol":        symbol,
            "direction":     direction,
            "quantity":      quantity,
            "entry_price":   price,
            "current_price": price,
            "stop_loss":     stop_loss,
            "take_profit":   take_profit,
            "entry_time":    time_str or datetime.now(UTC).isoformat(),
            "unrealized_pnl": 0.0,
            "entry_fee":     round(entry_fee, 4),
            "signal_source": signal_source,
            "signal_id":     None,  # default placeholder
        }
        if extra:
            pos.update(extra)
        self.positions[symbol] = pos
        db.save_position(pos)
        db.save_broker_state(self.balance, self.equity)
        logger.info(
            f"[PaperBroker] OPENED {direction.upper()} {symbol} "
            f"qty={quantity} price={price} SL={stop_loss} via {signal_source}"
        )
        db.save_order_log(symbol, direction, quantity, price,
                          stop_loss, take_profit, signal_source,
                          accepted=True, reject_reason=None)
        return True

    def on_qualified_signal(self, qualified) -> bool:
        """
        Nhận QualifiedSignal từ QualityGate, mở position với
        Kelly-sized quantity và lưu đầy đủ metadata.
        """
        from quality_gate_models import QualifiedSignal
        if not isinstance(qualified, QualifiedSignal):
            return False

        sig = qualified.signal
        entry_price = sig.entry_price
        if entry_price <= 0:
            logger.warning(f"[PaperBroker] on_qualified_signal: invalid entry_price={entry_price}")
            return False

        # Guard: không mở duplicate position
        if sig.symbol in self.positions:
            db.save_order_log(
                sig.symbol, sig.direction,
                0, entry_price,
                sig.stop_loss, sig.take_profit, sig.family,
                accepted=False, reject_reason="Position already open"
            )
            return False

        qty = round(qualified.position_size_usd / entry_price, 6)
        if qty <= 0:
            return False

        cost = qty * entry_price
        if cost > self.balance * 2.0:
            db.save_order_log(
                sig.symbol, sig.direction, qty, entry_price,
                sig.stop_loss, sig.take_profit, sig.family,
                accepted=False,
                reject_reason=f"Insufficient margin: cost={cost:.2f} balance={self.balance:.2f}"
            )
            return False

        entry_fee    = cost * 0.0005
        self.balance = round(self.balance - entry_fee, 4)

        pos = {
            # ── Core position fields ──
            "symbol":           sig.symbol,
            "direction":        sig.direction,
            "quantity":         qty,
            "entry_price":      entry_price,
            "current_price":    entry_price,
            "stop_loss":        sig.stop_loss,
            "take_profit":      sig.take_profit,
            "entry_time":       qualified.qualified_at,
            "unrealized_pnl":   0.0,
            "entry_fee":        round(entry_fee, 4),
            "signal_source":    sig.family,
            "signal_id":        sig.signal_id,
            # ── Quality Gate metadata ──
            "position_size_pct":  qualified.position_size_pct,
            "position_size_usd":  qualified.position_size_usd,
            "risk_amount_usd":    qualified.risk_amount_usd,
            "expected_value_r":   qualified.expected_value_r,
            "market_regime":      qualified.market_regime,
            "btc_structure":      qualified.btc_structure,
            "session_name":       qualified.session_name,
            "confidence_score":   sig.confidence_score,
            "risk_reward_ratio":  sig.risk_reward_ratio,
            "family":             sig.family,
            "interval":           getattr(sig, "interval", "unknown"),
            "cooldown_key":       qualified.cooldown_key,
        }
        self.positions[sig.symbol] = pos
        self._qualified_signals.append(qualified)   # ← lưu để dashboard đọc

        db.save_position(pos)
        db.save_broker_state(self.balance, self.equity)

        logger.info(
            f"[PaperBroker] QUALIFIED OPEN {sig.direction.upper()} {sig.symbol} "
            f"qty={qty} @ {entry_price} | "
            f"size={qualified.position_size_pct:.2f}% (${qualified.position_size_usd:.0f}) | "
            f"risk=${qualified.risk_amount_usd:.0f} | EV={qualified.expected_value_r:.3f}R | "
            f"regime={qualified.market_regime} | session={qualified.session_name}"
        )
        db.save_order_log(
            sig.symbol, sig.direction, qty, entry_price,
            sig.stop_loss, sig.take_profit, sig.family,
            accepted=True, reject_reason=None
        )
        return True

    def on_signal(self, signal_dict: Dict[str, Any]) -> bool:
        """Fallback processing for dictionary-based signals."""
        symbol = signal_dict.get("symbol")
        direction = signal_dict.get("direction", "long")
        entry_price = signal_dict.get("entry_price", 0.0)
        pos_usd = signal_dict.get("position_size_usd", 0.0)
        qty = round(pos_usd / entry_price, 6) if entry_price > 0 else 0.0
        
        return self.execute_order(
            symbol=symbol,
            direction=direction,
            quantity=qty,
            price=entry_price,
            stop_loss=signal_dict.get("stop_loss"),
            take_profit=signal_dict.get("take_profit"),
            time_str=signal_dict.get("qualified_at") or signal_dict.get("fired_at"),
            signal_source=signal_dict.get("family", "unknown"),
        )

    def get_qualified_signals(self, limit: int = 50) -> list:
        """
        Trả về danh sách QualifiedSignal gần nhất dưới dạng dict.
        Mới nhất trước (reversed).
        """
        signals = list(self._qualified_signals)[-limit:]
        result = []
        for qs in reversed(signals):
            try:
                d = qs.to_dict() if hasattr(qs, "to_dict") else {}
                result.append(d)
            except Exception:
                pass
        return result

    def close_position(
        self,
        symbol: str,
        price: float,
        time_str: str | None = None,
        reason: str = "Market Close",
    ):
        if symbol not in self.positions:
            return

        pos         = self.positions.pop(symbol)
        direction   = pos["direction"]
        entry_price = pos["entry_price"]
        quantity    = pos["quantity"]

        pnl      = (price - entry_price) * quantity if direction == "long" \
                   else (entry_price - price) * quantity
        exit_fee = price * quantity * 0.0005
        net_pnl  = pnl - exit_fee

        self.balance = round(self.balance + net_pnl, 4)

        trade = {
            "symbol":        symbol,
            "direction":     direction,
            "quantity":      quantity,
            "entry_price":   entry_price,
            "exit_price":    price,
            "entry_time":    pos["entry_time"],
            "exit_time":     time_str or datetime.now(UTC).isoformat(),
            "pnl":           round(net_pnl, 4),
            "fees":          round(pos["entry_fee"] + exit_fee, 4),
            "reason":        reason,
            "signal_source": pos.get("signal_source", "unknown"),
            "signal_id":     pos.get("signal_id"),
            # ── Quality Gate metadata (carry forward từ position) ──
            "position_size_pct": pos.get("position_size_pct", 0.0),
            "risk_amount_usd":   pos.get("risk_amount_usd", 0.0),
            "expected_value_r":  pos.get("expected_value_r", 0.0),
            "market_regime":     pos.get("market_regime", "unknown"),
            "btc_structure":     pos.get("btc_structure", "neutral"),
            "session_name":      pos.get("session_name", "unknown"),
            "family":            pos.get("family", "unknown"),
            "confidence_score":  pos.get("confidence_score", 0.0),
        }
        self.trade_history.append(trade)

        db.delete_position(symbol)
        db.save_trade(trade)
        db.save_broker_state(self.balance, self.equity)
        logger.info(f"[PaperBroker] CLOSED {symbol} at {price}. Net PnL: {net_pnl} ({reason})")

    def get_summary(self) -> Dict[str, Any]:
        return {
            "balance":               self.balance,
            "equity":                self.equity,
            "active_positions_count": len(self.positions),
            "positions":             list(self.positions.values()),
            "trade_history":         self.trade_history,
        }
