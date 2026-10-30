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

Các tài liệu phân tích và thiết kế đã được xây dựng trên nhánh [`dev`](https://github.com/lebaokhang123/aura_meme/tree/dev). Ứng dụng mới đang ở giai đoạn chuẩn bị triển khai; **backend, database, CI/CD và hạ tầng AWS chưa được công bố là đã vận hành**. Hướng dẫn khởi chạy và bằng chứng kiểm thử sẽ được bổ sung khi có mã nguồn tương ứng.

> Nhánh `main` lưu bản prototype/bài thực hành trước đây; nhánh `dev` dùng cho sản phẩm đang phát triển và có lịch sử Git độc lập.
