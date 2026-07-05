from __future__ import annotations

import logging
from datetime import datetime, UTC
from typing import Dict, Any, List

logger = logging.getLogger(__name__)


class PaperBroker:
    def __init__(self, initial_balance: float = 10000.0):
        self.balance = initial_balance
        self.equity = initial_balance
        self.positions: Dict[str, Dict[str, Any]] = {}
        self.trade_history: List[Dict[str, Any]] = []

    def process_tick(self, symbol: str, current_price: float, current_time: str):
        if symbol in self.positions:
            pos = self.positions[symbol]
            direction = pos['direction']
            entry_price = pos['entry_price']
            quantity = pos['quantity']

            if direction == 'long':
                unrealized = (current_price - entry_price) * quantity
            else:
                unrealized = (entry_price - current_price) * quantity

            pos['current_price'] = current_price
            pos['unrealized_pnl'] = round(unrealized, 4)

            # Check SL/TP exit
            sl_price = pos.get('stop_loss')
            tp_price = pos.get('take_profit')

            trigger_close = False
            close_reason = ""
            if direction == 'long':
                if sl_price and current_price <= sl_price:
                    trigger_close = True
                    close_reason = "Stop Loss"
                elif tp_price and current_price >= tp_price:
                    trigger_close = True
                    close_reason = "Take Profit"
            else:
                if sl_price and current_price >= sl_price:
                    trigger_close = True
                    close_reason = "Stop Loss"
                elif tp_price and current_price <= tp_price:
                    trigger_close = True
                    close_reason = "Take Profit"

            if trigger_close:
                self.close_position(symbol, current_price, current_time, close_reason)

        # Update equity
        unrealized_total = sum(pos['unrealized_pnl'] for pos in self.positions.values())
        self.equity = round(self.balance + unrealized_total, 4)

    def execute_order(
        self,
        symbol: str,
        direction: str,
        quantity: float,
        price: float,
        stop_loss: float | None = None,
        take_profit: float | None = None,
        time_str: str | None = None
    ) -> bool:
        if symbol in self.positions:
            return False

        if quantity <= 0 or price <= 0:
            return False

        cost = quantity * price
        if cost > self.balance * 2.0:  # 2x Leverage cap
            logger.warning(f"Simulated order failed: Insufficient margin for {symbol} (cost: {cost})")
            return False

        # Apply entry fee (5 bps)
        entry_fee = cost * 0.0005
        self.balance = round(self.balance - entry_fee, 4)

        self.positions[symbol] = {
            'symbol': symbol,
            'direction': direction,
            'quantity': quantity,
            'entry_price': price,
            'current_price': price,
            'stop_loss': stop_loss,
            'take_profit': take_profit,
            'entry_time': time_str or datetime.now(UTC).isoformat(),
            'unrealized_pnl': 0.0,
            'entry_fee': round(entry_fee, 4)
        }
        logger.info(f"Paper Broker: Position opened: {direction} {quantity} {symbol} at {price}")
        return True

    def close_position(self, symbol: str, price: float, time_str: str | None = None, reason: str = "Market Close"):
        if symbol not in self.positions:
            return

        pos = self.positions.pop(symbol)
        direction = pos['direction']
        entry_price = pos['entry_price']
        quantity = pos['quantity']

        if direction == 'long':
            pnl = (price - entry_price) * quantity
        else:
            pnl = (entry_price - price) * quantity

        # Apply exit fee (5 bps)
        exit_fee = price * quantity * 0.0005
        net_pnl = pnl - exit_fee

        self.balance = round(self.balance + net_pnl, 4)
        self.trade_history.append({
            'symbol': symbol,
            'direction': direction,
            'quantity': quantity,
            'entry_price': entry_price,
            'exit_price': price,
            'entry_time': pos['entry_time'],
            'exit_time': time_str or datetime.now(UTC).isoformat(),
            'pnl': round(net_pnl, 4),
            'fees': round(pos['entry_fee'] + exit_fee, 4),
            'reason': reason
        })
        logger.info(f"Paper Broker: Position closed: {symbol} at {price}. Net PnL: {net_pnl} ({reason})")

    def get_summary(self) -> Dict[str, Any]:
        return {
            'balance': self.balance,
            'equity': self.equity,
            'active_positions_count': len(self.positions),
            'positions': list(self.positions.values()),
            'trade_history': self.trade_history
        }
