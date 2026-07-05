# Signal Quality Canon v1 — Tiêu chuẩn Chất lượng Tín hiệu Giao dịch

Cẩm nang này định nghĩa các nguyên tắc thiết kế, phát triển và thẩm định tín hiệu giao dịch (Signal) trong hệ thống Research OS V3. Mọi Signal sinh ra bởi các mô-đun Generator, đăng ký trong Registry hoặc chạy realtime trong Orchestrator đều phải tuân thủ nghiêm ngặt cẩm nang này.

---

## 1. Triết lý Thiết kế 3 Lớp (Trigger, Confirmation, Invalidation)

Một tín hiệu giao dịch tốt không chỉ là một điều kiện đơn giản. Nó bao gồm ba thành phần logic bổ trợ lẫn nhau:

### 1.1 Trigger (Lớp kích hoạt)
- **Định nghĩa**: Điều kiện ban đầu để phát hiện sự thay đổi cấu trúc hoặc trạng thái thị trường.
- **Mục tiêu**: Đánh giá xem có dấu hiệu biến động hay cơ hội tiềm năng hay không.
- **Ví dụ**:
  - `BollingerWidth <= 0.15` (Nén độ biến động)
  - `rsi_14 <= 30` (Quá bán)
  - `MACD > MACD_signal` (Giao cắt động lượng)

### 1.2 Confirmation (Lớp xác nhận)
- **Định nghĩa**: Bộ lọc chất lượng nhằm xác nhận rằng trigger có độ tin cậy cao và không bị chống lại bởi các yếu tố dòng tiền hoặc khối lượng lớn.
- **Mục tiêu**: Giảm thiểu tối đa tín hiệu sai (false positive) trong các giai đoạn thanh khoản mỏng hoặc bẫy giá.
- **Ví dụ**:
  - `RelativeVolume >= 1.2` (Xác nhận dòng tiền tham gia)
  - `abs(TradeFlowImbalance) >= 0.2` (Xác nhận hướng mua/bán chủ động đồng thuận)
  - `market_correlation_20 >= 0.7` (Xác nhận tính liên kết với xu hướng chung của BTC)

### 1.3 Invalidation (Lớp vô hiệu hóa)
- **Định nghĩa**: Điều kiện phủ định giả thuyết đầu tư ban đầu, cho thấy cơ hội đã trôi qua hoặc bẫy giá đã sập.
- **Mục tiêu**: Hủy bỏ vị thế/kế hoạch giao dịch ngay lập tức nếu thị trường đi ngược lại luận điểm cốt lõi trước khi khớp lệnh.
- **Ví dụ**:
  - `BollingerWidth > 0.3` (Squeeze thất bại, độ biến động bung quá rộng ngoài dự kiến)
  - `SpreadBps > 10.0` (Chênh lệch giá mua/bán quá rộng, rủi ro trượt giá cao)
  - `price_vs_sma20 < -0.015` (Xu hướng chính bị gãy cấu trúc)

---

## 2. Tiêu chuẩn Biểu thức Logic (Python-Evaluated Expressions)

Các biểu thức phải được viết dưới dạng cú pháp Python hợp lệ, trả về giá trị kiểu boolean (`True`/`False`) khi được đánh giá bởi `eval()` trong môi trường chứa các chỉ báo kỹ thuật thô.

### 2.1 Từ khóa và Tên biến hợp lệ (indicator_keys)
Luôn sử dụng các khóa chỉ báo chuẩn đã được đăng ký:
- `BollingerWidth` (Độ rộng dải Bollinger)
- `bb_pct_b` (Vị trí giá trong dải Bollinger, từ 0 đến 1)
- `rsi_14`, `rsi_7` (Chỉ số sức mạnh tương đối)
- `MACD`, `MACD_signal`, `MACD_hist` (Các thành phần MACD)
- `RelativeVolume` hoặc `rel_volume_20` (Khối lượng tương đối)
- `TradeFlowImbalance` hoặc `trade_flow_imbalance_20` (Sự mất cân bằng dòng lệnh mua/bán)
- `large_trade_ratio` (Tỷ lệ lệnh lớn của tổ chức)
- `SpreadBps` (Chênh lệch giá mua bán tính theo điểm cơ bản)
- `btc_ret_1` (Lợi suất nến gần nhất của BTC)
- `market_correlation_20` (Hệ số tương quan của tài sản với BTC)

### 2.2 Quy tắc viết biểu thức
1. **Không sử dụng magic numbers vô căn cứ**: Các ngưỡng số phải tương thích với giá trị bình thường hóa (ví dụ: Z-Score từ -3.0 đến 3.0, rsi từ 0 đến 100, pct_b từ 0.0 đến 1.0).
2. **Luôn sử dụng toán tử viết thường**: `and`, `or`, `not` thay vì viết hoa hoặc ký hiệu toán học kiểu `&&`, `||`, `!`.
3. **An toàn kiểu dữ liệu**: Đảm bảo các so sánh số học không so sánh kiểu chuỗi (string) hoặc giá trị `None`.

---

## 3. Tiêu chuẩn cho từng họ Chiến lược (Strategy Families)

### 3.1 Breakout (Phá vỡ)
- **Confirmation**: Đòi hỏi sự đồng thuận của khối lượng tương đối (`RelativeVolume >= 1.2`) và dòng tiền (`TradeFlowImbalance` đồng hướng).
- **Invalidation**: Vô hiệu hóa ngay lập tức nếu giá quay ngược lại vùng tích lũy hoặc chênh lệch giá mua/bán (`SpreadBps`) giãn rộng đột biến.

### 3.2 Mean Reversion (Đảo chiều về giá trị trung bình)
- **Confirmation**: Xác nhận bằng các chỉ số dao động ở vùng cực hạn (`rsi_14 <= 30` hoặc `>= 70`) kết hợp với sự suy kiệt lực bán/mua chủ động.
- **Invalidation**: Tránh bẫy "bám biên" (band walking). Vô hiệu hóa nếu độ lệch chuẩn hoặc Z-Score tiếp tục giãn rộng vượt mức chịu đựng (ví dụ: `abs(zscore) > 3.0`).

### 3.3 Continuation (Tiếp diễn xu hướng)
- **Confirmation**: Chỉ báo xu hướng trung hạn (`ema_spread_8_21`) đồng thuận và khối lượng duy trì ở mức trung bình.
- **Invalidation**: Gãy cấu trúc hỗ trợ động (ví dụ: giá đóng cửa cắt qua đường SMA20).

### 3.4 Order Flow (Dòng lệnh microstructure)
- **Confirmation**: Sự mất cân bằng dòng tiền kéo dài (`trade_flow_imbalance_50`) đồng thuận với khối lượng giao dịch lớn của tổ chức (`large_trade_ratio`).
- **Invalidation**: Dòng tiền đảo chiều nhanh chóng hoặc chênh lệch spread vượt ngưỡng cho phép.

---

## 4. Ví dụ Tín hiệu Điển hình

### 4.1 Tín hiệu Chuẩn (Good Practice)
- **Signal**: `bollinger_squeeze_breakout`
  - **Trigger**: `BollingerWidth <= 0.15`
  - **Confirmation**: `RelativeVolume >= 1.2 and abs(TradeFlowImbalance) >= 0.2`
  - **Invalidation**: `BollingerWidth > 0.3 or SpreadBps > 10.0`
  *Luận điểm*: Xác định điểm nén chặt, chỉ kích hoạt khi có lực đẩy lớn từ volume & tape, hủy bỏ nếu biến động nổ ra quá rộng mà không có hướng đi ổn định hoặc trượt giá lớn.

### 4.2 Tín hiệu Tồi (Bad Practice)
- **Signal**: `bad_rsi_reversion`
  - **Trigger**: `rsi_14 < 30`
  - **Confirmation**: `None`
  - **Invalidation**: `None`
  *Lỗi*: Chỉ có trigger đơn độc, sẽ liên tục kích hoạt lệnh mua khi thị trường rơi tự do (gây cháy tài khoản do bẫy bắt dao rơi).
