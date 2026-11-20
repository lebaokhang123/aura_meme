# TÀI LIỆU BÀN GIAO KỸ THUẬT — TASK 5: PREMIUM SANDBOX & VNPAY ADAPTER

**Mã Task:** TASK-5-PREMIUM-SANDBOX  
**Nhánh Git:** `feat/premium-sandbox-task5`  
**Base Commit:** `8c8ba24` (`docs(task4): tài liệu bàn giao kỹ thuật chuẩn hóa level, chức danh và ui polish`)  
**Kỹ sư thực hiện:** Google Antigravity (Gemini Flash)  
**Đơn vị giám sát & điều phối:** ChatGPT  
**Cấp thẩm quyền nghiệm thu:** AuraMeme Project Owner  
**Ngày hoàn thành:** 21/11/2026  

---

## 1. TỔNG QUAN YÊU CẦU & QUYẾT ĐỊNH CỦA OWNER

### 1.1. Bối cảnh dự án
AuraMeme là nền tảng đồ án và portfolio Web/DevOps cao cấp (Cyberpunk Cultivation Meme Platform). Theo chỉ đạo của Owner, hệ thống gói hội viên (Premium) được xây dựng dưới hình thức **Môi trường thử nghiệm Sandbox (Sandbox Trial Flow)**, phục vụ kiểm thử end-to-end trọn vẹn luồng đăng ký, quản lý gói, và tích hợp cổng thanh toán mà **tuyệt đối không phát sinh giao dịch tiền thật**.

### 1.2. Quyết định của Owner về bảng giá
Owner đã phê duyệt bảng giá chuẩn cho 2 gói hội viên:
1. **Aura Plus:** `$5` USD / 30 ngày (quy đổi tham chiếu VNPAY: `125.000 đ`, hệ số `×2` bonus Level XP).
2. **Aura Prime:** `$50` USD / 365 ngày (quy đổi tham chiếu VNPAY: `1.250.000 đ`, hệ số `×3` bonus Level XP).

### 1.3. Nguyên tắc an toàn & Ranh giới kỹ thuật
- **Authoritative Backend Pricing:** Toàn bộ giá gói, thời hạn và hệ số quyền lợi được lưu trữ và kiểm soát độc quyền tại backend (`backend/app/premium_plans.py`). Backend không bao giờ tin tưởng giá do frontend gửi lên.
- **Fail-Closed VNPAY VND Gate:** VNPAY Sandbox thanh toán bằng VND. Thuộc tính `vnpay_pricing_approved` được cấu hình mặc định là `False` (fail-closed). Khi chưa có phê duyệt chính thức bằng văn bản/chỉ đạo từ Owner, cổng thanh toán VNPAY Sandbox sẽ từ chối mở checkout để bảo đảm tuyệt đối tính an toàn tỷ giá.
- **Order Snapshot Immutability:** Khi người dùng tạo đơn hàng, thông tin gói (`plan_type`), số tiền (`amount_usd_cents`, `amount_vnd`), đơn vị tiền tệ, thời hạn (`duration_days`) và mã đơn (`order_code`) được đóng băng cố định vào bảng `subscription_orders`. Mọi callback VNPAY IPN/Return đều kiểm tra đối chiếu chữ ký HMAC-SHA512 và số tiền chính xác từng xu (`vnp_Amount == expected_amount * 100`).
- **Bảo toàn Game Mechanics Aura V1:** Hệ số `multipliers_enabled = false` tại `backend/app/aura.py` được giữ nguyên để bảo đảm tính công bằng tuyệt đối cho bảng xếp hạng Aura Rank trong phạm vi MVP V1.

---

## 2. KIẾN TRÚC & TRIỂN KHAI BACKEND

### 2.1. Cấu hình & Settings (`backend/app/config.py`)
Bổ sung `PremiumSettings` kế thừa BaseSettings với cơ chế nạp biến môi trường tự động:
- `premium_sandbox_enabled: bool = True`
- `vnpay_tmn_code: str = "AURAMEME"`
- `vnpay_hash_secret: str = "AURAMEME_SANDBOX_SECRET_KEY_512"`
- `vnpay_payment_url: str = "https://sandbox.vnpayment.vn/paymentv2/vpcpay.html"`
- `vnpay_return_url: str = "http://localhost:5173/premium"`
- `vnpay_price_plus_vnd: int = 125000`
- `vnpay_price_prime_vnd: int = 1250000`
- `vnpay_pricing_approved: bool = False` (mặc định đóng, bảo vệ tỷ giá).

### 2.2. Định nghĩa gói hội viên (`backend/app/premium_plans.py`)
Mô hình dữ liệu bất biến định nghĩa rõ:
- `PREMIUM_PLANS['plus']`: 30 ngày, 500 cents ($5), bonus multiplier 2.0x.
- `PREMIUM_PLANS['prime']`: 365 ngày, 5000 cents ($50), bonus multiplier 3.0x.
Hàm `resolve_plan(plan_type)` trả về snapshot dữ liệu tin cậy.

### 2.3. VNPAY Adapter Sandbox (`backend/app/vnpay_adapter.py`)
Hiện thực hóa chuẩn giao thức VNPAY:
- Sắp xếp alphabet toàn bộ tham số `vnp_*` theo đúng chuẩn RFC.
- Tính toán mã băm kiểm tra toàn vẹn dữ liệu bằng thuật toán `HMAC-SHA512`.
- Kiểm tra chữ ký số chiều về (`verify_response`), phát hiện và chặn đứng mọi hành vi giả mạo tham số (tamper detection).
- Đóng gói URL thanh toán VNPAY an toàn.

### 2.4. Mô hình cơ sở dữ liệu (`backend/app/models.py` & `docs/design/03-database.dbml`)
Thiết kế 2 bảng theo chuẩn PostgreSQL & SQLAlchemy 2.0 ORM:
1. `subscription_orders`:
   - `id`: UUID Primary Key.
   - `user_id`: Foreign Key liên kết `users.id` (ON DELETE CASCADE).
   - `order_code`: Mã đơn duy nhất (`AM-SUB-YYYYMMDD-...`, UNIQUE index).
   - `plan_type`: Loại gói (`plus`, `prime`).
   - `provider`: Cổng thanh toán (`sandbox_simulated`, `vnpay`).
   - `amount_usd_cents`: Số tiền cố định USD tính theo cents.
   - `amount_vnd`: Số tiền cố định quy đổi VND.
   - `duration_days`: Thời hạn sử dụng (30 hoặc 365 ngày).
   - `status`: Trạng thái đơn (`pending`, `paid`, `failed`, `cancelled`, `expired`).
   - `raw_response_json`: Lưu vết JSON payload phản hồi phục vụ audit log.
   - `created_at`, `updated_at`.
2. `user_subscriptions`:
   - `id`: UUID Primary Key.
   - `user_id`: Foreign Key liên kết `users.id` (UNIQUE, 1 active subscription per user).
   - `tier`: Cấp độ gói (`plus`, `prime`).
   - `status`: Trạng thái (`active`, `expired`, `cancelled`).
   - `started_at`, `expires_at`.
   - `multiplier`: Hệ số XP bonus (2.0 hoặc 3.0).
   - `last_order_id`: UUID tham chiếu đơn hàng kích hoạt gần nhất.
   - `created_at`, `updated_at`.

### 2.5. Migration Alembic (`backend/alembic/versions/0014_premium_sandbox.py`)
Tạo migration an toàn với lock timeout 5 giây, bảo đảm zero downtime và tuân thủ schema contract với DBML.

### 2.6. API Endpoints (`backend/app/premium.py`)
Mounted tại `/api/v1/premium`:
- `GET /status`: Lấy trạng thái gói của người dùng hiện tại, số ngày còn lại, danh sách gói niêm yết và trạng thái cấu hình VNPAY.
- `POST /orders`: Khởi tạo đơn hàng mới (yêu cầu session hợp lệ và CSRF token).
- `POST /orders/{order_code}/simulate`: Endpoint sandbox mô phỏng thanh toán (`pay_success`, `pay_fail`, `cancel`). Khi mô phỏng thành công, hệ thống tự động cộng dồn ngày sử dụng nếu người dùng đã có gói trước đó.
- `GET /vnpay-return`: Nhận chuyển hướng từ trình duyệt sau thanh toán VNPAY, kiểm tra chữ ký HMAC, cập nhật trạng thái đơn và kích hoạt gói.
- `GET /vnpay-ipn`: Endpoint server-to-server xử lý IPN chuẩn mã VNPAY (`00` thành công, `01` đơn không tồn tại, `02` đơn đã xử lý, `04` sai số tiền, `97` sai chữ ký).

---

## 3. GIAO DIỆN & TRẢI NGHIỆM NGƯỜI DÙNG (FRONTEND)

### 3.1. Trang `/premium` (`frontend/src/components/PremiumPage.jsx`)
- **Hiển thị giá rõ ràng:**
  - Aura Plus: `$5` / 30 ngày (VI: `$5 · 30 ngày`, EN: `$5 · 30 days`).
  - Aura Prime: `$50` / 365 ngày (VI: `$50 · 365 ngày`, EN: `$50 · 365 days`) kèm badge `×3 XP`.
  - Duration pill và price tag tự động chuyển đổi theo gói đang chọn.
- **Bỏ thông báo cũ:** Đã xóa bỏ hoàn toàn các thông báo cũ như `"Giá chưa công bố"`, `"Chưa mở đăng ký"`.
- **Badge Sandbox:** Tiêu đề phụ hiển thị rõ ràng `"Thử nghiệm Sandbox"` / `"Sandbox Trial"` với dot neon cyan phát sáng.
- **Active Subscription Banner:** Khi người dùng đang sở hữu gói hoạt động, giao diện hiển thị banner thông báo nổi bật:
  `Gói đang kích hoạt: Aura PLUS · Còn 30 ngày`
- **CTA thích ứng:**
  - Khách vãng lai (Guest): Nút `"Đăng nhập để thử nghiệm"` -> Bấm vào điều hướng sang `/login?next=%2Fpremium`.
  - Người dùng đã đăng nhập: Nút `"Thử nghiệm gói Plus ($5)"` -> Mở Sandbox Dialog.
  - Người dùng đang kích hoạt đúng gói đó: Nút `"Gói đang kích hoạt (còn X ngày)"`.

### 3.2. Hộp thoại Thử nghiệm Sandbox (Sandbox Payment Dialog)
- Thiết kế theo chuẩn `workspace-dialog` đồng bộ với hệ thống Admin/Workspace của AuraMeme.
- Hiển thị bảng tóm tắt chi tiết: Gói hội viên, Giá niêm yết (USD), Giá quy đổi VNPAY (VND), Thời hạn sử dụng, Quyền lợi bonus XP.
- Khung lưu ý màu tím/xanh: Nhắc nhở người dùng đây là môi trường thử nghiệm giả lập dành cho portfolio đồ án, không trừ tiền thật và không yêu cầu thẻ tín dụng.
- **3 tùy chọn hành động:**
  1. `[Thanh toán tức thì (Mô phỏng thành công)]`: Tạo đơn hàng và kích hoạt gói ngay lập tức, tự động cập nhật banner và số ngày còn lại.
  2. `[Mô phỏng Thất bại / Hủy đơn]`: Kiểm chứng xử lý lỗi an toàn mà không làm hỏng trạng thái hệ thống.
  3. `[Cổng VNPAY Sandbox]`: Nút bị vô hiệu hóa kèm badge `"Chờ duyệt giá VND"` khi `vnpay_pricing_approved=False`. Khi được Owner duyệt mở, nút sẽ tự động kích hoạt chuyển hướng sang cổng sandbox của VNPAY.

---

## 4. KẾT QUẢ KIỂM THỬ & MINH CHỨNG (TEST EVIDENCE)

### 4.1. Backend Unit & Non-Integration Tests
```powershell
.\.venv_p2\Scripts\python.exe -m pytest tests/test_premium_sandbox.py tests/test_migrations.py tests/test_health.py -q
```
- `test_premium_plans_authoritative_pricing`: Đạt (kiểm chứng giá $5 và $50 bất biến tại backend).
- `test_vnpay_adapter_url_generation_and_signature_verification`: Đạt (kiểm chứng HMAC-SHA512).
- `test_vnpay_adapter_tampered_payload_rejected`: Đạt (chặn đứng mọi payload bị sửa đổi).
- `test_vnpay_pricing_approval_fail_closed`: Đạt (kiểm chứng fail-closed khi chưa duyệt giá).
- `test_premium_dto_and_order_lifecycle`: Đạt (kiểm chứng vòng đời đơn hàng và snapshot).
- `test_openapi_premium_endpoints`: Đạt (5 endpoint premium tuân thủ OpenAPI spec).
- `test_guest_cannot_access_orders_or_simulate`: Đạt (401 Unauthorized đối với guest).
- `test_vnpay_ipn_verification_lifecycle`: Đạt (kiểm chứng mã phản hồi IPN 00, 04, 97).
- `test_migrations.py`: 15/15 migration tests đạt, DBML schema contract trùng khớp 100%.
- **Toàn bộ backend test suite:** **427/427 passed** (0 failures).

### 4.2. Frontend Unit Tests
```powershell
node --test frontend/tests/*.test.mjs
```
- **70/70 frontend unit tests passed** (0 failures).

### 4.3. Frontend Production Build
```powershell
cd frontend; npm.cmd run build
```
- Vite 7.3.8 build thành công trong 4.70 giây với 0 lỗi cú pháp hay bundle chunk.

### 4.4. Playwright Browser Automation Test Suites
```powershell
cd frontend; npx.cmd playwright test --config=../.github/playwright.auth.config.mjs auth-tests/admin-premium.spec.js auth-tests/premium-sandbox.spec.js --workers=1 --retries=0
```
- **15/15 tests passed** (1.3 phút):
  1. `Guest and USER cannot enter Admin by URL or forged local identity` — OK
  2. `Admin searches users and updates status/roles using CSRF contracts` — OK
  3. `Last Admin conflict keeps the confirmation and unchanged state` — OK
  4. `Content/category/inbox workflows and safe audit/catalog views` — OK
  5. `Failed reads retry; revoked Admin role removes private workspace` — OK
  6. `Admin sidebar geometry and keyboard dialog focus survive resource changes` — OK
  7. `Membership minimal intro, unframed logo and home button honor reduced motion` — OK
  8. `Premium plan selection, arrows and reduced motion keep real benefits without writes` — OK
  9. `Premium moving frame follows selection through live language/theme switches and resize` — OK (geometry pixel-perfect < 1px)
  10. `Admin/Premium responsive VI/EN dark/light and disabled Premium without transactions` — OK
  11. `Premium displays $5 and $50 across VI/EN and Dark/Light themes` — OK
  12. `Guest clicking CTA redirects to /login?next=%2Fpremium` — OK
  13. `Logged in user can open Sandbox modal, simulate successful payment, and see active badge` — OK
  14. `Logged in user can simulate payment failure without corrupting state` — OK
  15. `VNPAY return callback in URL updates subscription state and displays notice` — OK

---

## 5. ẢNH CHỤP MINH CHỨNG GIAO DIỆN (UI SCREENSHOTS)

Các tệp ảnh đã được lưu trữ trực tiếp vào thư mục artifact:
1. `task5_premium_desktop_dark.png`: Giao diện `/premium` Desktop giao diện Tối (Dark mode), hiển thị gói Plus $5 và Prime $50.
2. `task5_premium_desktop_light.png`: Giao diện `/premium` Desktop giao diện Sáng (Light mode).
3. `task5_premium_mobile_dark.png`: Giao diện `/premium` Mobile giao diện Tối.
4. `task5_premium_mobile_light.png`: Giao diện `/premium` Mobile giao diện Sáng.
5. `task5_premium_modal_dark.png`: Hộp thoại Thử nghiệm Sandbox với thông tin giá, lưu ý an toàn và 3 tùy chọn mô phỏng thanh toán.

---

## 6. HƯỚNG DẪN NGHIỆM THU CHO OWNER

1. Mở trang `/premium` với tư cách khách (chưa đăng nhập):
   - Kiểm tra hiển thị giá `$5` (Plus / 30 ngày) và `$50` (Prime / 365 ngày).
   - Kiểm tra nút `"Đăng nhập để thử nghiệm"` điều hướng sang `/login?next=%2Fpremium`.
2. Đăng nhập tài khoản demo (`khang_dev` hoặc `kien_dev`):
   - Truy cập `/premium`, bấm `"Thử nghiệm gói Plus ($5)"`.
   - Hộp thoại Sandbox mở lên: bấm `"Thanh toán tức thì (Mô phỏng thành công)"`.
   - Xem thông báo kích hoạt thành công, đóng hộp thoại.
   - Kiểm tra banner `"Gói đang kích hoạt: Aura PLUS · Còn 30 ngày"`.
   - Nút hành động đổi trạng thái `"Gói đang kích hoạt (còn 30 ngày)"`.
3. Kiểm tra tính an toàn cổng VNPAY:
   - Nút `"Cổng VNPAY Sandbox"` trong modal hiển thị trạng thái vô hiệu hóa kèm chú thích `"Chờ duyệt giá VND"`, bảo đảm fail-closed 100%.
