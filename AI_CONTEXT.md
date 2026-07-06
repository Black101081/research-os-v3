# AI_CONTEXT.md — Bộ Nhớ Vĩnh Cửu Cho AI Assistant

> **Mục đích:** File này là bộ nhớ liên session của AI assistant (Perplexity/Claude).
> Đọc file này TRƯỚC KHI làm việc với bạn để khôi phục context.
> Cập nhật file này SAU MỖI session quan trọng.

---

## 🧠 Những Gì AI Cần Biết Ngay

### Người dùng là ai
- Handle: **Black101081**
- Mục tiêu: Xây dựng Research OS V3 — hệ thống nghiên cứu alpha và paper trading tự động trên Hyperliquid
- Phong cách làm việc: Thích đi thẳng vào vấn đề, không thích giải pháp tệ hơn khi có giải pháp tốt hơn
- Hay gọi AI là "bạn" hoặc "sếp" theo ngữ cảnh 😄
- **Ngôn ngữ:** Tiếng Việt

### Triết lý hệ thống
- Công cụ là để **nghiên cứu regime và alpha**, không phải mục đích cuối
- Ưu tiên: **Regime chuẩn trước** → chọn indicators khai thác được regime → chọn signal family phù hợp
- Không trade blindly — mọi signal đều phải có thesis rõ ràng gắn với regime

---

## 📋 Decisions Đã Thống Nhất

### Regime Engine
- **Hiện tại (đã implement):** 5 regime cứng, rule-based, threshold hardcode
  - `uptrend`, `downtrend`, `range_chop`, `high_volatility`, `transition_ambiguous`
  - Đã nâng lên 3-tier tradability: `full` / `selective` / `cautious` / `blocked`
- **Mục tiêu:** Xây lại thành **7 regime** (chưa implement — cần khôi phục spec từ session cũ)
- **⚠️ QUAN TRỌNG:** Spec 7 regime + 5 họ indicators đã được thảo luận trong session trước nhưng chưa được ghi lại. Hỏi người dùng để paste lại.

### Indicator Architecture
- **Mục tiêu:** Chia indicators thành **5 họ** (chưa có spec — hỏi người dùng)
- Hiện tại: Tất cả indicators gộp chung trong `factor_math.py`, không phân họ

### Signal Families (đã implement)
```
FAMILY_CONTINUATION      → macd_trend_continuation
FAMILY_DIVERGENCE         → rsi_divergence
FAMILY_BREAKOUT           → bb_squeeze_breakout
FAMILY_MEAN_REVERSION     → mean_reversion
FAMILY_ORDER_FLOW         → order_flow_imbalance
FAMILY_VOLATILITY_EVENT   → volatility_event
FAMILY_FUNDING_REVERSION  → funding_reversion
FAMILY_OI_REVERSAL        → oi_reversal
```

---

## 🔧 Trạng Thái Kỹ Thuật Hiện Tại

### Đã fix hôm nay (2026-07-06)
| Commit | Vấn đề | Fix |
|--------|--------|-----|
| `3cdc330` | Missing config keys crash startup | Thêm `symbols`, `candle_interval`, `write_every_seconds` vào config.json |
| `de5ef78` | `evaluate_all_signals` gọi 8 lần thay vì 1 | Refactor sang batch cache per TF |
| `4a1156c` | `transition_ambiguous` block tất cả trade | 3-tier adaptive tradability |
| `e56a644` | Registry write hang dashboard | asyncio.wait_for timeout=5s |
| `a9b46a9` | Quality Gate không wire vào broker | Fix `_emit_signal` → `on_qualified_signal` |
| `bbf546e` | Writer loop guard condition sai | Fix execution guard |

### Vấn đề còn lại (chưa fix)
- [ ] `regime_engine.py` — threshold hardcode, không validated, cần rebuild thành 7 regime
- [ ] Mock `sym_state` flat bars → đã fix bằng skip, nhưng signal library evaluation bị mất khi không có real sym_state
- [ ] Regime spec chưa được document → **cần hỏi người dùng**
- [ ] 5 họ indicators chưa được define → **cần hỏi người dùng**

### Active Specs vẫn = 0 ?
- Sau khi fix 3-tier tradability, cần restart Space
- Nếu vẫn 0: kiểm tra `regime_state.tradable` trong `/api/snapshot` → xem `trade_tier` là gì
- Fallback: kiểm tra `logic_ready` và `risk_status` trong strategy state

---

## 🗺️ Roadmap Thực Sự (Theo Đúng Thứ Tự Ưu Tiên)

```
1. [PENDING] Rebuild regime_engine.py → 7 regime, data-driven, validated
   └─ Cần spec 7 regime từ người dùng

2. [PENDING] Define 5 họ indicators + map từng họ vào regime
   └─ Cần spec từ người dùng

3. [PENDING] Backtest/validate regime labels trên historical data
   └─ Tool có sẵn: bootstrap_ohlcv.py + baseline_backtest_runner.py

4. [PENDING] Tune signal family → regime mapping dựa trên win rate thực tế

5. [IN PROGRESS] Fix bugs kỹ thuật để paper trading chạy được
   └─ Đủ stable để collect data cho bước 3
```

---

## 💬 Câu Hỏi Cần Hỏi Ngay Khi Bắt Đầu Session Mới

1. **"Bạn có spec 7 regime và 5 họ indicators từ session trước không? Paste vào đây để tôi tiếp tục."**
2. **"Active Specs hiện tại là bao nhiêu? Hệ thống đang ở trạng thái gì?"**

---

## 📝 Log Session

### Session 2026-07-06 (sáng)
- Toàn bộ thời gian dành cho fix bugs kỹ thuật
- Phát hiện root cause `Active Specs: 0` = regime block cứng
- Fix 3-tier tradability
- Phát hiện 5 vấn đề khác trong signal_orchestrator + config + risk_engine
- Người dùng nhắc: **mục tiêu thực sự là regime chuẩn, không phải fix bugs mãi**
- Kết luận: cần khôi phục spec 7 regime + 5 họ indicators từ session cũ
