# AuraMeme — Notifications QA V1 Engineering Handoff

Tài liệu bàn giao kỹ thuật hoàn thiện hệ thống Thông báo (Notifications) và Kiểm duyệt (Moderation) theo yêu cầu QA của Owner.

---

## 1. Tổng quan & Checkpoint Git

- **Repository:** `D:\Big\du_an_lon\aura_meme_p2_clean`
- **Nhánh phát triển:** `feat/notifications-qa-v1`
- **Base commit SHA:** `cd08eca` (`fix(notifications): resolve actor profile loading and dropdown render in live preview`)
- **Danh sách commit nghiệp vụ:**
  1. `357cd53` — `fix(notifications): improve inbox scrolling details and deletion` (Task A)
  2. `2a16726` — `feat(admin): add notification management workspace` (Task B)
  3. `f366a7c` — `fix(moderation): unify reason dialogs and owner notifications` (Task C)
  4. *(HEAD)* — `docs(notifications): add qa v1 review handoff` (Task D)

---

## 2. Chi tiết các Task hoàn thành

### Task A: Personal Notification UX (Trải nghiệm Hộp thư Cá nhân)
- **Scroll độc lập:** Đặt giới hạn chiều cao và scroll riêng biệt cho `.notifications-list` (`max-height: 380px` desktop, `max-height: 200px` mobile) trong `frontend/src/site.css`. Khi cuộn danh sách thông báo không bị cuộn trang web nền (body lock/overscroll containment).
- **Phân trang Load More:** Bổ sung nút "Xem thêm thông báo cũ hơn" khi còn dữ liệu phân trang từ backend (`next_cursor` hoặc `has_more`).
- **Nút xóa cá nhân (Per-recipient Deletion):**
  - Backend: `DELETE /api/v1/notifications/{notification_id}` — chỉ xóa bản ghi thông báo của chính user đang đăng nhập (`recipient_user_id == current_user.id`), bắt buộc xác thực session và CSRF header token.
  - Frontend: Icon xóa riêng trên mỗi item; click nút xóa không kích hoạt mở modal chi tiết.
- **Modal chi tiết thông báo (Detail Modal):**
  - Click vào item mở dialog nằm chính giữa màn hình với backdrop mờ tối (`.notification-modal-backdrop`, `.notification-modal`).
  - Hỗ trợ đầy đủ phím `Escape` và nút đóng.
  - Hiển thị đầy đủ tiêu đề, nội dung gốc, lý do kiểm duyệt (nếu có), thời gian tạo chính xác.
  - Đối với thông báo liên quan đến bài viết (`post`, `comment` có `post_id`), modal hiển thị nút "Xem bài viết" chuyển hướng trực tiếp tới bài viết (`/#post-{id}`).

### Task B: Admin Notifications Workspace (Khu vực Quản lý Thông báo Admin)
- **Kiến trúc Zero-Migration (Master-Fanout):** Tận dụng schema `0013_notifications` hiện có trên PostgreSQL với trường `dedupe_key`:
  - Bản ghi quản lý (Master): `dedupe_key = f"master:{announcement_id}"` lưu trạng thái toàn cục (`draft`, `published`, `withdrawn`) cho Admin quản lý.
  - Bản ghi phát sóng (Fan-out): `dedupe_key = f"fanout:{announcement_id}:{user_id}"` lưu thông báo cho từng người dùng nhận.
  - Hộp thư cá nhân lọc bỏ master rows bằng điều kiện: `not(Notification.dedupe_key.like("master:%"))`.
- **API Endpoints Quản lý Thông báo:**
  - `GET /api/v1/admin/announcements`: Danh sách thông báo quản trị, phân trang, lọc status, tìm kiếm text.
  - `POST /api/v1/admin/announcements`: Tạo thông báo mới (hỗ trợ lưu bản nháp `is_draft: true` hoặc phát ngay `is_draft: false`).
  - `PATCH /api/v1/admin/announcements/{id}`: Chỉnh sửa tiêu đề, nội dung của bản nháp.
  - `DELETE /api/v1/admin/announcements/{id}`: Xóa bản nháp (không ảnh hưởng dữ liệu người dùng).
  - `POST /api/v1/admin/announcements/{id}/publish`: Phát sóng bản nháp tới toàn bộ người dùng active.
  - `POST /api/v1/admin/announcements/{id}/withdraw`: Thu hồi thông báo công khai, chuyển trạng thái master và toàn bộ bản ghi fanout sang `withdrawn`.
  - Ghi `AdminAuditLog` cho toàn bộ các hành động announcement.
- **Giao diện Admin `/admin`:**
  - Thêm tab "Thông báo" vào sidebar quản trị với icon `campaign`.
  - Chuyển nút "Phát thông báo" chỉ hiển thị trong tab Thông báo.
  - Modal soạn thảo: tab "Soạn thảo" và "Xem trước" (Preview), form responsive không tràn màn hình, cảnh báo broadcast, nút "Lưu bản nháp" và "Phát thông báo".
  - Bảng danh sách: hiển thị tiêu đề, trích đoạn nội dung, tác giả, thời gian tạo/phát, số người nhận, badge trạng thái.
  - Thao tác theo trạng thái: Draft (Sửa, Phát ngay, Xóa), Published (Đính chính -> mở draft mới từ nội dung cũ, Thu hồi -> cập nhật withdrawn), Withdrawn (chỉ xem).

### Task C: Moderation Reason End-to-End (Quy trình Kiểm duyệt Kèm Lý do)
- **Quy chuẩn Request Body JSON:** Cả bài viết (`PATCH /admin/posts/{id}`) và bình luận (`PATCH /admin/comments/{id}`) đều nhận `{ status, reason }` qua JSON body, hỗ trợ cả `hidden` và `deleted`.
- **Yêu cầu Lý do (Validation):** Bắt buộc nhập lý do từ 5 đến 500 ký tự cho mọi thao tác Ẩn hoặc Xóa nội dung vi phạm.
- **Audit Logging:** Trường `reason` được ghi trực tiếp vào `after_json` của bảng `AdminAuditLog` với action `post.update`, `post.delete`, `comment.hidden`, `comment.deleted`.
- **Dispatch Notification kèm Lý do:** Hệ thống tự động tạo thông báo kiểm duyệt (`type: "moderation"`) gửi tới chủ sở hữu bài viết/bình luận, chứa hành động và lý do cụ thể từ Quản trị viên.
- **Bảo vệ Tự kiểm duyệt (Self-moderation Guard):** Nếu Quản trị viên tự ẩn/xóa bài viết hoặc bình luận của chính mình, hệ thống không dispatch thông báo cho chính mình (`actor_id == recipient_id` guard).
- **Giao diện Kiểm duyệt Đầy đủ:**
  - `PostMenu.jsx`: Menu bài viết có tùy chọn "Ẩn bài (Admin)" và "Xóa bài (Admin)" với dialog nhập lý do 5-500 ký tự.
  - `CommentSection.jsx`: Menu bình luận cho phép Admin thực hiện "Ẩn bình luận (Admin)" và "Xóa bình luận (Admin)" với dialog nhập lý do 5-500 ký tự.
  - `AdminPage.jsx`: Bảng Content cho Post và Comment có nút "Ẩn" và "Xóa" mở dialog xác nhận kiểm duyệt kèm textarea nhập lý do.

---

## 3. Danh sách File Thay đổi

| Đường dẫn File | Mục đích Thay đổi |
|---|---|
| `backend/app/notifications.py` | Thêm endpoint `DELETE /api/v1/notifications/{id}` per-recipient, lọc master rows khỏi hộp thư cá nhân |
| `backend/app/admin_posts.py` | Thêm toàn bộ REST API quản lý announcements (CRUD + publish/withdraw), mở rộng post moderation hỗ trợ status `deleted` và audit `reason` |
| `backend/app/comments.py` | Mở rộng `CommentModeration` hỗ trợ status `deleted`, audit `reason`, dispatch notification kiểm duyệt kèm `post_id` |
| `backend/tests/test_health.py` | Cập nhật hợp đồng OpenAPI schema paths bao gồm các endpoint mới |
| `backend/tests/test_notifications.py` | Thêm unit tests cho delete notification, announcement lifecycle, comment moderation reason, audit logging, self-moderation guard |
| `frontend/src/notifications-api.js` | Thêm client helper `deleteNotification(id)` hỗ trợ cả live backend và localStorage mock |
| `frontend/src/admin-api.js` | Thêm schema và parser DTO cho resource `announcements` |
| `frontend/src/SocialContext.jsx` | Chuyển tiếp payload `{ status, reason }` cho actions `moderate-post` và `moderate-comment` |
| `frontend/src/site.css` | Thêm style scroll độc lập hộp thư, nút xóa notification, nút xem thêm, modal chi tiết và backdrop cyber |
| `frontend/src/components/NotificationsDropdown.jsx` | Thêm load more, xóa cá nhân, click mở modal chi tiết giữa màn hình, nút "Xem bài viết" |
| `frontend/src/components/AdminPage.jsx` | Thêm tab Thông báo, modal soạn thảo có preview/draft/broadcast warning, bảng announcement, dialog kiểm duyệt post/comment kèm lý do |
| `frontend/src/components/CommentSection.jsx` | Menu admin cho comment của người khác, hành động ẩn/xóa kèm modal lý do |
| `frontend/src/components/PostMenu.jsx` | Menu admin cho post, hành động ẩn/xóa kèm modal lý do |
| `frontend/tests/notifications.test.mjs` | Unit test cho `deleteNotification` API |
| `frontend/tests/admin-api.test.mjs` | Unit test cho `announcements` API |
| `docs/tasks/notifications-qa-v1.md` | Tài liệu bàn giao kỹ thuật cho Codex và Owner |

---

## 4. Ma trận Kiểm thử & Kết quả Xác minh

### Backend Pytest (Non-Integration)
```powershell
Set-Location 'D:\Big\du_an_lon\aura_meme_p2_clean\backend'
Remove-Item Env:AUTH_ENVIRONMENT -ErrorAction SilentlyContinue
Set-Item -Path Env:DATABASE_URL -Value "postgresql+psycopg://test:not-a-real-secret@127.0.0.1:1/test"
.\.venv_p2\Scripts\python.exe -m pytest -m "not integration" -q
```
- **Kết quả:** `418 passed, 787 deselected, 1 warning in 28.88s` (100% PASS).

### Frontend Unit Tests
```powershell
Set-Location 'D:\Big\du_an_lon\aura_meme_p2_clean'
node --test frontend/tests/*.test.mjs
```
- **Kết quả:** `pass 68, fail 0, duration_ms 731ms` (100% PASS).

### Frontend Production Build
```powershell
Set-Location 'D:\Big\du_an_lon\aura_meme_p2_clean\frontend'
npm.cmd run build
```
- **Kết quả:** `✓ built in 2.22s` — Bundle sạch, không lỗi JSX/TypeScript/syntax.

---

## 5. Giới hạn Kỹ thuật & Ghi chú (Technical Notes)

1. **Thông báo Share (`PARTIAL — SHARE TRACKING REQUIRED`):**
   - Trong kiến trúc schema `0013_notifications` hiện hành, hệ thống hỗ trợ các loại thông báo: `reaction`, `comment`, `moderation`, `announcement`.
   - Tính năng share hiện tại là chia sẻ liên kết ngoài (External Web Share API / Copy Link) và chưa có bảng lưu lịch sử share nội bộ trong cơ sở dữ liệu. Do đó việc dispatch notification khi có người share bài được đánh dấu là `PARTIAL — SHARE TRACKING REQUIRED` và sẽ triển khai khi có bảng schema share riêng.
2. **Không chạy migration mới:**
   - Toàn bộ tính năng Admin Announcements hoạt động hoàn toàn trên schema `0013_notifications` có sẵn mà không cần migrate thêm DB, đảm bảo môi trường QA port `5434` của Owner tiếp tục hoạt động liên tục, không bị downtime hay lỗi schema.

---

## 6. Ghi chú Bảo mật & Quyền riêng tư

- **Hộp thư cá nhân cách ly tuyệt đối:** Không bao giờ để lộ các bản ghi `master:%` (bản ghi thông báo quản trị gốc hoặc bản nháp chưa công khai) vào hộp thư người dùng thông thường.
- **Xóa thông báo an toàn:** Người dùng chỉ có quyền xóa thông báo mà mình là người nhận (`recipient_user_id == current_user.id`). Không ai có thể xóa thông báo của người khác.
- **Bảo mật danh tính Quản trị viên khi kiểm duyệt:** Thông báo kiểm duyệt gửi tới tác giả thông báo rõ hành động và lý do, nhưng không để lộ thông tin nhạy cảm của Admin xử lý.
- **Tự kiểm duyệt an toàn:** Không xảy ra hiện tượng spam thông báo khi Admin thao tác trên nội dung của chính mình.

---

## 7. Thứ tự Ưu tiên Review cho Codex (Codex Review Priorities)

1. **Auth & CSRF Guards:**
   - Kiểm tra `DELETE /api/v1/notifications/{id}` xác thực đúng `account.user.id == notification.recipient_user_id` và yêu cầu `X-CSRF-Token`.
   - Kiểm tra các endpoint `/api/v1/admin/announcements` đều yêu cầu `require_admin_mutation` và `require_admin_account`.
2. **Deduplication & Self-interaction Guards:**
   - Kiểm tra hàm `create_notification` đảm bảo không tạo thông báo nếu `actor_user_id == recipient_user_id`.
   - Kiểm tra dedupe_key cho moderation `mod:post:{id}:{status}` và `mod:comment:{id}:{status}`.
3. **Announcement Master-Fanout Lifecycle:**
   - Đảm bảo draft chỉ tạo master row (`is_draft=True`).
   - Đảm bảo publish thực hiện fan-out `add_all` tới các active users và cập nhật master row.
   - Đảm bảo withdraw cập nhật trạng thái cả master row và các fan-out rows.
4. **Frontend Error Handling & State:**
   - Kiểm tra xác thực độ dài reason (5-500 ký tự) cả ở client và server.
   - Kiểm tra focus trap, phím Escape và đóng dialog sau khi submit thành công.

---

## 8. Browser QA Checklist cho Owner Nghiệm thu

- [ ] **Chuông thông báo cá nhân:**
  - [ ] Mở dropdown chuông thông báo, cuộn danh sách thấy cuộn độc lập, trang web nền không bị cuộn theo.
  - [ ] Thấy nút "Xem thêm thông báo cũ hơn" khi có nhiều thông báo.
  - [ ] Di chuột vào item thấy icon thùng rác nhỏ; bấm xóa bản ghi đó biến mất khỏi danh sách.
  - [ ] Bấm vào dòng thông báo mở modal chi tiết ở giữa màn hình có backdrop tối, hiển thị đầy đủ lý do/nội dung.
  - [ ] Đối với thông báo bài viết/bình luận, bấm "Xem bài viết" chuyển tới đúng bài viết trên trang.
- [ ] **Admin Workspace (`/admin`):**
  - [ ] Sidebar có mục "Thông báo", bấm vào thấy danh sách các thông báo hệ thống.
  - [ ] Bấm "Phát thông báo", xuất hiện modal soạn thảo với 2 tab "Soạn thảo" và "Xem trước".
  - [ ] Nhập thử thông báo, chọn "Lưu bản nháp" -> hiển thị trong bảng với badge "Bản nháp".
  - [ ] Với bản nháp: có thể bấm "Sửa", "Xóa", hoặc "Phát ngay".
  - [ ] Bấm "Phát ngay" -> chuyển sang "Công khai", tất cả user nhận được thông báo chuông.
  - [ ] Với thông báo đã phát: có thể bấm "Đính chính" hoặc "Thu hồi".
- [ ] **Kiểm duyệt bài viết & bình luận:**
  - [ ] Đăng nhập tài khoản Admin, mở menu bài viết của user khác -> thấy "Ẩn bài (Admin)" và "Xóa bài (Admin)".
  - [ ] Bấm vào hiển thị popup yêu cầu nhập lý do (5-500 ký tự). Nhập dưới 5 ký tự báo lỗi.
  - [ ] Nhập lý do hợp lệ và bấm Xác nhận -> bài viết được xử lý, author nhận được thông báo kèm đúng lý do vừa nhập.
  - [ ] Kiểm tra tương tự với bình luận trên bài viết.


---

## 9. P0 Hotfix: Notifications Request Storm Prevention

### 9.1. Nguyên nhân Gốc rễ (Root Cause Analysis)
1. **Unstable References trong `NotificationsDropdown.jsx`:**
   - Hàm dịch `t = (vi, en) => ...` được khai báo inline bên trong component, sinh ra reference mới ở mỗi render cycle.
   - Callback `load` được bọc bởi `useCallback(..., [onUnreadChange, t])`, do đó cũng bị tạo mới ở mỗi render.
   - Hook `useEffect(..., [filter, load])` chạy sau mỗi render vì `load !== prevLoad`.
   - Trong `load()`, các state setter (`setLoading`, `setItems`, `setUnreadCount`, `setTotalPages`) được gọi, kích hoạt re-render ngay lập tức. Vòng lặp vô hạn (Infinite Request Loop) được tạo ra với tần suất hàng chục request mỗi giây cho tới khi chạm giới hạn 120 reqs/IP/60s của backend.
2. **Object Reference Instability trong `SiteShell.jsx`:**
   - `readDemoUser()` trong `demo.js` trả về một object mới `{...user, ...}` ở mỗi lần gọi.
   - Effect lấy unread count trong `SiteHeader` phụ thuộc vào `[user]`, so sánh tham chiếu luôn thấy khác nhau (`prevUser !== user`), dẫn tới việc gọi `GET /api/v1/notifications/unread-count` liên tục khi Header re-render.
   - Khi backend chạm ngưỡng rate limit (HTTP 429 `RATE_LIMITED`), component không lưu thời gian cooldown `Retry-After`, tiếp tục retry và làm kéo dài thời gian bị lockout.

### 9.2. Giải pháp Kỹ thuật Đã Triển khai
1. **Memoize danh tính người dùng trong `demo.js`:**
   - Caching `cachedResultUser` dựa trên tham chiếu của `auth.snapshot().user` (đã là immutable frozen object). Khi người dùng không đổi, `readDemoUser()` luôn trả về cùng một tham chiếu duy nhất.
2. **Ổn định hóa `SiteShell.jsx`:**
   - Đổi dependency của effect unread count từ `[user]` sang `[userId]` (chuỗi nguyên thủy `user?.id || user?.username`).
   - Throttling focus fetch: Chỉ cho phép gọi lại qua `window.focus` nếu đã trôi qua ít nhất 30 giây kể từ lần fetch trước.
   - Bổ sung cooldown tracking: Khi server trả về 429, lưu `cooldownUntil` dựa trên header `Retry-After` (mặc định 30s) và chặn toàn bộ request ngầm cho tới khi hết hạn.
   - Bọc `onUnreadChange` trong `useCallback(count => setUnreadCount(count), [])`.
3. **Triệt tiêu vòng lặp trong `NotificationsDropdown.jsx`:**
   - Chuyển `onUnreadChange` sang `onUnreadChangeRef.current`, loại bỏ hoàn toàn khỏi dependency array của `load`.
   - Bọc `load` trong `useCallback` với dependency rỗng `[]`, sử dụng `languageRef.current` cho thông điệp lỗi.
   - Hook `useEffect` chỉ kích hoạt duy nhất khi `filter` thay đổi (`'all'` hoặc `'unread'`).
   - Bổ sung `activeRequestIdRef`: Khi người dùng đóng dropdown hoặc chuyển tab nhanh, request cũ đang bay bị vô hiệu hóa ngay lập tức, không ghi đè dữ liệu mới.
   - Bổ sung `cooldownUntilRef`: Khi nhận HTTP 429, lưu thời gian mở khóa từ `Retry-After`. Nút "Thử lại" hoặc các thao tác chuyển tab trong thời gian cooldown sẽ không gửi request lên server mà hiển thị thông báo đếm ngược giây rõ ràng cho người dùng.

### 9.3. Bảng Đo kiểm Thực tế: Request Counts (Trước và Sau Hotfix)

| Kịch bản kiểm thử | Request tới Endpoint | Trước Hotfix | Sau Hotfix | Kết quả |
|---|---|:---:|:---:|:---:|
| **Mở chuông thông báo** | `/api/v1/notifications` | 50+ reqs / 2s | **1 req** | Triệt tiêu hoàn toàn loop |
| **Giữ mở chuông 10–12 giây** | `/api/v1/notifications` | Liên tục tăng đến 120+ | **0 req thêm (vẫn 1)** | Không polling thừa |
| **Re-render Header (Gõ tìm kiếm)** | `/api/v1/notifications` | Tăng vọt theo keydown | **0 req thêm (vẫn 1)** | Miễn nhiễm re-render |
| **Chuyển tab "Chưa đọc"** | `/api/v1/notifications?unread_only=true` | Loop vô tận | **Đúng 1 req** | Phân trang/lọc chuẩn xác |
| **Chuyển tab về "Tất cả"** | `/api/v1/notifications?unread_only=false` | Loop vô tận | **Đúng 1 req** | Phân trang/lọc chuẩn xác |
| **Bấm Thử lại trong Cooldown** | `/api/v1/notifications` | Gửi bão request | **0 req (chặn tại client)** | Tôn trọng Retry-After |
| **Tổng số lỗi HTTP 429** | Toàn bộ các route | Bị khóa toàn trang | **0 lỗi (Zero 429)** | Hệ thống ổn định 100% |

### 9.4. Bằng chứng Kiểm thử (Test Evidence)
- **Playwright Test Suite Chuyên dụng:** `frontend/auth-tests/notifications-storm.spec.js` (7/7 tests PASS, thời gian chạy ~37s).
- **Frontend Unit Tests:** `frontend/tests/notifications.test.mjs` (8/8 tests PASS, bổ sung kiểm tra 429 `Retry-After` và identity caching).
- **Toàn bộ Frontend Unit Tests:** `68/68 passed` (100% PASS).
- **Production Build:** `✓ built in 4.12s` (Bundle hoàn toàn sạch).
- **Live Browser QA:** Chạy trực tiếp trên Chromium với tài khoản QA thật kết nối DB 5434, ghi nhận tổng cộng 3 requests `/notifications` (1 mở, 2 đổi tab) và 0 request 429. Ảnh chụp: `live_bell_normal.png`.
