# AuraMeme — System Architecture

## Hotfix nghiệm thu 23/11/2026

Owner cho phép tích hợp Task 1–5 sau gate hotfix. Checkout dùng selector có phạm vi .checkout-page để thắng rule input của Tailwind Forms được nạp sau stylesheet. Computed style Chrome trước sửa cho input Dark là rgb(255,255,255), chữ rgb(227,225,237). Font kế thừa Inter. Sau sửa giữ token màu theo theme, placeholder, focus và autofill. Screenshot nằm tại thư mục local AuraMemeReview/87f2574/hotfix-evidence.

Pending dùng cùng hạn một giờ ở create, GET, init PayPal, simulate và capture. Khóa hàng User cùng transaction trước khi tìm đơn chặn hai phiên tạo đồng thời. Tìm theo user và tier, sắp created_at DESC, id DESC; mở lại giữ created_at. Prime và Plus có đơn riêng. Đơn trùng lịch sử được giữ, đơn hợp lệ mới nhất được ưu tiên. Resume từ History đọc lại đơn trên server, kiểm quyền chủ đơn và thời hạn. Đối soát PayPal lỗi trả lỗi có thể thử lại, không tự capture từ nhánh catch init và không chuyển giao dịch chưa rõ sang thẻ. Return/cancel dùng origin đã được cho phép của request.

Admin 87f2574 đã được tái hiện trên cùng DB QA có expired và trả 200 với tổng 0. Nguyên nhân DTO thiếu expired bị except Exception che thành bảng rỗng. DTO/parser mới nhận đủ năm trạng thái, join username theo chủ đơn, trả số tiền USD/VND, completed_at và mã provider. Query read-only có search mã đơn, filter, phân trang và sort created_at DESC, id DESC. Lỗi SQL và DTO trả 500. Guest 401, member 403.

PDF của đơn được chọn đọc detail cùng endpoint successful riêng theo phiên, lấy tối đa 10 success theo completed_at mới nhất. History không còn fallback sang trang đang filter. Request history lỗi hiện thông báo thử lại. Bảng PDF có mã đơn cùng mã provider, xuống dòng tham chiếu dài. Header vẫn giữ đơn chọn dù nằm ngoài latest 10. Giá VND ghi rõ tham khảo. Dữ liệu mô phỏng được ghi nhãn Sandbox, không xác nhận PayPal thu tiền thật.

Bằng chứng tập trung gồm 5/20/50 phút reuse, quá hạn một giờ bị chặn, hai phiên concurrent cùng mã pending, Plus/Prime/Plus/Prime, Admin hai chủ đơn và lỗi SQL/DTO. Sáu PDF tải qua UI từ fixture PostgreSQL cô lập tương ứng 1/5/10/11 success, 5 success cộng pending/failed/expired/cancelled, và người mua khác. Extract xác nhận số dòng 1/5/10/10/5/1, thứ tự, cách ly, đơn chọn và provider. Mỗi PDF một trang A4, render đã kiểm. Matrix Chrome gồm Dark/Light, VI/EN, 375/1440 và PayPal/thẻ, focus, validation, autofill ép pseudo-state bằng CDP. Real buyer PayPal Sandbox E2E vẫn NOT VERIFIED.

Không đổi schema DB trong hotfix. DBML giữ schema 0014 đã nghiệm thu. Dữ liệu test tổng hợp được giữ trong DB QA, kể cả fixture từ các lượt thử chưa hoàn tất. Kết quả regression trên cây tích hợp và SHA dev được ghi tiếp sau khi có bằng chứng.


## Thông báo, danh tính và Premium Sandbox · Task 1–5

Thông báo social và bản ghi quản trị cùng transaction với hành động nguồn. Bản quản trị lưu trạng thái draft/published/withdrawn, bản phát có khóa duy nhất theo thông báo và người nhận. Session xác định hộp thư và backend kiểm quyền quản trị. Trang chính sách tĩnh hỗ trợ đường dẫn trực tiếp và nội dung tiếng Việt khi JavaScript tắt.

Thông tin công khai của tác giả do backend chiếu từ hồ sơ, tiến trình và hội viên. Chức danh chỉ dùng để hiển thị. RBAC đọc bảng vai trò. Khi thiếu level hợp lệ, DTO bỏ level và chức danh. Rank giữ chính sách điểm earned hiện hành.

Đơn Sandbox lưu giá và thời hạn lúc mua. Capture, webhook và đối soát đơn cũ dùng chung phép kiểm tra USD, merchant, tham chiếu đơn và capture COMPLETED. Khóa dòng đơn giữ hai callback của cùng đơn xử lý tuần tự. Callback webhook lấy thông tin Orders từ PayPal; xác minh không đủ thì dừng cấp quyền. Giao diện thẻ mô phỏng chỉ gửi hành động thanh toán và cần bật mô phỏng ngoài production. Không bật Live.

**Milestone:** M0.4 · **Phạm vi:** Kiến trúc ứng dụng, môi trường local, triển khai AWS và vận hành.  
**Sơ đồ:** [`04-system-architecture.drawio`](./04-system-architecture.drawio) (4 tab, đen trắng).  
**Trạng thái:** Kiến trúc **mục tiêu được đưa ra để chủ dự án duyệt**; tài liệu không xác nhận rằng các thành phần đã triển khai.

## 1. Tổng quan và ranh giới triển khai

```text
Browser / React UI
       |
       | HTTPS (production)
       v
Nginx — phục vụ static build, chuyển /api
       |
       v
FastAPI modular monolith
       |                   \
       | SQL                \ media bytes
       v                     v
PostgreSQL               Object storage (target)
1 database               (chẳng hạn AWS S3)
```

- **P0 — Blog học phần:** Auth/RBAC, hồ sơ, bài viết/danh mục/bình luận/ảnh, contact, quản trị/audit. Đây là phạm vi triển khai ưu tiên.
- **P1 — AuraMeme:** Aura gốc và Aura thưởng, Rank, streak, ví Khí Vận, Bảo Khố, catalog, inventory.
- **P2 — Mở rộng:** Ba ô sinh Khí Vận, Aura Plus/Prime, thanh toán/sandbox.
- **Một backend:** các module là các miền nghiệp vụ **trong một ứng dụng FastAPI**, không phải microservice hoặc database riêng.
- **Một PostgreSQL database:** các bảng và khóa tham chiếu xem `../design/03-database.dbml` và `../design/03-database-design.md`. Chỉ thêm migration theo phase thực sự xây dựng.
- **Nguồn ảnh:** DB lưu **metadata/object key**, còn file ảnh lưu trong môi trường phát triển hoặc object storage sản phẩm. Không lưu ảnh binary trực tiếp trong cột Postgres.

## 2. Quyết định kiến trúc

| Thành phần | Lựa chọn cho AuraMeme | Lý do | Giới hạn / phương án chưa chọn |
|---|---|---|---|
| Frontend | React + Vite + TypeScript | Giữ giao diện prototype có giá trị, type checking, tách UI với API | Vite dev server chỉ dùng khi phát triển; production phục vụ static build |
| Backend | FastAPI, modular monolith | Học Python/API, kiểm soát nghiệp vụ Aura và transaction tại server | Không chia microservices, không duy trì hai backend FastAPI + ASP.NET song song |
| Data access | SQLAlchemy + Alembic | ORM, transaction và migration có kiểm soát | Không để `create_all()` thay thế migration khi vận hành |
| Database | PostgreSQL | Dữ liệu quan hệ, ràng buộc, index, transaction rõ ràng | Không tách DB cho từng module; không dùng Firebase/Supabase mặc định |
| Media | Local dev → object storage trên production | Phân biệt bytes và metadata; không mất ảnh do thay container | Chưa chốt giá/giới hạn upload, bucket và lifecycle |
| Local packaged | Docker Compose | Reproduce local và học Docker networking/volumes | Không lắp K8s hoặc queue trước khi có nhu cầu |
| Web entry | Nginx | Một origin cho UI và `/api`, TLS + reverse proxy | Backend port và DB port không mở public |
| Production V1 | Một AWS EC2 + Compose + PostgreSQL volume | Đủ để thực hành deploy thủ công, có thật URL/HTTPS | Single point of failure; RDS/ALB/HA chỉ xem xét khi cần |
| CI/CD | GitHub Actions → image registry → EC2 | Lint/test/build/version/deploy, có health check và rollback | Chưa triển khai; không tự giả định workflow release |
| AWS access | IAM roles, OIDC cho GitHub Actions | Giảm việc lưu access key dài hạn trong GitHub | Phải giới hạn trust policy theo repo/ref/environment |
| Infrastructure as code | Terraform sau manual AWS | Biết tài nguyên nào đang tồn tại trước khi mã hóa IaC | Không Terraform trước khi hiểu đường đi thực tế |

## 3. Môi trường local

### 3.1 Phát triển từng ứng dụng (giai đoạn code)

- UI chạy `npm run dev` (Vite, ví dụ `localhost:5173`), gọi API tới FastAPI qua HTTP. Có thể dùng cấu hình proxy dev hoặc CORS chính xác theo origin.
- API chạy Uvicorn (ví dụ `localhost:8000`); PostgreSQL là cài local hoặc container; Alembic tạo và nâng schema.
- Port là **ví dụ dự kiến**, không phải cấu hình đã chạy.
- Nếu dùng cookie phiên đăng nhập, cần kiểm tra CORS, credentials, SameSite và CSRF cho request đổi dữ liệu; không tự dùng wildcard bừa bãi.

### 3.2 Đóng gói local (sau khi P0 chạy)

- `nginx` phục vụ React build; `/api` chuyển tới service `api` trong Compose.
- Service `api` kết nối PostgreSQL bằng **hostname `db`** qua Compose DNS, không dùng `localhost` trong container. `db` không publish cổng 5432 ra mạng công cộng.
- PostgreSQL sử dụng named volume; `.env`/secrets không commit vào Git. Volume tồn tại **không đồng nghĩa đã có backup**.
- Migration chạy theo thao tác được kiểm soát trước khi coi release mới đã sẵn sàng.

## 4. Luồng dữ liệu quan trọng

| Nghiệp vụ | Luồng request | Ranh giới tin cậy và dữ liệu thay đổi |
|---|---|---|
| Đăng ký / đăng nhập (P0) | Browser → `/api/v1/auth/...` → Auth module → PostgreSQL | Backend validate, hash mật khẩu, quản lý cookie/session, kiểm tra khóa tài khoản; không tin role do client gửi |
| Tạo bài đăng kèm ảnh (P0) | React → API → validate ảnh/ownership → media storage → DB metadata/bài | Giới hạn loại/kích thước; xác minh nội dung file; phục hồi khi ghi file thành công nhưng transaction DB lỗi |
| Bình luận / reaction (P0/P1) | Browser → Blog module → DB → (P1) Aura ledger | Authorization, giới hạn spam; điểm thưởng được tính tại backend, idempotency key nghiệp vụ và transaction |
| Điểm danh (P1) | Browser → Aura V1 → receipt + XP ledger trong DB (không ví) | Mốc ngày mới **07:00 Asia/Ho_Chi_Minh**, thời điểm lưu UTC; UNIQUE theo user/ngày; +15 XP gốc, retry delta0, không cấp Khí Vận; receipt ví legacy được giữ nguyên |
| Mở hòm (P1) | Browser → Vault V1 → odds cố định server → receipt/grant → quantity | V1 miễn phí, không ví/XP; CSPRNG, owner/idempotency/cooldown server; receipt+grant trong **cùng transaction**, metadata chỉ đọc khi schema0012 và runtime được bật |
| VIP (P2) | Payment provider → verified webhook → entitlement | Không tin callback frontend để cấp VIP; **Plus x2 / Prime x3 chỉ tăng Aura bonus/level/khung**; Rank và odds không nhân |

## 5. Bề mặt tấn công và biện pháp thiết kế

| Ranh giới | Nguy cơ | Biện pháp dự kiến |
|---|---|---|
| Browser → API | XSS, CSRF, abuse, giả role/user ID | Validate input, escape output, CSRF cho cookie auth, auth/RBAC/ownership tại API, rate limit |
| API → PostgreSQL | SQL Injection, sai quyền, trùng transaction | ORM/bind parameters, SQL role hạn chế, UNIQUE/FK, transaction/locking, integration tests |
| Upload → media | File giả MIME, quá dung lượng, mã nguy hiểm | Kiểm signature/type/size, hạn chế quyền lưu/truy cập, không chạy file upload như script |
| Internet → EC2 | Lộ cổng, brute force, TLS kém | SG chỉ public 80/443; SSH từ IP admin hoặc SSM; TLS; cập nhật bản vá; log và cảnh báo |
| Nginx → API | Giả mạo `X-Forwarded-*` | Chỉ tin forwarded headers từ reverse proxy thực sự đáng tin; không mở FastAPI trực tiếp public |
| GitHub Actions → AWS | Lộ AWS credential, sai deploy quyền | OIDC, IAM least privilege, scope trust policy, protected environment, tránh secrets trong logs |
| Dữ liệu/cấu hình | Xóa nhầm, disk full, hỏng máy, leaked secrets | Off-host backup + restore drill, quota/budget alert, rotate secrets, runbook và rollback |

Bộ kiểm bảo mật trước demo phải bao gồm các trường hợp âm tính (khách gọi API admin, user sửa bài người khác, upload file sai định dạng, SQL injection input, yêu cầu XP/case lặp, thiếu CSRF token). Tài liệu này **không khẳng định test đã chạy**.

## 6. Triển khai AWS V1 và giới hạn

**Đường request đề xuất:** Domain → DNS → EC2 Nginx HTTPS → static React hoặc `/api` FastAPI → PostgreSQL private trên cùng host. S3 là đích lưu media khi triển khai production; chưa mặc định đã tạo bucket.

**Trước khi public:** có AWS Budget alert, MFA tài khoản, SG đúng, TLS tự động gia hạn, secrets an toàn, DB volume, backup ngoài EC2 và thử restore. Giới hạn chủ động chấp nhận: một EC2 không có HA; lỗi host có thể làm gián đoạn cả web và database. Nếu dự án thực sự tăng trưởng, mới đánh giá RDS, ALB, nhiều AZ, CDN hoặc queue.

### Vòng đời release (mục tiêu)

1. Feature branch → review → lint/test/typecheck/build trên GitHub Actions.
2. Build image gắn **commit SHA**, đẩy image registry; xác thực AWS qua OIDC.
3. Deploy trên EC2 theo phiên bản, chạy migration tương thích, health check và smoke test.
4. Nếu hỏng, rollback application image; **schema rollback phải có kế hoạch riêng**, không mặc định rollback image là đủ.
5. Kiểm tra logs, 5xx/latency, CPU/RAM/disk/DB và kết quả backup/restore.

**Git hiện tại:** `dev` là nhánh có lịch sử độc lập với `main` prototype. Không mô tả PR `dev → main` thông thường như đã sẵn sàng. Khi V1 đạt yêu cầu, lưu lại phiên bản prototype thành branch/tag archive và chủ dự án phê duyệt chiến lược chuyển default branch/release mà không mất lịch sử mong muốn.

## 7. Quyết định cần chốt trước khi bắt đầu code hoặc deploy

1. **Backend:** xác nhận FastAPI/SQLAlchemy/Alembic là stack chính thức; không kế thừa ASP.NET lab cũ.
2. **Authentication:** cookie session, xác thực email/reset password, CSRF và chính sách OAuth Google/Discord.
3. **Upload:** dung lượng mỗi ảnh, loại ảnh, local storage dev, cách quản lý media object key và quy tắc xóa.
4. **AWS V1:** ngân sách, region, kích thước EC2, có dùng S3 từ đầu không, chiến lược backup ngoài host.
5. **CI/CD release:** thời điểm chuyển nhánh độc lập `dev` thành nền stable mới, image registry, cách rollback migration.
6. **Observability:** mức tối thiểu cần cảnh báo; điểm kết thúc/giữ log và thời gian backup retention.

Các tham số Aura/odds/payment còn mở đã nằm trong `03-database-design.md` và MASTER_PLAN V3; không quyết định thay chủ dự án tại M0.4.

## 8. Tài liệu tham chiếu

- `AURA_MEME_MASTER_PLAN_V3.md` — mục tiêu và milestone.
- `docs/design/03-database.dbml` + `docs/design/03-database-design.md` — thiết kế database và quan hệ.
- `docs/design/01-sitemap-*` và `02-usecase-*` — luồng nghiệp vụ.

## 9. Task 7 — Google Login, Forgot Password & Transactional Email (`feat/google-email-task7`)

### 9.1. Google Identity / OIDC (`backend/app/google_auth.py`)
- **Xác minh phía server:** Kiểm tra `aud`, `iss`, `exp`, `sub`, `email_verified=true` và `nonce` chống replay/login CSRF. Không lưu Google token trong `localStorage`.
- **Định danh ổn định & Chống chiếm đoạt tài khoản:** Bảng `user_oauth_identities` gắn `UNIQUE(provider, provider_sub)`. Nếu email Google trùng với tài khoản cục bộ chưa liên kết, backend trả `409 ACCOUNT_LINK_REQUIRED` (tuyệt đối không tự gộp theo email). Việc liên kết (`POST /api/v1/auth/google/link`) yêu cầu phiên đăng nhập + CSRF + xác minh lại mật khẩu hiện tại. Tài khoản mới từ Google chỉ nhận role `USER` và đặt mật khẩu sentinel `!google:...` không thể đăng nhập bằng password.

### 9.2. Quên mật khẩu (`backend/app/password_reset.py`)
- **Neutral Response & Token Một lần:** `POST /api/v1/auth/forgot-password` luôn trả thông báo trung tính giống hệt nhau (không lộ email có tồn tại hay không), rate-limit theo IP và email hash. Token ngẫu nhiên 32-byte chỉ lưu dạng SHA-256 (`password_reset_tokens.token_hash`), hạn dùng 30 phút.
- **Session Revocation:** `POST /api/v1/auth/reset-password` bắt buộc chính sách mật khẩu 12–128 ký tự, đánh dấu `used_at`, thu hồi toàn bộ `auth_sessions` cũ, không tự động đăng nhập; tài khoản Google-only bị từ chối rõ ràng (`400 GOOGLE_ONLY_ACCOUNT`). Frontend `ResetPasswordPage` xóa `?token=` khỏi URL bar ngay khi nạp bằng `history.replaceState`.

### 9.3. Hệ thống Email giao dịch (`backend/app/email_service.py`)
- Dùng chung cho 3 luồng: Quên mật khẩu, Tiếp nhận Contact/Feedback (có rate-limit chống spam), và Biên nhận Premium (chỉ gửi khi đơn `success`, chống gửi trùng theo `dedupe_key=premium:receipt:{order_code}`, lỗi gửi mail không rollback PayPal capture).
- **Chống giả mạo sender:** Chặn `no-reply@aurameme.com` khi `EMAIL_DOMAIN_VERIFIED=false` (`EMAIL_DOMAIN_UNVERIFIED`). Hỗ trợ 3 chế độ: `disabled`, `sandbox` (in-memory test capture), và `smtp` (TLS/SSL, tối đa 2 lần thử, không log secret).

### 9.4. Hướng dẫn Owner cấu hình Credentials (khi bật Live)
1. **Google Cloud Console:** Tạo OAuth 2.0 Web Client ID (loại Web application), cấu hình Authorized JavaScript origins (`http://localhost:5173`, `http://127.0.0.1:5173` và domain production), Authorized redirect URIs để trống đối với GIS JavaScript callback hiện hành. Không yêu cầu Client Secret. Gán `GOOGLE_CLIENT_ID` vào `backend/.env`. Endpoint Tokeninfo phục vụ local/demo; đánh giá nâng cấp sang xác minh ID Token bằng thư viện chính thức (`google-auth`) hoặc JWKS signature là gate bảo mật riêng trước production.
2. **SMTP / Email Provider:** Cấu hình `EMAIL_MODE=smtp`, `SMTP_HOST`, `SMTP_PORT`, `SMTP_USERNAME`, `SMTP_PASSWORD`, `EMAIL_FROM_ADDRESS`, `EMAIL_ADMIN_INBOX`, và chỉ bật `EMAIL_DOMAIN_VERIFIED=true` sau khi xác minh SPF/DKIM cho `aurameme.com`. Timestamp trong email biên nhận Premium hiển thị định dạng `HH:MM:SS - DD/MM/YYYY` theo múi giờ `Asia/Ho_Chi_Minh`, giữ nguyên dữ liệu thời gian gốc trong database.

## 10. Task 8 — Public Profile, Follower Count & Cookie Consent (`feat/public-profile-cookie-task8`)

### 10.1. Public Profile & Follower Count
- **Điều hướng tác giả:** Bọc Avatar, Tên hiển thị và `@username` thành liên kết tới `/profile/:username` trên Home, Explore (`stopPropagation` để không đè click mở bài) và Bình luận (`CommentSection`); hỗ trợ thêm alias `/u/:username` tại `main.jsx` & `ProfilePage.jsx`.
- **Ranh giới quyền riêng tư:** Khi User B hoặc Guest xem hồ sơ User A (`mine === false`), ẩn hoàn toàn nút chỉnh sửa hồ sơ và bộ sưu tập riêng tư, không gọi `/inventory/me` hay `/aura/progress` của người khác, không rò rỉ email/SĐT/biên lai.
- **Follower count trung thực:** Hiển thị số liệu thật nếu API trả về (`follower_count`), mặc định `0` (`Người theo dõi` / `Followers`) — không dựng số giả và chưa mở rộng Follow/Unfollow, Friends hay Chat.
- **Hover preview:** Đánh dấu `DEFER` theo quyết định mặc định để tránh làm phình kiến trúc và phạm vi kiểm thử.

### 10.2. Cookie Consent — Lucian UX/UI Prompt #225
- Port nguyên tinh thần **Lucian #225 ("Cookie consent with a bite", MIT License)** sang React component (`CookieConsent.jsx`, `cookie-consent.css`, `cookie-consent.js`) trong namespace `.am-cookie-*`.
- **Trung thực dữ liệu:** Cookie thiết yếu (`am_session` HttpOnly, CSRF, theme/language) luôn bật và không thể tắt; mục phân tích/tiếp thị công bố rõ ràng là chưa sử dụng tracker bên thứ ba và mặc định tắt. Lựa chọn lưu tại `aurameme-cookie-consent-v1` kèm `version` và `updatedAt`, liên kết trực tiếp tới `/privacy.html#cookies`, hỗ trợ mở lại từ nút cookie góc dưới trái, Dark/Light, VI/EN, Mobile 375px và `prefers-reduced-motion`.
- [FastAPI — Behind a Proxy](https://fastapi.tiangolo.com/advanced/behind-a-proxy/).
- [Docker — Networking in Compose](https://docs.docker.com/compose/how-tos/networking/).
- [GitHub Docs — Configuring OpenID Connect in AWS](https://docs.github.com/en/actions/how-tos/secure-your-work/security-harden-deployments/oidc-in-aws).
- [PostgreSQL — Constraints](https://www.postgresql.org/docs/current/ddl-constraints.html).
- [OWASP — Cheat Sheet Series](https://cheatsheetseries.owasp.org/).

**Bản vẽ và đặc tả là cơ sở triển khai về sau; không thay cho test, cấu hình hạ tầng hay chứng cứ vận hành.**

## Owner Acceptance Hotfix — Cấu hình PayPal Sandbox/SMTP và capture

`PremiumSettings` và `EmailSettings` đọc process env trước `backend/.env`. Launcher demo áp dụng cấu hình DB/auth/media từ allowlist riêng trong `backend/demo.local/.env`. Các khóa PayPal/SMTP được cấu hình riêng ở backend. Frontend và tiến trình mở browser không nhận các biến cấu hình này từ launcher. Tài khoản Buyer/Business tương tác ở Sandbox và nằm ngoài cấu hình ứng dụng.

Thanh toán PayPal Sandbox dùng order ID đầu vào để ràng buộc callback, và lưu capture ID do provider trả về sau khi đối soát. Mô phỏng dùng ý định riêng, không xuất hiện như provider approval và không thể ghi đè order có PayPal ID thật. Trạng thái order thành công độc lập với trạng thái hội viên ACTIVE.

## 25/11/2026 — Founder Collection và kiểm thử PostgreSQL disposable

Founder Collection ràng buộc đúng ID Khang Dev, chỉ xét avatar/background đã duyệt, đang hoạt động và có reward policy hợp lệ. Grant chạy theo khóa idempotency riêng, ghi inventory/InventoryGrant và audit, không sinh CaseOpen hoặc EXP. Daily check-in và mở rương giữ đường ghi EXP độc lập.

Kiểm thử Checkpoint 3 có worker commit thật. Khởi tạo PostgreSQL mới với tên `aurameme_test`, role ứng dụng cùng tên, schema public, cổng PostgreSQL 5432 và revision 0018. Container database không publish cổng và chạy với `--network none`. Tiến trình pytest dùng `--network container:<id>` để gọi 127.0.0.1:5432. Đặt `cluster_name` ở cấu hình server thành `aurameme-fp-<32 hex>`, truyền cùng tên qua `AURAMEME_DISPOSABLE_TEST_CLUSTER` và chỉ truyền DSN qua `TEST_DATABASE_URL`. Dùng phiên bản dependencies trong `requirements-ci.txt`.

Fixture đối chiếu danh tính, marker, revision, role và schema rỗng trước khi ghi. Ca mở rương và duyệt Admin đi qua HTTP, CSRF, session và transaction dependency thật. Dữ liệu rollback dùng một transaction, runner thay thế DB fixture của từng ca commit bằng bản clone của template sạch, giữ trigger append-only. Lệnh từ backend: python tests/run_final_polish_disposable.py --image <image-đã-cài-requirements-ci> --repeat 2 --regressions. Runner chỉ dừng container định danh do nó tạo.

CLI dry-run tách các mục đã có, có thể cấp và bị chặn. Execute dừng trước mutation nếu bất kỳ mục eligible nào bị chặn do thiếu policy. Execute trên demo là gate riêng của Owner.


## Hardening H02 — Authentication & Security Stabilization (27/11/2026)

- **Nhánh & Baseline:** `fix/h02-auth-security` từ `origin/dev@98ddc31` (bảo toàn `test/system-simulation@ee1fd45` cho H01).
- **Sửa lỗi đồng bộ Authentication đa tab:**
  - Nguyên nhân: `frontend/src/auth.js` reload tab khi `BroadcastChannel('aurameme-auth')` thông báo thay đổi, nhưng `frontend/src/main.jsx` chỉ redirect `protectedPage` khi thành `guest`, thiếu redirect cho `/login` và `/register` khi `authState.status === 'authenticated'`.
  - Thay đổi tối thiểu: thêm [auth-routing.js](../../frontend/src/auth-routing.js) (`resolveAuthRedirect`, `isProtectedPath`) sử dụng `safeReturnUrl`, lắng nghe `pageshow` (`ev.persisted`) trong [auth.js](../../frontend/src/auth.js) cho back/forward cache, và áp dụng redirect + render guard trong [main.jsx](../../frontend/src/main.jsx) khi `authState.status === 'authenticated'` trên `/login` hoặc `/register` (giữ nguyên `/verify-email`, `/reset-password`, `/forgot-password`).
  - Bảo mật: không truyền token/cookie qua `BroadcastChannel`, không tin `localStorage`, giữ server `/api/v1/users/me` và `guest_guard` là nguồn xác thực duy nhất.
- **Hiệu chỉnh benchmark H04 (ghi nhận từ audit `perf_baseline.py` H01):**
  - H01 `perf_baseline.py` dùng chung `httpx.AsyncClient` không tách session/cookie theo từng virtual user, chưa có think time giữa các request trong `run_stage`, thời lượng mỗi mức tải ngắn (4s), chưa đo riêng authenticated write workload. Sẽ hiệu chỉnh các tham số này trong H04 (không tối ưu sản phẩm ở H02).
- **Learning Check:** `PENDING OWNER`.


## Hardening H03 — Product Reliability & Error Handling (27/11/2026)

- **Nhánh & Baseline:** `fix/h03-product-reliability` từ `origin/dev@b20122c` (sau PR #46 H02 và CI `45914443441` PASS 3/3).
- **H03.1 — Admin Users Email:**
  - `frontend/src/admin-api.js`: giữ trường `email` cho `resource === 'users'` (giới hạn 254 ký tự), giữ nguyên việc loại bỏ `password_hash` và `email` trên `contacts`.
  - `frontend/src/components/AdminPage.jsx` & `frontend/src/workspace.css`: hiển thị `.admin-user-email` dưới `@username` và trên `.admin-role-list`, hỗ trợ ngắt dòng an toàn (`overflow-wrap: anywhere`) trên mobile và Dark/Light mode. Public profile/feed/search không thay đổi và không lộ email.
- **H03.2 — Email MIME Inline Logo:**
  - `backend/app/email_service.py`: loại bỏ `filename="aurameme-logo.png"` khỏi `html_part.add_related(..., disposition="inline")` và bổ sung `X-Attachment-Id: aurameme-logo` để tránh client Gmail nhận diện inline logo thành chip attachment. Giữ `cid:aurameme-logo` khớp `<aurameme-logo>` (tương thích toàn bộ test hiện hành) và bảo toàn PDF attachment trong Premium receipt.
  - Gmail visual acceptance trên inbox thật vẫn ở trạng thái `PENDING OWNER`.
- **H03.3 — Error Pages, Strict Routing & Error Boundary:**
  - Thêm `frontend/src/components/ErrorPage.jsx` (403, 404, 500, 503; cyber-clean gradient tím/cyan; VI/EN; Dark/Light; `prefers-reduced-motion`; không lộ stack trace/DSN/token) và `frontend/src/components/ErrorBoundary.jsx`.
  - `frontend/src/runtime.js`: thay `PAGE[path] || 'home'` bằng `isKnownRoute(path)` (kiểm kê rõ static routes + `PROFILE_ROUTE`), route không hợp lệ trả `notFound: true` và render `ErrorPage` 404.
  - `frontend/src/main.jsx` & `frontend/src/components/AdminPage.jsx`: USER đã đăng nhập truy cập `/admin` hoặc `/admin/contacts` nhận `ErrorPage` 404 chung (không lộ chi tiết khu quản trị), trong khi backend API vẫn giữ nguyên `403 FORBIDDEN`. Guest vẫn được redirect `/login?next=...` theo H02.
  - Lưu ý kiến trúc: `ErrorPage` là client-side UI trong SPA; HTTP status thực tế từ static hosting vẫn do Nginx/reverse proxy quyết định (không thay đổi hạ tầng trong H03).
- **Learning Check:** `PENDING OWNER`.


## ADR-H04: Batch Query Cho Feed Interactions (`read_post_states`) & Danh Gia Index/Search

- **Trang thai:** Da chap thuan & Trien khai tren nhanh `perf/h04-feed-optimization`.
- **Van de:** `GET /api/v1/posts?include_interactions=true` goi `read_post_state` theo vong lap tung bai viet (`N+1` queries: 27 SQL o `page_size=20`, 107 SQL o `page_size=100` cho Guest; 32 -> 112 SQL cho Auth), lam p50/p95 tang manh va kich hoat safe-stop o 25 VUs (`p95 = 6709.51 ms`).
- **Quyet dinh:**
  1. Them `read_post_states(post_ids, db, viewer_id, request, meme_states=None)` trong `backend/app/interactions.py`, dung `WHERE post_id IN (...)` + `GROUP BY` de gom reaction counts, comment counts, viewer reaction, va viewer bookmarks thanh hang so `O(1)` truy van (9 SQL cho Guest, 16 SQL cho Auth bat ke `page_size` 10/20/50/100), bo qua 2 truy van viewer khi `viewer_id is None`.
  2. Giu nguyen `read_post_state` cho endpoint don le `/api/v1/posts/{id}/interactions` va xac minh 100% parity qua PostgreSQL integration test (`backend/tests/test_h04_batch_interactions.py`).
  3. **Danh gia Search & Index:** Khong them migration/index moi o H04 vi: (a) `searchable(col)` dung `translate(translate(lower(...)))` + `ILIKE '%...%'` nen B-tree index thong thuong khong co tac dung; (b) giu nguyen Offset Pagination contract va tim kiem tieng Viet substring hien hanh; (c) giu nguyen `SELECT ... FOR UPDATE` tren `auth_sessions` de bao toan an toan xac thuc & single-flight session.
  4. **Learning Check:** `PENDING OWNER`.
- **H04 Final Query Count & Benchmark Caveats (Safety Gate):**
  - **Final SQL query count:** `Guest 10`, `Auth 17`, on dinh theo `page_size` `10/20/50/100` (bao gom `public_posts` visibility guard trong `read_post_states`).
  - **Pham vi benchmark:** Cac so lieu latency/RPS BEFORE/AFTER hien co duoc do truoc khi bo sung visibility guard cuoi; khong tuyen bo final candidate da duoc benchmark day du lai.
  - **Gioi han he thong:** HTTP 429 tu rate limiter tren loopback IP o 10-25 VUs va `feed_search` (~1.5s-1.9s) van la gioi han can theo doi.
  - **Test Harness Safety Gate:** Dung chung `scripts/h04/safety_guard.py` (fail-closed kiem tra container `aurameme-h01-sim-pg`, port mapping `127.0.0.1:55450`, DB `aurameme_test`, revision `0018_canonical_asset_filenames`, synthetic fixture marker, SMTP sandbox, va owned uvicorn subprocess tren cong rieng `18080`).


## ADR-H05: Admin Presence Monitoring (`feat/h05-admin-presence`)

- **Trang thai:** Da chap thuan & Trien khai tren nhanh `feat/h05-admin-presence`.
- **Van de:** Admin can theo doi so luong thanh vien va khach dang hoat dong gan thoi gian thuc ma khong tao database migration, khong ghi tung heartbeat vao PostgreSQL, khong dung WebSocket/SSE/Redis, va khong lam lo du lieu dinh danh ca nhan.
- **Quyet dinh:**
  1. **Single-process In-Memory Store (`PresenceStore` trong `backend/app/presence.py`):** Dung `OrderedDict` ket hop `threading.Lock`, `ttl_seconds=90`, va `max_entries=16384` cho moi loai (`_user_sessions`, `_guest_tokens`). Lazy prune cac ban ghi het han truoc khi ghi/doc va O(1) eviction khi day bo nho.
  2. **Identity & Privacy:**
     - Authenticated user: Xac thuc qua `am_session` cookie (read-only `SELECT` 1 truy van, khong `FOR UPDATE`, khong ghi DB); luu `(session_id) -> (user_id, expiry)` de nhieu tab/nhieu thiet bi cua cung 1 user chi dem **1** `distinct user_id`, va logout 1 thiet bi chi xoa `session_id` do.
     - Guest: Cap random token 32-byte vao cookie `am_guest` (`HttpOnly`, `SameSite=Lax`), chi luu `sha256` digest; khong dung IP hay browser fingerprint. Khi guest dang nhap, tu dong xoa `guest_digest` khoi `_guest_tokens` de tranh dem trung.
  3. **API & Frontend:**
     - `POST /api/v1/presence/heartbeat`: Origin guard + rate limit (12/60s per identity + `AuthBoundaryMiddleware`), `0 SQL` cho Guest, `1 read-only SELECT` cho Auth.
     - `GET /api/v1/admin/presence`: Guard `require_role("ADMIN")`, `Cache-Control: no-store`, chi tra tong hop (`active_total`, `active_users`, `active_guests`, `window_seconds`, `generated_at`).
     - Frontend `startPresenceHeartbeat` (30s interval, tam dung khi `hidden`, ton trong HTTP 429 `Retry-After`) va Admin Overview tab (polling 15s khi co quyen & dang xem).
  4. **Gioi han:** Chi chinh xac trong pham vi single-process (`workers=1`); neu scale multi-worker trong tuong lai, huong nang cap la Redis TTL (`SET EX` / `ZSET`).
  5. **Learning Check:** `PENDING OWNER`.

- **Bo sung Final Preflight (Eventual Consistency & ORM Lifecycle):**
  - **Session revocation & eventual consistency:** `heartbeat()` kiem tra day du `revoked_at`, `expires_at` (idle expiry), `created_at + ABSOLUTE_SECONDS` (absolute expiry), va `User.status == "active"`. Khi user `logout()`, `remove_session(session_id)` xoa ngay lap tuc khoi `PresenceStore`; tuy nhien neu session bi revoke tu xa hoac user bi khoa boi Admin, ban ghi presence cu co the ton tai toi da `TTL = 90s` truoc khi tu het han.
  - **Bounded capacity:** `max_entries = 16384` gioi han bo nho tren RAM, khong dong nghia ho tro `16.384 concurrent users` (nhieu session/thiet bi cua cung user hoac guest churn co the chiem nhieu entry).


## ADR-H06: Final Asset Lifecycle, Rarity Versioning, Tombstone & Founder Authority (`fix/h06-asset-lifecycle`)

- **Trang thai:** Da chap thuan & Trien khai tren nhanh `fix/h06-asset-lifecycle` (thay the quy tac bao ve co dinh 75 vat pham goc va `RARITY_IMMUTABLE` truoc do).
- **Van de:** Admin can quan ly toan dien ca vat pham goc lan vat pham tai len (doi ten, doi hang D/C/B/A/S, ngung luu hanh, khoi phuc) ngay ca khi da so huu/trang bi/mo ruong, va rieng Founder Khang Dev co quyen xoa vinh vien vat pham da luu tru, nhung van bao toan toan ven tham chieu (`fk_case_opens_pool_reward`, `aurameme_odds_guard`, `aurameme_equipment_guard`) va lich su mo ruong.
- **Quyet dinh:**
  1. **Migration `0019_asset_lifecycle_tombstone`:**
     - Them tombstone `asset_items.deleted_at` / `deleted_by` (`FK users.id ON DELETE RESTRICT`, `CHECK (deleted_at IS NULL OR NOT active)`).
     - Them `case_opens.reward_rarity` (luu snapshot hang tai thoi diem mo ruong) va thay `fk_case_pool_items_asset_rarity` bang `fk_case_pool_items_asset_id` (`asset_id -> asset_items.id ON DELETE RESTRICT`) de cac bang `case_pool_items` da `retired` giu nguyen hang lich su khi `asset_items.rarity` thay doi.
     - Cap nhat `aurameme_equipment_guard()`: cho phep doi `rarity` khi da co trong `user_inventory` (van khoa doi `kind`), va chan deactivate/tombstone neu `user_equipment` van dang tro toi.
  2. **RBAC & Founder Authority:** Moi `ADMIN` duoc doi ten, doi hang, duyet/tu choi, ngung luu hanh (`archive`), khoi phuc (`approve`). Rieng `DELETE /api/v1/admin/assets/{id}` chi cho phep `KHANG_DEV_ID` (`403 FORBIDDEN` cho Admin khac), chi ap dung khi dang `Archived` (`409 ASSET_NOT_ARCHIVED`), va bat buoc nhap xac nhan `XÓA VĨNH VIỄN`.
  3. **Vault Pool Versioning & Empty Bucket Policy:** Moi thay doi (`archive`, `reject`, `permanent_delete`, `rarity` change, `restore`) tao `CaseLootTable` phien ban moi (`odds_version + 1`), giu nguyen trong so D/C/B/A/S (`6890, 2000, 1000, 100, 10`). Neu mot bucket bi rong, thao tac quan ly van thanh cong kem `pool_warnings` cho Admin va ruong bi anh huong tam ngung mo (`503 NOT_READY`) cho den khi duoc bo sung.
  4. **Tombstone Isolation:** Toan bo truy van runtime (`inventory`, `vault/catalog`, `equipment`, `meme_reactions`, `vault_privilege` Founder reconciliation, `admin/assets`) loc `deleted_at IS NULL`, bao toan `CaseOpen`, `InventoryGrant`, EXP, wallet va `AdminAuditLog`.
  5. **Migration & Rollback Safety (`0018 -> 0019`):** Truoc khi nang cap `aurameme_demo` hoac moi truong chinh len `0019_asset_lifecycle_tombstone`, bat buoc `pg_dump -Fc` ban sao luu pre-0019. `downgrade()` cua `0019` duoc thiet ke fail-closed: sau khi da phat sinh du lieu tombstone (`deleted_at IS NOT NULL`) hoac thay doi rarity lich su (`case_pool_items.rarity <> asset_items.rarity`), lenh `alembic downgrade` se bi chan de bao ve du lieu lich su; khi can rollback bat buoc phuc hoi tu ban backup `pg_restore`.
  6. **Learning Check:** `PENDING OWNER`.
