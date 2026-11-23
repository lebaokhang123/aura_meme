# BÁO CÁO NGHIỆM THU VÀ BÀN GIAO KỸ THUẬT — TASK 9: TÍCH HỢP HỆ THỐNG & AUDIT TOÀN DIỆN

**Dự án:** AuraMeme (Cyberpunk Cultivation Meme Community Platform)  
**Nhánh tích hợp cuối:** `fix/task10-email-polish-qa` (kế thừa liền mạch `feat/task9-integration-audit` → `fix/task9-owner-qa-polish` → `feat/task10-email-identity`)  
**Repository:** `lebaokhang123/aura_meme`  
**Baseline tích hợp:** `origin/dev@8b22c29` (nơi Codex đã hoàn tất nghiệm thu và tích hợp Task 1–5)  
**Ngày thực hiện:** 23/11/2026  
**Kỹ sư thực hiện:** Antigravity (Senior Full-stack & QA Engineer)  
**Bên tiếp nhận:** Owner & Codex (Final Review & Merge)  

---

## 1. TỔNG QUAN PHẠM VI TÍCH HỢP (EXECUTIVE SUMMARY)

Toàn bộ các tính năng từ Task 6 đến Task 8, đợt UI polish Lucian (#403, #405, #409), bản đồng bộ Bảo Khố (Vault Demo Sync với 70 Meme + 5 Background), và cơ chế bảo mật guard fail-closed đã được hoàn thiện trên nhánh `feat/task9-integration-audit`.

### Các phân hệ tích hợp:
1. **Task 6 (Cảnh giới, Cấp bậc & Danh hiệu Admin):**
   - 10 Cảnh giới tu tiên chuẩn hóa: Luyện Khí, Trúc Cơ, Kim Đan, Nguyên Anh, Hóa Thần, Luyện Hư, Hợp Thể, Đại Thừa, Độ Kiếp, Chân Tiên.
   - Công thức Level V1 chuẩn: `XP = 10 + Level`, 10 cảnh giới × 10 cấp (Level 1–100).
   - Danh hiệu Admin thống nhất: **SÁNG THẾ THẦN** cho cả Khang Dev và Kien Dev, hiệu ứng vàng kim quang xà (`aura-admin`), icon vương miện hoàng gia, bảo lưu Level và cảnh giới thực.
   - Thẻ `LevelPill` và `TitleBadge` hiển thị đồng bộ trên Header, Profile, PostCard, CommentRow.
2. **Task 7 (Google OAuth UI, Quên mật khẩu & Email):**
   - Nút đăng nhập Google Cyberpunk UI trên form đăng nhập và đăng ký.
   - Luồng Quên mật khẩu & Đặt lại mật khẩu hoàn chỉnh: token một lần, thời hạn 15 phút, rate limit 3 lần/giờ, animation gửi thư và đếm ngược cooldown.
   - Phản hồi giao diện khi gửi lại email: thông báo thành công, xử lý lỗi 429 và chống spam bấm nhanh.
3. **Task 8 (Public Profile, Follower Count & Cookie Consent Lucian #409):**
   - Mở xem hồ sơ công khai từ tác giả bài viết và bình luận (`/profile/:username`).
   - Hiển thị follower / following count chuẩn xác, bảo mật dữ liệu riêng tư (không lộ email/phone).
   - Banner Cookie Consent chuẩn **Lucian #409** (thanh ngang compact ở chân trang, hiệu ứng cắn bánh quy bite & crumbs, nút cài đặt và mở lại từ footer, tôn trọng `prefers-reduced-motion`).
4. **Lucian UI Polish (#403, #405, #409):**
   - Login #403: Khôi phục form bo góc chuẩn 12px, nền tối cyber dark-first, floating labels, toggle ẩn/hiện mắt mật khẩu, rung cảnh báo viền đỏ khi sai mật khẩu.
   - Forgot Password #405: Hiệu ứng máy bay giấy xếp thư vào phong bì; vòng tròn đếm ngược cooldown; phản hồi tức thì khi gửi lại.
   - Cookie Consent #409: Tích hợp hoàn chỉnh thay thế toàn bộ thiết kế cũ.
5. **Vault Demo Sync & Củng cố Guard Fail-Closed:**
   - Sử dụng SQLAlchemy `make_url` kiểm tra chính xác từng trường: host phải là loopback (`localhost`, `127.0.0.1`, `::1`), database thuộc whitelist (`aurameme_demo`, `aurameme_vault_verify`, `aurameme_qa`, `aurameme_test`), role thuộc whitelist. Chặn đứng 100% các URL đánh lừa qua query parameter, username hay subdomain.
   - Kiểm tra `demo.py`: Chặn kích hoạt demo mode trên môi trường `production` hoặc `staging`.
   - Đồng bộ 2 rương (Meme: 70 vật phẩm, Background: 5 vật phẩm), drop rates chuẩn V1.
   - Runtime EXP: +2 EXP/lượt mở (trần 100 lượt/ngày = 200 EXP/ngày).
6. **Task 9B (VI/EN Bilingual Audit):**
   - Bổ sung 33 chuỗi dịch thuật thiếu trong `frontend/src/translations.json`. Chuẩn hóa song ngữ 100% cho bảng điều khiển Admin, modal xác nhận, lý do kiểm duyệt, thông báo lỗi và phân trang.

---

## 2. BẢO MẬT & KIỂM TRA GUARD FAIL-CLOSED (SECURITY HARDENING)

1. **Vault Catalog Fail-Closed Hardening via `make_url`:**
   - Thay thế hoàn toàn cách tìm chuỗi trong URL bằng phân tích cấu trúc đối tượng qua `make_url(db_url)` trong `backend/app/catalog_rights.py`.
   - Đã kiểm thử và chặn thành công các kỹ thuật URL injection:
     * Chèn host giả trong query string: `?fake_host=127.0.0.1` -> BỊ CHẶN.
     * Chèn user giả làm host: `postgresql://localhost:pass@evil.com/aurameme_demo` -> BỊ CHẶN.
     * Subdomain giả dạng loopback: `@evil-localhost.com/aurameme_demo` -> BỊ CHẶN.
     * Chèn database giả trong query string: `.../production_database?db=aurameme_demo` -> BỊ CHẶN.
     * Role/User không được phép: `@127.0.0.1/aurameme_demo` với user lạ -> BỊ CHẶN.
     * URL sai định dạng hoặc chuỗi rỗng -> BỊ CHẶN.
     * Kích hoạt demo trên production/staging -> BỊ CHẶN.
2. **Zero Secret Leaks & Git Boundary:**
   - 70 file meme demo và 5 background chỉ nằm trong thư mục `demo.local/catalog` (được `.gitignore` bảo vệ qua `*.local`).
   - Không có file `.env`, private key, signing token hay database credentials nào bị commit vào Git.
3. **Data Boundary & Anti-Tampering:**
   - Danh hiệu "SÁNG THẾ THẦN" được kiểm tra nghiêm ngặt dựa trên server role `ADMIN` và ID tài khoản hợp lệ, không thể giả mạo từ client.
   - Trần EXP mở rương (+2 EXP, max 200/ngày) được quản lý độc lập tại server, chống race condition bằng Idempotency-Key.

---

## 3. MA TRẬN KẾT QUẢ KIỂM THỬ (TEST VERIFICATION MATRIX)

### 3.1. Backend Unit Tests & Security Negative Suite
- **Pytest (Non-Integration):** `521 passed, 1 skipped, 798 deselected, 0 failed` (31.10s).
- **Email, Identity & MIME PDF Receipt Suite (`test_task7_google_email_reset.py` + `test_task10_identity.py`):** `12 passed, 0 failed` (2.55s).
- **Vault Negative Security Suite:** `17 passed, 0 failed` (1.51s), bao gồm toàn bộ negative tests chống lừa URL guard.

### 3.2. Frontend Unit Tests & Build
- **Node Test Runner:** `84 passed, 0 failed` (0.88s).
- **Production Build (`npm run build`):** `398 modules transformed, built in 4.66s` (0 syntax errors).

### 3.3. Browser E2E Thật & Autonomous QA Suite (Real Backend + PostgreSQL Clone `aurameme_qa`)
- **File test:** `auth-tests/vault-real-smoke.spec.js` (không dùng `route.fulfill()` cho Vault) — **1 PASSED (10.5s)**.
- **Autonomous Full QA Suite (Real Backend + Real Frontend + Real DB Clone):**
  * **Home Desktop & Mobile:** Sticky sidebars trái/phải (`position: sticky`), ảnh bài viết demo load thật HTTP 200 (`naturalWidth > 0`), không tràn ngang mobile (375×812).
  * **Vault Desktop & Mobile:** 15 vật phẩm/trang (5 cột × 3 hàng), đủ 70 Meme (5 trang) và 5 Background (1 trang), mở rương thật cộng +2 EXP, trang bị nền lưu bền vững sau reload.
  * **Public Profile (`/u/:username` & `/profile/:username`):** Hiển thị bộ sưu tập Meme đã sở hữu và Background đã sở hữu (tiêu đề căn giữa), tự động áp dụng hiệu ứng nền đã trang bị của chủ hồ sơ đang xem và khôi phục nền của người xem khi rời hồ sơ, đồng thời tải đầy đủ danh sách bài viết công khai của chủ hồ sơ.
  * **About (`/about`):** Liên kết email (`mailto:`) và GitHub (`target="_blank" rel="noopener noreferrer"`) chính xác cho Khang Dev và Kien Dev.
  * **Register, Verify Email & Reset Password:** Form 5 trường rõ ràng với báo lỗi inline theo từng ô; cho phép trùng tên hiển thị (`display_name`) nhưng bắt buộc `@tag` (`username`) duy nhất; chặn đăng nhập trước khi xác minh email (`403 ACCOUNT_UNVERIFIED`); kích hoạt tài khoản qua `/verify-email?token=...`; token đặt lại mật khẩu chỉ dùng 1 lần (`400 INVALID_RESET_TOKEN` khi dùng lại).
  * **Google Onboarding Modal:** Khi tài khoản Google mới chưa có `@tag`, hiển thị modal chọn `@tag` duy nhất với token ký HMAC-SHA256 thời hạn 15 phút (`POST /api/v1/auth/google/onboarding`).
  * **Email Design Polish & Live Gmail SMTP (`thothayvtv38@gmail.com`):**
    - Nhúng logo AuraMeme chính thức dạng inline CID PNG (`cid:aurameme-logo`, `image/png`) bên trái tên thương hiệu trong header mọi email.
    - Chuẩn hóa tiêu đề `[AuraMeme] - <Tiêu đề>` qua helper chống thiếu/trùng prefix.
    - Contact chỉ gửi **1 email xác nhận duy nhất** tới người gửi (`[AuraMeme] - Tiếp nhận góp ý`) theo bố cục `Mã tham chiếu → Chủ đề → Nội dung` (tự động xuống dòng, chống XSS), trong khi dữ liệu vẫn lưu đầy đủ trong DB và hiển thị tại `/admin/contacts`.
    - Biên nhận Premium phân biệt rõ nhãn phương thức (`Thẻ mô phỏng nội bộ`, `PayPal mô phỏng nội bộ`, `PayPal Sandbox`), giữ nút xem lịch sử và **đính kèm trực tiếp file PDF thật** (`AuraMeme-Receipt-AM-xxxx.pdf`, `application/pdf`) khớp 100% với bản tải từ website.

### 3.4. Browser UI Mocked Suites (Playwright Chrome)
*Các bộ test dưới đây sử dụng mock/stub mạng có chủ đích để kiểm thử giao diện, animation và phản hồi client:*
- `realm-title-task6.spec.js`: 2 passed (Ma trận 10 cảnh giới, danh hiệu Sáng Thế Thần, dark/light theme).
- `google-email-task7.spec.js`: 2 passed (Form Google login, luồng reset password & cooldown).
- `public-profile-cookie-task8.spec.js`: 2 passed (Hồ sơ công khai, follower count & Cookie banner).
- `lucian-ui-polish.spec.js`: 4 passed (Lucian #403 floating labels, #405 paper plane envelope, #409 cookie bite & crumbs).
- `vault-browser-smoke.spec.js`: 1 passed (Roulette reel animation & receipt modal UI).
- `premium-sandbox.spec.js`: 22 passed (Premium sandbox, checkout form, order history, PDF receipts).
- `profile-fidelity.spec.js`: 9 passed (Activity heatmap, geometry fidelity).
- `social-api.spec.js`: 14 passed (Post card, comment row, reactions, filters).

---

## 4. PHÂN LOẠI TRẠNG THÁI XÁC MINH (VERIFIED / MOCKED / NOT VERIFIED)

1. **Hệ thống gửi Email Gmail SMTP thực tế (`VERIFIED LIVE`):** Đã kết nối và gửi nhận thực tế qua `smtp.gmail.com:587` (STARTTLS) với tài khoản `AuraMeme - No Reply <thothayvtv38@gmail.com>`, xác nhận đầy đủ logo inline CID, tiêu đề `[AuraMeme] - <Tiêu đề>`, Contact 1 chiều và file đính kèm PDF biên nhận mở được, đầy đủ dấu tiếng Việt.
2. **Luồng Xác minh Email đăng ký, Đặt lại mật khẩu 1 lần & Google Onboarding chọn `@tag` (`VERIFIED E2E ON QA CLONE`):** Đã kiểm thử trọn vòng trên backend FastAPI thật, trình duyệt Chromium thật và PostgreSQL clone `aurameme_qa` tại revision `0016_account_email_verifications`.
3. **Google OAuth Popup với Google Cloud Client ID thật (`MOCKED TOKEN / LIVE OAUTH NOT VERIFIED`):** Luồng xác thực chữ ký onboarding token, kiểm tra trùng `@tag`, khởi tạo tài khoản và cấp session cookie đã kiểm thử thật trên DB; bước người dùng đăng nhập qua popup Google Identity Services bên ngoài cần `GOOGLE_CLIENT_ID` từ Google Cloud Console.
4. **PayPal Real Buyer Sandbox Popup (`MOCKED ADAPTER / LIVE POPUP NOT VERIFIED`):** Luồng tạo đơn hàng, đối soát mã đơn, thẻ mô phỏng nội bộ, tạo & đính kèm PDF biên nhận đã kiểm thử thật; bước đăng nhập tài khoản buyer trên trang `sandbox.paypal.com` cần buyer credentials của PayPal Developer.
5. **Database Production / Demo gốc (`PRESERVED / UNTOUCHED`):** Database `aurameme_demo` được giữ nguyên vẹn 100% tại revision `0012_aura_v1`. Toàn bộ migration `0013`–`0016` và kiểm thử QA chỉ chạy trên database clone độc lập `aurameme_qa` với role riêng `aurameme_qa`.

---

## 5. HƯỚNG DẪN KHỞI ĐỘNG MÔI TRƯỜNG QA

### 5.1. Thông tin truy cập website QA
- **URL Website:** `http://localhost:5173`
- **Backend API:** `http://127.0.0.1:8000`
- **Database:** PostgreSQL clone `aurameme_qa` trên port 5432.
- **File cấu hình cục bộ (đã gitignore):** `.env.qa` (không chứa bất kỳ secret nào trong Git).

### 5.2. Lệnh khởi động một bước (One-Step Launcher)
```powershell
cd D:\Big\du_an_lon\aura_meme_p2_task9
.\run_qa.bat
```
Hoặc khởi động từng dịch vụ nạp cấu hình từ `.env.qa`:
```powershell
# Terminal 1 - Backend:
cd D:\Big\du_an_lon\aura_meme_p2_task9\backend
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --env-file ..\.env.qa

# Terminal 2 - Frontend:
cd D:\Big\du_an_lon\aura_meme_p2_task9\frontend
npm.cmd run dev -- --host localhost --port 5173
```

---
*Trạng thái hiện tại: Đã hoàn tất toàn bộ kiểm thử tự động và chụp bằng chứng nghiệm thu, sẵn sàng bàn giao Codex review và merge vào `dev`.*
