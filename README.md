# AuraMeme

<p align="center">
  <img src="frontend/public/assets/brand/favicon-64.png" alt="AuraMeme Logo" width="64" height="64" />
</p>

<p align="center">
  <strong>Nền tảng mạng xã hội chia sẻ meme & blog văn hóa số</strong>
</p>

---

## 1. Giới thiệu dự án

**AuraMeme** là nền tảng mạng xã hội đa phương tiện kết hợp cơ chế trò chơi hóa (gamification), được xây dựng với mục tiêu mang đến một không gian trực tuyến lành mạnh, sáng tạo và văn minh dành cho cộng đồng yêu thích meme và văn hóa số.

Dự án cung cấp trải nghiệm tương tác phong phú, gắn kết cộng đồng thông qua các tính năng cốt lõi:

- **Chia sẻ & Tương tác Meme:** Đăng tải hình ảnh meme chất lượng cao, bài viết blog, thảo luận, bình luận và thả các biểu cảm cảm xúc phong phú.
- **Cơ chế Aura & EXP:** Người dùng tích lũy điểm Bá Khí (Aura) và EXP thông qua các hoạt động tích cực như điểm danh hàng ngày, tương tác cộng đồng và đóng góp nội dung giá trị.
- **Hệ thống Cảnh giới & Cấp độ (Level):** Hệ thống 10 Cảnh giới với 100 cấp độ (Level) mang đậm dấu ấn huyền huyễn/tu tiên, đem lại trải nghiệm thăng tiến hào hứng cho người dùng.
- **Bảng xếp hạng (Rank):** Vinh danh những thành viên có cống hiến nổi bật và tích lũy Aura cao nhất trong cộng đồng.
- **Bảo Khố (Vault):** Tính năng vòng quay may mắn cho phép người dùng mở các rương quà để sưu tầm những avatar meme độc đáo và hình nền thẻ cá nhân lung linh thuộc các phẩm cấp từ D đến S.

---

## 2. Thành viên thực hiện

Dự án được nghiên cứu và phát triển bởi:

- **Lê Bảo Khang** — Trưởng nhóm / Phát triển hệ thống
- **Phan Trung Kiên** — Thành viên / Phát triển hệ thống

---

## 3. Cách chạy dự án

### Yêu cầu môi trường

Để khởi chạy dự án trên máy tính cá nhân, bạn cần chuẩn bị:

- **Hệ điều hành:** Windows 10/11 (để sử dụng tệp lệnh `run.bat`).
- **Node.js:** Phiên bản `>= 22.12.0`.
- **Python:** Phiên bản `>= 3.12`.
- **Cơ sở dữ liệu:** PostgreSQL 15 trở lên.

### Khởi chạy nhanh

1. **Cài đặt các gói phụ thuộc:**
   - **Frontend:**
     ```powershell
     cd frontend
     npm ci
     cd ..
     ```
   - **Backend:**
     ```powershell
     cd backend
     python -m venv .venv
     .\.venv\Scripts\Activate.ps1
     pip install -r requirements-ci.txt
     pip install -e . --no-deps
     cd ..
     ```

2. **Chạy ứng dụng:**
   Dự án đã được tích hợp sẵn tệp lệnh tự động hóa, bạn chỉ cần chạy một trong hai câu lệnh sau tại thư mục gốc:

   - **Chế độ Demo:**
     ```powershell
     .\run.bat demo
     ```
   - **Chế độ Phát triển (Dev):**
     ```powershell
     .\run.bat dev
     ```

3. **Truy cập ứng dụng:**
   Sau khi các tiến trình khởi động thành công, mở trình duyệt web và truy cập theo đường dẫn:
   ```
   http://localhost:5173
   ```

---

## 4. Lời cảm ơn

Chúng tôi xin gửi lời cảm ơn chân thành đến Quý Thầy Cô và các cố vấn kỹ thuật đã tận tình hướng dẫn, đóng góp những ý kiến quý báu trong suốt quá trình hoàn thiện dự án. Đồng thời, nhóm cũng gửi lời cảm ơn đến gia đình, bạn bè và toàn thể cộng đồng đã luôn đồng hành, thử nghiệm và ủng hộ AuraMeme.
