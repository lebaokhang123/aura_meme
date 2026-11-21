# TÀI LIỆU BÀN GIAO KỸ THUẬT — TASK 5: PREMIUM SANDBOX & VNPAY ADAPTER (FINAL POLISH)

**Mã Task:** TASK-5-PREMIUM-SANDBOX-FINAL  
**Nhánh Git:** `feat/premium-sandbox-task5`  
**Base Commit Kế thừa:** `75a2a98` (Task 5 ban đầu) kết hợp cherry-pick Task 4 (`c72f8b2`, `27a3b7a`)  
**Kỹ sư thực hiện:** Google Antigravity (Gemini Flash)  
**Đơn vị giám sát & điều phối:** ChatGPT  
**Cấp thẩm quyền nghiệm thu:** AuraMeme Project Owner  
**Ngày hoàn thành:** 21/11/2026  

---

## 1. TỔNG QUAN YÊU CẦU & QUYẾT ĐỊNH CỦA OWNER

### 1.1. Bối cảnh dự án
AuraMeme là nền tảng đồ án và portfolio Web/DevOps cao cấp (Cyberpunk Cultivation Meme Community Platform). Hệ thống hội viên (Aura Membership) được phát triển hoàn chỉnh trải nghiệm thị giác và quy trình đăng ký, quản lý gói, tích hợp cổng thanh toán Sandbox mà **tuyệt đối không phát sinh giao dịch tiền thật**.

### 1.2. Bảng giá chính thức do Owner phê duyệt
Owner đã phê duyệt giá niêm yết chuẩn:
1. **Aura Plus:** `$5` USD / 30 ngày (tham chiếu quy đổi VND: `125.000 đ`, hệ số `×2` bonus Level XP).
2. **Aura Prime:** `$50` USD / 365 ngày (tham chiếu quy đổi VND: `1.250.000 đ`, hệ số `×3` bonus Level XP).

### 1.3. Nhận diện thị giác cao cấp (High-Tier Visual Identity)
- **Aura Plus (Grandmaster — Đại Cao Thủ):** Sắc đỏ lửa, cam cháy, vàng kim và đen (`#ef4444`, `#f97316`, `#eab308`). Năng lượng nóng bỏng, viền phát sáng tỏa nhẹ ra ngoài.
- **Aura Prime (Challenger — Thách Đấu):** Sắc trắng bạc, xanh dương, cyan và vàng kim (`#f8fafc`, `#38bdf8`, `#06b6d4`, `#fbbf24`). Hào quang đa tầng sáng ngời, nổi bật vượt trội.
- **Bảo tồn mỹ thuật:** Không sao chép logo/tài sản Riot Games; không phá vỡ khung viền (Vault frame) hay background của prompt #056; hỗ trợ chuẩn `prefers-reduced-motion: reduce`.

---

## 2. KIẾN TRÚC & TRIỂN KHAI HOÀN THIỆN

### 2.1. Nút Premium trên Header (`frontend/src/components/SiteShell.jsx` & `site.css`)
- **Trạng thái Free (Chưa có gói):** Nút `.header-premium-btn--free` hiển thị nhãn `"Mua Aura"` (VI) / `"Get Aura"` (EN) với hiệu ứng gradient RGB tím-cyan-xanh chuyển động mượt mà từ trái sang phải (`auraRgbSweep`).
- **Trạng thái Plus:** Nút `.header-premium-btn--plus` hiển thị `"Aura Plus"` theo phong cách Grandmaster đỏ-cam-vàng-đen với viền ánh lửa.
- **Trạng thái Prime:** Nút `.header-premium-btn--prime` hiển thị `"Aura Prime"` theo phong cách Challenger trắng-xanh-cyan-vàng với glow nổi bật.
- Cả ba trạng thái đều click điều hướng trực tiếp sang `/premium` để xem thông tin gói.

### 2.2. Avatar Indicator & Tích xanh Hội viên (`SiteShell.jsx` & `site.css`)
- **Avatar Glow:** Khi có gói hội viên, avatar người dùng trên Header được bao bọc bởi viền phát sáng tương ứng (`.aura-avatar--plus`, `.aura-avatar--prime`) với chu kỳ nhịp thở (pulse) 3 giây.
- **Blue Member Checkmark (`.aura-member-badge`):** Biểu tượng tích xanh nhỏ gọn nằm ở góc dưới bên phải avatar, mang ý nghĩa khẳng định **Hội viên Aura** (Aura Member), có tooltip và accessible label chuẩn xác (không gây hiểu nhầm thành tài khoản xác minh danh tính).
- Khi gói hết hạn, cả viền glow và dấu tick tự động biến mất mà không ảnh hưởng avatar gốc hay frame vật phẩm Vault.

### 2.3. Nguồn trạng thái Subscription dùng chung (`frontend/src/PremiumContext.jsx`)
- Cung cấp React Context `PremiumProvider` bọc toàn ứng dụng tại `main.jsx`.
- Lưu trữ `subscription`, `loading` và phương thức `refresh()`.
- Tự động nạp trạng thái khi người dùng đăng nhập, làm mới khi thanh toán hoặc đăng xuất; không thăm dò liên tục và không lưu trái phép vào localStorage.

### 2.4. Đồng bộ ô AURA PERKS tại Trang chủ (`frontend/src/components/AuraPerksCard.jsx`)
- **Free:** Hiển thị nhãn `"Đã mở đăng ký"` / `"Available"`, mô tả nhận bonus EXP khi nâng cấp Level, nút `"Xem Plus / Prime"` dẫn sang `/premium`.
- **Plus / Prime:** Hiển thị tên gói tương ứng kèm tích xanh verified, badge `"Đang kích hoạt"`, số ngày sử dụng còn lại chính xác từ server, và nút `"Gia hạn gói"` / `"Extend Subscription"`.

### 2.5. Tinh gọn giao diện `/premium` (`frontend/src/components/PremiumPage.jsx` & `workspace.css`)
- Đã loại bỏ hoàn toàn nhãn `"Sandbox Trial"` phía trên logo và các dòng disclaimer lặp lại.
- Thêm huy hiệu `×2 EXP` (`.u056-badge-exp--plus`) cho thẻ Plus và `×3 EXP` (`.u056-badge-exp--prime`) cho thẻ Prime.
- Nút CTA chuyển sang hành động trực quan:
  - Khách: `"Đăng nhập để mua gói"` / `"Sign in to purchase"`.
  - Chưa có gói: `"Mua gói Plus ($5)"` / `"Mua gói Prime ($50)"` (EN: `"Buy Aura Plus ($5)"` / `"Buy Aura Prime ($50)"`).
  - Đã có gói: `"Gói đang kích hoạt (còn X ngày)"`.
- Hiển thị giá: tiếng Anh hiển thị `$5` và `$50`; tiếng Việt hiển thị giá VND làm tròn kèm USD (`125.000 đ ($5)` và `1.250.000 đ ($50)`).

### 2.6. Tăng cường bảo mật thanh toán Backend (`backend/app/premium.py`)
1. **Khóa Endpoint Mô phỏng:** `POST /premium/orders/{order_code}/simulate` được bổ sung guard kiểm tra nghiêm ngặt môi trường: nếu `ENVIRONMENT == 'production'`, từ chối ngay lập tức với mã lỗi `403 FORBIDDEN`.
2. **User Scoping & CSRF:** Bắt buộc session xác thực hợp lệ và CSRF token server cấp; chỉ cho phép chính chủ đơn hàng thao tác trên đơn của mình.
3. **Cộng dồn ngày sử dụng (Subscription Extension):** Khắc phục lỗi làm mất số ngày còn lại khi gia hạn. Logic mới:
   `base_time = sub.expires_at if (sub.expires_at and sub.expires_at > now) else now`
   `sub.expires_at = base_time + timedelta(days=plan.duration_days)`
4. **Phân tách Return URL và IPN:** Return URL chỉ phục vụ điều hướng và hiển thị kết quả cho người dùng; IPN là kênh thông báo server-to-server có thẩm quyền cao nhất để ghi nhận đơn và kích hoạt subscription với kiểm tra chữ ký số HMAC-SHA512.
5. **Fail-Closed VNPAY Gateway:** Cổng VNPAY Sandbox giữ trạng thái khóa (`vnpay_pricing_approved=False`) cho đến khi Owner phê duyệt giá VND chính thức.

---

## 3. KẾT QUẢ KIỂM THỬ TOÀN DIỆN (TEST EVIDENCE)

### 3.1. Backend Non-Integration Pytest Suite
```powershell
cd backend
Remove-Item Env:AUTH_ENVIRONMENT -ErrorAction SilentlyContinue
Set-Item -Path Env:DATABASE_URL -Value "postgresql+psycopg://test:not-a-real-secret@127.0.0.1:1/test"
.\.venv\Scripts\python.exe -m pytest -m "not integration" -q
```
- **Kết quả:** **428 passed**, 787 deselected, 0 failed (36.85s).
- Bao gồm 9/9 tests chuyên biệt cho Premium (`tests/test_premium_sandbox.py`):
  - `test_premium_plans_authoritative_pricing`: Đạt (giá $5 và $50 bất biến).
  - `test_vnpay_adapter_url_generation_and_signature_verification`: Đạt (HMAC-SHA512).
  - `test_vnpay_adapter_tampered_payload_rejected`: Đạt (chặn dữ liệu giả mạo).
  - `test_vnpay_pricing_approval_fail_closed`: Đạt (khóa cổng khi chưa duyệt giá).
  - `test_premium_dto_and_order_lifecycle`: Đạt (vòng đời đơn hàng).
  - `test_openapi_premium_endpoints`: Đạt (OpenAPI spec contract).
  - `test_guest_cannot_access_orders_or_simulate`: Đạt (401 Unauthorized).
  - `test_vnpay_ipn_verification_lifecycle`: Đạt (IPN 00, 04, 97).
  - `test_subscription_extension_accumulates_days`: Đạt (gia hạn gói cộng dồn ngày chính xác).

### 3.2. Frontend Unit Tests
```powershell
node --test frontend/tests/*.test.mjs
```
- **Kết quả:** **78/78 passed**, 0 failed (1.1s).
- Kiểm chứng toàn diện: Relative Time scaling (8 tests), Notifications, Identity caching, Meme toggle, Vault, Sound, Preferences, Profile heatmap.

### 3.3. Frontend Production Build
```powershell
cd frontend
npm.cmd run build
```
- **Kết quả:** Vite 7.3.8 build thành công trong 3.25 giây với 0 lỗi cú pháp hay chunking error.

### 3.4. Playwright Browser Automation Test Suites
1. **Premium & Admin Suite (16 tests):**
   ```powershell
   cd frontend
   npx.cmd playwright test --config=../.github/playwright.auth.config.mjs auth-tests/premium-sandbox.spec.js auth-tests/admin-premium.spec.js --workers=1 --retries=0
   ```
   - **Kết quả:** **16/16 passed** (1.2m).
   - Bao gồm kiểm thử mới: `Header button, avatar indicators, and Home Aura Perks card sync with subscription state` (Free, Plus, Prime).

2. **Core Auth & Social Suite (64 tests):**
   ```powershell
   cd frontend
   npx.cmd playwright test --config=../.github/playwright.auth.config.mjs auth-tests/social-api.spec.js auth-tests/profile-fidelity.spec.js auth-tests/profile-contact.spec.js auth-tests/aura-api.spec.js auth-tests/rank-api.spec.js --workers=1 --retries=0
   ```
   - **Kết quả:** **64/64 passed** (3.2m).
- **Tổng cộng Playwright:** **80/80 passed** (100% tỷ lệ thành công).

---

## 4. ẢNH CHỤP MINH CHỨNG GIAO DIỆN (UI SCREENSHOTS)

Các tệp ảnh minh chứng giao diện thực tế đã được lưu vào thư mục artifact:
1. [task5_premium_desktop_dark.png](file:///C:/Users/sammy/.gemini/antigravity/brain/cc803197-d415-4eaf-80c2-1173a22c12aa/task5_premium_desktop_dark.png): Giao diện `/premium` Desktop Dark mode tinh gọn, hiển thị giá $5 / $50, badge ×2 EXP & ×3 EXP, nút Mua gói.
2. [task5_premium_desktop_light.png](file:///C:/Users/sammy/.gemini/antigravity/brain/cc803197-d415-4eaf-80c2-1173a22c12aa/task5_premium_desktop_light.png): Giao diện `/premium` Desktop Light mode.
3. [task5_premium_mobile_dark.png](file:///C:/Users/sammy/.gemini/antigravity/brain/cc803197-d415-4eaf-80c2-1173a22c12aa/task5_premium_mobile_dark.png): Giao diện `/premium` Mobile Dark mode (viewport 375px) không tràn viền.
4. [task5_premium_modal_dark.png](file:///C:/Users/sammy/.gemini/antigravity/brain/cc803197-d415-4eaf-80c2-1173a22c12aa/task5_premium_modal_dark.png): Hộp thoại Xác nhận đơn hàng với bảng tóm tắt, lưu ý sandbox an toàn và nút VNPAY Sandbox giữ trạng thái fail-closed.
5. [task5_home_header_perks_dark.png](file:///C:/Users/sammy/.gemini/antigravity/brain/cc803197-d415-4eaf-80c2-1173a22c12aa/task5_home_header_perks_dark.png): Trang chủ Desktop Dark mode thể hiện nút Header "Aura Prime", avatar glow Challenger, tích xanh hội viên và thẻ AURA PERKS phản ánh gói Prime đang kích hoạt.

---

## 5. RÀO CẢN KỸ THUẬT & ĐIỂM NGHẼN CẦN OWNER PHÊ DUYỆT (BLOCKERS)

Để bảo vệ tuyệt đối tính an toàn tài chính và an ninh hệ thống, các hạng mục sau **tạm thời giữ trạng thái fail-closed** và cần phê duyệt chính thức từ Owner trước khi mở cổng thật:

1. **Phê duyệt tỷ giá / Giá thanh toán VND chính thức:**
   - Mức giá tham chiếu hiện tại (`125.000 đ` cho Plus và `1.250.000 đ` cho Prime) mới là giá định hướng, chưa phải giá thanh toán được chốt bằng văn bản.
   - Khi Owner xác nhận tỷ giá chính thức, hệ thống sẽ bật `vnpay_pricing_approved=True` tại cấu hình backend.
2. **Merchant Credentials VNPAY thực tế:**
   - Hiện hệ thống sử dụng sandbox parameters (`TMN_CODE="AURAMEME"`, secret test). Cần bộ thông tin tài khoản Merchant chính thức từ VNPAY Sandbox hoặc Production.
3. **Cấu hình IPN Webhook Live Callback:**
   - Cần cấu hình địa chỉ IPN callback public có bảo vệ HTTPS (ví dụ thông qua domain production chính thức hoặc webhook gateway an toàn) để VNPAY có thể bắn tín hiệu server-to-server.
4. **Quyết định kinh doanh về cơ chế nâng cấp gói (Upgrade Tier Policy):**
   - Hiện tại hệ thống đang bảo toàn ngày hết hạn theo nguyên tắc cộng dồn an toàn. Nếu người dùng chuyển từ Plus lên Prime giữa chu kỳ, cần quyết định của Owner về việc quy đổi giá trị ngày còn lại của gói cũ hay thay thế hoàn toàn.

---

## 6. BẢN VÁ KỸ THUẬT TOÀN DIỆN (TECHNICAL HOTFIX)

Sau quá trình rà soát độc lập từ ChatGPT, nhánh `feat/premium-sandbox-task5` đã được bổ sung bản vá kỹ thuật hoàn chỉnh:

### 6.1. Đồng bộ Hợp đồng DTO Frontend ↔ Backend
- **Tên trường gói:** Thay thế trường `plan_type` không nhất quán bằng trường định danh chuẩn `plan_tier` (`'plus'` | `'prime'`) trên `CreateOrderInput` và toàn bộ flow tạo đơn của `PremiumPage.jsx`.
- **Nhà cung cấp sandbox:** Đổi tên provider từ `'vnpay'` sang `'vnpay_sandbox'` để phản ánh chính xác môi trường thử nghiệm và phân biệt với cổng thanh toán thật.
- **Trạng thái kích hoạt gói:** Chuẩn hóa toàn bộ schema DTO `SubscriptionDto` và client context sang thuộc tính duy nhất `is_active: bool`. Loại bỏ hoàn toàn fallback legacy `active: bool`.

### 6.2. Phân tách và Xử lý Chuẩn xác VNPAY Return URL & IPN
- **HTTP 302 Redirect:** Backend `handle_vnpay_return` trả về `RedirectResponse` chuẩn HTTP 302 chuyển hướng trình duyệt về `/premium?vnp_status=success&order_code=...`. Khắc phục triệt để lỗi trình duyệt cố gọi JSON fetch vào URL chuyển hướng.
- **Phân định thẩm quyền:** Return URL tuyệt đối không tự ý ghi nhận kích hoạt subscription. Endpoint IPN (`handle_vnpay_ipn`) giữ vai trò duy nhất và có thẩm quyền tối cao (authoritative webhook) để xác thực chữ ký HMAC-SHA512, đối soát số tiền và kích hoạt gói cho người dùng.

### 6.3. Siết chặt Bảo mật Endpoint Mô phỏng (Payment Simulation)
- Cập nhật hàm `simulate_subscription_order` để đọc cấu hình môi trường thực tế từ `request.app.state.auth.settings.auth_environment` và `premium_settings.premium_sandbox_enabled`.
- Chặn đứng mọi hành vi gọi simulate trên môi trường production bằng mã lỗi nghiêm ngặt `403 FORBIDDEN`.

### 6.4. Helper Làm tròn Tiền tệ VND 10.000 đ
- Bổ sung helper `round_vnd_to_nearest_10k` trong `backend/app/premium_plans.py` phục vụ tính toán và làm tròn số tiền VND đến mốc 10.000 đ gần nhất khi áp dụng bảng giá động trong tương lai.

### 6.5. Cập nhật Fixture và Bổ sung Test Cases
- Bổ sung 7 test cases mới trong `backend/tests/test_premium_sandbox.py` (nâng tổng số non-integration tests lên **435 tests passed**).
- Cập nhật toàn diện mock fixtures trong `frontend/auth-tests/premium-sandbox.spec.js` tuân thủ 100% hợp đồng kỹ thuật mới (**16/16 Playwright tests passed**).
