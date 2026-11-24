# AuraMeme — Task 4: Level, Chức Danh & UI Polish Engineering Handoff

## Checkpoint kỹ thuật 22/11/2026

Hai patch cuối 6e72143 và 72f2032 tương đương c72f8b2 và 27a3b7a trên Task 5. Chức danh công khai không tham gia kiểm quyền. Sửa thứ tự khởi tạo biến tác giả của bình luận để feed mock render được. Bộ Profile/Contact đã chạy đủ chín ca sau khi đổi phép đo form sang khoảng cách thực giữa các phần tử.

Tài liệu bàn giao kỹ thuật hoàn thành **Task 4: Chuẩn hóa Level, Chức danh tác giả & Tinh chỉnh Giao diện** cho nền tảng AuraMeme theo chỉ đạo của Owner và ChatGPT.

---

## 1. Tổng quan & Checkpoint Git

- **Repository:** `D:\Big\du_an_lon\aura_meme_p2_clean`
- **Nhánh phát triển:** `feat/identity-level-title-task4`
- **Base commit SHA:** `bdb0889` (`fix(privacy): hoàn thiện nội dung và đồng bộ footer`)
- **Tập tin đã sửa đổi & bổ sung:**
  - `backend/app/account_schemas.py`: Bổ sung `level`, `realm`, `title` vào `UserPublic` với model validator suy diễn cảnh giới và chức danh đặc biệt (`khang_dev` -> "Bá Chủ Thiên Lôi", `kien_dev` -> "Thiên Tướng Độ Ách", người dùng thường -> Cảnh giới).
  - `backend/app/aura_runtime.py`: Bổ sung `public_level_column(now)` (truy vấn con vô hướng, loại bỏ hoàn toàn N+1 queries) và `read_public_level(db, owner, now)`. Sửa lỗi so sánh JSONB bằng `cast(literal(_SNAPSHOT), JSONB)`.
  - `backend/app/blog.py`: Tích hợp `public_level_column` vào `public_posts`, `post_dto`, `list_posts`, `create_post`, `get_post`, `update_post`.
  - `backend/app/comments.py`: Tích hợp `public_level_column` vào `comment_dto`, `list_comments`, `add_comment`, `list_user_comments`.
  - `backend/app/account.py`: Cập nhật `get_public_user` trả về level/realm/title qua `public_level_column`.
  - `backend/tests/test_health.py` & `backend/tests/test_aura_reads.py`: Bổ sung kiểm thử schema OpenAPI và kiểm thử bảo vệ chính sách SQL subquery.
  - `frontend/src/social-api.js`: Chuẩn hóa mapping `apiAuthor` hiển thị `LVL X · Chức danh`.
  - `frontend/src/components/PostCard.jsx`: Tích hợp `LevelPill` và `nickname` hiển thị định dạng chuẩn.
  - `frontend/src/components/CommentSection.jsx`: Hiển thị `LevelPill` và chức danh trong từng hàng bình luận.
  - `frontend/src/components/ProfilePage.jsx`: Cập nhật hiển thị chức danh tại header và truyền thông tin public level sang `AuraProgress`.
  - `frontend/src/components/AuraProgress.jsx`: Đồng bộ layout khung Level/chức danh Trang chủ (`.am-home-aura-progress`), hỗ trợ tài khoản đăng nhập động lẫn fallback.
  - `frontend/src/profile-page.css`: Thêm style `.am-home-aura-progress`, tinh chỉnh toàn diện Aura Activity Grid (màu sắc tím/cyan native, tooltip nhạy, cuộn mượt di động).
  - `frontend/src/contact-page.css`: Thay thế 5 khai báo `'Times New Roman'` bằng `'Plus Jakarta Sans'` và `'Inter'`.
  - `frontend/tests/social-api.test.mjs` & `frontend/auth-tests/social-api.spec.js`: Cập nhật unit test và bổ sung E2E test cho Level & Chức danh.

---

## 2. Chi tiết 4 Hạng mục Triển khai

### 2.1. Hạng mục 1 — Chuẩn hóa Tác giả trên Bài viết & Bình luận
- **Quy tắc hiển thị:** Định dạng thống nhất `Tên hiển thị · @username · LVL X · Chức danh` trên Home Feed, Explore, Profile và mục Bình luận.
- **Quy tắc Chức danh:**
  - Admin/Tác giả đặc biệt có chức danh tôn hiệu máy chủ quy định (`khang_dev`: "Bá Chủ Thiên Lôi", `kien_dev`: "Thiên Tướng Độ Ách").
  - Người dùng thông thường hiển thị Cảnh giới tương ứng với Level (`LVL 1` -> "Luyện Khí", `LVL 25` -> "Trúc Cơ", v.v.).
  - Khi chưa có Level (`level is None`), hệ thống ẩn cả Level, Realm và Title để đảm bảo an toàn dữ liệu.
- **Kiến trúc Zero N+1:** `public_level_column` được tính toán trực tiếp thông qua một correlated scalar subquery gắn vào câu lệnh SELECT của danh sách bài viết/bình luận, hoàn toàn không phát sinh N+1 truy vấn database.
- **Tương thích Mobile:** Cụm badge danh hiệu tự động xuống dòng mượt mà khi màn hình hẹp, không gây tràn ngang khung (overflow).

### 2.2. Hạng mục 2 — Đồng bộ Ô Level / Chức danh tại Trang chủ
- **Vấn đề trước đây:** Ô Level ở sidebar Trang chủ bị tràn viền, text đè nhau, fix cứng giá trị cũ "Lvl 79", không khớp với ô Thông tin tài khoản chuẩn.
- **Giải pháp:** Sử dụng component `AuraProgress` tái sử dụng với class `.am-home-aura-progress`.
  - Bố cục flex dọc cân đối, bo góc `border-radius: 12px`, bóng đổ nhẹ `box-shadow: 0 0 20px rgba(168, 85, 247, 0.12)`.
  - Badges Level và Chức danh đặt trong `.am-profile-badges` căn giữa, viền vàng kim hổ phách sắc nét.
  - Thanh tiến độ hiển thị phần trăm Exp chuẩn xác, caption `Exp` và `Chuỗi ngày` rõ ràng.
  - Hiển thị động theo tài khoản đang đăng nhập hoặc fallback chuẩn khi chưa đăng nhập.

### 2.3. Hạng mục 3 — Tinh chỉnh Lịch Hoạt động Aura trên Trang Cá nhân (`/profile`)
- **Vấn đề trước đây:** Lưới đóng góp mang giao diện mặc định GitHub (màu `#0d1117`, xanh lá), chưa đồng bộ ngôn ngữ thiết kế AuraMeme cyberpunk/tu chân.
- **Giải pháp:**
  - Nền lưới sử dụng token `var(--am-surface-container-lowest)` kết hợp viền mờ `var(--am-outline-variant)`.
  - 5 cấp độ hoạt động (0 -> 4) được thiết kế theo dải màu tím/cyan nhận diện của AuraMeme:
    - Dark mode: Level 0 (`#13082a`), Level 1 (`#3b1875`), Level 2 (`#7c3aed`), Level 3 (`#a855f7`), Level 4 (`#06b6d4` cyan rực rỡ).
    - Light mode: Level 0 (`#f1f5f9`), Level 1 (`#d8b4fe`), Level 2 (`#a855f7`), Level 3 (`#7e22ce`), Level 4 (`#0284c7`).
  - Tooltip hiển thị thông tin ngày đóng góp với giao diện bo góc, bóng mờ mịn, định vị tự động tránh tràn màn hình.
  - Cuộn ngang tự nhiên trên thiết bị di động với `-webkit-overflow-scrolling: touch`.
  - **Bảo toàn nguyên vẹn:** Thuật toán 53 tuần / 371 ô, kích thước chuẩn 741px x 146px, điều hướng bàn phím (Arrow keys / Tab / Focus) và xử lý timezone.

### 2.4. Hạng mục 4 — Chuẩn hóa Font chữ Trang Liên hệ (`/contact`)
- **Vấn đề trước đây:** Trong `frontend/src/contact-page.css` còn tồn đọng 5 vị trí sử dụng font `'Times New Roman'`.
- **Giải pháp:**
  - Tiêu đề và nút gửi: Chuẩn hóa về `'Plus Jakarta Sans', sans-serif`.
  - Nhãn, nhóm chủ đề và văn bản hướng dẫn: Chuẩn hóa về `'Inter', sans-serif`.
  - Giữ nguyên cấu trúc form, validation và toàn bộ hành vi gửi thông tin liên hệ.

### 2.5. Hạng mục 5 — Bản vá Hoàn thiện (Task 4 Final Polish)
- **Chuẩn hóa Helper Thời gian Tương đối (`relativeTime`):**
  - Tự động chuyển đổi đa đơn vị mốc thời gian: giây (`giây trước` / `seconds ago`), phút (`phút trước` / `minutes ago`), giờ (`giờ trước` / `hours ago`), ngày (`ngày trước` / `days ago`), tháng (`tháng trước` / `months ago`), năm (`năm trước` / `years ago`).
  - Sử dụng chuẩn `Intl.RelativeTimeFormat(lang, { numeric: 'always' })` quốc tế, hỗ trợ đầy đủ song ngữ VI và EN theo tùy chọn người dùng.
  - Xử lý biên an toàn: các mốc thời gian trong tương lai, 0 giây trôi qua hoặc giá trị không hợp lệ (`null`, `undefined`, `NaN`, chuỗi không phải ngày) đều trả về `Vừa xong` (VI) hoặc `Just now` (EN).
  - Tách thành module `frontend/src/relative-time.js` độc lập để phục vụ kiểm thử đơn vị nhanh và tối ưu tải trang.
  - Ưu tiên tính động theo `post.createdAt` trên cả `PostCard` và `PostHeader`, không để nhãn tĩnh che khuất thời gian thực tế.
- **Tái cấu trúc Tiêu đề Bình luận thành 2 Dòng:**
  - Dòng 1: Tên hiển thị · @username · LevelPill · Chức danh.
  - Dòng 2: Mốc thời gian tương đối hiển thị màu mờ (muted, `text-outline`), font mono nhỏ gọn (`10.5px`), nằm ngay dưới dòng 1 và ở trên nội dung bình luận.
  - Dòng 3: Nội dung văn bản bình luận.
  - Bố cục flex dọc bảo đảm không bị tràn ngang hoặc che khuất menu thao tác (xóa/ẩn) trên cả di động và máy tính.
- **Đồng bộ Song ngữ VI / EN cho ô "AURA PERKS" tại Trang chủ:**
  - Tạo component tái sử dụng `AuraPerksCard.jsx` tích hợp hook `usePreferences()`.
  - Thay thế toàn bộ mã cố định tiếng Việt bằng cơ chế song ngữ:
    - Kicker badge: `AURA PERKS` & `Sắp ra mắt` / `Coming soon`.
    - Tiêu đề & mô tả: `Aura Plus / Prime` & `Sắp ra mắt: bonus Exp dành cho Level.` / `Coming soon: bonus EXP for your Level.`.
    - 4 dòng đặc quyền (perks): dịch mượt mà, giữ trọn icon và màu sắc.
    - Nút CTA: `Xem Plus / Prime` -> `Explore Plus / Prime` trỏ về `/premium`.
  - Giữ trọn bố cục Stitch gốc, không làm vỡ viền hay hiệu ứng ánh sáng gradient.

---

## 3. Kết quả Kiểm thử & Xác minh (Verification Evidence)

### 3.1. Backend Unit & Regression Tests (Pytest)
```powershell
cd backend
Remove-Item Env:AUTH_ENVIRONMENT -ErrorAction SilentlyContinue
Set-Item -Path Env:DATABASE_URL -Value "postgresql+psycopg://test:not-a-real-secret@127.0.0.1:1/test"
.\.venv_p2\Scripts\python.exe -m pytest -m "not integration" -q
```
- **Kết quả:** **419 passed, 787 deselected, 0 failed** in 45.34s.

### 3.2. Frontend Unit Tests
```powershell
node --test tests/*.test.mjs
```
- **Kết quả:** **70 passed, 0 failed** (tất cả 70 bộ kiểm thử đơn vị thành công 100%).

### 3.3. Frontend Production Build
```powershell
cd frontend
npm.cmd run build
```
- **Kết quả:** **Vite build SUCCESS** (thời gian build 4.70s, sinh bundle tối ưu trong `dist/`).

### 3.4. Playwright End-to-End Test Suite
```powershell
npx.cmd playwright test --config=../.github/playwright.auth.config.mjs auth-tests/social-api.spec.js auth-tests/profile-fidelity.spec.js auth-tests/profile-contact.spec.js auth-tests/aura-api.spec.js auth-tests/rank-api.spec.js --workers=1 --retries=0
```
- **Kết quả:** **64 passed, 0 failed** (14 tests `social-api.spec.js` + 50 tests `profile-fidelity/contact/aura/rank`).

---

## 4. Minh chứng Giao diện (Screenshots Artifacts)

12 ảnh chụp màn hình kiểm định thực tế được lưu tại thư mục artifacts:
- **Trang chủ (Home):**
  - `task4_home_desktop_dark.png` (Desktop 1440px Dark Mode)
  - `task4_home_desktop_light.png` (Desktop 1440px Light Mode)
  - `task4_home_mobile_dark.png` (Mobile 375px Dark Mode)
  - `task4_home_mobile_light.png` (Mobile 375px Light Mode)
- **Trang cá nhân (Profile):**
  - `task4_profile_desktop_dark.png` (Desktop 1440px Dark Mode)
  - `task4_profile_desktop_light.png` (Desktop 1440px Light Mode)
  - `task4_profile_mobile_dark.png` (Mobile 375px Dark Mode)
  - `task4_profile_mobile_light.png` (Mobile 375px Light Mode)
- **Trang liên hệ (Contact):**
  - `task4_contact_desktop_dark.png` (Desktop 1440px Dark Mode)
  - `task4_contact_desktop_light.png` (Desktop 1440px Light Mode)
  - `task4_contact_mobile_dark.png` (Mobile 375px Dark Mode)
  - `task4_contact_mobile_light.png` (Mobile 375px Light Mode)

Hotfix 23/11/2026 tích hợp cùng nền Task 1–5. Chi tiết payment/Admin/PDF và bằng chứng regression được nối trong premium-sandbox-task5.md. Phạm vi hotfix giữ các quyết định UI của task này.

---

## 5. Task 6 — Hệ thống Màu & Hiệu ứng 10 Cảnh Giới + 2 Chức Danh Đặc Biệt (`feat/realm-title-task6`)

- **Base SHA:** `682d247` (`feat/premium-sandbox-task5`)
- **Worktree:** `D:\Big\du_an_lon\aura_meme_p2_task6`

### 5.1. Vì sao làm & Quyết định Kiến trúc
- **Single Source of Truth cho 10 cảnh giới:** Chuẩn hóa hàm `realm_for_level(level)`, `admin_cosmetic_title(is_admin)`, `public_title_for_user(level, is_admin)` tại `backend/app/aura_v1.py`, dùng chung cho `UserPublic` (`account_schemas.py`), `AccountPrivate` (`account.py`), `blog.py`, `comments.py`, và `leaderboard` (`aura_reads.py`).
- **Xác thực danh hiệu Admin theo vai trò DB (Zero N+1):** Bỏ hoàn toàn 2 danh hiệu cũ (`Bá Chủ Thiên Lôi`, `Thiên Tướng Độ Ách`) và thay bằng danh hiệu thống nhất **`Sáng Thế Thần`** cho cả hai Admin (Khang Dev & Kien Dev). Backend xác định quyền thông qua correlated `EXISTS` subquery (`public_is_admin_column()` kiểm tra `UserRole` + `Role.code == "ADMIN"`), tuyệt đối không suy diễn từ username hay dữ liệu client.
- **Loại bỏ hoàn toàn hardcode username trên Frontend:** Frontend chỉ render dữ liệu `level`, `realm`, `title` do backend xác thực và cấp phát.
- **Tách bạch Level thật và Chức danh đặc biệt:** `Sáng Thế Thần` là cosmetic title độc lập, không biến thành cảnh giới thứ 11. Huy hiệu `LVL` của Admin vẫn giữ đúng màu/bậc của cảnh giới thật (ví dụ Khang `LVL 79` -> Tier 8 `Đại Thừa`, Kien `LVL 12` -> Tier 2 `Trúc Cơ`) và tự động thăng bậc khi lên Level.

### 5.2. Data Flow & Phân quyền / Bảo mật
1. **Backend:** `UserProgress.level_cached` (`public_level_column(now)`) + `public_is_admin_column()` -> `UserPublic.public_identity()` suy diễn `(realm, title)`. Trường nội bộ `is_admin_title` được đánh dấu `exclude=True` nên không rò rỉ ra JSON công khai. Nếu `level is None`, cả `realm` và `title` đều bị lược bỏ (`exclude_if=None`), tuyệt đối không bịa chức danh.
2. **Session `/users/me`:** `AccountPrivate.title` sử dụng `exclude_if=lambda v: v is None`, chỉ trả về `"Sáng Thế Thần"` khi `"ADMIN" in basic.roles`, giữ nguyên contract cho user thường.
3. **Frontend:** `frontend/src/realm-tier.js` + `frontend/src/components/RealmBadges.jsx` + `frontend/src/realm-badges.css` dùng chung cho Home (`PostCard`, `AuraProgress`), Explore (`PostCard`), Comment (`CommentSection`), Profile (`ProfilePage`, `PostCard`, `AuraProgress`), và `HallIdentity`.

### 5.3. Ngôn ngữ Thiết kế Màu sắc, Hiệu năng & Accessibility
- **Thang năng lượng 10 cảnh giới thống nhất (giữ nguyên bản Owner đã duyệt):** Slate (`Luyện Khí`) -> Jade (`Trúc Cơ`) -> Emerald (`Kim Đan`) -> Azure (`Nguyên Anh`) -> Indigo (`Hóa Thần`) -> Violet (`Luyện Hư`) -> Amethyst (`Hợp Thể`) -> Crimson (`Đại Thừa`) -> Lightning Ember (`Độ Kiếp`) -> Celestial Prismatic (`Phi Thăng`).
- **Hiệu ứng Sáng Thế Thần — Vạn Vận Quy Tông:** Bảng màu tím vũ trụ + vàng thần thánh + trắng ngọc + cyan thiên thể (phân biệt rõ với Aura Prime vàng đặc), tích hợp 4 lớp: Sacred Halo (viền đa lớp), Divine Smoke (khói năng lượng mềm bằng CSS radial-gradient), Cosmic Convergence (2 dải ánh sáng cyan/gold hội tụ vào trung tâm), và Divine Emblem (SVG thiên tinh 4 cánh tối giản).
- **Hiệu năng Feed theo kích thước:** `SM` (Bình luận) chỉ có viền/glow tĩnh; `MD` (Bài đăng/Explore/Rank) chỉ kích hoạt smoke & convergence khi `:hover`/`:focus-visible`; `LG` (Profile/Aura Card) chạy hiệu ứng đầy đủ trên compositor thread (`transform`/`opacity`) và chỉ kích hoạt trong `@media (prefers-reduced-motion: no-preference)`.
- **Accessibility:** Tương phản văn bản >= 4.5:1 ở cả Dark Mode và Light Mode (`.u219[data-theme="light"]`), có biểu tượng SVG nhận diện riêng (WCAG 1.4.1), và fallback `@media (forced-colors: active)`.

### 5.4. Giới hạn & Gợi ý Giải thích Phỏng vấn
- **Giới hạn:** Trang `/rank` UI vẫn giữ `MaintenancePage` theo cấu hình hiện tại (API `/api/v1/leaderboard` đã sẵn sàng trả `level`, `realm`, `title`). Không thêm dependency ngoài.
- **Khi phỏng vấn có thể trình bày:**
  - *Tại sao không hardcode chức danh admin ở frontend?* Vì phân quyền/nhận diện phải đi từ backend (single source of truth), tránh bị giả mạo hoặc lệch trạng thái khi policy chưa sẵn sàng.
  - *Tại sao không dùng animation liên tục trên PostCard?* Hàng trăm animation `box-shadow` đồng thời gây repaint nặng; dùng CSS tĩnh trên feed và compositor-only `transform`/`opacity` + `prefers-reduced-motion: no-preference` giúp giữ 60fps và đạt chuẩn accessibility.
