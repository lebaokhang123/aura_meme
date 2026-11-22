# AuraMeme — Task 2: Admin Workspace UX Refinement Engineering Handoff

## Checkpoint kỹ thuật 22/11/2026

Bộ test PostgreSQL kiểm draft chưa fan-out, publish một lần, publish lặp trả 409, withdraw cập nhật bản người nhận. Test browser kiểm composer, phân trang và nút thao tác. Screenshot mới ghi qua Playwright outputPath trong worktree.

Tài liệu bàn giao kỹ thuật hoàn thành **Task 2: Tối ưu trải nghiệm trang quản trị `/admin` (Admin Workspace UX Refinement)** và đợt nghiệm thu **Task 2 Final Polish** theo đúng yêu cầu chỉ đạo của Owner, ChatGPT giám sát và Codex review cuối.

---

## 1. Tổng quan & Checkpoint Git

- **Repository:** `D:\Big\du_an_lon\aura_meme_p2_clean`
- **Nhánh phát triển:** `feat/admin-ux-task2`
- **Base commit SHA:** `1b80b3e` (`fix(notifications): center detail modal and simplify inbox`)
- **Trạng thái:** Toàn bộ các subtask nghiệp vụ và đợt tinh chỉnh cuối (Task 2 Final Polish) đã hoàn thành với commit độc lập; verification tests 100% pass.
- **Danh sách commit nghiệp vụ trên nhánh:**
  1. `cdc5c13` — `refactor(admin): streamline content review actions` (Subtask A)
  2. `70b19ae` — `refactor(admin): improve contact detail and status workflow` (Subtask B)
  3. `6bbd419` — `refactor(admin): humanize administration audit history` (Subtask C)
  4. `6ec4013` — `style(admin): refine announcement composer copy and preview icon` (Subtask D)
  5. `1d70df0` — `style(admin): use approved guardian workspace icon` (Subtask E)
  6. `352a5fa` — `fix(admin): standardize pagination to ten records` (Subtask F)
  7. `f89c87f` — `docs(admin): document task2 review handoff`
  8. `4c0678a` — `fix(notifications): improve inbox message hierarchy` (Final Polish A)
  9. `4d63ad2` — `refactor(admin): unify announcement action icons` (Final Polish B)
  10. `f233fe9` — `style(admin): normalize content action buttons` (Final Polish C)
  11. `a42fa5b` — `test(admin): add visual and automated coverage for task 2 final polish`
  12. *(HEAD)* — `fix(admin): bỏ nút đính chính thông báo đã phát` (Task 2 Final Fix)

---

## 2. Chi tiết các Subtask hoàn thành

### Subtask A: Streamline Content Review Actions & Read-Only Preview Modal
- **Loại bỏ thẻ `<details>` gây vỡ layout:** Gỡ bỏ hoàn toàn thẻ `<details><summary>Xem nội dung</summary></details>` làm bung vỡ cấu trúc lưới bảng trong danh sách bài viết & bình luận. Thay thế bằng snippet tóm tắt 1 dòng mờ sạch sẽ (`.admin-content-snippet`), `text-overflow: ellipsis`.
- **Cụm 4 Action Icon Buttons (`.admin-action-icons`):**
  1. `visibility`: Xem chi tiết bài viết / bình luận. Mở modal read-only preview.
  2. `visibility_off` / `visibility`: Toggle ẩn / hiển thị lại. Nếu bài viết đang hiển thị, icon `visibility_off` mở modal nhập lý do kiểm duyệt; nếu đang bị ẩn, icon `visibility` cho phép khôi phục lại trạng thái công khai; disabled nếu đã bị xóa.
  3. `delete`: Nút xóa (màu đỏ `text-error`), mở modal xác nhận và nhập lý do xóa; disabled nếu nội dung đã bị xóa.
  4. `open_in_new`: Mở bài viết gốc trên trang web người dùng (`/#post-${id}`) trong tab mới an toàn (`target="_blank" rel="noopener noreferrer"`). Nếu bài viết/bình luận đang bị ẩn hoặc xóa, icon chuyển sang trạng thái disabled với tooltip giải thích `Không thể mở nội dung đã ẩn hoặc đã xóa`.
- **Modal Read-Only Content Preview:**
  - Header: Hiển thị tác giả (`@username`), thời gian tạo (`stamp`), và badge trạng thái.
  - Body: Tiêu đề bài viết, nội dung bài viết/bình luận đầy đủ với định dạng chuẩn (`white-space: pre-wrap`), khung hiển thị ảnh/video an toàn (`.admin-content-preview-media`).
  - Đối với bình luận: Trích dẫn bài viết gốc (`.admin-content-ref-quote`).
  - **Bảo mật tuyệt đối:** Hoàn toàn KHÔNG CÓ các nút like, reaction, comment box, share trong modal này.
  - Footer modal: Nút hành động duy nhất là nút "Đóng" (`workspace-primary`).

### Subtask B: Redesign Contact Management Modal UX
- **Cấu trúc phân cấp thông tin rõ ràng:**
  - **Header Info Card (`.admin-contact-info-card`):** Icon đại diện người gửi, tên người gửi (`name`), ngày giờ gửi (`created_at`), badge trạng thái (`new`, `in_review`, `resolved`), và tiêu đề thư (`subject`) in đậm nổi bật.
  - **Hộp nội dung thư độc lập (`.admin-contact-body-box`):** Nền container tối chuyên biệt (`var(--am-surface-container-lowest)`), padding rộng rãi, giãn dòng thoáng, có thanh cuộn riêng biệt (`max-height: 220px; overflow-y: auto`), giữ nguyên xuống dòng của người gửi (`white-space: pre-wrap`).
  - **Khu vực cập nhật trạng thái (`.admin-contact-status-section`):** Dropdown select trạng thái xử lý rõ ràng, kèm chú thích hướng dẫn phối hợp đội ngũ hỗ trợ.
  - **Footer Actions:** Nút "Hủy" và nút "Lưu trạng thái" (`busy ? 'Đang lưu…' : 'Lưu trạng thái'`).
- **Bảo vệ quyền riêng tư (Privacy Guard):** Giữ nguyên quy chuẩn client-side DTO mapping loại bỏ PII email không cần thiết theo đúng unit test `Admin mapping drops secrets and unnecessary user/contact PII`.

### Subtask C: Human-Readable Admin Audit History
- **Đổi tên Tab & Ghi chú mục:**
  - Tab name: `'audit-logs': ['Nhật ký quản trị', 'Admin activity']` (thay vì "Nhật ký kiểm duyệt").
  - Ghi chú: `'Ghi lại các thay đổi do quản trị viên thực hiện: ai đã làm gì và khi nào.'`
- **Nhân tính hóa hành động (Action Mapping):**
  - Chuyển toàn bộ các chuỗi kỹ thuật thô (`post.update`, `post.hidden`, `post.deleted`, `comment.hidden`, `comment.deleted`, `announcement.create`, `announcement.publish`, `announcement.withdraw`, `contact.update`, `user.status`, `user.roles`, `category.create`, `category.update`, `asset.review`) sang ngôn ngữ tự nhiên thân thiện cho cả Tiếng Việt và Tiếng Anh (ví dụ: "Cập nhật bài viết", "Phát thông báo hệ thống", "Cập nhật trạng thái liên hệ", v.v.).
- **Hiển thị Người thực hiện & Đối tượng:**
  - Người thực hiện: Phân biệt rõ `"Bạn (Admin hiện tại)"` khi thao tác do chính Admin đang đăng nhập thực hiện hoặc mã rút gọn `"Quản trị viên #..."`.
  - Đối tượng tác động: Phân loại rõ ràng (Bài viết, Bình luận, Liên hệ, Thông báo, Người dùng, Danh mục, Vật phẩm).
- **Collapsible Technical Details & Copy Button:**
  - Đưa mã UUID kỹ thuật dài vào thẻ gập mở `<details className="admin-audit-tech-details">`.
  - Bổ sung nút "Sao chép" (`admin-copy-btn`) kèm phản hồi trực quan "Đã sao chép" khi copy UUID vào clipboard.

### Subtask D: Notification Composer Microcopy Polish
- **Tiêu đề Dialog:** Đổi thành `Soạn thông báo hệ thống` / `Compose system announcement`.
- **Mô tả cảnh báo:** Rút gọn súc tích thành `Thông báo sẽ được gửi tới tất cả thành viên đang hoạt động.` / `All active members will receive this announcement.`
- **Nút mắt xem trước icon-only:** Nút `#admin-preview-eye-btn` chuyển thành icon con mắt đơn lẻ dạng nút vuông 32x32px bo góc chuẩn Cyberpunk, loại bỏ text phụ bên cạnh, giữ nguyên tooltip và `aria-label="Giữ để xem trước"`.
- **Thẻ xem trước trực tiếp:** Loại bỏ dòng chú thích thừa `"Thả chuột hoặc phím để tiếp tục soạn thảo"`.

### Subtask E: Approved Guardian Workspace Icon
- **Asset bảo trợ được phê duyệt:** Copy asset chuẩn `04_admin_guardian-circle-48.png` từ kho tài nguyên gốc vào `frontend/public/assets/brand/04_admin_guardian-circle-48.png`.
- **Thay thế Icon Khiên cũ:** Thay thế icon font `shield` trong sidebar admin `.admin-brand-mark` bằng thẻ `<img src="/assets/brand/04_admin_guardian-circle-48.png" alt="AuraMeme Guardian" width="40" height="40" className="admin-brand-logo-img" />`.
- **Tạo hình bo tròn hoàn hảo:** CSS `.admin-brand-mark` bo tròn 50%, ảnh cover sắc nét, hòa hợp với tông màu đen tím của giao diện Admin.

### Subtask F: Standardize Pagination Across All Resources (Page Size 10)
- **Chuẩn hóa `page_size=10`:** Đổi toàn bộ query tham số phân trang của Admin Workspace sang `page_size: '10'` (thay vì 20), giúp trang tải nhanh hơn và danh sách hiển thị vừa vặn trong một màn hình.
- **Phòng chống kẹt trang rỗng (Empty Page Trap Prevention):**
  - Trong logic fetch: Nếu trang hiện tại trả về danh sách rỗng (`items.length === 0`) khi `page > 1` và `total > 0`, hệ thống tự động lùi về trang trước `page - 1`.
  - Trong logic xóa/ẩn: Khi xóa hoặc ẩn mục cuối cùng trên trang (`data.items.length === 1 && page > 1`), hệ thống tự động decrement `page` về `page - 1` để Admin luôn nhìn thấy dữ liệu hợp lệ.

---

## 3. Chi tiết Task 2 Final Polish

### A. Personal Notification Card — Phân cấp 4 dòng độc lập
- **File:** `frontend/src/components/NotificationsDropdown.jsx`, `frontend/src/site.css`
- **Commit:** `4c0678a` (`fix(notifications): improve inbox message hierarchy`)
- **Giải pháp:**
  - Tách bạch hoàn toàn nội dung thông báo thành 4 dòng hiển thị riêng biệt theo đúng cấu trúc:
    1. **Dòng 1 — Tên người gửi (`.notification-card-actor`):** In đậm font 700, màu trắng sáng, phân tách độc lập với tiêu đề (không ghép trong một `<span>`). Tự động hiển thị tên người gửi hoặc tên định danh hệ thống ("Admin Tổng Chủ", "Hệ thống AuraMeme", "Ban Quản Trị AuraMeme").
    2. **Dòng 2 — Tiêu đề (`.notification-card-title`):** Font 600, màu tím nhạt thương hiệu (`#d0bcff`). Với announcement lấy tiêu đề thật từ payload; với reaction/comment/moderation hiển thị tiêu đề hành động rõ ràng.
    3. **Dòng 3 — Nội dung tóm tắt (`.notification-card-snippet`):** Font 400, màu xám nhạt (`#9c98a8`), áp dụng CSS ellipsis nghiêm ngặt: `min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;`. Không cắt ngắn chuỗi trong JavaScript/state để modal xem chi tiết vẫn đọc trọn vẹn văn bản.
    4. **Dòng 4 — Thời gian (`.notification-card-time`):** Font mono JetBrains 11px, màu `#8e8a9a`, hiển thị thời gian tương đối ("vừa xong", "2 giờ trước", v.v.).
  - Giữ vững toàn bộ các tính năng đã qua nghiệm thu: chống bão request storm, cooldown 429 Retry-After, chấm xanh unread, nút xóa và modal xem chi tiết.

### B. Admin Announcement Action Icons & Read-Only Preview Modal
- **File:** `frontend/src/components/AdminPage.jsx`, `frontend/src/workspace.css`
- **Commit:** `4d63ad2` (`refactor(admin): unify announcement action icons`)
- **Giải pháp:**
  - **Loại bỏ `<details><summary>Xem nội dung</summary></details>`:** Thay bằng dòng snippet tóm tắt `.admin-content-snippet`, tránh bung vỡ cấu trúc bảng.
  - **Chuẩn hóa cụm Action Icons theo từng trạng thái:**
    - **Published (Đã phát):**
      - `visibility`: Mở modal xem trước chi tiết (read-only).
      - `undo`: Thu hồi thông báo với dialog xác nhận cảnh báo an toàn.
      *(Lưu ý: Nút "Đính chính" đã được lược bỏ hoàn toàn theo yêu cầu chỉ đạo mới nhất của Owner, giữ cấu trúc tinh gọn với đúng 2 nút thao tác).*
    - **Draft (Bản nháp):**
      - `visibility`: Xem trước nội dung bản nháp trong modal.
      - `edit`: Sửa bản nháp trực tiếp trong composer.
      - `send`: Phát thông báo ngay với dialog xác nhận.
      - `delete`: Xóa bản nháp vĩnh viễn với dialog xác nhận.
    - **Withdrawn (Đã thu hồi):**
      - `visibility`: Xem lại chi tiết thông báo đã thu hồi; các hành động khác bị ẩn.
  - **Modal Read-Only Announcement Preview:**
    - Căn giữa màn hình hoàn hảo, hiển thị chi tiết: Tiêu đề, Người phát (`@actor_username`), Thời gian tạo/phát, Badge trạng thái, Số người nhận (`recipients_count`), và toàn bộ nội dung thông báo đầy đủ (`white-space: pre-wrap`).
    - Nút đóng duy nhất ở góc trên và chân dialog, hỗ trợ phím Esc để đóng nhanh.

### C. Chuẩn hóa kích thước Action Icon Buttons (40px x 40px)
- **File:** `frontend/src/workspace.css`
- **Commit:** `f233fe9` (`style(admin): normalize content action buttons`)
- **Giải pháp:**
  - Giải quyết dứt điểm xung đột CSS độ ưu tiên giữa `.admin-list-panel .workspace-row-actions button` (trước đó ghi đè `min-height: 44px; padding: 6px 10px; background: transparent;`) và `.admin-icon-btn`.
  - Phân tách rõ ràng: Các nút văn bản thuần ("Khóa", "Sửa vai trò", "Chỉnh sửa") giữ rule `.admin-list-panel .workspace-row-actions button:not(.admin-icon-btn)`.
  - Cụm icon buttons sử dụng selector scoped mạnh: `.admin-list-panel .workspace-row-actions .admin-icon-btn, .admin-icon-btn`:
    - Click target chuẩn xác: `width: 40px; min-width: 40px; max-width: 40px; height: 40px; min-height: 40px; max-height: 40px; padding: 0; box-sizing: border-box;`.
    - Icon Material Symbols: `font-size: 19px; width: 19px; height: 19px; display: inline-flex; align-items: center; justify-content: center;`.
    - Border-radius `8px`, viền `1px solid var(--am-outline-variant)`, nền `var(--am-surface-container)`.
    - Nút xóa (`.text-error`) chuyển sắc đỏ nhẹ thanh lịch khi hover: `background: color-mix(in srgb, var(--am-error) 12%, transparent);`.
    - Thẻ liên kết `<a>` (như icon `open_in_new`) có kích thước và giao diện hoàn toàn đồng nhất 100% với thẻ `<button>`.
    - Responsive: Layout flexbox với `gap: 6px; flex-wrap: wrap;` bảo đảm không bao giờ tràn hoặc co rúm trên thiết bị di động.

---

## 4. Bằng chứng kiểm thử & Visual QA (Evidence)

### 4.1. Frontend Unit Tests (Node test runner)
```powershell
cd frontend
node --test tests/*.test.mjs
# Kết quả: 70 passed, 0 failed (100% pass)
```
*(Đã xác minh và ghi nhận làm rõ chênh lệch 62 vs 70 tests trước đây: do Windows PowerShell glob không mở rộng `notifications.test.mjs` khi chạy từ root; chạy trực tiếp trong thư mục `frontend` mở rộng trọn vẹn toàn bộ 7 file với 70 unit tests đạt 100%).*

### 4.2. Frontend Production Build (Vite 7)
```powershell
cd frontend
npm.cmd run build
# Kết quả: Built in 3.02s, 130 modules transformed, zero syntax/chunk errors.
```

### 4.3. Backend Non-Integration Pytest
```powershell
cd backend
Remove-Item Env:AUTH_ENVIRONMENT -ErrorAction SilentlyContinue
Set-Item -Path Env:DATABASE_URL -Value "postgresql+psycopg://test:not-a-real-secret@127.0.0.1:1/test"
.\.venv_p2\Scripts\python.exe -m pytest -m "not integration" -q
# Kết quả: 418 passed, 0 failed, 787 deselected in 40.81s (100% pass)
```

### 4.4. Playwright End-to-End Suite
Toàn bộ 3 file test E2E trọng yếu đều pass 100%:
```powershell
cd frontend
npx.cmd playwright test --config=../.github/playwright.auth.config.mjs auth-tests/notifications-storm.spec.js auth-tests/admin-ux.spec.js auth-tests/admin-premium.spec.js --workers=1 --retries=0
# Kết quả: 25 passed (100% pass)
```
- `notifications-storm.spec.js`: 8/8 tests passed.
- `admin-ux.spec.js`: 9/9 tests passed (bổ sung test tự động kiểm tra cấu trúc 4 dòng thẻ thông báo, CSS ellipsis, cụm icon thông báo và kích thước 40px).
- `admin-premium.spec.js`: 8/8 tests passed.

### 4.5. Danh mục ảnh chụp Visual QA (Artifacts)
Ảnh chụp nghiệm thu tại thư mục Artifact (`C:\Users\sammy\.gemini\antigravity\brain\cc803197-d415-4eaf-80c2-1173a22c12aa`):
- `notification_dropdown_4lines.png`: Dropdown thông báo với 4 dòng rõ rệt: Tên người gửi, Tiêu đề, Nội dung tóm tắt (cắt bằng CSS ellipsis), Thời gian.
- `admin_qa_task2_announcements.png`: Bảng Thông báo hệ thống trong trang Admin hiển thị snippet tóm tắt và cụm icon action chuẩn hóa.
- `admin_qa_task2_announcement_preview.png`: Modal xem trước thông báo hệ thống dạng read-only, căn giữa trang, đầy đủ thông tin người phát và số người nhận.
- `admin_qa_task2_desktop.png`: Toàn cảnh giao diện Desktop Admin 1440px với cụm 4 icon chuẩn 40x40px.
- `admin_qa_task2_content_preview.png`: Modal xem trước nội dung bài viết read-only.
- `admin_qa_task2_contact_modal.png`: Modal xử lý liên hệ với hộp cuộn độc lập.
- `admin_qa_task2_audit_activity.png`: Tab Nhật ký quản trị với ngôn ngữ thân thiện và nút copy ID.
- `admin_qa_task2_tablet.png`: Giao diện Admin trên Tablet 768px.
- `admin_qa_task2_mobile.png`: Giao diện Admin trên Mobile 375px responsive hoàn hảo.

---

## 5. Hướng dẫn Review cho Codex

Khi Codex thực hiện review kỹ thuật:
1. Kiểm tra log commit: `git log -6 --oneline`.
2. Kiểm tra diff từng commit theo mã hash:
   - `4c0678a`: Phân tách 4 dòng thông báo cá nhân, CSS ellipsis trên dòng snippet.
   - `4d63ad2`: Chuẩn hóa icon thông báo Admin (`visibility`, `edit`, `undo` / `send` / `delete`) và modal read-only preview.
   - `f233fe9`: Chuẩn hóa kích thước 40px x 40px và style nút icon Admin.
   - `a42fa5b`: Bổ sung kiểm thử tự động và cập nhật ảnh chụp visual QA.
3. Chạy lệnh xác minh toàn diện:
   ```powershell
   cd frontend
   node --test tests/*.test.mjs
   npm.cmd run build
   npx.cmd playwright test --config=../.github/playwright.auth.config.mjs auth-tests/notifications-storm.spec.js auth-tests/admin-ux.spec.js auth-tests/admin-premium.spec.js --workers=1 --retries=0
   ```
4. Kiểm tra an toàn bảo mật: Không phá vỡ hotfix request storm, không rò rỉ dữ liệu ngoài luồng, không ảnh hưởng các hệ thống khác ngoài phạm vi được chỉ định.


Hotfix 23/11/2026 tích hợp cùng nền Task 1–5. Chi tiết payment/Admin/PDF và bằng chứng regression được nối trong premium-sandbox-task5.md. Phạm vi hotfix giữ các quyết định UI của task này.
