# AuraMeme — API Contract & Data Flow

**Milestone:** M0.5 · **Backend:** FastAPI modular monolith · **Data:** PostgreSQL · **Trạng thái:** thiết kế mục tiêu, chưa triển khai.

**Tài liệu cùng mốc:** [`05-openapi.yaml`](./05-openapi.yaml) là **hợp đồng machine-readable**; [`05-data-flows.drawio`](./05-data-flows.drawio) là **sơ đồ luồng** 6 tab (đen trắng). File Markdown này mô tả ranh giới, quyền truy cập, bất biến dữ liệu và điều kiện nghiệm thu, không lặp chi tiết mọi schema.

## 1. Phạm vi và ranh giới

| Giai đoạn | Phân hệ | Phạm vi |
|---|---|---|
| **P0 — Core Blog** | Auth, Users, Posts, Comments, Categories, Media, Contact, Admin | Hợp đồng đầy đủ, triển khai đầu tiên |
| **P1 — AuraMeme** | Reaction, Bookmark, XP, Check-in, Leaderboard, Vault, Inventory | Hợp đồng thiết kế cho các API lõi; giá/odds/xp còn phải chốt |
| **P2 — Mở rộng** | Generator 3 ô, Aura Plus/Prime, thanh toán | **Chưa định nghĩa endpoint giao dịch** trước khi chốt quy tắc thanh toán/claim |

Một API backend phục vụ tất cả module; **không tạo microservices**. React gọi cùng origin `/api/v1` qua Nginx ở production và qua proxy dev khi lập trình local. PostgreSQL lưu dữ liệu quan hệ và media metadata; file ảnh nằm ngoài database.

## 2. Quy ước hợp đồng HTTP

| Chủ đề | Quy tắc |
|---|---|
| Prefix | `/api/v1`, health check riêng `/health` |
| Định dạng | `application/json` UTF-8; ảnh upload `multipart/form-data` |
| ID | UUID; `users/{username}` dùng tên công khai và không trả PII |
| Danh sách | `{items: [...], pagination: {page, page_size, total, total_pages}}` |
| Phân trang | `page` bắt đầu 1; `page_size` mặc định 20, tối đa 100; sorting dùng allowlist |
| Error | `{error: {code, message, request_id, details?}}`; không lộ stack trace/SQL |
| Request auth | Cookie `am_session` dạng **opaque**, HttpOnly/Secure (HTTPS), SameSite=Lax; session hash/expiry ở DB |
| CSRF | `GET /auth/csrf` cấp token; mọi POST/PUT/PATCH/DELETE yêu cầu `X-CSRF-Token`, kể cả form khách |
| Trạng thái | GET 200; POST tạo mới 201; xóa logic/đăng xuất 204; 401/403/404/409/422/429 khi phù hợp |
| Phân quyền | Backend tự kiểm quyền ADMIN, người sở hữu bài viết, trạng thái tài khoản; không tin dữ liệu role từ React |
| Idempotency | Check-in theo `(user_id, effective_day)`; mở hòm có header `Idempotency-Key` |

**CSRF:** OpenAPI mô tả header và cookie, còn implementation phải chọn pattern token an toàn được ràng buộc phiên (hoặc pre-session cho form đăng nhập), tránh token trong URL/log. Kiểm tra Origin/SameSite và CORS chính xác. Chính sách này sẽ được xác nhận khi triển khai Auth, không đồng nghĩa đã có code chạy.

**M2.1 · Owner duyệt 2026-11-04:** email trim + lowercase toàn chuỗi theo schema M1.4. Bổ sung 401 cho login thất bại, 403 cho CSRF register/login; giữ schema nghiệp vụ/error format. GET csrf vẫn public: pre-session hết hạn được cấp mới, không mặc định 401. Implementation dùng pre-session ngẫu nhiên có hạn trong store bounded một process và HMAC-SHA256 gắn pre-session/session; login tiêu thụ pre-session và cấp session riêng. Cookie HttpOnly/host-only/Path=/SameSite=Lax, Secure trên production HTTPS; idle 30 phút, absolute 12 giờ, row lock khi trượt hạn/revoke. Không bật CORS; chỉ nhận Origin hoặc Referer thuộc allowlist chính xác. Limiter/pre-session RAM chưa đáp ứng multi-worker; M2.1 đã kiểm chứng PostgreSQL và merge PR #4, xem bàn giao nội bộ. Reset password/email verification/OAuth không thuộc M2.1.

**M2.2 · Owner duyệt 2026-11-05:** riêng ProfilePatch bổ sung `additionalProperties: false`; giữ field/endpoint và hợp đồng Auth M2.1. PATCH phân biệt omission/null, media phải owned+ready; public profile chỉ active và whitelist PII-safe, avatar_url null khi chưa có provider. Đổi mật khẩu và revoke phiên khác trong một transaction, khóa user → session thống nhất với login/logout; dependency commit trước gửi response. Chưa triển khai Admin CRUD hoặc media URL service.

**M3.1 · Owner duyệt 2026-11-05:** additionalProperties:false cho CategoryInput/CategoryPatch/PostInput/PostPatch; category mới active, post mặc định draft, PATCH không gửi status giữ nguyên. Category hidden/author không active/media không ready làm post không public. Post owner mutation lọc ID+author tại DB; hidden/deleted không được sửa, foreign/missing/repeated post DELETE trả404. Category DELETE idempotent hide và ghi audit; post DELETE giữ hàng/FK. URLs null tới khi có provider; comments_count optional omit, không dùng count giả. Content chỉ text JSON, chưa renderer. Không thay các field/endpoint hợp đồng khác.

## 3. API P0 — Blog phục vụ môn học

**M3.2 · chính sách Owner chốt 2026-11-05:** POST media nhận một multipart file; session/CSRF/Origin trước parse, MIME/signature/decode nhất quán. 5 MiB/file, 12.000.000 pixels/frame; GIF tối đa60 frames/40.000.000 pixels cộng dồn (cùng ngân sách áp dụng ảnh động PNG/WebP). Private local bytes ngoài webroot, PostgreSQL chỉ metadata; UUID key, exclusive write/fsync, COMMIT trước201/ready. Giữ original bytes; cleanup khi DB từ chối, safe reconciliation event khi cleanup thất bại hoặc COMMIT không xác định; filesystem không nằm trong DB transaction.

**Media Display · overhaul 2026-11-08:** GET `/api/v1/media/{media_id}` chỉ phục vụ media ready khi đang gắn bài public (published, category/author active, chưa deleted) hoặc avatar/cover của tài khoản active; session owner được preview draft/chưa gắn. Mỗi GET kiểm lại visibility, masked404 cho foreign/private/missing/corrupt/link; không static mount hay object key trong response. Reader pin directory/file, từ chối reparse/symlink/hardlink và đọc tối đa5MiB, so size metadata. Decode theo giới hạn upload, bỏ metadata và EXIF orientation được áp vào pixels; static→PNG, animation→GIF giữ frame/timing/loop trong ngân sách, output tối đa80MiB. `?still=true` dùng cùng quyền và xuất PNG frame đầu cho reduced motion. no-store/nosniff/CSP sandbox. Upload.url, Post.media_url, UserPublic.avatar_url và AccountPrivate.avatar_url/cover_url là đường dẫn tương đối cùng origin để đi qua Vite proxy; private profile vẫn giữ các media ID. Không thêm migration/DELETE/retention hoặc đổi private writer.

Giới hạn delivery: GIF có nhiều frame giống nhau và delay cực dài có thể vượt trường delay16-bit sau khi encoder gộp frame; normal GET masked404 thay vì500, `still=true` vẫn dùng được. Animated PNG/WebP được chuyển sang bảng màu GIF, không bảo đảm giữ toàn bộ màu gốc; bytes upload riêng tư không thay đổi.

GET `/api/v1/users/{username}` trả `PublicProfile` kế thừa `UserPublic`, thêm `cover_url` nullable để hiển thị ảnh bìa đã lưu của tài khoản active. Các author DTO ở post/comment/leaderboard vẫn dùng `UserPublic`, không thêm cover hoặc thông tin riêng tư. Avatar/cover dùng cùng endpoint media kiểm visibility, không lộ storage key.

### Public và tài khoản

| HTTP | Endpoint | Quyền | Công dụng |
|---|---|---|---|
| GET | `/health` | Public | Health check |
| GET | `/api/v1/auth/csrf` | Public | Lấy token cho thao tác thay đổi |
| POST | `/api/v1/auth/register` | Guest | Tạo account; không tự cấp role ADMIN |
| POST | `/api/v1/auth/login` | Guest | Xác thực, cấp session cookie |
| POST | `/api/v1/auth/logout` | User | Thu hồi phiên |
| GET/PATCH | `/api/v1/users/me` | User | Xem/sửa hồ sơ riêng |
| PUT | `/api/v1/users/me/password` | User | Đổi mật khẩu |
| GET | `/api/v1/users/{username}` | Public | Hồ sơ công khai |

### Blog, Media, Contact

| HTTP | Endpoint | Quyền | Công dụng |
|---|---|---|---|
| GET | `/api/v1/posts` | Public | Search, category, sort, pagination |
| POST | `/api/v1/posts` | User | Đăng bài |
| GET/PATCH/DELETE | `/api/v1/posts/{post_id}` | Public / owner | Xem / sửa / xóa logic |
| GET | `/api/v1/categories` | Public | Danh mục hiển thị |
| GET/POST | `/api/v1/posts/{post_id}/comments` | Public / User | Đọc / thêm bình luận |
| DELETE | `/api/v1/comments/{comment_id}` | Owner | Xóa logic bình luận |
| POST | `/api/v1/media` | User | Upload ảnh, nhận `media_id` |
| GET | `/api/v1/media/{media_id}` | Public/owner | Ảnh đã bỏ metadata theo visibility hiện tại; `still=true` cho frame đầu |
| POST | `/api/v1/contact` | Guest/User | Gửi liên hệ, lưu database |

**Search:** Query `GET /posts?page=1&page_size=20&search=meme&category=gaming&sort=created_desc`. Search và sort phải tham số hóa/allowlist, không ghép trực tiếp SQL từ dữ liệu người dùng. **P0:** một category/post, không quá một ảnh/post, chỉ JPG/PNG/WebP/GIF.

### Quản trị (mọi endpoint yêu cầu ADMIN)

| HTTP | Endpoint | Mục đích |
|---|---|---|
| GET/POST | `/api/v1/admin/users` | Danh sách / tạo user |
| PATCH/DELETE | `/api/v1/admin/users/{user_id}` | Sửa, khóa/kích hoạt, xóa logic |
| PUT | `/api/v1/admin/users/{user_id}/roles` | Gán role; bảo vệ admin cuối cùng |
| GET | `/api/v1/admin/posts` | Xem bài mọi trạng thái |
| PATCH/DELETE | `/api/v1/admin/posts/{post_id}` | Ẩn/hiện/xóa logic |
| GET/POST | `/api/v1/admin/categories` | Xem cả danh mục ẩn / tạo |
| PATCH/DELETE | `/api/v1/admin/categories/{category_id}` | Sửa / ẩn hoặc ngưng dùng |
| GET | `/api/v1/admin/contacts` | Tra cứu liên hệ |
| PATCH | `/api/v1/admin/contacts/{contact_id}` | Cập nhật xử lý liên hệ |
| GET | `/api/v1/admin/audit-logs` | Xem nhật ký quản trị |

Các màn hình Home giới thiệu/About/Team có thể là **React static content**, không tạo bảng/API CMS chỉ để hoàn thiện sitemap. Các thao tác quản trị làm thay đổi dữ liệu phải ghi `admin_audit_logs` trong cùng transaction khi phù hợp.

## 4. API P1 — Aura và Bảo Khố

| HTTP | Endpoint | Quyền | Dữ liệu quan trọng |
|---|---|---|---|
| PUT/DELETE | `/api/v1/posts/{post_id}/reactions` | User | Một reaction hiện hành/user/post (đề xuất M0.3) |
| PUT/DELETE | `/api/v1/posts/{post_id}/bookmark` | User | Lưu/bỏ lưu, không thưởng XP |
| GET | `/api/v1/aura/progress` | User | earned, bonus, total, level, streak, Khí Vận |
| POST | `/api/v1/aura/check-in` | User | Tính ngày theo 07:00 giờ VN; một ngày một lần |
| GET | `/api/v1/leaderboard` | Public | `period=week|all`; chỉ Aura gốc |
| GET | `/api/v1/vault/cases` | Public | Danh mục hòm đang mở |
| GET | `/api/v1/vault/cases/{case_id}` | Public | Tỷ lệ *đã công bố* theo ngưỡng Aura gốc |
| POST | `/api/v1/vault/cases/{case_id}/open` | User | Key retry; debit + cấp vật phẩm nguyên tử |
| GET | `/api/v1/inventory/me` | User | Bộ sưu tập của tôi |
| PUT | `/api/v1/inventory/equipment/{slot_kind}` | User | Trang bị/tháo đồ đúng loại và thuộc sở hữu |

**Nguyên tắc sản phẩm đã thống nhất:** Free ×1, Aura Plus ×2, Aura Prime ×3 nhân **Aura thưởng** cho level/khung; **Rank và tỷ lệ rương chỉ tính earned_xp**. Khí Vận không rút tiền/chuyển cho người khác. P2 mới bật entitlement/thu tiền, không tạo endpoint mua VIP giả để gọi như đã triển khai.

## 5. Luồng dữ liệu và transaction contracts

**05-data-flows.drawio** có các tab:

1. **00 — API Boundary:** Browser → Nginx → FastAPI modules → PostgreSQL / media storage.
2. **01 — Auth and Session (P0):** Lấy CSRF → đăng nhập → xác minh mật khẩu → cấp cookie → tra session cho lần gọi tiếp theo.
3. **02 — Posts and Media (P0):** Upload ảnh, xác minh owner → tạo post bằng `media_id` → trả 201. Xử lý cleanup ảnh nếu lưu bytes thành công nhưng metadata thất bại.
4. **03 — Daily Checkin (P1):** Backend xác định `effective_day` (07:00 VN), khóa bản ghi, ghi thưởng XP/Khí Vận trong cùng transaction. Retry trả kết quả đã có.
5. **04 — Vault Opening (P1):** Backend chọn published loot pool + CSPRNG, trừ ví, lưu open, cấp vật phẩm, commit **một transaction**. UI chỉ làm hoạt ảnh.
6. **05 — Admin and Audit (P0):** Kiểm cookie, ADMIN, nghiệp vụ, transaction + audit; user thường gọi endpoint admin trả 403.

**Không nhầm sơ đồ với bằng chứng runtime:** transaction order, khóa row, FK, các case lỗi và khôi phục dữ liệu được kiểm chứng khi phát triển và integration test.

## 6. Bài test hợp đồng khi đến phase triển khai

| Nhóm | Test bắt buộc |
|---|---|
| Auth | Đúng/sai mật khẩu, khóa user, hết hạn phiên, CSRF thiếu/sai, logout và revoke |
| Role | Guest gọi admin → 401; User gọi admin → 403; user sửa bài người khác → 403 hoặc 404 |
| Blog | CRUD, tên category sai, ảnh không thuộc owner, phân trang/sort, SQLi input không đổi truy vấn |
| Upload | Fake MIME, vượt dung lượng, ảnh quá lớn, trạng thái rejected, cleanup orphan objects |
| Aura | 06:59/07:00/07:01 VN, 2 request đồng thời, đổi múi giờ client, không nhận thưởng lần hai |
| Vault | 2 lần dùng cùng Idempotency-Key, cùng key khác payload 409, thiếu Khí Vận, race double spend, odds không nhận từ client |
| Audit | Admin thay role/status/hide post có audit log, không ghi secret/PII nhạy cảm |

## 7. Quyết định cần phê duyệt khi triển khai

- **Auth (P0):** thời gian sống session; reset mật khẩu, email verification, chính sách cookie và pre-auth CSRF. Google/Discord OAuth để sau.
- **Media (P0):** hạn dung lượng, kích thước ảnh, local storage dev và bucket production.
- **Aura (P1):** XP/caps/moderation, một hay nhiều reaction, quy tắc reversal, ngưỡng level/rank.
- **Vault (P1):** lượt free/day, giá hòm, cơ chế vật phẩm trùng, odds đã mô phỏng và duyệt.
- **P2:** 3 ô generator, gói VIP và payment provider/webhook khi tới giai đoạn, chưa hiện thực API.

## 8. Nguồn thiết kế

- `AURA_MEME_MASTER_PLAN_V3.md` — phạm vi, feature và quy tắc đã duyệt.
- `docs/design/03-database.dbml` và `03-database-design.md` — bảng, PK/FK và transaction invariant.
- `docs/architecture/04-architecture-decisions.md` — backend, reverse proxy, môi trường local/cloud, bảo mật.
- [OpenAPI Specification 3.0.3](https://spec.openapis.org/oas/v3.0.3.html).
- [FastAPI — Behind a Proxy](https://fastapi.tiangolo.com/advanced/behind-a-proxy/).
- [OWASP — CSRF Prevention](https://cheatsheetseries.owasp.org/cheatsheets/Cross-Site_Request_Forgery_Prevention_Cheat_Sheet.html).
- [OWASP — SQL Injection Prevention](https://cheatsheetseries.owasp.org/cheatsheets/SQL_Injection_Prevention_Cheat_Sheet.html).


**M5.2 · Owner duyệt 2026-11-06:** thêm GET `/api/v1/users/me/posts` (page/page_size/status draft/published/hidden) và GET `/api/v1/users/me/posts/{post_id}`. Cần session active, lọc author_id từ session và loại deleted; foreign/missing/deleted detail trả404. `OwnPost` kế thừa Post, thêm `media_id` UUID nullable cho editor private; không object_key/file path/PII mới. GET public và media_url=null giữ nguyên, không mở media delivery.

Owner duyệt M6.1c: riêng GET `/api/v1/aura/progress` và GET `/api/v1/leaderboard` bổ sung503/`NOT_READY`, dùng error schema hiện có; không đổi response fields/endpoint. Progress vẫn cần session, leaderboard public. Missing/draft/invalid policy hoặc trạng thái P1 thiếu trả NOT_READY, không tự publish policy hoặc bật runtime rewards.

Owner duyệt M6.2: POST `/api/v1/aura/check-in` bổ sung503/NOT_READY, error schema hiện có; session/CSRF/Origin trước readiness. Chưa mở runtime phát thưởng, không thay endpoint/response fields và không coi fixture schedule là chính sách được duyệt.

M7.1b Owner duyệt GET `/api/v1/catalog/assets/{asset_id}` public chỉ cho catalog active/rights approved. Đọc bounded từ CATALOG_STORAGE_ROOT riêng, kiểm SHA256/MIME, decode và xuất PNG bỏ metadata, no-store/nosniff; missing/inactive/rights/hash/file không hợp lệ trả404. Không phục vụ media_uploads, không mount thư mục hoặc tự duyệt catalog. Inventory/equipment luôn kiểm owner từ session, quantity>0/active/slot, DB guard bảo vệ khi thay quantity/active.

M7.2a: GET common case chỉ công bố version published có policy effective và bands0→∞ không hở/chồng, đủ5rarities/sum10000bps, positive bucket có item active/rightsapproved. Seed/activate/odds economics chưa được duyệt; danh sách rỗng/chi tiết404 khi chưa ready. Draw engine dùng CSPRNG secrets hai tầng; simulation seed chỉ tests, không endpoint chọn reward từ client.

M7.2b Owner duyệt503/NOT_READY riêngPOSTcase-open, session/CSRF/Origin trước readiness; runtime không grant/debit/consumequota. Idempotency-Key12–128 theo contract. Atomicopen/weekly7of7/grants chỉ simulator aurameme_test/public với policy draft; các giá/odds/quota/duplicate-mode fixtures không phải luật sản phẩm. HTTP không nối simulator kể cả có policy fixture.

**Đọc reaction/bookmark:** GET `/api/v1/posts/{post_id}/interactions` trả `post_id`, `reaction_counts` đủ `like/laugh/fire`, `comments_count`, `viewer_reaction` nullable và `bookmarked`. Counts chỉ gồm reaction của user active và comment visible/chưa xóa của author active. Bài không public trả404; counts và visibility được đọc cùng một SQL statement. Guest không có trạng thái cá nhân; cookie đã gửi nhưng sai/hết hạn/khóa trả401, không âm thầm thành Guest. Session hợp lệ dùng cùng cơ chế refresh/revoke hiện hành. Không trả actor IDs, danh sách người lưu hoặc tổng bookmark.

GET `/api/v1/users/me/bookmarks` cần session, lấy owner từ phiên; trả PostPage bằng DTO/public visibility hiện hành với `page`, `page_size`, `search` title/content, `category` slug và `sort=created_desc|created_asc|title_asc`. Bài hidden/draft/deleted, tác giả locked, category hidden hoặc media không ready bị loại. Pagination/sort có UUID tie-break; không cho user chọn owner qua query. PUT/DELETE reaction/bookmark giữ nguyên idempotency và không cộng Aura. Giao diện chi tiết đọc trạng thái một lần, không gọi endpoint này cho từng card của feed.

**Điều khiển danh sách theo đề tài:** mọi route dưới giữ `page/page_size`, quyền hiện hành và UUID tie-break. Search là substring literal (escape `%/_`), tối đa100 ký tự, NUL bị422; sort chỉ nhận allowlist, không ghép SQL từ input.

| GET | Search | Filter | Sort (đầu tiên là mặc định) |
|---|---|---|---|
| `/posts/{post_id}/comments` | body | author username exact; public visibility giữ nguyên | created_asc, created_desc |
| `/users/me/posts` | title/content | status, category slug; owner từ session | created_desc, created_asc, title_asc |
| `/admin/users` | username/email/display_name | status, role USER/ADMIN | username_asc, username_desc, created_desc, created_asc |
| `/admin/posts` | title/content | status, category slug | created_desc, created_asc, title_asc |
| `/admin/categories` | name/slug | status | slug_asc, name_asc, name_desc |
| `/categories` | name/slug | slug; chỉ active | slug_asc, name_asc, name_desc |
| `/admin/contacts` | name/email/subject/body, chỉ Admin | status | created_desc, created_asc, subject_asc |
| `/admin/audit-logs` | action/target_type/target_id/actor_id | action exact, target_type exact, actor_id UUID | created_desc, created_asc, action_asc |

Audit chỉ tìm và trả metadata hiện có, không tìm hoặc trả before/after snapshots. Contact là inbox có quyền Admin, không mở search nội dung cho public. Không thay trạng thái bài, quyền người dùng, schema hoặc cơ chế soft delete.
