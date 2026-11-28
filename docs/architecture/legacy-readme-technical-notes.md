# Ghi chú Kỹ thuật & Nghiệm thu Baseline (Lưu trữ từ README cũ)

Tài liệu này lưu trữ toàn bộ các ghi chú kỹ thuật nội bộ, chi tiết kiểm chứng gate và hiện trạng tích hợp từng được ghi lại trong `README.md` gốc trước khi hoàn thiện trang giới thiệu dự án chính thức.

---

## 1. Hotfix & Nghiệm thu Task 1–5

- Gate local Task 1–5 và hotfix thanh toán đã được kiểm chứng trên cây tích hợp `e541138`. Chi tiết phân biệt lượt full, retry, PostgreSQL cô lập và phần PayPal Sandbox tại `docs/tasks/premium-sandbox-task5.md`.
- Bản nghiệm thu xuất phát từ Task 5 `682d247`. Baseline GitHub `dev` là `eacfa7d`.
- Kiến trúc: Frontend React 19 / Vite 7 JSX, backend FastAPI modular monolith, cơ sở dữ liệu PostgreSQL.
- Tính năng: Hộp thư thông báo cá nhân, chính sách VI/EN tại `/privacy.html`, cấp độ và chức danh công khai theo tác giả. Admin quản lý vòng đời thông báo. Premium Sandbox bán gói Plus (5 USD/30 ngày) và Prime (50 USD/365 ngày), không tự gia hạn.

---

## 2. Kiến trúc Frontend & API Mode

- React 19, JavaScript/JSX, Vite 7; 14 màn hình Guest/User/Auth trên 8 route.
- Giao diện Responsive, hỗ trợ Dark/Light mode, đa ngôn ngữ VI/EN; Header/Footer dùng chung.
- Home/Explore: Danh mục (category), tìm kiếm (search), bộ lọc New/Hot; số lượng bài viết đếm theo cơ sở dữ liệu thực tế.
- Tương tác API thực: Feed, phân trang, tạo/chỉnh sửa/xóa bài đăng, tải lên ảnh PNG/JPEG/GIF/WebP, 6 loại biểu cảm (reactions) bài viết và bình luận, emoji, cùng hệ thống kiểm duyệt bài viết có phân quyền RBAC và ghi nhật ký kiểm toán (Admin Audit Log).
- Xác thực (Auth): Cookie HttpOnly và cơ chế chống giả mạo CSRF; danh tính và quyền hạn người dùng được xác thực từ máy chủ qua endpoint `/users/me`.

---

## 3. Game Mechanics V1 — Khôi phục Bảo Khố MVP & Đồng bộ

- **Cảnh giới & Cấp độ:** 10 cảnh giới × 10 Level; XP thăng cấp `10 + Level` từ Lv.1 đến Lv.100. Điểm danh nhận +15 Aura gốc/ngày vào lúc 07:00 (giờ Việt Nam), giới hạn earned XP mạng xã hội đạt tối đa 135/ngày. Xếp hạng (Rank) tính theo Aura gốc.
- **Hai rương Bảo Khố (Vault V1):**
  - **Rương Background:** 5 background thuộc 5 phẩm cấp D/C/B/A/S.
  - **Rương Meme:** 70 avatar meme (D=25, C=18, B=14, A=8, S=5), đã duyệt bản quyền nội bộ.
  - **Tỷ lệ mở rương:** D=68.9% (6890 bps), C=20.0% (2000 bps), B=10.0% (1000 bps), A=1.0% (100 bps), S=0.1% (10 bps).
  - **Quy tắc EXP mở rương:** Mỗi lần mở rương thành công nhận +2 EXP (tối đa 100 lượt có thưởng/ngày, trần 200 EXP/ngày, độc lập với trần Social). Từ lượt 101 trở đi vẫn nhận vật phẩm nhưng không cộng thêm EXP. Cơ chế Idempotency-Key chống cấp thưởng trùng.
- **Fail-closed Catalog Rights (`app/catalog_rights.py`):** Bảo vệ asset demo nghiêm ngặt; chỉ kích hoạt khi có đủ các cờ môi trường hợp lệ trên host loopback cục bộ.

---

## 4. Kiểm thử & CI/CD Pipeline

- Workflow GitHub Actions (`.github/workflows/ci.yml`) kích hoạt khi mở PR hoặc push vào `main`/`dev`.
- Backend non-DB test: Kiểm thử logic không chạm cơ sở dữ liệu ngoài.
- Frontend build & unit test: Đảm bảo mã nguồn React biên dịch sạch và vượt qua các bài kiểm tra giao diện.
- Browser regression test: Kiểm thử tự động với Playwright headless Chromium.
- Nghiêm cấm can thiệp hoặc tự ý chạy migration phá hủy trên cơ sở dữ liệu production/demo.

---

## 5. Chuẩn bị phát hành MVP v1.0.0 (`chore/official-release-v1`)

- Mã nguồn phát hành dưới giấy phép **MIT License** (`Copyright (c) 2026 Lê Bảo Khang (lebaokhang123)`).
- `.gitattributes` loại trừ `AGENTS.md`, `run.bat` và `run_qa.bat` khỏi Git release archives (`export-ignore`) nhưng vẫn giữ đầy đủ trong workspace phát triển.
- Lưu ý phạm vi license bên thứ ba: `PyMuPDF==2.1` dùng AGPL-3.0 / Artifex Commercial License; `psycopg`/`psycopg-binary` dùng LGPL-3.0-only; asset/logo minh họa tuân theo phạm vi ghi nhận tại `frontend/ASSET_SOURCES.md` và `frontend/public/third-party-notices.txt`.
