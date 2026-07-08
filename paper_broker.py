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
        self.pending_orders: List[Dict[str, Any]] = []

        logger.info(
            f"[PaperBroker] Loaded {len(self.positions)} positions, "
            f"{len(self.trade_history)} trades from DB"
        )

    def process_tick(self, symbol: str, current_price: float, current_time: str, indicators: dict | None = None):
        # ── 1. Update pending limit orders (Post-Only + Chasing simulation) ──
        still_pending = []
        for order in getattr(self, "pending_orders", []):
            if order["symbol"] != symbol:
                still_pending.append(order)
                continue
                
            filled = False
            if order["direction"] == "long" or order["direction"] == "buy":
                if current_price <= order["limit_price"]:
                    filled = True
            else:
                if current_price >= order["limit_price"]:
                    filled = True
                    
            if filled:
                self._fill_pending_order(order, order["limit_price"], 0.0, current_time)
                continue
                
            order["ticks_waiting"] += 1
            if order["ticks_waiting"] >= 5:
                if order["chase_count"] < 3:
                    order["chase_count"] += 1
                    order["ticks_waiting"] = 0
                    order["limit_price"] = current_price
                    logger.info(f"[PaperBroker] CHASE #{order['chase_count']} for {symbol}: new limit_price={current_price}")
                    still_pending.append(order)
                else:
                    taker_fee_pct = 0.0005
                    total_slippage = 0.0003
                    if order["direction"] == "long" or order["direction"] == "buy":
                        fill_price = current_price * (1 + total_slippage)
                    else:
                        fill_price = current_price * (1 - total_slippage)
                    logger.info(f"[PaperBroker] CHASE MAXED OUT. Filling as Taker for {symbol} at {fill_price}")
                    self._fill_pending_order(order, fill_price, taker_fee_pct, current_time)
            else:
                still_pending.append(order)
                
        self.pending_orders = still_pending

        # ── 2. Standard position SL/TP checks ──
        matching_keys = [k for k, p in self.positions.items() if p["symbol"] == symbol]
        for key in matching_keys:
            pos = self.positions[key]
            direction   = pos["direction"]
            entry_price = pos["entry_price"]
            quantity    = pos["quantity"]

            if direction == "long":
                unrealized = (current_price - entry_price) * quantity
            else:
                unrealized = (entry_price - current_price) * quantity

            pos["current_price"]   = current_price
            pos["unrealized_pnl"]  = round(unrealized, 4)

            # ── 2b. Breakeven and Trailing Stop-Loss logic ──
            initial_sl = pos.get("initial_sl")
            if initial_sl is None:
                initial_sl = pos.get("stop_loss")
                pos["initial_sl"] = initial_sl

            if initial_sl and initial_sl > 0:
                risk_per_unit = abs(entry_price - initial_sl)
            else:
                risk_per_unit = 0.02 * entry_price

            breakeven_triggered = bool(pos.get("breakeven_triggered", False))
            max_fav = pos.get("max_favorable_price", entry_price)
            if max_fav is None:
                max_fav = entry_price

            if direction == "long" or direction == "buy":
                max_fav = max(max_fav, current_price)
                pos["max_favorable_price"] = max_fav
                
                # Check for breakeven trigger
                if not breakeven_triggered and current_price - entry_price >= risk_per_unit:
                    pos["breakeven_triggered"] = True
                    pos["stop_loss"] = entry_price
                    logger.info(f"[PaperBroker] BREAKEVEN TRIGGERED for Long {symbol} at {current_price} (SL moved to {entry_price})")
                    breakeven_triggered = True
                    
                # Trailing stop
                if breakeven_triggered:
                    atr_pct = 0.02
                    if indicators:
                        atr_val = indicators.get("atr_14_pct") or indicators.get("natr") or indicators.get("atr_pct_14")
                        if atr_val is not None:
                            atr_pct = atr_val / 100.0
                    
                    trail_dist = 1.5 * atr_pct * entry_price
                    new_sl = round(max_fav - trail_dist, 6)
                    if pos["stop_loss"] is None or new_sl > pos["stop_loss"]:
                        pos["stop_loss"] = new_sl
                        logger.info(f"[PaperBroker] TRAILING SL MOVED UP for Long {symbol} to {new_sl} (max_fav={max_fav})")
            else:
                max_fav = min(max_fav, current_price)
                pos["max_favorable_price"] = max_fav
                
                # Check for breakeven trigger
                if not breakeven_triggered and entry_price - current_price >= risk_per_unit:
                    pos["breakeven_triggered"] = True
                    pos["stop_loss"] = entry_price
                    logger.info(f"[PaperBroker] BREAKEVEN TRIGGERED for Short {symbol} at {current_price} (SL moved to {entry_price})")
                    breakeven_triggered = True
                    
                # Trailing stop
                if breakeven_triggered:
                    atr_pct = 0.02
                    if indicators:
                        atr_val = indicators.get("atr_14_pct") or indicators.get("natr") or indicators.get("atr_pct_14")
                        if atr_val is not None:
                            atr_pct = atr_val / 100.0
                            
                    trail_dist = 1.5 * atr_pct * entry_price
                    new_sl = round(max_fav + trail_dist, 6)
                    if pos["stop_loss"] is None or new_sl < pos["stop_loss"]:
                        pos["stop_loss"] = new_sl
                        logger.info(f"[PaperBroker] TRAILING SL MOVED DOWN for Short {symbol} to {new_sl} (max_fav={max_fav})")

            sl_price = pos.get("stop_loss")
            tp_price = pos.get("take_profit")
            trigger_close = False
            close_reason  = ""

            if direction == "long" or direction == "buy":
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
                self.close_position(symbol, pos.get("signal_source", "unknown"), current_price, current_time, close_reason)
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
        pos_key = f"{symbol}_{signal_source}"
        if pos_key in self.positions:
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
            "breakeven_triggered": False,
            "initial_sl":    stop_loss,
            "max_favorable_price": price,
        }
        if extra:
            pos.update(extra)
        self.positions[pos_key] = pos
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
        pos_key = f"{sig.symbol}_{sig.family}"
        if pos_key in self.positions:
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

        # --- Limit Post-Only Execution Simulation ---
        pending_order = {
            "symbol": sig.symbol,
            "direction": sig.direction,
            "qty": qty,
            "limit_price": entry_price,
            "stop_loss": sig.stop_loss,
            "take_profit": sig.take_profit,
            "family": sig.family,
            "signal_id": sig.signal_id or f"{sig.symbol}_{sig.family}_{getattr(sig, 'interval', 'unknown')}",
            "signal_res": sig,
            "qualified": qualified,
            "chase_count": 0,
            "ticks_waiting": 0,
            "extra": {
                "execution_style": "limit_post_only"
            }
        }
        self.pending_orders.append(pending_order)
        
        logger.info(
            f"[PaperBroker] QUALIFIED LIMIT SUBMITTED {sig.direction.upper()} {sig.symbol} "
            f"qty={qty} @ {entry_price} | size=${qualified.position_size_usd:.0f}"
        )
        return True

    def _fill_pending_order(self, order: dict, fill_price: float, fee_pct: float, fill_time: str):
        symbol = order["symbol"]
        direction = order["direction"]
        qty = order["qty"]
        sig = order["signal_res"]
        qualified = order["qualified"]
        
        pos_key = f"{symbol}_{sig.family}"
        cost = qty * fill_price
        entry_fee = cost * fee_pct
        self.balance = round(self.balance - entry_fee, 4)
        
        pos = {
            "symbol":           symbol,
            "direction":        direction,
            "quantity":         qty,
            "entry_price":      fill_price,
            "current_price":    fill_price,
            "stop_loss":        order["stop_loss"],
            "take_profit":      order["take_profit"],
            "entry_time":       fill_time,
            "unrealized_pnl":   0.0,
            "entry_fee":        round(entry_fee, 4),
            "signal_source":    sig.family,
            "signal_id":        order["signal_id"],
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
            "breakeven_triggered": False,
            "initial_sl":        order["stop_loss"],
            "max_favorable_price": fill_price,
        }
        self.positions[pos_key] = pos
        self._qualified_signals.append(qualified)
        
        db.save_position(pos)
        db.save_broker_state(self.balance, self.equity)
        
        logger.info(
            f"[PaperBroker] QUALIFIED OPEN (FILLED LIMIT) {direction.upper()} {symbol} "
            f"qty={qty} @ {fill_price} | size=${qualified.position_size_usd:.0f} | fee={entry_fee:.4f}"
        )
        db.save_order_log(symbol, direction, qty, fill_price,
                          order["stop_loss"], order["take_profit"], sig.family,
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
        signal_source: str,
        price: float,
        time_str: str | None = None,
        reason: str = "Market Close",
    ):
        pos_key = f"{symbol}_{signal_source}"
        if pos_key not in self.positions:
            return

        pos         = self.positions.pop(pos_key)
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

        db.delete_position(symbol, signal_source)
        db.save_trade(trade)
        db.save_broker_state(self.balance, self.equity)
        logger.info(f"[PaperBroker] CLOSED {symbol} ({signal_source}) at {price}. Net PnL: {net_pnl} ({reason})")

    def clear_all_positions(self):
        self.positions.clear()
        conn = db.get_connection()
        with conn:
            conn.execute("DELETE FROM paper_positions")
        conn.close()
        logger.info("[PaperBroker] Cleared all open positions from memory and database.")

    def get_summary(self) -> Dict[str, Any]:
        return {
            "balance":               self.balance,
            "equity":                self.equity,
            "active_positions_count": len(self.positions),
            "positions":             list(self.positions.values()),
            "trade_history":         self.trade_history,
        }
