# Walkthrough - Nâng cấp chất lượng Signal (TASK A)

Chúng tôi đã thiết kế và triển khai một giải pháp toàn diện cho **TASK A**, nâng cấp toàn bộ hệ thống tín hiệu trong Research OS V3 thành kiến trúc 3 lớp vững chắc: **Trigger + Confirmation + Invalidation**.

---

## 1. Danh sách các file đã thay đổi

- **[signal_template_library_v1.json](file:///c:/Users/Black/Downloads/ResearchOS/research-os-v3/signal_template_library_v1.json)**:
  - Cập nhật 12 họ template families để có đủ 8 trường metadata chất lượng.
  - Cập nhật 18 tín hiệu trong `signal_catalog` có đủ biểu thức `trigger_definition`, `confirmation_definition`, `invalidation_definition` và các trường tóm tắt luận điểm (thesis).
- **[research_knowledge/signal_quality_canon_v1.md](file:///c:/Users/Black/Downloads/ResearchOS/research-os-v3/research_knowledge/signal_quality_canon_v1.md)** *[NEW]*:
  - Cẩm nang tiêu chuẩn thiết kế và hướng dẫn viết biểu thức logic cho tín hiệu chất lượng cao.
- **[signal_generator.py](file:///c:/Users/Black/Downloads/ResearchOS/research-os-v3/signal_generator.py)**:
  - Cập nhật trình sinh candidate để tự động tạo 3 biểu thức logic riêng cho từng template family và sinh siêu dữ liệu tương ứng.
- **[signal_orchestrator.py](file:///c:/Users/Black/Downloads/ResearchOS/research-os-v3/signal_orchestrator.py)**:
  - Cập nhật hàm đánh giá tín hiệu để kiểm tra riêng lẻ `triggered`, `confirmed`, và `invalidated`.
  - Triển khai thuật toán tính điểm `confirmation_score` và `invalidation_score` dựa trên độ thỏa mãn của các biểu thức con.
  - Expose hàm built-in `abs()` an toàn trong môi trường sandbox `safe_eval_expression`.
- **[realtime_engine.py](file:///c:/Users/Black/Downloads/ResearchOS/research-os-v3/realtime_engine.py)**:
  - Tích hợp 3 lớp đánh giá tín hiệu mới vào bộ xử lý realtime.
  - Chặn đứng hoàn toàn việc đưa các tín hiệu `"direction": "signal_only"` thành candidate vào lệnh thực tế.
  - Tự động reset trạng thái chiến lược về `standby` nếu tín hiệu bị `invalidated = True`.
- **[tests/test_signal_quality.py](file:///c:/Users/Black/Downloads/ResearchOS/research-os-v3/tests/test_signal_quality.py)** *[NEW]*:
  - Bộ unit test kiểm thử toàn diện toàn bộ các chức năng nâng cấp mới.

---

## 2. Quyết định Thiết kế (Design Decisions)

1. **Đánh giá Biểu thức Sandbox An toàn**: Trong `safe_eval_expression`, chúng tôi truyền trực tiếp hàm `abs` vào ngữ cảnh `safe_dict` để các biểu thức như `abs(TradeFlowImbalance)` có thể chạy mượt mà mà vẫn giữ bảo mật tuyệt đối cho sandbox (không chứa các hàm built-in nguy hiểm khác).
2. **Tính điểm Con (Sub-condition Scoring)**: Hàm `compute_expr_score` tự động phân tách biểu thức qua các từ khóa `and`/`or` để đo lường mức độ đồng thuận của thị trường đối với luận điểm (đạt giá trị từ `0.0` đến `1.0`).
3. **Quản lý Vòng đời Candidate**: Chúng tôi định nghĩa `thesis_state` rõ ràng:
   - `'aligned'`: Khi tín hiệu `active` và sẵn sàng.
   - `'invalidated'`: Khi điều kiện phủ định xảy ra.
   - `'not_triggered'`: Khi chưa khớp điều kiện trigger ban đầu.

---

## 3. Ví dụ 3 Signals Trước và Sau nâng cấp

### 1. `bollinger_squeeze_breakout`
*   **Trước**: Chỉ kiểm tra phá vỡ dải Bollinger thô.
*   **Sau**:
    *   *Trigger*: `BollingerWidth <= 0.15`
    *   *Confirmation*: `RelativeVolume >= 1.2 and abs(TradeFlowImbalance) >= 0.2`
    *   *Invalidation*: `BollingerWidth > 0.3 or SpreadBps > 10.0`

### 2. `zscore_recenter`
*   **Trước**: Chỉ kiểm tra z-score vượt ngưỡng.
*   **Sau**:
    *   *Trigger*: `abs(zscore_close_20) >= 1.5`
    *   *Confirmation*: `rsi_14 <= 30 or rsi_14 >= 70`
    *   *Invalidation*: `abs(zscore_close_20) > 3.0 or volatility_ratio_5_20 > 1.5`

### 3. `macd_trend_continuation`
*   **Trước**: Kiểm tra giao cắt MACD cơ bản.
*   **Sau**:
    *   *Trigger*: `MACD > MACD_signal and ema_spread_8_21 > 0`
    *   *Confirmation*: `MACD_hist > 0 and RelativeVolume >= 1.0`
    *   *Invalidation*: `MACD <= MACD_signal or price_vs_sma20 < -0.02`

---

## 4. Cơ chế hoạt động của Logic Active hiện tại

Logic hoạt động realtime tuân thủ quy trình sau:
1.  **Đánh giá điều kiện thị trường**: Trích xuất các chỉ số thô kỹ thuật từ WebSocket feed.
2.  **Đánh giá 3 lớp**:
    *   `triggered = safe_eval(trigger_definition)`
    *   `confirmed = safe_eval(confirmation_definition)` (nếu có, mặc định là True)
    *   `invalidated = safe_eval(invalidation_definition)` (nếu có, mặc định là False)
3.  **Quyết định Tín hiệu**:
    `active = triggered and confirmed and not invalidated and regime_ok and tradable`
4.  **Hành động của Chiến lược**:
    *   Nếu `active = True` và không phải `signal_only` -> Gán chiến lược thành trạng thái `candidate` (vị thế tiềm năng).
    *   Nếu `invalidated = True` hoặc `active = False` -> Reset chiến lược về `standby`.

---

## 5. Kết quả Kiểm thử

- Chạy unit test riêng: `tests/test_signal_quality.py` -> **100% PASS** (5 tests).
- Chạy bộ test hệ thống: `run_full_test_suite.py` -> **100% PASS** (42 tests).
- Chạy thử nghiệm Alpha Factory Demo: `alpha_factory_demo_v1.py` -> **Thành công hoàn toàn**.
