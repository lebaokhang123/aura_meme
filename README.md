# AuraMeme

AuraMeme là đồ án web cộng đồng chia sẻ meme. Frontend chính hiện là bản Stitch React đã được Owner duyệt; backend FastAPI/PostgreSQL được giữ riêng để phát triển tiếp.

## Frontend hiện tại

- React 19, JavaScript/JSX, Vite 7; 14 màn Guest/User/Auth trên 8 route.
- Responsive, dark/light, VI/EN; header/footer dùng chung.
- Home/Explore: category, search, New/Hot; số danh mục đếm theo bài hiện có.
- Demo tạo bài text/PNG/JPEG/GIF, reaction, bình luận, chèn emoji, xóa có xác nhận và chia sẻ đúng bài.
- Dữ liệu tương tác và file lưu trong IndexedDB theo browser/origin. Frontend chưa kết nối API; đăng nhập mẫu không phải xác thực thật.
- Rank/Vault/Contact và các chức năng tương lai có trạng thái demo/bảo trì, không phát thưởng hoặc thanh toán thật.

## Chạy demo

Cần Node.js >=22.12.0 và npm. Không cần khởi động backend hoặc database để xem frontend.

```powershell
cd frontend
npm ci
npm run dev
```

Mở http://127.0.0.1:5173. Đăng nhập bằng Khang_dev@example.com, Kien_dev@example.com hoặc Gigachad@example.com với mật khẩu demo bất kỳ; ứng dụng không lưu mật khẩu.

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
| [backend/](backend/) | FastAPI modular monolith, Alembic, PostgreSQL; chưa tích hợp vào frontend demo |
| [docs/design/](docs/design/) | Sitemap, use case và thiết kế dữ liệu |
| [docs/architecture/](docs/architecture/) | Kiến trúc và các quyết định thiết kế |
| [docs/api/](docs/api/) | Hợp đồng API và data flow; một phần phản ánh runtime legacy |

Các thay đổi backend local chưa thuộc checkpoint frontend này. Không tự migrate/seed database development. Code frontend cũ có thể phục hồi qua Git history; backup/evidence nội bộ không được đưa lên GitHub.

## Game Mechanics V1 — đặc tả, chưa bật runtime

Owner đã chốt 10 cảnh giới ×10 Level; XP lên cấp ` 10 + Level ` từ Lv.1–100, điểm danh +15 Aura gốc/ngày tại07:00 Việt Nam và earned XP cap135/ngày. Rank tính Aura gốc. Hai rương Meme/Ảnh Bìa quay miễn phí, có cooldown, nhận trùng; odds D68,9/C20/B10/A1/S0,1 và không cộng XP khi mở hòm. Plus30 ngày XP×2, Prime365 ngày XP×3; VNPAY Sandbox, chưa bán tiền thật. Ví Khí Vận/generator legacy đang hoãn. Cần task API/schema/test tương ứng trước khi tích hợp.

## Phạm vi kiểm chứng

Frontend có unit tests và browser regression cho14màn, Guest/3user demo,375/768/1440px, theme/language, filter/history và lưu trữ lỗi/reload. Đây là demo frontend để review UI/logic; chưa chứng minh triển khai production hoặc vận hành backend/DevOps.

Nguồn/license và xác nhận của Owner đối với asset được ghi riêng trong [asset ledger](frontend/ASSET_SOURCES.md); license mã nguồn không tự áp dụng cho mọi ảnh bên thứ ba.
