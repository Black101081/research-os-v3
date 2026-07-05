
import sys, json, time, csv
from pathlib import Path
from datetime import datetime, timezone
import websocket

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from realtime_engine import ResearchEngine
from bootstrap_ohlcv import warmup_engine

reports = ROOT / 'sandbox_test_reports'
reports.mkdir(parents=True, exist_ok=True)
summary_csv = reports / 'btc_15m_soak_summary.csv'
detail_csv = reports / 'btc_15m_soak_detail.csv'
status_json = reports / 'btc_15m_soak_status.json'
final_json = reports / 'btc_15m_soak_final.json'
errors_log = reports / 'btc_15m_soak_errors.log'

engine = ResearchEngine(symbols=['BTC'], max_bars=500, thresholds={})
warm = warmup_engine(engine, ['BTC'], '1m', 240)

start_wall = datetime.now(timezone.utc)
run_seconds = 900
end_epoch = time.time() + run_seconds
endpoint = 'wss://api.hyperliquid.xyz/ws'
subs = [
    {"method": "subscribe", "subscription": {"type": "trades", "coin": "BTC"}},
    {"method": "subscribe", "subscription": {"type": "bbo", "coin": "BTC"}},
]

summary_fields = [
    'ts_utc','elapsed_sec','messages_total','trade_events_total','bbo_events_total',
    'last_trade','current_bar_close','current_bar_volume','active_signals','execution_ready_count',
    'risk_allow_count','risk_block_count','risk_warn_count','regime','tradable',
    'spread_bps','micro_volatility','trade_flow_imbalance','live_ret_from_last_close',
    'recent_reactivity_events'
]
detail_fields = [
    'ts_utc','message_type','current_bar_changed','factors_changed_count','indicators_changed_count',
    'regime_changed','signals_changed_count','strategies_changed_count','risk_changed',
    'validation_changed','reactive_source','factors_changed','indicators_changed','signals_changed',
    'strategies_changed','risk_packets_changed'
]

if not summary_csv.exists():
    with open(summary_csv, 'w', newline='', encoding='utf-8') as f:
        csv.DictWriter(f, fieldnames=summary_fields).writeheader()
if not detail_csv.exists():
    with open(detail_csv, 'w', newline='', encoding='utf-8') as f:
        csv.DictWriter(f, fieldnames=detail_fields).writeheader()

state = {
    'started_at_utc': start_wall.isoformat(),
    'warmup_bars_loaded': warm.get('BTC', 0),
    'endpoint': endpoint,
    'run_seconds': run_seconds,
    'status': 'running',
    'messages_total': 0,
    'trade_events_total': 0,
    'bbo_events_total': 0,
    'acks': 0,
    'last_error': None,
}
status_json.write_text(json.dumps(state, indent=2, ensure_ascii=False), encoding='utf-8')

ws = None
last_flush = 0
try:
    ws = websocket.create_connection(endpoint, timeout=10)
    for s in subs:
        ws.send(json.dumps(s))
    while time.time() < end_epoch:
        try:
            raw = ws.recv()
            msg = json.loads(raw)
            channel = msg.get('channel')
            state['messages_total'] += 1
            if channel == 'subscriptionResponse':
                state['acks'] += 1
                continue
            if channel == 'trades':
                data = msg.get('data', []) if isinstance(msg.get('data'), list) else []
                state['trade_events_total'] += len(data)
            elif channel == 'bbo':
                state['bbo_events_total'] += 1
            before_len = len(engine.snapshot()['BTC'].get('recent_reactivity', []))
            engine.process_message(msg)
            snap = engine.snapshot()['BTC']
            after_events = snap.get('recent_reactivity', [])
            latest_diff = after_events[-1] if len(after_events) > before_len else (after_events[-1] if after_events else None)

            now_utc = datetime.now(timezone.utc).isoformat()
            risk_packets = snap.get('risk_packets', {}) or {}
            risk_allow = sum(1 for v in risk_packets.values() if v.get('risk_status') == 'ALLOW')
            risk_warn = sum(1 for v in risk_packets.values() if v.get('risk_status') == 'ALLOW_WITH_WARNINGS')
            risk_block = sum(1 for v in risk_packets.values() if v.get('risk_status') in {'BLOCK','FLATTEN_ONLY'})
            active_signals = sum(1 for v in snap.get('signals', {}).values() if v.get('active'))
            execution_ready = sum(1 for v in snap.get('strategies', {}).values() if v.get('execution_ready'))
            factors = snap.get('factors', {})
            regime_state = snap.get('regime_state', {})
            current_bar = snap.get('current_bar') or {}

            if latest_diff:
                with open(detail_csv, 'a', newline='', encoding='utf-8') as f:
                    csv.DictWriter(f, fieldnames=detail_fields).writerow({
                        'ts_utc': now_utc,
                        'message_type': latest_diff.get('message_type'),
                        'current_bar_changed': latest_diff.get('current_bar_changed'),
                        'factors_changed_count': len(latest_diff.get('factors_changed', [])),
                        'indicators_changed_count': len(latest_diff.get('indicators_changed', [])),
                        'regime_changed': latest_diff.get('regime_changed'),
                        'signals_changed_count': len(latest_diff.get('signals_changed', [])),
                        'strategies_changed_count': len(latest_diff.get('strategies_changed', [])),
                        'risk_changed': latest_diff.get('risk_changed'),
                        'validation_changed': latest_diff.get('validation_changed'),
                        'reactive_source': latest_diff.get('reactive_source'),
                        'factors_changed': '|'.join(latest_diff.get('factors_changed', [])),
                        'indicators_changed': '|'.join(latest_diff.get('indicators_changed', [])),
                        'signals_changed': '|'.join(latest_diff.get('signals_changed', [])),
                        'strategies_changed': '|'.join(latest_diff.get('strategies_changed', [])),
                        'risk_packets_changed': '|'.join(latest_diff.get('risk_packets_changed', [])),
                    })

            if time.time() - last_flush >= 15:
                with open(summary_csv, 'a', newline='', encoding='utf-8') as f:
                    csv.DictWriter(f, fieldnames=summary_fields).writerow({
                        'ts_utc': now_utc,
                        'elapsed_sec': round((datetime.now(timezone.utc) - start_wall).total_seconds(), 1),
                        'messages_total': state['messages_total'],
                        'trade_events_total': state['trade_events_total'],
                        'bbo_events_total': state['bbo_events_total'],
                        'last_trade': snap.get('last_trade'),
                        'current_bar_close': current_bar.get('close'),
                        'current_bar_volume': current_bar.get('volume'),
                        'active_signals': active_signals,
                        'execution_ready_count': execution_ready,
                        'risk_allow_count': risk_allow,
                        'risk_block_count': risk_block,
                        'risk_warn_count': risk_warn,
                        'regime': regime_state.get('regime'),
                        'tradable': regime_state.get('tradable'),
                        'spread_bps': factors.get('spread_bps'),
                        'micro_volatility': factors.get('micro_volatility_20'),
                        'trade_flow_imbalance': factors.get('trade_flow_imbalance_20'),
                        'live_ret_from_last_close': factors.get('live_ret_from_last_close'),
                        'recent_reactivity_events': len(after_events),
                    })
                state.update({
                    'status': 'running',
                    'last_heartbeat_utc': now_utc,
                    'messages_total': state['messages_total'],
                    'trade_events_total': state['trade_events_total'],
                    'bbo_events_total': state['bbo_events_total'],
                    'last_trade': snap.get('last_trade'),
                    'active_signals': active_signals,
                    'execution_ready_count': execution_ready,
                    'risk_statuses': {k:v.get('risk_status') for k,v in risk_packets.items()},
                    'regime': regime_state.get('regime'),
                    'tradable': regime_state.get('tradable'),
                })
                status_json.write_text(json.dumps(state, indent=2, ensure_ascii=False), encoding='utf-8')
                last_flush = time.time()
        except Exception as e:
            state['last_error'] = f'{type(e).__name__}: {e}'
            errors_log.write_text((errors_log.read_text(encoding='utf-8') if errors_log.exists() else '') + state['last_error'] + '\n', encoding='utf-8')
            time.sleep(1)
finally:
    if ws is not None:
        try:
            ws.close()
        except Exception:
            pass
    snap = engine.snapshot().get('BTC', {})
    final = {
        'status': 'completed',
        'started_at_utc': state['started_at_utc'],
        'ended_at_utc': datetime.now(timezone.utc).isoformat(),
        'warmup_bars_loaded': warm.get('BTC', 0),
        'messages_total': state['messages_total'],
        'trade_events_total': state['trade_events_total'],
        'bbo_events_total': state['bbo_events_total'],
        'acks': state['acks'],
        'last_trade': snap.get('last_trade'),
        'active_signals': sum(1 for v in snap.get('signals', {}).values() if v.get('active')),
        'execution_ready_count': sum(1 for v in snap.get('strategies', {}).values() if v.get('execution_ready')),
        'risk_statuses': {k:v.get('risk_status') for k,v in (snap.get('risk_packets', {}) or {}).items()},
        'regime': (snap.get('regime_state', {}) or {}).get('regime'),
        'tradable': (snap.get('regime_state', {}) or {}).get('tradable'),
        'recent_reactivity_tail': (snap.get('recent_reactivity') or [])[-5:],
        'last_error': state.get('last_error'),
    }
    final_json.write_text(json.dumps(final, indent=2, ensure_ascii=False), encoding='utf-8')
    status_json.write_text(json.dumps(final, indent=2, ensure_ascii=False), encoding='utf-8')
