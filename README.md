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

**Backend, database, CI/CD và hạ tầng AWS chưa triển khai.** Tài liệu thiết kế trên nhánh [`dev`](https://github.com/lebaokhang123/aura_meme/tree/dev) là cơ sở cho các mốc tiếp theo.

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

> Nhánh `main` lưu bản prototype/bài thực hành trước đây; nhánh `dev` dùng cho sản phẩm đang phát triển và có lịch sử Git độc lập.
