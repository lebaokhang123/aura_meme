# AuraMeme — Handoff hiện tại

- **Cập nhật:** 2026-10-30 · **Giai đoạn:** M0.6 — chuẩn hóa quy trình, đang chờ owner review.
- **Repository:** `https://github.com/lebaokhang123/aura_meme`; GitHub đã có nhánh `dev` và `main` với lịch sử tách biệt; `main` là prototype/lab cũ, **không merge tự động**.
- **Đã có trên `dev` khi kiểm tra:** M0.1 Sitemap, M0.2 Use Case, M0.3 DBML/Database Design, M0.4 Architecture, M0.5 API Contract/Data Flow.
- **Nền kỹ thuật đã thiết kế:** React/Vite/TypeScript → FastAPI modular monolith → PostgreSQL; Docker/AWS/CI/CD theo mốc sau, **chưa coi là đã triển khai**.
- **M0.6 gửi review:** `RULES.md`, `TASKS.md`, `HANDOFF.md`; **chưa xác minh đã commit/push**. Trạng thái máy local cần `git status` để xác nhận.
- **Vướng mắc/ràng buộc:** chưa duyệt toàn bộ Open Decisions ở DBML/spec; chỉ khóa ngay trước task phụ thuộc. Không đưa bản demo payment/XP/case lên production như đã kiểm thử.
- **Bước kế tiếp sau khi M0.6 được duyệt:** `M1.1` — audit code prototype, kiểm tra branch/working tree và xác nhận thành phần UI giữ lại trước khi khởi tạo app thực.
- **Quy trình:** Codex hỗ trợ có giới hạn → chạy test thực → mentor/owner review → owner tự commit/push. Commit tiếng Việt, không thay lịch sử `main`/`dev`.

> File này là **trạng thái mới nhất**, không tích lũy nhật ký buổi làm việc. Sau mỗi phiên chỉ cập nhật 5–10 dòng trên.
