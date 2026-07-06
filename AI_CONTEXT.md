# AI_CONTEXT.md — Bộ Nhớ Vĩnh Cửu Cho AI Assistant

> **Mục đích:** File này là bộ nhớ liên session của AI assistant.
> Đọc file này TRƯỚC KHI làm việc với bạn để khôi phục context.
> Cập nhật file này SAU MỖI session quan trọng.

---

## 🧠 Những Gì AI Cần Biết Ngay

### Người dùng là ai
- Handle: **Black101081**
- Mục tiêu: Xây dựng Research OS V3 — hệ thống **nghiên cứu alpha** và paper trading tự động trên Hyperliquid
- Phong cách: Thích đi thẳng vào vấn đề. Không thích giải pháp tệ khi có giải pháp tốt hơn. Phê bình thẳng thắn nếu AI nói sai.
- **Ngôn ngữ:** Tiếng Việt

### Triết lý hệ thống (QUAN TRỌNG)
> "Công cụ là để nghiên cứu regime và alpha. Không phải mục đích cuối."
> "Phải vượt qua sự phổ thông thì mới có chiến lược của mình. Nếu không thì làm sao thắng được."

Ưu tiên đúng: **Regime chuẩn trước** → chọn indicators khai thác được regime → chọn signal family → validate bằng data

---

## 📊 Kiến Trúc Hiện Tại (Thực Tế)

### Regime Engine — Vấn đề cốt lõi chưa giải quyết
- **Hiện tại:** 5 regime rule-based, threshold hardcode, không validated
  - `uptrend`, `downtrend`, `range_chop`, `high_volatility`, `transition_ambiguous`
- **Vấn đề:** MACD(12,26,9) thiết kế cho daily 1979, trên m1 là noise. RSI14 trên m1 overfit microstructure. Threshold không được validate trên BTC/ETH/SOL Hyperliquid 2025-2026.
- **Mục tiêu:** Xây lại với indicators đúng TF, data-driven, có backtest validation
- **NOTE:** “7 regime” được nhắc đến trong chat nhưng **chưa có spec cụ thể** — cần xây dựng lại từ đầu

### Indicator Layer — Sai từ gốc
| Indicator | Thiết kế gốc | Trên m1 thực tế |
|-----------|--------------|-------------------|
| MACD(12,26,9) | Daily —26 ngày trend | 26 phút = random noise |
| RSI14 | Daily −2 tuần momentum | 14 phút overfit microstructure |
| ZScore20 | 20 bars context | 20 phút quá ngắn cho mean reversion |
| ATR14 | Daily range thực | m1 ATR tiny, SL bị sweep liên tục |
| Divergence | m5 minimum | m1 fractal 100% false positives |

**Kết luận từ log chat:** Hệ thống đang xây trên nền sai. Không phải thiếu vài cái mà là sai từ tư tưởng nền.

### Khoảng cách thực tế
| Layer | Hiện có | Cần | Thiếu quan trọng nhất |
|-------|----------|------|------------------------|
| Factors | 19 | ~60 | ADX, VWAP deviation, OI, funding rate, orderbook depth |
| Indicators | 18 | ~80 | EMA stack, Keltner, Donchian, VWAP bands, multi-TF bias |
| Signals | 3 active | 20-30 | Tất cả 7 families chỉ có 3 implements |
| Strategies | 3 | 10-15 | Không có asset-specific, không có multi-TF |
| Quality Gate | 4 checks | 14 | Không có WFO, Sharpe gate, decay tracking |
| Timeframe | m1 only | m1/m5/m15/1h | SOL và ETH m1 = noise floor |

---

## 🏗️ Kiến Trúc 4 Tầng Cần Xây

### Tầng 1 — Multi-Timeframe Engine (quan trọng nhất)
Hyperliquid WS hỗ trợ đầy đủ multi-TF:
```
{"method":"subscribe","subscription":{"type":"candle","coin":"BTC","interval":"5m"}}
Supported: 1m, 3m, 5m, 15m, 30m, 1h, 2h, 4h
Limit: 1000 subscriptions per IP — 3 coins x 4 TF x 3 types = 36 subs
```

Asset-TF fitness rules:
- **BTC m1**: scalp signals, momentum, order flow
- **BTC m5**: breakout, continuation
- **ETH m5**: mean reversion, BB
- **ETH m15**: trend following
- **SOL m15**: breakout, divergence
- **SOL 1h**: trend following, cross-asset

### Tầng 2 — Factor/Indicator Layer nâng cấp
Theo thứ tự ROI cao nhất:
1. **ADX/DMI** — trend strength filter, loại 60% false breakout
2. **VWAP deviation bands** — institutional reference price
3. **OBV/CVD** (Cumulative Volume Delta) — real order flow
4. **EMA stack** (9/21/50/200) — trend structure
5. **Keltner Channel** — volatility-adjusted mean reversion
6. **Funding rate z-score** — crypto-native unique alpha
7. **Open Interest change** — conviction filter
8. **Stochastic KD** — timing oscillator
9. **Volume Profile** (POC/VAH/VAL) — key levels

### Tầng 3 — Signal Library thực chiến
Signal tiers (theo độ unique):
- **Tier 1 — Unique Alpha** (crypto-native): `funding_rate_reversion`, `oi_spike_reversal`, `liquidation_cascade_entry`, `perp_basis_arbitrage`
- **Tier 2 — Multi-TF Alignment**: `htf_trend_m15_entry_m1`, `vwap_daily_reversion`, `daily_level_reaction`
- **Tier 3 — Order Flow**: `cvd_breakout`, `large_block_absorption`, `bid_ask_flip_momentum`

### Tầng 4 — Quality Gate thực sự
Mọi signal phải pass TRƯỚC khi vào live:
```
gate1: min 200 trade samples
gate2: Sharpe >= 0.8 out-of-sample
gate3: Win rate >= 42%
gate4: Profit factor >= 1.3
gate5: Max drawdown <= 15%
gate6: regime_conditional_performance (uptrend/downtrend separate)
gate7: asset_tf_fitness score >= 0.6
gate8: signal_correlation < 0.7 (không overlap với existing)
gate9: walk_forward_stability >= 0.7 (IS vs OOS Sharpe ratio)
```
Auto-demote nếu: live_sharpe < 0.3 trong 50 trades gần nhất

---

## 📝 Signal Families Hiện Tại (29 signals trong catalog)
```
FAMILY_CONTINUATION    → macd_trend_continuation, ema_crossover_trend_entry
FAMILY_DIVERGENCE       → rsi_divergence, rsi_divergence_reversal
FAMILY_BREAKOUT         → bb_squeeze_breakout, high_vol_momentum_burst
FAMILY_MEAN_REVERSION   → mean_reversion, liquidation_snap_back, perp_basis_reversion,
                           vwap_deviation_snap, range_high_low_fade, zscore_vol_adjusted_reversion
FAMILY_ORDER_FLOW       → order_flow_imbalance, micro_momentum_scalp
FAMILY_VOLATILITY_EVENT → volatility_event
FAMILY_FUNDING          → funding_reversion
```

---

## 🔧 Trạng Thái Kỹ Thuật Hiện Tại (cập nhật 2026-07-06)

### Đã fix hôm nay
| Commit | Vấn đề | Fix |
|--------|--------|-----|
| `3cdc330` | Missing config keys | Thêm `symbols`, `candle_interval`, `write_every_seconds` |
| `de5ef78` | `evaluate_all_signals` gọi 8 lần | Batch cache per TF |
| `4a1156c` | `transition_ambiguous` block hết trade | 3-tier adaptive tradability |
| `e56a644` | Registry write hang dashboard | asyncio.wait_for timeout=5s |
| `a9b46a9` | Quality Gate không wire vào broker | Fix `on_qualified_signal` |

### Các bugs đã biết, đã fix trước đó
- `regime_engine.py` if-elif reorder (`range_chop` bị dead code) → đã fix
- `prevBollingerWidth` capture sau update (regression) → đã fix
- `closecount` threshold 10 vs 35 → đã fix (35)
- `signal_orchestrator.py` JSON load 1 lần khi import → đã fix
- Paper broker không được dispatch → đã fix

### Vấn đề cốt lõi CHƯ A giải quyết
- [ ] **Regime engine:** threshold hardcode, không validated, dùng indicators sai TF
- [ ] **Multi-TF architecture:** chỉ có m1, cần m1/m5/m15/1h
- [ ] **Indicator layer:** thiếu ADX, CVD, VWAP, Keltner, Funding z-score
- [ ] **Signal library:** 3/7 families có ý nghĩa — 4 families chưa có real edge
- [ ] **Quality Gate:** chỉ 4 checks, thiếu WFO, Sharpe gate, decay

---

## 🗺️ Roadmap Đúng Thứ Tự Ưu Tiên

```
1. [NEXT] Xây Multi-TF Engine — subscribe m5/m15/1h trên Hyperliquid WS
   └─ Đã có prompt Tầng 1 hoàn chỉnh từ session trước, hỏi người dùng

2. [NEXT] Thêm ADX, CVD, VWAP deviation vào factor_math.py
   └─ ROI cao nhất, loại false signals ngay tại nguồn

3. [LATER] Rebuild regime_engine.py — sử dụng ADX + ATR multi-TF
   └─ Sau khi có indicators đúng mới classify được regime chính xác

4. [LATER] Backtest/validate regime labels trên historical data
   └─ Tool có sẵn: bootstrap_ohlcv.py + baseline_backtest_runner.py

5. [LATER] Tune signal family → regime mapping dựa trên win rate thực tế
```

---

## 💬 Câu Hỏi Cần Hỏi Khi Bắt Đầu Session Mới

1. **"Hệ thống hiện tại đang ở trạng thái gì? Active Specs là bao nhiêu? Có trade nào chạy không?"**
2. **"Bạn muốn tiếp tục từ điểm nào? Multi-TF Engine, Indicator layer, hay Regime rebuild?"**

---

## 📝 Log Session

### Session 2026-07-06 (buổi sáng)
- Bắt đầu: Active Specs = 0, không có trade nào
- Fix 5 bugs kỹ thuật trong signal_orchestrator, config, risk_engine, app.py
- Phát hiện root cause = regime block cứng, fix 3-tier tradability
- Người dùng nhắc: **mục tiêu thực sự là regime chuẩn, không phải fix bugs mãi**
- Phục hồi context từ file log chat (675KB) — tìm được toàn bộ kiến trúc 4 tầng, signal library, indicator roadmap
- Kết luận: **"7 regime" chưa có spec cụ thể** trong log — cần xây dựng mới
- Tạo AI_CONTEXT.md này làm bộ nhớ vĩnh cửu
