# AuraMeme

Gate local Task 1–5 và hotfix thanh toán đã được kiểm chứng trên cây tích hợp e541138. Xem docs/tasks/premium-sandbox-task5.md để phân biệt lượt full, retry, PostgreSQL cô lập và phần PayPal còn NOT VERIFIED.

## Hotfix 23/11/2026

Owner cho phép tích hợp sau khi checkout, pending recovery, Admin transactions và PDF đạt gate. Bằng chứng và quyết định kỹ thuật tại docs/tasks/premium-sandbox-task5.md. Quy tắc cập nhật tài liệu hiện có áp dụng khi tích hợp Task 6–8 sau này.

## Nghiệm thu Task 1–5 · 22/11/2026

Bản nghiệm thu xuất phát từ Task 5 `682d247`. Baseline GitHub `dev` là `eacfa7d`. Tích hợp chờ Owner duyệt. Frontend React/Vite JSX, backend FastAPI và PostgreSQL.

Người dùng có hộp thư cá nhân, trang chính sách VI/EN tại `/privacy.html`, cấp độ và chức danh công khai theo tác giả. Admin quản lý vòng đời thông báo. Premium Sandbox bán Plus 5 USD/30 ngày và Prime 50 USD/365 ngày, không tự gia hạn. Lịch sử và biên lai đọc dữ liệu đơn từ API. Bằng chứng thanh toán trọn vòng qua người mua PayPal Sandbox còn thiếu.

Xem các tài liệu trong [docs/tasks](docs/tasks), [hợp đồng API](docs/api/05-api-design.md) và [thiết kế dữ liệu](docs/design/03-database-design.md).

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

### Chạy demo Bảo Khố (Vault MVP)
Để chạy bản demo có đầy đủ 2 rương (70 Meme + 5 Background):
1. Đảm bảo thư mục `backend/demo.local/catalog` có đủ 75 file ảnh (nguồn lưu trữ tại `D:\Big\du_an_lon\aura_meme_mvp\backend\demo.local\catalog`).
2. Đảm bảo `backend/demo.local/.env` có:
   ```env
   VAULT_RUNTIME_ENABLED=true
   AURAMEME_OWNER_MEME_DEMO=1
   ```
3. Chạy `.\run.bat demo`. Đăng nhập một trong ba tài khoản demo (`khang_dev@example.com`, `kien_dev@example.com`, `gigachad@example.com`) để mở và trang bị vật phẩm.

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

## Game Mechanics V1 — Khôi phục Bảo Khố MVP & Đồng bộ

Owner đã chốt 10 cảnh giới ×10 Level; XP lên cấp ` 10 + Level ` từ Lv.1–100, điểm danh +15 Aura gốc/ngày tại 07:00 Việt Nam và earned XP cap 135/ngày. Rank tính Aura gốc.

### Hai rương Bảo Khố (Vault V1)
- **Rương Background:** 5 background D/C/B/A/S (1 background mỗi cấp hiếm).
- **Rương Meme:** 70 avatar meme (D=25, C=18, B=14, A=8, S=5), đã được duyệt tên và quyền demo nội bộ.
- **Tỷ lệ mở rương:** D=68.9% (6890 bps), C=20.0% (2000 bps), B=10.0% (1000 bps), A=1.0% (100 bps), S=0.1% (10 bps).
- **Quy tắc EXP hiện hành:** Mỗi lần mở rương thành công nhận **+2 EXP** (tối đa 100 lượt có thưởng/ngày, trần 200 EXP/ngày, độc lập với trần Social 135 EXP/ngày). Từ lượt 101 trở đi vẫn nhận vật phẩm, không cộng thêm EXP. Retry cùng Idempotency-Key trả lại biên lai gốc, không cấp thưởng hay EXP trùng.
  > *Lưu ý mâu thuẫn tài liệu:* Tài liệu Game Mechanics sơ khởi cũ từng ghi "không XP từ quay", nhưng bản thiết kế MVP hoàn thiện (Phiên 005–010) và runtime code chính thức đã chốt thưởng **+2 EXP/lượt mở**. Giữ nguyên runtime đã được Owner nghiệm thu.

### Hiện trạng dữ liệu & Đồng bộ với dev
- **Code Vault:** Đầy đủ trên `dev@8b22c29` (Frontend `VaultPage.jsx`, backend `app.vault`, `app.vault_runtime`, `app.vault_open`, `app.vault_exp_award`).
- **Bản vá quyền private demo (`app/catalog_rights.py`):** Khôi phục điều kiện `owner_private_demo` với cơ chế fail-closed nghiêm ngặt: chỉ kích hoạt khi có đồng thời `AURAMEME_OWNER_MEME_DEMO=1`, `AUTH_ENVIRONMENT` thuộc `{'development', 'test', 'local'}`, `ENVIRONMENT` không phải `production`/`staging`, database host là loopback (`localhost`, `127.0.0.1`, `::1`), và tên database thuộc danh sách kiểm duyệt (`aurameme_demo`, `aurameme_vault_verify`, `aurameme_test`). Đã có suite kiểm thử negative (`test_vault_security_negative.py`) bảo đảm fail-closed 100%.
- **Dữ liệu Database:** 75 asset items, 2 case definitions, 2 published loot tables tồn tại đầy đủ, nguyên vẹn trong PostgreSQL `aurameme_demo` (schema `0012_aura_v1`).
- **Media Catalog:** Đủ 75/75 file ảnh tại `backend/demo.local/catalog`, khớp 100% mã hash SHA-256 với database.
- **Môi trường Codex QA 5189:** Sử dụng database test cô lập (`aurameme_test` trên Docker `aurameme-hotfix-test-15`), tuân thủ nghiêm ngặt quy tắc an toàn không can thiệp/seed vào `aurameme_demo`, do đó không tự có sẵn catalog demo nếu không nối cấu hình.
- **Bảo mật Git:** Tuyệt đối không commit 70 file meme riêng, file `.env`, signing key hay database dump lên Git public. Cấu hình nằm trong thư mục `demo.local/` (đã được `.gitignore` bảo vệ qua `*.local`).

## Phạm vi kiểm chứng

Frontend có unit tests và browser regression cho14màn, Guest/3user demo,375/768/1440px, theme/language, filter/history và lưu trữ lỗi/reload. Auth có unit, kiểm thử UI với HTTP stub và E2E thật trên DB riêng qua `backend/tests/run_auth_browser.py`. Chưa chứng minh triển khai production hoặc vận hành backend/DevOps.

Nguồn/license và xác nhận của Owner đối với asset được ghi riêng trong [asset ledger](frontend/ASSET_SOURCES.md); license mã nguồn không tự áp dụng cho mọi ảnh bên thứ ba.

## Nhánh sản phẩm và CI trên GitHub Actions

`main` là nhánh mặc định của sản phẩm. Tạo nhánh công việc từ `dev` và tích hợp qua PR có CI xanh. Checkout nghiệm thu local theo `origin/dev`. Khi phát hành, mở PR từ `dev` vào `main` để giữ lịch sử phát triển.

Một workflow `.github/workflows/ci.yml` chạy khi mở/cập nhật PR hoặc push vào `main` hay `dev`, với quyền `contents: read`, không deploy hoặc dùng secrets. Các action được pin theo commit SHA; Node/Python có phiên bản cụ thể, frontend dùng `npm ci`, backend dùng `backend/requirements-ci.txt` khóa dependency runtime/test (cập nhật cùng `pyproject.toml`).

- **Backend non-DB (Windows):** chạy các test không mang marker integration, gồm filesystem/launcher Windows. Loại module migration và các ca gọi Alembic demo; không có PostgreSQL service hoặc URL DB thật.
- **Frontend build and unit (Ubuntu):** cài lockfile, build và chạy các test Node hiện có.
- **Frontend browser regression (Ubuntu):** kiểm tra Auth UI ở API mode với HTTP stub, sau đó build rõ `--mode mock` và chạy suite demo bằng Chromium đi kèm phiên bản Playwright đã khóa; config riêng trong `.github/` giữ config frontend gốc. Không retry để che lỗi; upload evidence khi fail, giữ 7 ngày. Suite vẫn cần Internet cho Tailwind CDN, Google Fonts và ảnh từ xa.

**NOT COVERED TRÊN CI:** PostgreSQL integration/schema guard trên DB thật, migration/downgrade, backend browser E2E và launcher chạy trọn dịch vụ. Các lượt local được ghi riêng, không cộng vào CI. Job backend xanh chỉ chứng minh nhóm non-DB; không có nghĩa toàn bộ backend hoặc Game Mechanics đã PASS. Không tạo/migrate DB development/demo/production trong workflow này.

Social E2E thật chạy trên **aurameme_test/public0010 rỗng**: sau build API và cài Chromium, từ backend chạy `python tests/run_social_browser.py <private-config-containing-TEST_DATABASE_URL>`. Runner tạo ba tài khoản/role tổng hợp, kiểm Guest/User/Admin và4định dạng ảnh, dọn đúng fixture rồi xác minh29bảng rỗng/schema không đổi. Không sử dụng ba tài khoản/mật khẩu demo thật, không migrate hoặc dùng DB development/demo. Không có Auth/Blog fixture tự seed trong startup. `request_id` UUID tùy chọn giúp retry POST bài/bình luận trả lại cùng record; thay payload/actor trả409.

Social E2E cũng hỗ trợ DB E2E riêng: `python tests/run_social_browser.py <private-e2e-config> --e2e`, chỉ nhận `aurameme_e2e`/role `aurameme_e2e_app`/public0010 rỗng. Không chạy suite khi Owner đang dùng phiên preview có fixture. Sáu reaction post/comment được kiểm chọn/đổi/gỡ. UI Ẩn/Xóa yêu cầu xác nhận; Hủy/Escape không gửi mutation.
