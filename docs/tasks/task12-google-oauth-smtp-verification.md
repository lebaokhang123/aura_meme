# TÀI LIỆU BÀN GIAO KỸ THUẬT — TASK 12: GOOGLE OAUTH & SMTP REAL VERIFICATION

## 1. Thông tin mốc & Trạng thái

- **Baseline sản phẩm:** `origin/dev@98f6f88` (Merge pull request #42 from lebaokhang123/codex/nghiem-thu-final-polish).
- **Nhánh thực hiện:** `feat/google-smtp-verification`.
- **Worktree độc lập:** `aurameme-google-smtp` (cô lập ngoài workspace chính).
- **Trạng thái kỹ thuật:** `READY FOR RELEASE APPROVAL`.
- **Google OAuth:** `LIVE VERIFIED (PASS)` (Owner đã trực tiếp đăng ký, onboarding tag và đăng nhập thành công).
- **SMTP:** `INBOX CONFIRMED 4/4 (PASS)` (Owner đã xác nhận nhận đủ 4 email giao dịch trên Gmail).
- **PDF Attachment:** `ATTACHMENT CONFIRMED` (File PDF đính kèm hóa đơn Premium mở được; nội dung chi tiết không tự đánh dấu PDF content PASS).
- **Email Verification & Password Reset Live:** `LIVE VERIFIED (PASS)` (Owner đã đăng ký, xác minh email và reset password thành công).
- **Giao diện Chờ Xác minh Email & Cooldown 30s:** `LIVE VERIFIED (PASS)` (5 thành phần căn giữa tối giản, cooldown 30s reload-proof, hỗ trợ định dạng `MM:SS` khi `Retry-After > 59s`).
- **Fail-closed & Chống bypass:** `VERIFIED` (Bắt buộc fail-closed khi `EMAIL_VERIFICATION_REQUIRED=true` và email service/mode bị tắt; kiểm tra `EmailResult.status in ("sent", "sandbox_captured")`; đồng bộ cooldown 30s & rate-limit dùng chung giữa `register` và `resend-verification`).
- **Quyết định phạm vi:** `FEATURE FREEZE` (Đóng băng tính năng, không mở rộng scope; Account Linking nâng cao thuộc backlog tương lai).
- **Chính sách bảo mật:** Giữ nguyên chính sách chống chiếm đoạt tài khoản (Anti-Takeover) hiện hành (409 khi trùng email).
- **Learning Check:** `PENDING`.

---

## 2. Khảo sát & Đánh giá Kiến trúc Hiện hành

### 2.1. Google Identity Services (GIS) / OpenID Connect
- **Frontend (`frontend/src/components/LucianGoogleButton.jsx`):**
  - Tích hợp chuẩn Google Identity Services SDK (`https://accounts.google.com/gsi/client`).
  - Lấy cấu hình runtime từ endpoint `GET /api/v1/auth/google/config` (`client_id` + `enabled`).
  - Sử dụng cơ chế One Tap / GIS Button popup an toàn với `nonce` ngẫu nhiên chống replay/login CSRF.
  - Khi người dùng đăng nhập tài khoản Google mới, hệ thống mở modal Onboarding để người dùng tự chọn Tag/Username (`@tag`), sau đó gọi `POST /api/v1/auth/google/onboarding` với token HMAC ký bảo mật.
  - Xử lý lỗi mượt mà: khi hủy đăng nhập, đóng popup hoặc lỗi mạng, nút tự động khôi phục trạng thái `idle` và hiển thị thông báo trung tính, tuyệt đối không làm đơ hay crash UI.
- **Backend (`backend/app/google_auth.py`):**
  - Xác thực trực tiếp ID Token JWT với Google Tokeninfo API: kiểm tra audience (`aud == client_id`), issuer (`iss in accounts.google.com`), hạn dùng (`exp > now`), trạng thái email đã xác minh (`email_verified == True`), và `nonce`.
  - **Chính sách chống chiếm đoạt tài khoản (Anti-Takeover):** Nếu email Google trùng với tài khoản cục bộ chưa liên kết, backend từ chối tự động gộp và trả về mã lỗi `409 ACCOUNT_LINK_REQUIRED`.
  - **Liên kết tài khoản an toàn:** Endpoint `POST /api/v1/auth/google/link` bắt buộc phải có phiên đăng nhập hợp lệ + CSRF token + xác minh lại mật khẩu hiện tại (`current_password`).
  - Phân quyền an toàn: Tài khoản tạo mới từ Google luôn có role mặc định là `USER`, mật khẩu sentinel `!google:...` không thể đăng nhập bằng password brute-force.
  - Không cần `Client Secret` (GIS Client-side Web App chỉ yêu cầu Client ID).

### 2.2. Dịch vụ Email giao dịch & SMTP (`backend/app/email_service.py`)
- Sử dụng chuẩn `smtplib` với cơ chế kết nối an toàn TLS/SSL (`smtp.gmail.com:587`, STARTTLS).
- Nhúng logo chính thức AuraMeme qua inline CID PNG (`cid:aurameme-logo`) để hiển thị trực tiếp trong Gmail mà không phụ thuộc vào link ảnh ngoài hay localhost.
- Chuẩn hóa tiêu đề email toàn hệ thống: tiền tố `[AuraMeme] - <Tiêu đề>`.
- Cơ chế khử trùng lặp `dedupe_key` chống gửi lặp thư khi người dùng click nhiều lần hoặc webhook gọi lại.
- Bốn luồng email chuẩn:
  1. **Xác minh tài khoản (Account Verification):** Token 32-byte ngẫu nhiên lưu dạng SHA-256 (`token_hash`), hạn 24 giờ, sử dụng một lần.
  2. **Quên mật khẩu (Password Reset):** Phản hồi trung tính (neutral message) chống dò email, token SHA-256 hạn 30 phút, thu hồi toàn bộ session cũ khi reset thành công.
  3. **Tiếp nhận góp ý (Contact):** Gửi thư xác nhận cho người gửi kèm Mã tham chiếu (`contact_id`), Chủ đề, Nội dung.
  4. **Biên nhận Premium (Receipt PDF):** Tự động sinh file PDF A4 chuẩn (`AuraMeme-Receipt-<order_code>.pdf`), gắn logo, thông tin đơn hàng, ghi rõ nhãn mô phỏng Sandbox.

---

## 3. Hướng dẫn Owner Tạo Google Cloud OAuth Client ID

Owner vui lòng thực hiện các bước sau trên trình duyệt (không chia sẻ mật khẩu hay OTP):

1. **Truy cập Google Cloud Console:**
   - Mở liên kết: [https://console.cloud.google.com/](https://console.cloud.google.com/) và đăng nhập bằng tài khoản Google của bạn.
2. **Chọn hoặc tạo Project:**
   - Bấm vào thanh chọn dự án ở thanh tiêu đề trên cùng -> Chọn **New Project** (Dự án mới).
   - Đặt tên dự án (ví dụ: `AuraMeme`) -> Bấm **Create**.
3. **Cấu hình Màn hình đồng thuận (OAuth consent screen):**
   - Vào menu bên trái: **APIs & Services** (API và dịch vụ) -> **OAuth consent screen** (Màn hình đồng thuận OAuth).
   - Chọn **External** (Người dùng bên ngoài) -> Bấm **Create**.
   - Điền thông tin cơ bản:
     - **App name:** `AuraMeme`
     - **User support email:** Chọn email của bạn.
     - **Developer contact information:** Điền email của bạn.
   - Bấm **Save and Continue** (Lưu và tiếp tục).
   - Mục **Scopes** (Phạm vi): Bấm **Add or remove scopes** -> Chọn 3 scope cơ bản: `.../auth/userinfo.email`, `.../auth/userinfo.profile`, `openid` -> Bấm **Update** -> Bấm **Save and Continue**.
   - Mục **Test users** (Người dùng thử nghiệm):
     - **RẤT QUAN TRỌNG:** Vì ứng dụng đang ở chế độ Testing, bạn cần bấm **+ Add users** và thêm địa chỉ Gmail mà bạn sẽ dùng để thử nghiệm đăng nhập.
     - Bấm **Save and Continue** -> Bấm **Back to Dashboard**.
4. **Tạo OAuth Client ID:**
   - Vào menu bên trái: **APIs & Services** -> **Credentials** (Thông tin xác thực).
   - Bấm **+ Create Credentials** (Tạo thông tin xác thực) -> Chọn **OAuth client ID**.
   - **Application type** (Loại ứng dụng): Chọn **Web application** (Ứng dụng web).
   - **Name:** `AuraMeme Web Client`.
   - **Authorized JavaScript origins** (Nguồn gốc JavaScript được ủy quyền): Bấm **+ Add URI** và thêm 2 URI local:
     - `http://localhost:5173`
     - `http://127.0.0.1:5173`
   - **Authorized redirect URIs** (URI chuyển hướng được ủy quyền):
     - **Để trống** đối với GIS callback hiện hành (vì thư viện Google Identity Services sử dụng callback JavaScript trực tiếp trong trình duyệt).
     - Không yêu cầu Client Secret.
   - Bấm **Create**.
5. **Lấy Client ID và cấu hình:**
   - Cửa sổ hiện ra sẽ hiển thị **Your Client ID** (chuỗi ký tự có đuôi `.apps.googleusercontent.com`).
   - *(Lưu ý: Bạn KHÔNG cần quan tâm đến Client Secret vì kiến trúc GIS không sử dụng Secret phía client).*
   - Điền Client ID này vào file `backend/.env`:
     ```env
     GOOGLE_CLIENT_ID=xxxxxxxxxxxx-xxxxxxxxxxxxxxxx.apps.googleusercontent.com
     ```
6. **Đánh giá Tokeninfo & Security Gate Production:**
   - Cơ chế hiện hành sử dụng Google Tokeninfo API (`https://oauth2.googleapis.com/tokeninfo`) xác minh ID Token trực tiếp từ máy chủ Google, rất an toàn và thuận tiện cho môi trường local/demo.
   - Việc nâng cấp sang xác minh chữ ký mã hóa cục bộ bằng thư viện chính thức (`google-auth`) và Google JWKS public keys là một gate bảo mật nâng cao riêng biệt trước khi go-live production, không mở rộng phạm vi của Task 12 khi cơ chế hiện tại đang vận hành ổn định.

---

## 4. Nghiệm thu Thực tế SMTP & Giao diện Chờ Xác minh Email

Owner đã xác nhận bằng hình ảnh nhận đầy đủ 4 email giao dịch thực tế trên Gmail (từ tài khoản sender SMTP đã cấu hình):
1. `[AuraMeme] - Xác minh địa chỉ email`: Hiển thị rõ ràng link kích hoạt và logo AuraMeme inline.
2. `[AuraMeme] - Đặt lại mật khẩu`: Hiển thị link đặt lại mật khẩu trong 30 phút.
3. `[AuraMeme] - Tiếp nhận góp ý`: Hiển thị email phản hồi liên hệ có Mã tham chiếu (`contact_id`), Chủ đề và Nội dung.
4. `[AuraMeme] - Biên nhận thanh toán Aura Prime`: Có file PDF đính kèm (`AuraMeme-Receipt-....pdf`) mở được, đúng định dạng A4 và hiển thị logo. Timestamp trong email đã được chuẩn hóa sang định dạng `HH:MM:SS - DD/MM/YYYY` (múi giờ `Asia/Ho_Chi_Minh`).

### Giao diện Chờ Xác minh Email (Pending Verification UI Redesign)
Theo đúng yêu cầu tối giản và nhận diện AuraMeme của Owner:
- **Cấu trúc 5 thành phần căn giữa từ trên xuống dưới:**
  1. Icon phong bì thư 72px outline, gradient tím/cyan (`#d0bcff` / `#4cd7f6`), không nền khối.
  2. Dòng thông báo: "Chúng tôi đã gửi liên kết xác minh đến" (EN: "We have sent a verification link to").
  3. Địa chỉ email thực tế của người dùng: nổi bật, đậm hơn các dòng chữ khác, ngắt dòng an toàn.
  4. Dòng hướng dẫn: "Vui lòng xác minh để hoàn tất đăng ký tài khoản AuraMeme" (EN: "Please verify to complete your AuraMeme account registration").
  5. Bộ đếm ngược thời gian thực: "Gửi lại sau 00:30" (giảm từng giây). Khi hết 30s, tự động chuyển thành text link gạch chân "Gửi lại email xác minh" (EN: "Resend verification email").
- **Nguyên tắc thiết kế tuân thủ nghiêm ngặt:**
  - Không có card, không viền border, không khung bao quanh nội dung hay đường phân cách.
  - Không nút bấm dạng hình hộp; resend là text link thuần túy.
  - Đồng bộ cooldown 30s giữa frontend và backend (`POST /api/v1/auth/resend-verification`), lưu session storage chống bypass bằng reload trang.
  - Rate limit bảo vệ kép: IP (10 req/10 min) và email hash (5 req/10 min).
  - Hỗ trợ đầy đủ Dark/Light Mode, VI/EN, responsive mobile.
  - Thông báo lỗi chỉ hiển thị khi có lỗi phát sinh.

### Bảng trạng thái nghiệm thu:
| Hạng mục | SMTP AUTH | SMTP ACCEPTED / SENT | INBOX CONFIRMED | TIẾN TRÌNH / TRẠNG THÁI | Ghi chú |
|---|---|---|---|---|---|
| Xác thực tài khoản | **PASS** | **PASS** | **INBOX CONFIRMED** | **LIVE VERIFIED (PASS)** | UI 5 thành phần tối giản, fail-closed, cooldown 30s & rate-limit đồng bộ |
| Quên mật khẩu | **PASS** | **PASS** | **INBOX CONFIRMED** | **LIVE VERIFIED (PASS)** | Phản hồi trung tính, thu hồi session cũ, đặt lại mật khẩu thành công |
| Tiếp nhận liên hệ | **PASS** | **PASS** | **INBOX CONFIRMED** | **CONFIRMED** | Mã tham chiếu -> Chủ đề -> Nội dung (Integration Verified) |
| Hóa đơn Premium | **PASS** | **PASS** | **INBOX CONFIRMED** | **ATTACHMENT CONFIRMED** | File PDF A4 mở được, timestamp GMT+7 chuẩn hóa; không tự đánh dấu PDF content PASS |

> [!NOTE]
> `test_checkpoint4_smtp_e2e.py` sử dụng mock session và sandbox captured SMTP outbox (mocked service-flow tests) nhằm kiểm thử logic nghiệp vụ an toàn mà không gửi thư mạng hay sửa đổi database thật.

---

## 5. Kết quả Kiểm thử Kỹ thuật

| Bộ kiểm thử | Lệnh thực thi | Kết quả | Trạng thái |
|---|---|---|---|
| Targeted Google, Email & Health | `pytest tests/test_checkpoint4_smtp_e2e.py tests/test_checkpoint1_google_auth.py tests/test_task10_identity.py tests/test_task7_google_email_reset.py tests/test_health.py -q` | **34 passed**, 1 warning | **PASS** |
| Frontend Node Unit Tests | `node --test tests/*.test.mjs` | **88 passed**, 0 failed | **PASS** |
| Frontend Production Build | `npm.cmd run build` (Vite v7.3.8) | 402 modules transformed, 0 error | **PASS** |

## 6. Xác nhận Bảo toàn Hệ thống

- Không chạm, không sửa đổi workspace chính.
- Không chạm thư mục private assets.
- Mọi database (`aurameme_demo`, `aurameme_dev`) và tài khoản demo được bảo toàn nguyên vẹn 100%.
