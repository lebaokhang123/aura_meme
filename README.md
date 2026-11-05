# AuraMeme

**AuraMeme** là dự án ứng dụng web cộng đồng chia sẻ meme, kết hợp tính năng blog, tương tác bài viết và cơ chế tích lũy điểm Aura. Dự án hướng tới việc xây dựng một sản phẩm có thể vận hành, đồng thời thực hành thiết kế hệ thống, lập trình web và quy trình triển khai DevOps.

## Phạm vi sản phẩm

- **Blog cộng đồng (P0):** tài khoản, hồ sơ cá nhân, phân loại bài viết, đăng bài, bình luận, tìm kiếm, trang liên hệ và chức năng quản trị.
- **Tương tác và Aura (P1):** biểu cảm, lưu bài, bảng xếp hạng, điểm danh hằng ngày, ví Khí Vận, Bảo Khố và vật phẩm trang trí.
- **Mở rộng (P2):** ô tạo Khí Vận, gói thành viên và mô phỏng thanh toán; chỉ triển khai sau các chức năng cốt lõi.

## Công nghệ dự kiến

| Thành phần | Công nghệ |
|---|---|
| Frontend | React, TypeScript, Vite |
| Backend | Python, FastAPI (modular monolith) |
| Database | PostgreSQL, Alembic |
| Đóng gói và triển khai | Docker Compose, Nginx, AWS |
| Tích hợp và vận hành | GitHub Actions, giám sát, sao lưu và Infrastructure as Code theo từng giai đoạn |

## Tài liệu kỹ thuật

| Nội dung | Tài liệu |
|---|---|
| Sitemap, Use Case | [`docs/design/`](docs/design/) |
| Mô hình dữ liệu và đặc tả PostgreSQL | [`03-database.dbml`](docs/design/03-database.dbml) · [`03-database-design.md`](docs/design/03-database-design.md) |
| Kiến trúc hệ thống | [`04-system-architecture.drawio`](docs/architecture/04-system-architecture.drawio) · [`04-architecture-decisions.md`](docs/architecture/04-architecture-decisions.md) |
| Hợp đồng API và luồng dữ liệu | [`05-openapi.yaml`](docs/api/05-openapi.yaml) · [`05-api-design.md`](docs/api/05-api-design.md) · [`05-data-flows.drawio`](docs/api/05-data-flows.drawio) |

## Trạng thái dự án

Frontend nền tảng nằm trong [`frontend/`](frontend/), tái sử dụng giao diện prototype. Có Home, Explore, About/Team, Contact, Login và Register. **Đây là bản preview:** bài viết và số liệu là dữ liệu mẫu; đăng nhập, đăng ký, gửi liên hệ, tạo bài và phần thưởng chưa kết nối backend. Các form preview không gửi hoặc lưu dữ liệu.

Backend nền tảng có `GET /health`, cấu hình môi trường, lệnh kiểm tra PostgreSQL và migration schema 11 bảng P0. M1.4 chỉ thử migration trên DB test riêng, chưa áp dụng vào development hoặc triển khai API nghiệp vụ; frontend vẫn là preview độc lập. CI/CD và hạ tầng AWS chưa triển khai. Tài liệu thiết kế trên nhánh [`dev`](https://github.com/lebaokhang123/aura_meme/tree/dev) là cơ sở cho các mốc tiếp theo.

## Chạy frontend local

Yêu cầu Node.js **22.12 trở lên** và npm. Từ thư mục repository:

```powershell
cd frontend
npm ci
npm run dev
```

Mở URL Vite in ra trong terminal (mặc định `http://localhost:5173`). Không cần backend hoặc PostgreSQL cho bản preview này.

```powershell
npm run lint     # TypeScript typecheck, chưa phải ESLint
npm run build    # Typecheck và production bundle trong dist/
npm run preview  # Xem production bundle sau build
npm test         # Smoke test Playwright, cần Google Chrome đã cài
```

Smoke test tự chạy Vite trên `127.0.0.1:4173`, kiểm routing, refresh, alias/404, màn hình 375/768/1440px, bàn phím và giảm chuyển động. Font/icon được self-host cùng giấy phép; ảnh chưa xác minh được thay bằng SVG placeholder tự tạo. Xem [`frontend/ASSET_SOURCES.md`](frontend/ASSET_SOURCES.md).

## Chạy backend local (Windows)

Yêu cầu Python **3.12 trở lên**. Từ thư mục repository, dùng PowerShell:

```powershell
cd backend
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --only-binary=:all: -e ".[test]"
if (-not (Test-Path .env)) { Copy-Item .env.example .env }
# Sửa DATABASE_URL, AUTH_ENVIRONMENT và AUTH_ALLOWED_ORIGINS trong .env.
# Chỉ tạo signing key lần đầu, không ghi đè key đang dùng:
.\.venv\Scripts\python.exe -c "import secrets; from dotenv import dotenv_values, set_key; v=dotenv_values('.env').get('AUTH_SIGNING_KEY'); set_key('.env','AUTH_SIGNING_KEY',secrets.token_urlsafe(48)) if not v or v.startswith('CHANGE_ME') else None"
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Các lệnh gọi Python trực tiếp trong venv nên không cần đổi ExecutionPolicy hoặc activate. Environment ghi đè `backend/.env`. `DATABASE_URL` bắt buộc có dạng `postgresql+psycopg://user:password@host:5432/database`; percent-encode ký tự đặc biệt trong user/password. `.env.example` chỉ có placeholder, không phải credential hoạt động. `DB_CONNECT_TIMEOUT` là số giây từ 1 đến 30, mặc định 5. Không đưa `.env` hoặc URL chứa mật khẩu vào Git/log.

`AUTH_SIGNING_KEY` bắt buộc, ít nhất 32 byte ngẫu nhiên; placeholder bị từ chối. `AUTH_ENVIRONMENT=production` mặc định yêu cầu HTTPS và cookie Secure. Chỉ dùng `development` với origin loopback cụ thể cho HTTP local; `AUTH_ALLOWED_ORIGINS` là JSON array origin chính xác, không wildcard. Không bật CORS; frontend dùng same-origin/proxy theo thiết kế. Chưa migrate `aurameme_dev`: Auth sẽ chưa chạy nghiệp vụ trên development cho tới khi được Owner phê duyệt riêng.

- `http://127.0.0.1:8000/health` → HTTP 200, `{"status":"ok"}`: kiểm tra tiến trình API; không xác nhận DB đã sẵn sàng.
- `http://127.0.0.1:8000/openapi.json` và `/docs`: hợp đồng runtime chỉ cho endpoint đã triển khai. Đặc tả toàn dự án nằm tại `docs/api/05-openapi.yaml`.
- Thiếu/sai cấu hình làm startup thất bại với lỗi đã ẩn giá trị nhạy cảm. DB chưa sẵn sàng vẫn có thể chạy health; dùng probe riêng bên dưới.

Mở terminal khác tại `backend/`:

```powershell
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m app.db  # SELECT 1: exit 0 nếu OK, exit 1 nếu cấu hình/DB lỗi
```

Probe dùng connection context manager của SQLAlchemy, trả connection về pool và dispose khi kết thúc; không tạo/sửa bảng. Engine API dùng `pool_pre_ping`, được dispose khi shutdown. Không bật SQL echo hoặc in connection string khi probe lỗi.

Integration test chỉ kết nối khi bạn đặt **environment** `TEST_DATABASE_URL`; không tự đọc biến này từ `.env`, không tạo database. Nếu thiếu biến, test cần DB ghi rõ SKIPPED thay vì nhận PASS cho DB thật. Dùng trình soạn thảo/secret manager để đặt giá trị riêng; không dán credential vào lịch sử terminal.

### Migration P0 (M1.4)

Alembic hiện chỉ cho phép database **`aurameme_test`**, tách khỏi `DATABASE_URL` development. Không có DSN trong `alembic.ini`, không tự migrate khi FastAPI startup. Offline SQL và migration development được chặn trong milestone này.

Lưu test URL riêng vào `backend/.env` dưới tên `TEST_DATABASE_URL` rồi chạy từ `backend/` bằng PowerShell; đoạn sau chỉ truyền giá trị vào process con, không in credential:

```powershell
@'
import os, subprocess, sys
from dotenv import dotenv_values
env = os.environ.copy()
env["TEST_DATABASE_URL"] = dotenv_values(".env")["TEST_DATABASE_URL"]
subprocess.run([sys.executable, "-m", "alembic", "current"], env=env, check=True)
raise SystemExit(subprocess.call([sys.executable, "-m", "pytest", "-q"], env=env))
'@ | & .\.venv\Scripts\python.exe -
```

Test migration thực hiện upgrade → upgrade lại → downgrade base → upgrade, so DBML/metadata và thử constraint trong transaction rollback. **Downgrade xóa các bảng của migration**: chỉ dùng DB test chuyên dụng. Bộ test từ chối schema lạ hoặc bảng ứng dụng có dữ liệu; bản thân downgrade cũng khóa các bảng P0 và từ chối nếu còn hàng, không tự xóa dữ liệu để chạy tiếp. Không reset database/volume. Kết thúc để DB test ở `0001_p0` (head), không có dữ liệu nghiệp vụ mẫu. Không áp dụng schema/rollback vào development ở M1.4.

### Authentication (M2.1)

`GET /api/v1/auth/csrf` cấp token JSON gắn với pre-session có hạn 10 phút hoặc session đang đăng nhập. Gửi token qua `X-CSRF-Token` và Origin/Referer hợp lệ cho register/login/logout. Sau login, gọi lại GET csrf để lấy token gắn với session mới; token pre-auth bị tiêu thụ. GET vẫn public và cấp pre-session mới nếu cookie cũ hết hạn. Không đưa token vào URL/log/localStorage.

Register tạo user/profile/USER role trong một transaction, không tự login; email được trim + lowercase toàn chuỗi. Password 12–128 ký tự, Argon2id 19 MiB/2 iterations/parallelism 1, không truncate. Login cấp session token ngẫu nhiên mới, DB chỉ giữ SHA-256 digest. Cookie `am_session` HttpOnly, host-only, Path=/, SameSite=Lax, Secure ở production. Idle timeout 30 phút trượt, absolute 12 giờ tại server; logout chỉ revoke session hiện tại. Các tab cùng profile chia sẻ cookie, các thiết bị có phiên độc lập.

Chạy nhóm không cần PostgreSQL: `.\.venv\Scripts\python.exe -m pytest -q -m "not integration"`. Full suite dùng đoạn truyền TEST_DATABASE_URL ở trên: có test Auth với savepoint/rollback và test concurrency trên các UUID test riêng, cleanup đúng dữ liệu tạo ra. Chỉ dùng `aurameme_test` chuyên dụng, không chạy song song với thao tác SQL của Owner; không dùng database có dữ liệu cần giữ. Đừng coi nhóm không cần DB là nghiệm thu integration.

Giới hạn hiện tại: limiter và pre-session store bounded trong RAM, chỉ hỗ trợ **một process**; restart hủy pre-session, chưa có shared limiter cho multi-worker/production. Rate limit theo IP thật (không tin X-Forwarded-For) và email đăng nhập; cấu hình proxy/retention session cần review ở milestone vận hành. Không có OAuth/JWT/reset password/đổi mật khẩu hoặc kết nối frontend trong M2.1.

> Nhánh `main` lưu bản prototype/bài thực hành trước đây; nhánh `dev` dùng cho sản phẩm đang phát triển và có lịch sử Git độc lập.
