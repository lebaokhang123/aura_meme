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

## 6. PRE-MERGE HOTFIX & ADMIN MVP (CHECKPOINTS A–E)

### 6.1. Tổng quan các hạng mục đã hoàn thành
Theo chỉ đạo của Owner trước khi bàn giao Codex nghiệm thu và merge vào `dev`, nhóm kỹ thuật Antigravity đã hoàn tất 5 Checkpoint tuần tự với độ phủ kiểm thử tự động toàn diện:

1. **Checkpoint A — Sửa lỗi chức năng cấp bách (`e7addd3`):**
   - **Thanh tìm kiếm Header (`SiteShell.jsx`):** Phím Backspace khi xóa rỗng ký tự giữ nguyên trang hiện tại, tuyệt đối không tự ý chuyển về Home hoặc reload; chỉ điều hướng khi nhấn Enter hoặc click nút tìm kiếm; phím tắt `Ctrl+K` kích hoạt ô tìm kiếm; phím `Escape` hủy focus an toàn.
   - **Thương hiệu Biên nhận PDF (`receipt-pdf.js`, `receipt_pdf.py`):** Khôi phục đầy đủ nhận diện thương hiệu `AURAMEME`, `AuraMeme Community`, `https://aurameme.com`, `AuraSpark Global Inc.`, `thothayvtv38@gmail.com` và ghi chú pháp lý phi thương mại.
   - **Khóa danh tính Contact (`contact.py`, `ContactPage.jsx`):** Loại bỏ hoàn toàn việc nhận tên/email giả mạo từ client. Hệ thống tự động đọc danh tính trực tiếp từ phiên đăng nhập backend; ô Họ tên và Email được khóa `readOnly` kèm biểu tượng ổ khóa bảo mật.
   - **Tối ưu kết nối Database (`db.py`):** Ổn định connection pool với cấu hình `pool_size=10, max_overflow=20, pool_timeout=15, pool_recycle=1800, pool_pre_ping=True`, ngăn ngừa triệt để lỗi nghẽn connection khi kiểm thử tải.
   - **Đồng bộ hiệu ứng nền Hồ sơ (`main.jsx`, `ProfilePage.jsx`):** Khi xem hồ sơ người dùng không trang bị hiệu ứng nền, hệ thống tự động hoàn nguyên về nền mặc định, không bị lưu đè hiệu ứng nền của tài khoản trước đó.

2. **Checkpoint B — Lucian Auth UI & Đăng ký Chuẩn mực (`85a7f98`):**
   - **Nút Google Sign-in Lucian #401 (`LucianGoogleButton.jsx`):** Chuẩn hóa 3 trạng thái (Chờ: logo Google chính thức + "Tiếp tục với Google"; Đang kết nối: vòng xoay 4 màu Google quay vô tận + "Đang kết nối…"; Thành công: dấu tích xanh + "Đã đăng nhập"). Modal Google Onboarding hiển thị logo chữ G chuẩn 4 màu.
   - **Form Đăng ký Lucian #244 (`LucianRegisterForm.jsx`):** Khung tóm tắt lỗi tổng (`.u244-sm` / `.u244-sb`), hiệu ứng rung lắc `.is-shake` khi submit có lỗi, nhãn báo lỗi inline chi tiết từng ô (`.u244-ms`), huy hiệu kiểm tra hợp lệ live (`.u244-ok`).
   - **Chính sách bảo mật:** Checkbox điều khoản mặc định chưa tick, liên kết duy nhất tới `/privacy.html`, thông báo lỗi rõ ràng nếu người dùng chưa đồng ý.

3. **Checkpoint C — Admin UI & Quản trị Tài khoản 30 Ngày (`e1f2951`):**
   - **Sidebar Quản trị viên (`AdminPage.jsx`):** Loại bỏ hoàn toàn mục "QUẢN LÝ CỘNG ĐỒNG" và card "Quyền quản trị" rườm rà; tinh chỉnh liên kết "Về trang chủ".
   - **Nút Tìm kiếm Icon:** Tích hợp nút kính lúp dạng icon-only trực tiếp bên trong `.admin-search-input-wrap`.
   - **Xóa mềm và Khôi phục 30 ngày (`admin_users.py`, `auth_schemas.py`):** Cung cấp API `POST /api/v1/admin/users/{user_id}/restore` cùng trường `deleted_at`; giao diện hiển thị huy hiệu đếm ngược số ngày còn lại trước khi xóa vĩnh viễn kèm các nút thao tác nhanh (Khóa/Mở khóa, Phân quyền, Xóa/Khôi phục).

4. **Checkpoint D — Admin Catalog & Quản trị Tài sản Meme (`8303770`):**
   - **Định dạng danh sách 3 dòng:** Dòng 1 Tên hiển thị (`display_name`), Dòng 2 UUID đầy đủ kèm nút sao chép tiện lợi, Dòng 3 Phân loại chi tiết (`Avatar · Hạng D · Đã duyệt`).
   - **Bộ nút thao tác chuẩn:** 3 icon thao tác rõ ràng (Xem trước, Chỉnh sửa, Xóa/Lưu trữ).
   - **Upload Meme Avatar Modal:** Nút (+) mở modal tải lên file `.jpg`, `.png`, hoặc `.zip` hàng loạt.
   - **Quy chuẩn đặt tên tệp nghiêm ngặt:** Bắt buộc tuân thủ `<Rank>_<ddmmyy>_<stt>.<ext>` (`Rank` thuộc `D, C, B, A, S`, ngày tháng hợp lệ, số thứ tự tự nhiên).
   - **Hàng đợi duyệt & Modal xem trước đa ngữ cảnh:** Hiển thị danh sách vật phẩm chờ duyệt (`pending`) với modal xem trước đồng thời 4 ngữ cảnh: Avatar 1:1, Khung hồ sơ, Biểu cảm bình luận, và Hộp rương bảo khố; hỗ trợ Duyệt (`approve`), Từ chối (`reject`) và Lưu trữ (`archive`).
   - **Bảo vệ di sản:** Khóa bảo vệ tuyệt đối 70 Meme demo và 5 Background gốc, không cho phép xóa hay chuyển trạng thái từ chối.
   - **Tương thích Cookie Consent:** Cập nhật bộ phân giải `cookie-consent.js` tương thích ngược linh hoạt, không chặn tương tác trình duyệt khi thiếu trường tùy chọn.

5. **Checkpoint E — Hồi quy Kiểm thử & Chụp Bằng chứng Nghiệm thu (`2ff2a6c`, `7cdffc4`):**
   - Đồng bộ hóa logic tìm kiếm client-side feed (`feed-data.js`), cách ly quyền riêng tư kho đồ hồ sơ (`ProfilePage.jsx`), chuẩn hóa văn bản xác nhận Contact và điều chỉnh nhịp đồng bộ của roulette rương bảo khố.
   - Toàn bộ các suite kiểm thử tự động đạt 100% tỷ lệ pass.

### 6.2. Nhật ký Commit (Branch: `fix/premerge-owner-hotfix-admin`)
```text
7cdffc4 test(qa): bo sung kich ban capture bang chung va xac minh giao dien checkpoint a-d
2ff2a6c fix(regression): dong bo kiem thu bo loc, thong bao contact, privacy ho so va smoke bao kho
8303770 feat(admin-catalog): quan ly vat pham meme, upload jpg png zip theo quy chuan ten va duyet pending
e1f2951 feat(admin): tinh chinh sidebar, nut tim kiem icon va quan ly xoa khoi phuc tai khoan 30 ngay
85a7f98 feat(auth-ui): tich hop nut google lucian #401, form dang ky lucian #244 va checkbox chinh sach bao mat
e7addd3 fix(hotfix): sua tim kiem header, khoi phuc thuong hieu bien lai pdf, khoa danh tinh contact va nen ho so
```

### 6.3. Bảng Ma trận Kiểm thử Tự động (Verification Matrix)
| Phạm vi kiểm thử | Lệnh thực thi | Kết quả | Trạng thái |
| :--- | :--- | :--- | :--- |
| **Backend Unit & Logic** | `pytest -m "not integration" -q` | **525 passed, 1 skipped** (0 failed) | **PASSED** |
| **Frontend Unit Tests** | `node --test frontend/tests/*.test.mjs` | **84 passed** (0 failed) | **PASSED** |
| **Frontend Production Build**| `cd frontend; npm run build` | **0 errors, build in 5.76s** | **PASSED** |
| **Playwright Full Suite** | `npx playwright test (13 spec files)` | **172 passed** (0 failed) | **PASSED** |

### 6.4. Ma trận Bằng chứng Nghiệm thu (Captured Screenshots)
Toàn bộ 10 ảnh chụp màn hình bằng chứng nghiệm thu đã được lưu trữ bền vững tại thư mục artifact `C:\Users\sammy\.gemini\antigravity\brain\cc803197-d415-4eaf-80c2-1173a22c12aa`:

1. `qa_17_search_header_fix.png` (255,481 bytes) — Thanh tìm kiếm header giữ nguyên trang khi xóa ký tự bằng Backspace.
2. `qa_18_pdf_receipt_restored_branding.png` (137,761 bytes) — Biên nhận PDF hiển thị đầy đủ nhận diện thương hiệu AuraMeme và ghi chú pháp lý.
3. `qa_19_contact_identity_locked.png` (109,709 bytes) — Form liên hệ tự động khóa danh tính người dùng theo session DB thật với icon ổ khóa.
4. `qa_20_lucian_401_google_button.png` (254,225 bytes) — Nút Google Lucian #401 và modal Google Onboarding với chữ G 4 màu.
5. `qa_21_lucian_244_register_validation.png` (244,281 bytes) — Form đăng ký Lucian #244 với khung báo lỗi tổng, hiệu ứng rung và inline message.
6. `qa_22_register_privacy_checkbox.png` (274,284 bytes) — Checkbox Chính sách bảo mật mặc định chưa chọn, liên kết `/privacy.html`.
7. `qa_23_admin_sidebar_cleaned.png` (100,767 bytes) — Sidebar Admin được dọn dẹp gọn gàng, bỏ mục thừa, có nút về trang chủ.
8. `qa_24_admin_users_30day_restore.png` (95,072 bytes) — Bảng quản trị tài khoản với huy hiệu đếm ngược 30 ngày xóa mềm và nút khôi phục.
9. `qa_25_admin_catalog_meme_upload.png` (185,594 bytes) — Modal upload Meme Avatar chuẩn hóa quy tắc tên file `<Rank>_<ddmmyy>_<stt>.<ext>`.
10. `qa_26_admin_catalog_pending_preview.png` (137,580 bytes) — Hàng đợi duyệt tài sản Meme và modal xem trước đa ngữ cảnh (Avatar, Khung, Reaction, Hộp quà).

---
*Trạng thái kết luận bàn giao:* **READY FOR CODEX REVIEW**

