# AuraMeme — Task 3: Trang Chính sách Bảo mật (Privacy Policy) Engineering Handoff

Tài liệu bàn giao kỹ thuật hoàn thành **Task 3 — Xây dựng Trang Chính sách Bảo mật (Privacy Policy Page)** cho nền tảng mạng xã hội tu tiên cyberpunk AuraMeme, tuân thủ chặt chẽ chỉ đạo của Owner và định hướng giám sát của ChatGPT.

---

## 1. Tổng quan & Checkpoint Git

- **Repository:** `D:\Big\du_an_lon\aura_meme_p2_clean`
- **Nhánh phát triển:** `feat/policies-task3`
- **Base commit SHA:** `74a0397` (`fix(admin): bỏ nút đính chính thông báo đã phát` — commit chốt của Task 2)
- **Tập tin tạo mới / chỉnh sửa:**
  - `frontend/public/privacy.html` — Trang chính sách bảo mật HTML5 độc lập, song ngữ, đa chủ đề.
  - `frontend/auth-tests/privacy-policy.spec.js` — Bộ kiểm thử tự động Playwright gồm 11 kịch bản toàn diện.
  - `docs/tasks/policies-task3.md` — Báo cáo kỹ thuật bàn giao chi tiết.
- **URL xem trước trực tiếp:** `http://127.0.0.1:5173/privacy.html` (hoặc qua Vite preview).
- **Trạng thái:** Hoàn tất 100%; toàn bộ 11 kiểm thử Playwright và 70 kiểm thử unit test đều đạt kết quả PASS.

---

## 2. Kiến trúc Kỹ thuật & Căn cứ Pháp lý

### 2.1. Căn cứ Pháp lý Việt Nam áp dụng
Nội dung chính sách được xây dựng bám sát thực tế kiến trúc mã nguồn của AuraMeme và các văn bản quy phạm pháp luật hiện hành tại Việt Nam:
1. **Luật Bảo vệ dữ liệu cá nhân số 91/2025/QH15:** Quy định về sự đồng ý rõ ràng, minh bạch mục đích xử lý dữ liệu, quyền của chủ thể dữ liệu (truy cập, rút lại sự đồng ý, xóa dữ liệu) và bảo vệ dữ liệu trẻ em.
2. **Nghị định số 356/2025/NĐ-CP:** Quy định chi tiết các biện pháp kỹ thuật và tổ chức bảo vệ dữ liệu cá nhân.
3. **Nghị định số 147/2024/NĐ-CP:** Quy định về quản lý, cung cấp, sử dụng dịch vụ Internet và thông tin trên mạng (yêu cầu lưu trữ thông tin xác thực tài khoản, nhật ký kết nối tối thiểu để phục vụ an toàn an ninh mạng).

### 2.2. Cấu trúc 11 Điều khoản Chính sách
Toàn bộ văn bản gồm 11 phần song ngữ (Tiếng Việt mặc định và Tiếng Anh):
1. **Giới thiệu và Phạm vi áp dụng (Introduction & Scope):** Giới thiệu nền tảng AuraMeme, nguyên tắc xử lý dữ liệu và gắn badge ghi chú trạng thái dự thảo kỹ thuật tương ứng giai đoạn P2 Social MVP.
2. **Các loại dữ liệu AuraMeme thu thập (Data We Collect):** Minh bạch các bảng dữ liệu thực tế trong database PostgreSQL: tài khoản (username, email, Argon2/Bcrypt hash), hồ sơ tu tiên (bio, danh hiệu cảnh giới, cấp độ Aura, avatar, background), nội dung mạng xã hội (bài đăng meme, bình luận, reaction), lịch sử điểm danh daily check-in, nhật ký AuraLedger, hòm đồ vật phẩm Vault, thư liên hệ và nhật ký quản trị AdminAuditLog.
3. **Mục đích & Căn cứ xử lý dữ liệu (Purposes & Legal Grounds):** Nêu rõ mục đích vận hành tài khoản, tính toán Rank/Level, kiểm duyệt an toàn mạng xã hội, gửi thông báo hệ thống và căn cứ hợp đồng dịch vụ / sự đồng ý của người dùng.
4. **Dữ liệu công khai & Dữ liệu riêng tư (Public vs Private Data):** Phân định ranh giới bảo mật nghiêm ngặt (theo đúng hợp đồng DTO backend):
   - *Công khai:* Tên hiển thị, username, cảnh giới, cấp độ tu tiên, bài đăng, bình luận công khai, huy hiệu đã trang bị.
   - *Riêng tư:* Địa chỉ email cá nhân, mật khẩu băm, CSRF token, session token, thư gửi admin, IP kết nối, lịch sử audit log.
5. **Cookie & Lưu trữ trình duyệt (Cookies & Local Storage):**
   - Cookie phiên HttpOnly, SameSite=Lax/Strict ngăn ngừa XSS/CSRF.
   - Lưu trữ `localStorage` duy nhất cho tùy chọn giao diện (`aurameme-ui-preferences` gồm theme dark/light và language vi/en).
   - Cam kết không sử dụng cookie theo dõi quảng cáo của bên thứ ba (no third-party tracking pixels).
6. **Bảo mật & Kiểm soát truy cập (Security & Access Control):** Mã hóa mật khẩu một chiều (Argon2 / Bcrypt), bảo vệ chống tấn công CSRF hai lớp, phân quyền theo vai trò (RBAC: USER, ADMIN), giới hạn tần suất request (Rate Limiting) và nhật ký AdminAuditLog lưu vết hành vi quản trị.
7. **Chia sẻ dữ liệu & Dịch vụ bên thứ ba (Data Sharing & Third Parties):** Khẳng định không bán dữ liệu người dùng; chỉ lưu trữ trên hạ tầng máy chủ cục bộ / tự host; cơ chế Aura Plus / Prime hiện là mô phỏng sandbox, không tích hợp cổng thanh toán bên ngoài.
8. **Thời gian lưu trữ & Xóa dữ liệu (Retention & Deletion):** Quy định thời gian lưu trữ dữ liệu tài khoản (cho đến khi có yêu cầu xóa), thời gian lưu vết nhật ký an ninh mạng tối thiểu theo NĐ 147/2024/NĐ-CP (12 tháng).
9. **Quyền của chủ thể dữ liệu (Your Data Rights):** Hướng dẫn người dùng thực thi đầy đủ quyền: xem/sửa thông tin hồ sơ, yêu cầu trích xuất dữ liệu, thu hồi sự đồng ý hoặc yêu cầu xóa tài khoản thông qua trang Hồ sơ hoặc form Liên hệ ban quản trị.
10. **Người dùng chưa thành niên (Children & Minors):** Quy định độ tuổi tối thiểu sử dụng dịch vụ (khuyến nghị 13+ hoặc có sự đồng ý của cha mẹ/người giám hộ theo quy định pháp luật).
11. **Cập nhật chính sách & Kênh liên hệ (Updates & Contact):** Quy trình thông báo khi chính sách có thay đổi và thông tin liên hệ chính thức qua form `/contact` hoặc email quản trị.

---

## 3. Điểm nhấn Thiết kế & Trải nghiệm Người dùng (UX/UI)

- **Trang độc lập, Zero Dependency:** Được viết hoàn toàn bằng HTML5 ngữ nghĩa, CSS thuần (CSS Custom Properties) và Vanilla JS, không phụ thuộc thư viện bên ngoài giúp tải trang siêu tốc (<150ms).
- **Bộ đôi Chủ đề Cyberpunk Dark & Clean Light:**
  - *Dark Theme (mặc định):* Tông nền `#12131a`, viền `#2d3042`, điểm nhấn tím cyberpunk `#d0bcff` và cyan `#4cd7f6`, tương đồng tuyệt đối với toàn bộ hệ thống AuraMeme Stitch UI.
  - *Light Theme:* Độ tương phản cao, nền sáng mịn `#f8f8fc`, chữ `#1b1b22`, đảm bảo đọc văn bản dài không mỏi mắt.
- **Chuyển đổi Ngôn ngữ Song ngữ (VI / EN):** Nút toggle trên thanh điều hướng cho phép chuyển nhanh giữa Tiếng Việt và Tiếng Anh; đồng bộ trực tiếp với `aurameme-ui-preferences` trong `localStorage`.
- **Zero-JS Fallback:** Khi người dùng tắt JavaScript trong trình duyệt, trang vẫn tự động hiển thị đầy đủ 100% nội dung Tiếng Việt nhờ bộ quy tắc CSS `html[lang="vi"] .lang-en { display: none !important; }`.
- **Mục lục Điều hướng Thông minh (Table of Contents):**
  - *Trên Desktop (>=1024px):* Sidebar dính cố định (`position: sticky`), tích hợp ScrollSpy dựa trên `IntersectionObserver` tự động đánh dấu mục đang xem.
  - *Trên Mobile (<1024px):* Menu xổ xuống dạng `<details class="policy-mobile-toc">` gọn gàng, tiết kiệm không gian màn hình.
- **Hỗ trợ In ấn & Xuất PDF (`@media print`):** Tự động ẩn thanh điều hướng, nút bấm, sidebar và mở rộng toàn văn bản với màu chữ đen nền trắng chuẩn văn kiện pháp lý khi người dùng nhấn `Ctrl + P`.

---

## 4. Kết quả Kiểm thử Toàn diện

### 4.1. Bộ Kiểm thử Tự động Playwright (`auth-tests/privacy-policy.spec.js`)
Đã triển khai và chạy thành công 11 test case:
1. `Direct navigation to /privacy.html returns 200 and non-empty content` — **PASS (1.6s)**
2. `Refreshing /privacy.html preserves content intact` — **PASS (1.6s)**
3. `Back link navigates to home page and direct /privacy.html link works` — **PASS (2.4s)**
4. `Default VI displays Vietnamese sections and hides English` — **PASS (1.6s)**
5. `Switching language to EN displays English and updates title` — **PASS (1.8s)**
6. `Switching theme toggles data-theme and dark class` — **PASS (1.6s)**
7. `Preferences restore from localStorage on page reload` — **PASS (1.6s)**
8. `Anchor links (#sec-1 to #sec-11) point to valid sections and scroll` — **PASS (2.2s)**
9. `Responsive layout has no horizontal overflow across viewports (375x812, 768x1024, 1440x900)` — **PASS (1.9s)**
10. `Zero-JS fallback displays Vietnamese content properly` — **PASS (1.7s)**
11. `Capture visual screenshots for Desktop Dark, Desktop Light, and Mobile Dark` — **PASS (1.9s)**

**Tổng kết:** **11 passed (24.3s)**, 0 failed.

### 4.2. Bộ Kiểm thử Hồi quy Frontend
- **Frontend Unit Tests:** 70/70 PASS (`node --test tests/*.test.mjs`, thời gian chạy 760ms).
- **Vite Production Build:** Thành công 100% trong 2.49s (`npm run build`).

### 4.3. Bằng chứng Hình ảnh Visual QA
Các tệp ảnh chụp thực tế đã được lưu trữ tại thư mục artifacts:
1. `privacy_policy_desktop_dark.png` — Giao diện máy tính chế độ Tối (Dark mode).
2. `privacy_policy_desktop_light.png` — Giao diện máy tính chế độ Sáng (Light mode).
3. `privacy_policy_mobile_dark.png` — Giao diện điện thoại di động chế độ Tối (Mobile Dark mode 375px).

---

## 5. Những Điểm Cần Chủ Sở Hữu (Owner) Xác Nhận / Phê Duyệt Pháp Lý

Bản chính sách hiện tại là **bản dự thảo kỹ thuật minh bạch**, được xây dựng dựa trên mã nguồn thực tế của AuraMeme. Để trở thành văn bản pháp lý chính thức có hiệu lực công bố ra công chúng, Owner cần rà soát và bổ sung 4 thông tin:
1. **Tên pháp nhân chính thức:** Cập nhật tên công ty/tổ chức sở hữu nền tảng AuraMeme và mã số doanh nghiệp (nếu có).
2. **Kênh tiếp nhận khiếu nại chuyên trách:** Xác định hộp thư điện tử chính thức của Người phụ trách bảo vệ dữ liệu (DPO), ví dụ: `dpo@aurameme.vn` hoặc `privacy@aurameme.vn`.
3. **Thời hạn lưu trữ nhật ký:** Xác nhận chính sách lưu trữ nhật ký truy cập (dự thảo đang ghi tối thiểu 12 tháng theo NĐ 147/2024/NĐ-CP).
4. **Cơ chế xác minh độ tuổi trẻ em:** Xác nhận quy trình kiểm tra và thu thập sự đồng ý của cha mẹ/người giám hộ khi người dùng dưới 16 tuổi đăng ký tài khoản theo Luật BV DLCN 91/2025/QH15.

---

## 6. Hướng dẫn Nghiệm thu Nhanh cho Owner

1. Mở trình duyệt và truy cập `http://127.0.0.1:5173/privacy.html`.
2. Kiểm tra giao diện mặc định (chủ đề Dark Cyberpunk, ngôn ngữ Tiếng Việt, mục lục bên trái).
3. Bấm nút biểu tượng mặt trời/mặt trăng trên thanh điều hướng để xem chuyển đổi Dark/Light mode tức thì.
4. Bấm nút `EN` để chuyển đổi toàn bộ 11 điều khoản sang Tiếng Anh.
5. Thử click các mục lục từ mục 1 đến mục 11 để kiểm tra cuộn mượt (smooth scroll) đến từng điều khoản.
6. Thu nhỏ cửa sổ trình duyệt xuống kích thước điện thoại để trải nghiệm menu mục lục di động dạng rút gọn.
