# SYSTEM MASTER — Research OS V3

> **Đọc file này trước khi làm bất cứ thứ gì.**  
> Đây là nguồn sự thật duy nhất về pipeline, kiến trúc, và trạng thái hệ thống.

---

## 1. Mục Tiêu Hệ Thống

Research OS V3 là hệ thống **paper trading tự động** chạy realtime trên Hyperliquid.

Nó KHÔNG đặt lệnh thật. Nó:
1. Nhận market data từ Hyperliquid WebSocket
2. Tính toán factors → indicators → signals → strategies
3. Đánh giá chất lượng signal qua Quality Gate
4. Mở/đóng paper trade qua Paper Broker
5. Lưu kết quả để phân tích và cải tiến alpha

---

## 2. Pipeline Đầy Đủ (Thứ Tự Tuyến Tính)

```
[Hyperliquid WS]
      │
      ▼
Step 1: INGEST — Nhận raw message, parse channel type
      │  file: realtime_engine.py → process_message()
      │
      ▼
Step 2: NORMALIZE — Chuẩn hóa thành internal schema
      │  file: realtime_engine.py → _handle_candle(), _handle_bbo(), _handle_trades()
      │
      ▼
Step 3: STATE UPDATE — Cập nhật rolling OHLCV bars
      │  file: realtime_engine.py → SymbolState.update()
      │  MTF bars: multi_tf_state.py
      │
      ▼
Step 4: FACTORS — Tính toán incremental factors từ bars
      │  file: factor_math.py → compute_factors_np()
      │  Gồm: ret_5, volatility_20, zscore, flow_imbalance, divergence...
      │
      ▼
Step 5: INDICATORS — Tính indicators từ factors + bars
      │  file: factor_math.py → compute_indicators_np()
      │  Gồm: RSI, MACD, BollingerBands, ATR, ZScore_Close...
      │
      ▼
Step 6: REGIME — Classify market regime từ factors + indicators
      │  file: regime_engine.py → classify_regime()
      │  Regimes: uptrend, downtrend, range_chop, high_volatility, transition_ambiguous
      │  Output: {regime, confidence, tradable, allowed_signal_families}
      │
      ▼
Step 7: SIGNALS — Evaluate signal templates từ indicator state
      │  file: signal_orchestrator.py → evaluate_supported_signals()
      │  file: signal_library.py (static templates)
      │  file: promoted_signal_bridge.py (dynamic promoted alphas)
      │  Output per signal: {triggered, confirmed, invalidated, direction, score}
      │
      ▼
Step 8: RISK — Tính position size, SL, TP
      │  file: risk_engine.py → build_risk_packet_v1()
      │  Gồm: ATR-based SL, risk%, target_quantity, EV ratio
      │
      ▼
Step 9: QUALITY GATE — Filter signal đủ điều kiện trade
      │  file: quality_gate.py → evaluate()
      │  Checks: regime_fit, signal_score, EV ratio, risk limits
      │  Output: QualifiedSignal hoặc GateRejection
      │
      ▼
Step 10: PAPER BROKER — Mở/đóng/manage paper positions
      │  file: paper_broker.py → on_qualified_signal(), process_tick()
      │  SL/TP auto-exit, PnL tracking, equity update
      │
      ▼
Step 11: VALIDATION — Build validation packet cho signal
      │  file: validation_bridge.py → build_validation_packet()
      │  file: realtime_engine.py → _compute_validation()
      │
      ▼
Step 12: REGISTRY — Ghi strategy candidates ra disk
      │  file: async_registry_writer.py
      │  file: alpha_registry.py
      │  Output: runtime/registry/*.json
      │
      ▼
Step 13: API / DASHBOARD — Expose state
         file: app.py (FastAPI)
         file: static/index.html (Dashboard UI)
```

---

## 3. Kiến Trúc 4 Tầng

```
┌─────────────────────────────────────────────────────┐
│  TẦNG 1: DATA LAYER                                 │
│  Nhận và chuẩn hóa market data                      │
│  hyperliquid_ws_client.py                           │
│  realtime_engine.py (ingest + normalize + state)    │
│  multi_tf_state.py                                  │
│  bootstrap_ohlcv.py (warmup historical)             │
├─────────────────────────────────────────────────────┤
│  TẦNG 2: RESEARCH LAYER                             │
│  Tính toán tất cả giá trị phân tích                 │
│  factor_math.py (factors + indicators)              │
│  regime_engine.py                                   │
│  signal_orchestrator.py + signal_library.py         │
│  tf_indicator_engine.py                             │
│  asset_tf_fitness.py                                │
│  reactivity_diff.py                                 │
├─────────────────────────────────────────────────────┤
│  TẦNG 3: EXECUTION LAYER                            │
│  Quyết định và thực thi paper trade                 │
│  risk_engine.py                                     │
│  quality_gate.py + quality_gate_models.py           │
│  paper_broker.py                                    │
│  database.py (persistence)                          │
├─────────────────────────────────────────────────────┤
│  TẦNG 4: ALPHA FACTORY LAYER                        │
│  Sinh, đánh giá, promote alpha candidates           │
│  alpha_factory_runner.py                            │
│  alpha_registry.py + alpha_registry_store.py        │
│  alpha_lifecycle.py                                 │
│  promotion_engine.py                               │
│  promoted_signal_bridge.py                         │
│  validation_bridge.py                              │
│  async_registry_writer.py                          │
│  backtest_bridge.py                                │
└─────────────────────────────────────────────────────┘
```

---

## 4. Luồng Dữ Liệu Chính (Data Flow)

```
Candle (1m) ──→ SymbolState.bars
                    │
                    ├──→ factor_math → factors{} → indicators{}
                    │                      │
                    │                      └──→ regime_state{tradable, regime}
                    │
                    ├──→ signal_orchestrator → signals{triggered, confirmed}
                    │
                    ├──→ risk_engine → risk_packets{sl, tp, quantity}
                    │
                    └──→ _compute_strategies() → strategies{execution_ready}
                                                        │
                                            execution_ready=True
                                                        │
                                                        ▼
                                              quality_gate.evaluate()
                                                        │
                                               GATE_PASS / REJECT
                                                        │
                                                        ▼
                                           paper_broker.on_qualified_signal()
                                                        │
                                                  OPEN POSITION
```

---

## 5. Điều Kiện Để execution_ready = True

Tất cả 4 điều kiện PHẢI đúng:

```python
execution_ready = (
    bars_ok          # close_count >= 35 (đủ warmup)
    and logic_ready  # triggered AND confirmed AND NOT invalidated
    and fitness_ok   # asset/tf phù hợp với signal family
    and state.regime_state.get('tradable', False)  # regime cho phép
)
```

### Regime nào là tradable?

| Regime | Tradable | Allowed Families |
|--------|----------|------------------|
| uptrend | ✅ | continuation, breakout, order_flow, cross_asset, divergence, mean_reversion |
| downtrend | ✅ | continuation, breakout, order_flow, cross_asset, divergence, mean_reversion |
| range_chop | ✅ | mean_reversion, divergence |
| transition_ambiguous | ✅ | all (paper mode) |
| high_volatility | ❌ | none |

---

## 6. File Map — File Nào Làm Gì

| File | Tầng | Bước | Nhiệm vụ |
|------|------|------|----------|
| `hyperliquid_ws_client.py` | 1 | 1 | WS connect + subscribe |
| `realtime_engine.py` | 1+2 | 1-9 | Engine chính, xử lý mọi thứ |
| `multi_tf_state.py` | 1 | 3 | Multi-timeframe bar state |
| `bootstrap_ohlcv.py` | 1 | - | Pull historical candles trước khi WS start |
| `factor_math.py` | 2 | 4-5 | Tính factors, indicators, divergence |
| `regime_engine.py` | 2 | 6 | Classify market regime |
| `signal_orchestrator.py` | 2 | 7 | Evaluate signal templates |
| `signal_library.py` | 2 | 7 | Static signal definitions |
| `promoted_signal_bridge.py` | 4 | 7 | Dynamic promoted alpha signals |
| `risk_engine.py` | 3 | 8 | SL/TP/size calculation |
| `quality_gate.py` | 3 | 9 | Signal quality filter |
| `paper_broker.py` | 3 | 10 | Paper trade execution |
| `database.py` | 3 | - | SQLite persistence |
| `validation_bridge.py` | 4 | 11 | Build validation packets |
| `async_registry_writer.py` | 4 | 12 | Write registry artifacts |
| `alpha_registry.py` | 4 | 12 | Alpha registry CRUD |
| `alpha_lifecycle.py` | 4 | - | Alpha lifecycle state machine |
| `app.py` | - | 13 | FastAPI + Dashboard serve |
| `globals.py` | - | - | Module-level singletons |
| `telemetry.py` | - | - | Error rate + latency tracking |

---

## 7. Trạng Thái Hiện Tại (cập nhật July 2026)

### ✅ Đã hoạt động
- Data ingest từ Hyperliquid WS (candle, trades, bbo, allMids)
- Factor + indicator computation
- Signal evaluation (30+ signals)
- Risk packet calculation
- Quality gate filtering
- Paper broker open/close positions
- Dashboard UI hiển thị realtime

### ⚠️ Vấn đề còn lại
- **Error Rate ~71%**: Một số message channels từ WS live đang crash
  trong `process_message()`. Cần xem HF Space Logs để biết channel nào.
- **REGIME_FIT ❌**: Đã fix — `transition_ambiguous` được thêm vào tradable.

### 🔴 Không làm
- Live order execution (chỉ paper)
- Multi-account management
- Live PnL reporting ra ngoài

---

## 8. Quy Tắc Cho AI Agent (AG/Copilot)

> **Đọc kỹ trước khi sửa bất cứ thứ gì:**

1. **Mỗi fix phải map vào 1 bước cụ thể** trong pipeline (Step 1-13)
2. **Không thêm file mới** nếu chưa biết nó nằm ở tầng nào
3. **Không sửa logic tầng 2** (factors/indicators/signals) khi đang debug tầng 3 (execution)
4. **Error rate cao** → kiểm tra Step 1-3 trước (ingest/normalize/state)
5. **TRADE:X** → kiểm tra Step 6 (regime tradable) và Step 9 (quality gate)
6. **Không có trade** dù TRADE:✓ → kiểm tra Step 8 (risk quantity > 0) và Step 10 (broker)
7. **Sau mỗi fix**, ghi rõ: "Fix này giải quyết Step X, file Y, dòng Z"

---

## 9. Cách Verify Hệ Thống Hoạt Động

```bash
# 1. Dashboard mở được
curl https://gionuibk-research-os-v3.hf.space/health

# 2. Signals đang tính
curl https://gionuibk-research-os-v3.hf.space/api/snapshot | jq '.symbols.BTC.signals | length'

# 3. Paper broker có trade
curl https://gionuibk-research-os-v3.hf.space/api/broker | jq '.trades | length'

# 4. Error rate
curl https://gionuibk-research-os-v3.hf.space/api/telemetry | jq '.error_rate_pct'
```

Hệ thống healthy khi:
- Error rate < 5%
- Bars >= 35 cho tất cả symbols
- Ít nhất 1 trade trong 2 giờ đầu
