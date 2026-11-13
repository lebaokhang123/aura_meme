# AuraMeme

AuraMeme là đồ án web cộng đồng chia sẻ meme. Frontend chính hiện là bản Stitch React đã được Owner duyệt; Auth đã nối với FastAPI/PostgreSQL; Social/Blog đã nối API; Game Mechanics chưa tích hợp.

## Frontend hiện tại

- React 19, JavaScript/JSX, Vite 7; 14 màn Guest/User/Auth trên 8 route.
- Responsive, dark/light, VI/EN; header/footer dùng chung.
- Home/Explore: category, search, New/Hot; số danh mục đếm theo bài hiện có.
- API thật: feed/category/search/New–Hot/pagination, tạo/sửa/xóa bài, upload PNG/JPEG/GIF/WebP, sáu reaction bài/bình luận, chèn emoji và moderation có RBAC/audit.
- Auth mặc định dùng API thật, cookie HttpOnly và CSRF; danh tính/quyền lấy từ `/users/me`, không tin localStorage.
- API mode chỉ dùng PostgreSQL, không đọc/nhập IndexedDB demo. Category và counts lấy từ DB. Mock mode riêng vẫn giữ bộ demo/UI regression cũ. Level/danh xưng trên card API là placeholder, chưa tính Aura/XP.
- Rank/Vault/Contact và các chức năng tương lai có trạng thái demo/bảo trì, không phát thưởng hoặc thanh toán thật.

## Chạy local

Cần Node.js >=22.12.0, backend và PostgreSQL đã cấu hình. `run.bat demo`/`run.bat dev` dùng Auth API thật, frontend tại `http://localhost:5173`; không trộn hostname với 127.0.0.1. Auth/Social cần revision `0010_social_reactions`; launcher dừng nếu DB rỗng hoặc schema không khớp và không tự migrate/seed. Nâng demo từ0009 chỉ sau khi Owner duyệt, có backup và restore drill; development giữ nguyên.

Tại root repository đã cấu hình demo và cài dependencies, chạy:

```powershell
.\run.bat demo
```

Backend venv cần cài package của chính checkout (`cd backend`, `python -m pip install -r requirements-ci.txt`, rồi `python -m pip install -e . --no-deps` trong venv). Frontend cần `npm ci`. Launcher không tự sửa secrets hoặc dùng môi trường của checkout khác. `run.bat dev` chỉ chạy khi development đã có schema được chuẩn bị riêng; không dùng nó để tự khởi tạo DB.

Khi chỉ cần chạy frontend riêng (backend đã chạy):

```powershell
cd frontend
npm ci
npm run dev
```

Vite proxy `/api` đến `http://127.0.0.1:8000`, giữ Origin. Backend local cần cho phép chính xác `http://localhost:5173` trong cấu hình Auth development; cấu hình production vẫn yêu cầu HTTPS. Đăng nhập bằng email và mật khẩu local thực tế; ứng dụng không lưu mật khẩu hoặc session token trong web storage.

Ba tài khoản demo: `khang_dev@example.com`, `kien_dev@example.com` (USER + ADMIN), `gigachad@example.com` (USER). Công cụ `python -m app.demo_accounts` chỉ đọc kế hoạch mặc định; `--apply` yêu cầu xác nhận và nhập mật khẩu ẩn. Xem [hướng dẫn frontend](frontend/SETUP.txt).

```powershell
npm run build
node --test tests/*test.mjs
npm test
```

Browser tests dùng Chrome qua Playwright. Tailwind Play CDN, Google Fonts và một số ảnh từ xa cần Internet. Xóa storage/đổi origin sẽ không thấy dữ liệu demo đã tạo. Xem [hướng dẫn frontend](frontend/SETUP.txt) và [nguồn asset](frontend/ASSET_SOURCES.md).

## Cấu trúc

| Thư mục | Vai trò |
|---|---|
| [frontend/](frontend/) | Frontend Stitch demo hiện hành, source/reference/assets/tests |
| [backend/](backend/) | FastAPI modular monolith, Alembic, PostgreSQL; Auth đã tích hợp |
| [docs/design/](docs/design/) | Sitemap, use case và thiết kế dữ liệu |
| [docs/architecture/](docs/architecture/) | Kiến trúc và các quyết định thiết kế |
| [docs/api/](docs/api/) | Hợp đồng API và data flow; một phần phản ánh runtime legacy |

Frontend/backend nền đã checkpoint qua PR #26/#27. Không tự migrate/seed database development. Code frontend cũ có thể phục hồi qua Git history; backup/evidence nội bộ không được đưa lên GitHub.

## Game Mechanics V1 — đặc tả, chưa bật runtime

Owner đã chốt 10 cảnh giới ×10 Level; XP lên cấp ` 10 + Level ` từ Lv.1–100, điểm danh +15 Aura gốc/ngày tại07:00 Việt Nam và earned XP cap135/ngày. Rank tính Aura gốc. Hai rương Meme/Ảnh Bìa quay miễn phí, có cooldown, nhận trùng; odds D68,9/C20/B10/A1/S0,1 và không cộng XP khi mở hòm. Plus30 ngày XP×2, Prime365 ngày XP×3; VNPAY Sandbox, chưa bán tiền thật. Ví Khí Vận/generator legacy đang hoãn. Cần task API/schema/test tương ứng trước khi tích hợp.

## Phạm vi kiểm chứng

Frontend có unit tests và browser regression cho14màn, Guest/3user demo,375/768/1440px, theme/language, filter/history và lưu trữ lỗi/reload. Auth có unit, kiểm thử UI với HTTP stub và E2E thật trên DB riêng qua `backend/tests/run_auth_browser.py`. Chưa chứng minh triển khai production hoặc vận hành backend/DevOps.

Nguồn/license và xác nhận của Owner đối với asset được ghi riêng trong [asset ledger](frontend/ASSET_SOURCES.md); license mã nguồn không tự áp dụng cho mọi ảnh bên thứ ba.

## CI trên GitHub Actions

Một workflow `.github/workflows/ci.yml` chạy khi mở/cập nhật PR vào `dev` và khi push `dev`, với quyền `contents: read`, không deploy hoặc dùng secrets. Các action được pin theo commit SHA; Node/Python có phiên bản cụ thể, frontend dùng `npm ci`, backend dùng `backend/requirements-ci.txt` khóa dependency runtime/test (cập nhật cùng `pyproject.toml`).

- **Backend non-DB (Windows):** chạy các test không mang marker integration, gồm filesystem/launcher Windows. Loại module migration và các ca gọi Alembic demo; không có PostgreSQL service hoặc URL DB thật.
- **Frontend build and unit (Ubuntu):** cài lockfile, build và chạy các test Node hiện có.
- **Frontend browser regression (Ubuntu):** kiểm tra Auth UI ở API mode với HTTP stub, sau đó build rõ `--mode mock` và chạy suite demo bằng Chromium đi kèm phiên bản Playwright đã khóa; config riêng trong `.github/` giữ config frontend gốc. Không retry để che lỗi; upload evidence khi fail, giữ 7 ngày. Suite vẫn cần Internet cho Tailwind CDN, Google Fonts và ảnh từ xa.

**NOT COVERED TRÊN CI:** PostgreSQL integration/schema guard trên DB thật, migration/downgrade, backend browser E2E và launcher chạy trọn dịch vụ. Các lượt local được ghi riêng, không cộng vào CI. Job backend xanh chỉ chứng minh nhóm non-DB; không có nghĩa toàn bộ backend hoặc Game Mechanics đã PASS. Không tạo/migrate DB development/demo/production trong workflow này.

Social E2E thật chạy trên **aurameme_test/public0010 rỗng**: sau build API và cài Chromium, từ backend chạy `python tests/run_social_browser.py <private-config-containing-TEST_DATABASE_URL>`. Runner tạo ba tài khoản/role tổng hợp, kiểm Guest/User/Admin và4định dạng ảnh, dọn đúng fixture rồi xác minh29bảng rỗng/schema không đổi. Không sử dụng ba tài khoản/mật khẩu demo thật, không migrate hoặc dùng DB development/demo. Không có Auth/Blog fixture tự seed trong startup. `request_id` UUID tùy chọn giúp retry POST bài/bình luận trả lại cùng record; thay payload/actor trả409.

Social E2E cũng hỗ trợ DB E2E riêng: `python tests/run_social_browser.py <private-e2e-config> --e2e`, chỉ nhận `aurameme_e2e`/role `aurameme_e2e_app`/public0010 rỗng. Không chạy suite khi Owner đang dùng phiên preview có fixture. Sáu reaction post/comment được kiểm chọn/đổi/gỡ. UI Ẩn/Xóa yêu cầu xác nhận; Hủy/Escape không gửi mutation.
