# AuraMeme — Task 2: Admin Workspace UX Refinement Engineering Handoff

Tài liệu bàn giao kỹ thuật hoàn thành **Task 2: Tối ưu trải nghiệm trang quản trị `/admin` (Admin Workspace UX Refinement)** theo đúng yêu cầu chỉ đạo của Owner, ChatGPT giám sát và Codex review cuối.

---

## 1. Tổng quan & Checkpoint Git

- **Repository:** `D:\Big\du_an_lon\aura_meme_p2_clean`
- **Nhánh phát triển:** `feat/admin-ux-task2`
- **Base commit SHA:** `1b80b3e` (`fix(notifications): center detail modal and simplify inbox`)
- **Trạng thái:** Toàn bộ 6 subtask nghiệp vụ A-F đã hoàn thành với commit riêng rẽ; verification tests 100% pass.
- **Danh sách commit nghiệp vụ trên nhánh:**
  1. `cdc5c13` — `refactor(admin): streamline content review actions` (Subtask A)
  2. `70b19ae` — `refactor(admin): improve contact detail and status workflow` (Subtask B)
  3. `6bbd419` — `refactor(admin): humanize administration audit history` (Subtask C)
  4. `6ec4013` — `style(admin): refine announcement composer copy and preview icon` (Subtask D)
  5. `1d70df0` — `style(admin): use approved guardian workspace icon` (Subtask E)
  6. `352a5fa` — `fix(admin): standardize pagination to ten records` (Subtask F)
  7. *(HEAD)* — `docs(admin): document task2 review handoff` (Subtask G)

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
- **Tiêu đề Dialog:** Đổi thành `Soạn Thông báo` / `Compose Announcement`.
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

## 3. Bằng chứng kiểm thử & Visual QA (Evidence)

### 3.1. Frontend Unit Tests (Node test runner)
```powershell
node --test frontend/tests/*.test.mjs
# Kết quả: 62 passed, 0 failed (100% pass)
```

### 3.2. Frontend Production Build (Vite 7)
```powershell
cd frontend
npm.cmd run build
# Kết quả: Built in 4.88s, 130 modules transformed, zero error.
```

### 3.3. Backend Unit & Regression Pytest
```powershell
cd backend
.\.venv_p2\Scripts\python.exe -m pytest -m "not integration" -q
# Kết quả: 418 passed, 0 failed, 787 deselected in 44.96s (100% pass)
```

### 3.4. Playwright End-to-End Suite
1. **`auth-tests/admin-premium.spec.js`:**
   - 10 tests passed (100% pass).
2. **`auth-tests/admin-ux.spec.js`:**
   - 7/7 tests passed (100% pass).
   - Kiểm thử toàn diện 6 subtasks A, B, C, D, E, F và capture screenshots.

### 3.5. Danh mục ảnh chụp Visual QA (Artifacts)
Toàn bộ ảnh chụp màn hình nghiệm thu được lưu tại thư mục Artifact:
- `admin_qa_task2_desktop.png`: Toàn cảnh Desktop 1440px bảng Bài viết với 4 icon action, snippet tóm tắt, logo Guardian mới.
- `admin_qa_task2_content_preview.png`: Modal xem trước bài viết read-only, không nút like/comment, căn giữa hoàn hảo.
- `admin_qa_task2_contact_modal.png`: Modal xử lý liên hệ với khối thông tin người gửi, hộp scroll tin nhắn riêng, dropdown trạng thái.
- `admin_qa_task2_audit_activity.png`: Tab Nhật ký quản trị với tên hành động humanized, khối ID kỹ thuật kèm nút sao chép.
- `admin_qa_task2_tablet.png`: Giao diện trên Tablet 768px.
- `admin_qa_task2_mobile.png`: Giao diện trên Mobile 375px responsive, không vỡ layout, cụm icon căn chỉnh chuẩn.

---

## 4. Hướng dẫn Review cho Codex

Khi Codex thực hiện review kỹ thuật:
1. Kiểm tra log commit: `git log -8 --oneline`.
2. Kiểm tra diff từng commit theo mã hash:
   - `cdc5c13`: Cụm 4 icon và modal xem trước nội dung.
   - `70b19ae`: Modal xử lý liên hệ có phân cấp rõ ràng.
   - `6bbd419`: Nhân tính hóa nhật ký quản trị và nút sao chép ID.
   - `6ec4013`: Tinh chỉnh microcopy composer và icon xem trước.
   - `1d70df0`: Logo guardian tròn trong sidebar admin.
   - `352a5fa`: Chuẩn hóa phân trang 10 mục và cơ chế chống kẹt trang rỗng.
3. Chạy lệnh xác minh Playwright:
   ```powershell
   cd frontend
   npx.cmd playwright test --config=../.github/playwright.auth.config.mjs auth-tests/admin-ux.spec.js --workers=1 --retries=0
   ```
4. Kiểm tra các ranh giới bảo mật: Không rò rỉ PII email ngoài luồng cho phép, không phá vỡ CSRF contracts, không ảnh hưởng các hệ thống Notifications, Vault, Rank đã nghiệm thu.
