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

    def on_qualified_signal(self, qualified: QualifiedSignal) -> bool:
        """Process qualified signal from quality gate."""
        entry_price = qualified.signal.entry_price
        if entry_price <= 0:
            return False
        qty = round(qualified.position_size_usd / entry_price, 6)
        if symbol_in := qualified.signal.symbol in self.positions:
            return False
        
        cost = qty * entry_price
        if cost > self.balance * 2.0:
            return False

        entry_fee = cost * 0.0005
        self.balance = round(self.balance - entry_fee, 4)

        pos = {
            "symbol":        qualified.signal.symbol,
            "direction":     qualified.signal.direction,
            "quantity":      qty,
            "entry_price":   entry_price,
            "current_price": entry_price,
            "stop_loss":     qualified.signal.stop_loss,
            "take_profit":   qualified.signal.take_profit,
            "entry_time":    qualified.qualified_at,
            "unrealized_pnl": 0.0,
            "entry_fee":     round(entry_fee, 4),
            "signal_source": qualified.signal.family,
            "signal_id":     qualified.signal.signal_id,
        }
        self.positions[qualified.signal.symbol] = pos
        db.save_position(pos)
        db.save_broker_state(self.balance, self.equity)
        logger.info(
            f"[PaperBroker] OPENED QUALIFIED {qualified.signal.direction.upper()} {qualified.signal.symbol} "
            f"qty={qty} price={entry_price} SL={qualified.signal.stop_loss} via {qualified.signal.family}"
        )
        db.save_order_log(qualified.signal.symbol, qualified.signal.direction, qty, entry_price,
                          qualified.signal.stop_loss, qualified.signal.take_profit, qualified.signal.family,
                          accepted=True, reject_reason=None)
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
            "symbol":       symbol,
            "direction":    direction,
            "quantity":     quantity,
            "entry_price":  entry_price,
            "exit_price":   price,
            "entry_time":   pos["entry_time"],
            "exit_time":    time_str or datetime.now(UTC).isoformat(),
            "pnl":          round(net_pnl, 4),
            "fees":         round(pos["entry_fee"] + exit_fee, 4),
            "reason":       reason,
            "signal_source": pos.get("signal_source", "unknown"),
            "signal_id":     pos.get("signal_id"),
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
