# AuraMeme — Project Tasks

**Nguồn tiến độ:** file này là bảng công việc của sản phẩm; cập nhật khi thực hiện và review từng task.  
**Trạng thái:** `TODO` → `DOING` → `REVIEW` → `DONE`; dùng `BLOCKED` khi cần quyết định hoặc kết quả bên ngoài.  
**Ưu tiên:** P0 = yêu cầu blog học phần; P1 = AuraMeme portfolio; P2 = mở rộng. Chỉ có **một task chủ động** tại một thời điểm.

## 1. Giai đoạn thiết kế M0

| ID | Kết quả | Trạng thái | Bằng chứng |
|---|---|---|---|
| M0.1 | Sitemap | DONE | `docs/design/01-sitemap-*.drawio` |
| M0.2 | Use Case | DONE | `docs/design/02-usecase-*.drawio` |
| M0.3 | ERD DBML và đặc tả PostgreSQL | DONE (design) | `docs/design/03-database.dbml`, `03-database-design.md` |
| M0.4 | System Architecture | DONE (design) | `docs/architecture/04-*` |
| M0.5 | API Contract và Data Flow | DONE (design) | `docs/api/05-*` |
| **M0.6** | Quy tắc phát triển, backlog và handoff | **REVIEW** | `RULES.md`, `TASKS.md`, `HANDOFF.md` |

Các nhãn `DONE (design)` xác nhận có tài liệu để triển khai, **không** có nghĩa API/DB/AWS đã được chạy hoặc kiểm thử runtime.

## 2. Backlog triển khai

| ID | Phase | Kết quả cần đạt / tiêu chí nghiệm thu tóm tắt | Trạng thái |
|---|---|---|---|
| **M1.1** | P0 | Kiểm tra repo `dev` và bản prototype `main`, xác định giao diện giữ lại, khóa cấu trúc thư mục thật; không hợp nhất lịch sử | TODO |
| M1.2 | P0 | Frontend Vite/React/TS chạy local; giữ design được duyệt, build thành công | TODO |
| M1.3 | P0 | FastAPI `/health`, cấu hình môi trường và PostgreSQL kết nối an toàn; chạy test smoke | TODO |
| M1.4 | P0 | Alembic migration P0 đầu tiên, upgrade/downgrade trên DB thử nghiệm; đối chiếu DBML | TODO |
| M2.1 | P0 | Register/login/logout, session cookie và CSRF; lỗi input và login giả bị từ chối | TODO |
| M2.2 | P0 | Profile, đổi mật khẩu, USER/ADMIN + kiểm quyền; test user không leo quyền | TODO |
| M3.1 | P0 | Category/post CRUD theo owner; list/detail/search/filter/sort/pagination từ DB thật | TODO |
| M3.2 | P0 | Media upload an toàn (tối đa một ảnh/post) và comment; test ownership/file sai | TODO |
| M4.1 | P0 | Admin quản lý users, roles, posts, categories; audit và authorization tests | TODO |
| M4.2 | P0 | Contact, About/Team thật; chức năng P0 theo đề tài chạy end-to-end | TODO |
| M5.1 | P0/P1 | Tích hợp/polish UI; responsive 375/768/1440, accessibility, bỏ mock đang giả hoạt động | TODO |
| M6.1 | P1 | Aura base/bonus, policy, leaderboard; test anti-farm, idempotency, concurrent XP | TODO |
| M6.2 | P1 | Daily check-in/streak mốc 07:00 VN; ledger wallet và test biên ngày | TODO |
| M7.1 | P1 | Catalog có kiểm quyền asset; inventory/equipment và khung cấp độ | TODO |
| M7.2 | P1 | Rương chung + odds version + CSPRNG; Monte Carlo và test debit/grant nguyên tử | TODO |
| M8.1 | P0 delivery | Docker Compose + Nginx local; fresh-clone smoke và migration | TODO |
| M9.1 | P0 delivery | AWS manual, domain/HTTPS, DB private, budget và off-host backup/restore | TODO |
| M10.1 | DevOps | CI/CD lint/test/build/deploy, image SHA, health check và rollback | TODO |
| M11.1 | DevOps | Monitoring, logs, alert, security review và restore drill có chứng cứ | TODO |
| M12.1 | DevOps | Terraform hóa hạ tầng đang chạy; fmt/validate/plan và kiểm soát state | TODO |
| M13.1 | Delivery | Báo cáo, slides, demo/video, release và câu chuyện CV phỏng vấn | TODO |
| M14.1 | P2 / optional | Rương tier, generator 3 ô, Aura Plus/Prime, sandbox payment sau MVP | TODO |

**Thứ tự:** Hoàn thành P0 của M1–M5 trước P1; nếu hạn nộp môn gần, đưa M8–M9 lên ngay sau P0 core. Không lấy M6/M7 làm blocker của việc deploy blog. Tách task thành bước con trong phiên đang làm, không tạo file task mới chỉ để đếm tiến độ.

## 3. Task đang chuẩn bị: M1.1 — Repo & prototype baseline

**Mục tiêu:** Biết chính xác code nào sẽ được giữ và điểm xuất phát nào an toàn; chưa tự động chép ASP.NET lab sang backend mới.

**Input:** `origin/dev`, `origin/main`, prototype clone riêng tại `D:\Big\du_an_lon\aura_meme_prototype` (nếu còn), sitemap, master plan và kiến trúc M0.4.

**Thực hiện:**

1. Trên repo làm việc, kiểm `git status`, `git branch -avv`, `git remote -v`; không reset hoặc merge nhánh độc lập.
2. Kiểm tra UI trong bản prototype: trang thực có, component/animation reusable, dependency, build scripts. Phân loại **giữ / chỉnh / bỏ** theo yêu cầu M0.1–M0.5.
3. Chọn cấu trúc tối thiểu `frontend/` và `backend/` khi đến task tạo code. Không tự mang phần bài thực hành ASP.NET vào backend FastAPI.
4. Chạy build prototype **nếu đủ môi trường và source**; lưu lệnh/kết quả thực (không ghi PASS nếu chưa chạy).

**PASS khi:** owner duyệt danh sách thành phần giữ lại + biết rõ điểm xuất phát Git + có phạm vi thực thi M1.2; chưa cần triển khai backend/DB tại M1.1.

## 4. Các quyết định nghiệp vụ phải khóa đúng lúc

| Nhóm | Khóa trước khi | Căn cứ |
|---|---|---|
| Auth/email/session/reset | M2.1 | `03-database-design.md`, `05-api-design.md` |
| Upload limits/retention | M3.2 | `03-database-design.md` |
| XP/caps/rank/reversal | M6.1 | `03-database-design.md` |
| Daily reward/weekly icon | M6.2 | `03-database-design.md` |
| Odds, miễn phí, giá rương, duplicates | M7.2 | `03-database-design.md` |
| Generator rate/claim | M14.1 | `03-database-design.md` |
| VIP/webhook/provider/refund | M14.1 | `03-database-design.md` |
| AWS budget/backup | M9.1 | `04-architecture-decisions.md` |

Tài liệu chưa khóa một con số thì không tự seed “production”. Mỗi thay đổi quy tắc kéo theo cập nhật tài liệu và test của module liên quan.

## 5. Quy tắc cập nhật

- Khi bắt đầu: chuyển đúng task thành `DOING`, cập nhật `HANDOFF.md`.
- Có code/sơ đồ xong: `REVIEW`; chỉ thành `DONE` sau **test thực tế + owner review + commit**.
- Blocker ghi ngay tại task, không mở rộng backlog để che lấp lỗi chưa sửa.
- Ghi link commit/PR hoặc bằng chứng test **khi có thật**, không ghi thời gian hoặc trạng thái giả.
