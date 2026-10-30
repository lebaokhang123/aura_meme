# AuraMeme — System Architecture

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
| Điểm danh (P1) | Browser → Aura module → check-in + XP/wallet ledger trong DB | Mốc ngày mới **07:00 Asia/Ho_Chi_Minh**, thời điểm lưu UTC; UNIQUE theo user/ngày; retry không cộng hai lần |
| Mở hòm (P1) | Browser → Vault module → odds server → debit ví → cấp item | Odds dùng Aura gốc; backend chọn kết quả/CSPRNG; debit và grant trong **cùng transaction**, kiểm soát concurrent requests |
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
- [FastAPI — Behind a Proxy](https://fastapi.tiangolo.com/advanced/behind-a-proxy/).
- [Docker — Networking in Compose](https://docs.docker.com/compose/how-tos/networking/).
- [GitHub Docs — Configuring OpenID Connect in AWS](https://docs.github.com/en/actions/how-tos/secure-your-work/security-harden-deployments/oidc-in-aws).
- [PostgreSQL — Constraints](https://www.postgresql.org/docs/current/ddl-constraints.html).
- [OWASP — Cheat Sheet Series](https://cheatsheetseries.owasp.org/).

**Bản vẽ và đặc tả là cơ sở triển khai về sau; không thay cho test, cấu hình hạ tầng hay chứng cứ vận hành.**
