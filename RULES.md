# AuraMeme — Quy chuẩn phát triển

**Mốc:** M0.6 · **Áp dụng cho:** repository `lebaokhang123/aura_meme`, nhánh sản phẩm `dev`.

## 1. Nguyên tắc

- Phát triển **một sản phẩm React/Vite/TypeScript + FastAPI + PostgreSQL** theo mô hình modular monolith. Mỗi module là phần của cùng backend, không phải microservice.
- **P0:** blog và chức năng theo đề tài. **P1:** Aura, Rank, Streak, Khí Vận, Bảo Khố cơ bản. **P2:** generator ba ô, VIP và thanh toán thử nghiệm. Chỉ triển khai đúng phase cần thiết; DevOps làm theo các mốc trong `TASKS.md`.
- Mỗi công việc nhỏ có **đầu ra chạy được, phép kiểm chứng, review**. Không đánh dấu hoàn thành chỉ dựa trên mô tả của AI.
- Không tự ý thay đổi nghiệp vụ đã duyệt. Trường hợp còn quyết định mở, ghi vào task phụ thuộc thay vì âm thầm lựa chọn giá, xác suất hay quyền.
- Không dựng cả hệ thống/thư mục rỗng trước thời điểm thực sự sử dụng. Không thêm microservices, Kubernetes, message queue hay thư viện lớn chỉ để “cho chuyên nghiệp”.

## 2. Nguồn thiết kế

| Nội dung | Nguồn chính |
|---|---|
| Yêu cầu, phạm vi và mốc sản phẩm | `AURA_MEME_MASTER_PLAN_V3.md` (tài liệu nguồn tại máy chủ dự án, chỉ đưa vào Git khi owner duyệt) và đề tài môn học |
| Trang và vai trò | `docs/design/01-sitemap-*.drawio`, `02-usecase-*.drawio` |
| Cấu trúc dữ liệu | `docs/design/03-database.dbml` |
| Ràng buộc DB và bất biến nghiệp vụ | `docs/design/03-database-design.md` |
| Kiến trúc | `docs/architecture/04-system-architecture.drawio`, `04-architecture-decisions.md` |
| Giao tiếp frontend ↔ backend | `docs/api/05-openapi.yaml`, `05-api-design.md`, `05-data-flows.drawio` |
| Tiến độ và bàn giao | `TASKS.md`, `HANDOFF.md` |

**Quy tắc xung đột:** không tự suy diễn rằng DBML, OpenAPI và Markdown luôn nhất quán; nêu mâu thuẫn cho owner xem, cập nhật các tài liệu bị ảnh hưởng trong cùng task. Tên M0.1–M0.6 là **các bước thiết kế của giai đoạn M0** trong lộ trình học hiện tại; các mốc M1–M14 tiếp tục theo bảng triển khai của Master Plan V3.

## 3. Git và nhánh

**Trạng thái gốc khi chốt quy trình:** `main` lưu prototype/lab cũ; `dev` là dòng lịch sử mới, độc lập, dành cho sản phẩm thực. Không mặc định mở PR/merge `dev → main`. Việc đổi default branch hoặc lưu trữ `main` là quyết định release riêng của owner.

- Thay đổi tài liệu rất nhỏ: được phép commit trực tiếp lên `dev` sau khi tự review.
- Thay đổi code/logic: tạo `feat/<scope>`, `fix/<scope>`, `docs/<scope>` hoặc `infra/<scope>` **từ `dev`**, review rồi đưa về `dev` (PR khuyến khích khi code thay đổi đáng kể).
- Khi có CI, dùng kết quả check thực tế trước khi merge; nếu làm việc nhiều người, cân nhắc bảo vệ `dev` bằng branch rules. Không bật quy tắc khiến người làm solo bị khóa khỏi quy trình.
- Commit bằng **tiếng Việt**, ngắn và phản ánh phạm vi; ví dụ `feat: bổ sung API đăng nhập`, `test: kiểm tra phân quyền quản trị`, `docs: chuẩn hóa quy trình phát triển M0.6`.
- Chỉ stage file thuộc task. Tránh `git add .` khi chưa kiểm tất cả file; cấm đưa `.env`, token, API key, database dump, dữ liệu người dùng hay asset chưa có quyền phân phối lên Git.
- **Không** `push --force`, `reset --hard`, `clean -fd`, xóa/ghi đè `.git` hoặc thay lịch sử `main`/`dev` khi chưa có kế hoạch và owner phê duyệt.

### Bắt đầu một nhánh code (máy đã có clone hợp lệ)

```powershell
git status
git fetch origin
git switch dev
git pull --ff-only origin dev
git switch -c feat/m1-foundation
```

Nếu chưa có nhánh local `dev`: `git switch --track -c dev origin/dev`, sau khi chắc chắn working tree sạch. Nếu `git pull --ff-only` thất bại, **dừng và xem lịch sử/working tree**, không tự rebase/reset. Khi hoàn tất code: stage file cụ thể, xem `git diff --cached`, commit, push feature branch và tạo PR vào `dev` nếu phù hợp.

## 4. Quy trình một task

1. **Chọn một task** trong `TASKS.md`, xác nhận điều kiện bắt đầu và file cần chạm.
2. **Đọc đúng nguồn**: code hiện hành, spec liên quan, tài liệu API/DB và test liên quan. Đầu ra phải nối được vào chức năng user thực dùng.
3. **Làm ít nhưng đủ:** backend → migration → API → UI → test tùy vertical slice; không cố hoàn thành nhiều mốc trong một lần.
4. **Tự kiểm chứng:** ghi lệnh đã chạy và kết quả thật. Có test âm tính về quyền/validation/IDOR khi chạm API; có test transaction/concurrency khi chạm Aura/Wallet/Vault.
5. **Review diff:** đối chiếu scope, bảo mật, UI hiện có, tài liệu thay đổi; owner duyệt trước khi commit.
6. **Commit & cập nhật:** commit tiếng Việt, cập nhật trạng thái `TASKS.md` và bàn giao ngắn trong `HANDOFF.md`.

### Definition of Done

- Đầu ra đúng yêu cầu, không còn nút/endpoint giả được mô tả là hoạt động.
- Bằng chứng kiểm chứng **thực chạy**; lỗi được sửa và chạy lại. Test chưa có/chưa chạy phải ghi rõ `NOT TESTED`.
- Quyền truy cập, validation, secrets, dữ liệu người dùng và migration được xem xét đúng phần thay đổi.
- Chỉ file thuộc phạm vi đã review; không gộp refactor phụ, không làm mất UI prototype tốt đã được chọn giữ.
- `TASKS.md` phản ánh trạng thái hiện tại; `HANDOFF.md` đủ để tiếp tục trên máy hoặc phiên chat khác.

## 5. Hợp tác với Codex và AI

Mỗi yêu cầu Codex phải nêu: **mục tiêu / nguồn cần đọc / đường dẫn được phép sửa / phần không được làm / tiêu chí test / cách báo cáo**.

- Yêu cầu Codex **đọc code hiện có trước khi sửa**, đưa ra phạm vi và cách kiểm chứng. Với thay đổi lớn, tách thành nhiều task.
- Cho phép Codex viết boilerplate, test, migration hoặc sửa lỗi trong phạm vi đã duyệt; **không** tự stage, commit, push, reset, xóa, deploy hay tạo chi phí cloud.
- Báo cáo cuối yêu cầu: file đã đổi, `git diff --stat`, lệnh kiểm chứng, kết quả PASS/FAIL thực tế, rủi ro còn lại. Tránh ghi log dài vào tài liệu sản phẩm.
- Mentor phản biện và owner là người quyết định; không xem thông báo “done” của Codex là bằng chứng test.

## 6. Bảo mật và tài sản

- Auth/role/owner luôn kiểm server; cookie auth cần xử lý CSRF; ORM bind parameters, sort/filter allowlist; mật khẩu hash an toàn; upload kiểm cả chữ ký file, MIME, kích thước và ownership.
- Aura/Khí Vận dùng ledger, business-key idempotency, transaction và row locking. Mốc check-in **07:00 Asia/Ho_Chi_Minh**; Rank/odds dựa vào Aura gốc; VIP chỉ tăng Aura bonus cho level/cosmetic.
- Chỉ đưa ảnh/âm thanh/cosmetic có quyền sử dụng rõ ràng vào repo/release. Việc chưa xác minh quyền là blocker của asset đó, không là lý do sao chép không kiểm soát.
- AWS, webhook thanh toán, backup/restore, CI/CD, Terraform **chỉ triển khai ở milestone tương ứng**, kèm kiểm thử; không tuyên bố hạ tầng đang chạy từ sơ đồ kiến trúc.

## 7. Tài liệu tham chiếu

- GitHub — Protected branches: https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-protected-branches
- GitHub — Removing sensitive data: https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/removing-sensitive-data-from-a-repository
- PostgreSQL — Constraints: https://www.postgresql.org/docs/current/ddl-constraints.html
- OWASP — API Security Top 10: https://owasp.org/API-Security/
