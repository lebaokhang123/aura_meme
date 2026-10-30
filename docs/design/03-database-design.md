# AuraMeme — Database Design & Data Dictionary

**Mốc:** M0.3 · **Cơ sở dữ liệu:** PostgreSQL · **Kiến trúc:** một database, bảy phân hệ logic.

Tài liệu này quy định cấu trúc dữ liệu dự kiến của AuraMeme, đồng bộ với `03-erd-aurameme.drawio`. Mọi bảng đều có khai báo kiểu, khóa và quan hệ. Đây là **đặc tả thiết kế**, không phải bằng chứng rằng migration hoặc hệ thống đã được triển khai.

## 1. Kiến trúc dữ liệu

| Phân hệ | Mục đích | Giai đoạn |
|---|---|---|
| 01 Account/Auth | Danh tính, hồ sơ, quyền hạn, phiên đăng nhập | P0 |
| 02 Blog/Media | Bài viết, danh mục, bình luận, reaction, ảnh, liên hệ | P0 / P1 |
| 03 Aura/Streak/Wallet | Tích điểm, lịch sử thưởng, điểm danh, Khí Vận | P1 |
| 04 Vault/Inventory | Catalog, rương, tỷ lệ, tài sản, trang bị | P1 |
| 05 Generator | Ba ô sinh Khí Vận | P2 |
| 06 Membership/Payment | Aura Plus/Prime, trạng thái gói và thanh toán | P2 |
| 07 Admin/Audit | Báo cáo vi phạm, nhật ký quản trị | P0 / P1 |

**P0** = phần blog phục vụ môn học; **P1** = đặc trưng AuraMeme; **P2** = chức năng mở rộng. Không tạo toàn bộ 35 bảng ngay khi bắt đầu code. Mỗi phase chỉ tạo migration cho những bảng được sử dụng.

### Quy tắc đã thống nhất

- Một tài khoản `users` có thể mang role `USER` hoặc `ADMIN`; không tách database riêng cho admin.
- V1: mỗi bài viết thuộc một danh mục; tối đa một ảnh JPG/PNG/WebP/GIF.
- Aura gốc dùng cho Rank và tỷ lệ rương; Aura Plus ×2 / Prime ×3 chỉ tăng điểm thưởng để lên level và nhận khung nhanh hơn.
- Điểm danh tính theo ngày mới bắt đầu **07:00, Asia/Ho_Chi_Minh**; timestamp sự kiện lưu dạng UTC.
- Khí Vận là tiền ảo nội bộ, không chuyển khoản, không rút tiền.
- Gói thanh toán mới ở mức thiết kế; không mặc định có hệ thống thanh toán thật.

## 2. Quy ước

| Ký hiệu | Ý nghĩa |
|---|---|
| PK | Primary Key — khóa chính |
| FK | Foreign Key — khóa ngoại |
| UQ | Unique — ràng buộc duy nhất |
| NN | NOT NULL — bắt buộc có dữ liệu |
| NULL | Thuộc tính có thể chưa có giá trị |
| 1:0..1 | Một bản ghi có tối đa một bản ghi liên quan |
| 1:N | Một bản ghi liên kết nhiều bản ghi |

- Tên bảng/cột dùng `snake_case`, ID thường là `uuid`; thời gian sự kiện dùng `timestamptz`.
- `UQ1`, `UQ2` trên sơ đồ chỉ **nhóm cột của một khóa**, không phải mọi cột đều unique riêng.
- Các dòng FK trong tài liệu là định nghĩa chi tiết. Sơ đồ trực quan chỉ nối quan hệ nội bộ trọng yếu để không bị rối; các FK liên phân hệ nằm trong mục “Tham chiếu ngoại vi” trên mỗi tab.
- Không có `ON DELETE CASCADE` cho dữ liệu nghiệp vụ cần audit; chính sách xóa/ẩn thực hiện tại service.
- Ràng buộc phụ thuộc nhiều bảng (tổng tỷ lệ = 100%, số dư, quyền sở hữu, không thưởng hai lần) phải được bảo vệ bằng transaction/service và kiểm thử, không chỉ dựa vào FK/CHECK.

## 3. Danh mục bảng và thuộc tính

## 01 Account/Auth

### `users` [P0]

| Trường | PostgreSQL | NULL | Vai trò / ý nghĩa |
|---|---|---|---|
| `id` | `uuid` | NN | PK |
| `username` | `text` | NN | Trim + ASCII lowercase, 3–32 ký tự [a-z0-9_]; UQ |
| `email` | `text` | NN | Trim + lowercase theo chính sách email đề xuất; UQ |
| `password_hash` | `text` | NN | Argon2id; không lưu mật khẩu plaintext |
| `status` | `text` | NN | active / locked / deleted |
| `created_at` | `timestamptz` | NN |  |
| `updated_at` | `timestamptz` | NN |  |
| `deleted_at` | `timestamptz` | NULL | NULL khi chưa soft delete |

- PK: `(id)`
- UQ: `(username)`
- UQ: `(email)`
- CHECK / validation: username/email đã trim, lowercase, không rỗng; username đúng allowlist; status IN (active,locked,deleted); (status=deleted) = (deleted_at IS NOT NULL).
- Quy tắc nghiệp vụ: Thiết kế chuẩn hóa email case-insensitive toàn chuỗi; cần owner duyệt trước auth. Giữ unique khi soft delete để tránh chiếm lại danh tính. User bị khóa bị chặn đăng nhập và thao tác nhạy cảm tại server.

### `roles` [P0]

| Trường | PostgreSQL | NULL | Vai trò / ý nghĩa |
|---|---|---|---|
| `id` | `uuid` | NN | PK |
| `code` | `text` | NN | USER / ADMIN |
| `description` | `text` | NN |  |

- PK: `(id)`
- UQ: `(code)`
- CHECK / validation: code IN (USER,ADMIN).
- Quy tắc nghiệp vụ: Quy tắc đã thống nhất: Admin là role của user. Không có bảng tài khoản admin riêng.

### `user_roles` [P0]

| Trường | PostgreSQL | NULL | Vai trò / ý nghĩa |
|---|---|---|---|
| `user_id` | `uuid` | NN | PK; FK |
| `role_id` | `uuid` | NN | PK; FK |
| `granted_at` | `timestamptz` | NN |  |

- PK: `(user_id,role_id)`
- FK: `(user_id) -> users(id)`
- FK: `(role_id) -> roles(id)`
- Quy tắc nghiệp vụ: Bảng nối N:N. Cấp/thu hồi role ghi admin_audit_logs trong cùng transaction; bảo vệ admin cuối cùng tại service.

### `profiles` [P0]

| Trường | PostgreSQL | NULL | Vai trò / ý nghĩa |
|---|---|---|---|
| `user_id` | `uuid` | NN | PK; FK |
| `display_name` | `text` | NN |  |
| `birth_year` | `smallint` | NULL | Chưa cung cấp; dùng năm sinh đúng đề bài, không buộc thu ngày sinh |
| `address` | `text` | NULL | Chưa cung cấp; thông tin riêng tư |
| `phone` | `text` | NULL | Chưa cung cấp; giữ dạng chuỗi |
| `bio` | `text` | NULL | Chưa có giới thiệu |
| `avatar_media_id` | `uuid` | NULL | FK; Chưa chọn ảnh upload |
| `cover_media_id` | `uuid` | NULL | FK; Chưa chọn ảnh bìa |
| `show_streak` | `boolean` | NN | P1, mặc định false |
| `updated_at` | `timestamptz` | NN |  |

- PK: `(user_id)`
- FK: `(user_id) -> users(id)`
- FK: `(user_id,avatar_media_id) -> media_uploads(owner_id,id)` — MATCH SIMPLE: media NULL có chủ đích
- FK: `(user_id,cover_media_id) -> media_uploads(owner_id,id)` — MATCH SIMPLE: media NULL có chủ đích
- CHECK / validation: birth_year IS NULL OR birth_year BETWEEN 1900 AND 9999.
- Quy tắc nghiệp vụ: users 1:0..1 profiles; tạo profile cùng đăng ký để service bảo đảm 1:1 khi cần. Server kiểm năm sinh không ở tương lai; không dùng now() trong CHECK. Profile công khai không xuất email/phone/address/birth_year nếu chưa có consent. Ảnh phải thuộc user, trạng thái ready; composite FK bên dưới.

### `auth_sessions` [P0]

| Trường | PostgreSQL | NULL | Vai trò / ý nghĩa |
|---|---|---|---|
| `id` | `uuid` | NN | PK |
| `user_id` | `uuid` | NN | FK |
| `token_hash` | `text` | NN | Chỉ digest token ngẫu nhiên entropy cao |
| `created_at` | `timestamptz` | NN |  |
| `expires_at` | `timestamptz` | NN |  |
| `revoked_at` | `timestamptz` | NULL | NULL khi chưa revoke |

- PK: `(id)`
- UQ: `(token_hash)`
- FK: `(user_id) -> users(id)`
- CHECK / validation: expires_at > created_at; revoked_at IS NULL OR revoked_at >= created_at.
- Quy tắc nghiệp vụ: Thiết kế P0: email/password + opaque session cookie HttpOnly/Secure/SameSite, CSRF cho mutation. Đổi mật khẩu/khóa user revoke session. OAuth Google để sau, chưa tạo bảng P2 chỉ để dự phòng.

## 02 Blog/Media

### `categories` [P0]

| Trường | PostgreSQL | NULL | Vai trò / ý nghĩa |
|---|---|---|---|
| `id` | `uuid` | NN | PK |
| `slug` | `text` | NN | UQ; lowercase |
| `name` | `text` | NN |  |
| `status` | `text` | NN | active / hidden |
| `created_at` | `timestamptz` | NN |  |
| `updated_at` | `timestamptz` | NN |  |

- PK: `(id)`
- UQ: `(slug)`
- CHECK / validation: slug/name không rỗng; status IN (active,hidden).
- Quy tắc nghiệp vụ: ĐÃ CHỐT V1: một post thuộc đúng một category. Category còn post dùng hidden, không xóa làm mất FK.

### `media_uploads` [P0]

| Trường | PostgreSQL | NULL | Vai trò / ý nghĩa |
|---|---|---|---|
| `id` | `uuid` | NN | PK |
| `owner_id` | `uuid` | NN | FK |
| `object_key` | `text` | NN | UQ; khóa object storage, không phải client path |
| `mime` | `text` | NN | image/jpeg, image/png, image/webp, image/gif |
| `size_bytes` | `bigint` | NN | Dung lượng > 0 |
| `status` | `text` | NN | pending / ready / rejected / deleted |
| `created_at` | `timestamptz` | NN |  |
| `updated_at` | `timestamptz` | NN |  |

- PK: `(id)`
- UQ: `(object_key)`
- UQ: `(owner_id,id)`
- FK: `(owner_id) -> users(id)`
- CHECK / validation: size_bytes > 0; mime theo allowlist ảnh; status IN (pending,ready,rejected,deleted).
- Quy tắc nghiệp vụ: FK chỉ bảo vệ tồn tại/owner; signature/MIME/size/frame limits và ready phải kiểm server. Hạn dung lượng cụ thể cần chốt trước triển khai. Không chứa binary trong DB; không đưa video/sound vào upload P0.

### `posts` [P0]

| Trường | PostgreSQL | NULL | Vai trò / ý nghĩa |
|---|---|---|---|
| `id` | `uuid` | NN | PK |
| `author_id` | `uuid` | NN | FK |
| `category_id` | `uuid` | NN | FK |
| `media_id` | `uuid` | NULL | FK; Bài chỉ có chữ; một cột => tối đa 01 ảnh |
| `title` | `text` | NN |  |
| `content` | `text` | NN | Có thể rỗng nếu có ảnh; không lưu HTML chưa sanitize |
| `status` | `text` | NN | draft / published / hidden / deleted |
| `created_at` | `timestamptz` | NN |  |
| `updated_at` | `timestamptz` | NN |  |
| `deleted_at` | `timestamptz` | NULL | Chưa soft delete |

- PK: `(id)`
- FK: `(author_id) -> users(id)`
- FK: `(category_id) -> categories(id)`
- FK: `(author_id,media_id) -> media_uploads(owner_id,id)` — MATCH SIMPLE: media_id NULL = không ảnh; author_id luôn NOT NULL
- CHECK / validation: title không rỗng; content không rỗng OR media_id IS NOT NULL; status theo allowlist; (status=deleted) = (deleted_at IS NOT NULL).
- Quy tắc nghiệp vụ: Một category/post; 0..1 media thuộc chính author. Sửa/xóa/hide giữ ID để ledger/report không mồ côi; không cascade delete nội dung đã được audit.

### `comments` [P0]

| Trường | PostgreSQL | NULL | Vai trò / ý nghĩa |
|---|---|---|---|
| `id` | `uuid` | NN | PK |
| `post_id` | `uuid` | NN | FK |
| `author_id` | `uuid` | NN | FK |
| `body` | `text` | NN |  |
| `status` | `text` | NN | visible / hidden / deleted |
| `created_at` | `timestamptz` | NN |  |
| `updated_at` | `timestamptz` | NN |  |
| `deleted_at` | `timestamptz` | NULL | Chưa soft delete |

- PK: `(id)`
- FK: `(author_id) -> users(id)`
- FK: `(post_id) -> posts(id)`
- CHECK / validation: body không rỗng; status IN (visible,hidden,deleted); (status=deleted) = (deleted_at IS NOT NULL).
- Quy tắc nghiệp vụ: Bình luận phẳng P0; không tự thêm threaded comments. Giữ lịch sử ID cho chống farm và reversal.

### `post_reactions` [P1]

| Trường | PostgreSQL | NULL | Vai trò / ý nghĩa |
|---|---|---|---|
| `post_id` | `uuid` | NN | PK; FK |
| `user_id` | `uuid` | NN | PK; FK |
| `reaction_type` | `text` | NN | like / laugh / fire |
| `created_at` | `timestamptz` | NN |  |
| `updated_at` | `timestamptz` | NN |  |

- PK: `(post_id,user_id)`
- FK: `(user_id) -> users(id)`
- FK: `(post_id) -> posts(id)`
- CHECK / validation: reaction_type IN (like,laugh,fire).
- Quy tắc nghiệp vụ: Thiết kế: chỉ một reaction hiện hành/user/post; đổi loại cập nhật cùng hàng. Unlike–re-like không tạo sự kiện thưởng mới; event reward có khóa nghiệp vụ ổn định theo policy, không theo request UUID.

### `post_bookmarks` [P1]

| Trường | PostgreSQL | NULL | Vai trò / ý nghĩa |
|---|---|---|---|
| `post_id` | `uuid` | NN | PK; FK |
| `user_id` | `uuid` | NN | PK; FK |
| `created_at` | `timestamptz` | NN |  |

- PK: `(post_id,user_id)`
- FK: `(user_id) -> users(id)`
- FK: `(post_id) -> posts(id)`
- Quy tắc nghiệp vụ: Thiết kế P1 theo Save Post trong use case; không thưởng Aura khi bookmark/share click.

### `contact_messages` [P0]

| Trường | PostgreSQL | NULL | Vai trò / ý nghĩa |
|---|---|---|---|
| `id` | `uuid` | NN | PK |
| `user_id` | `uuid` | NULL | FK; Guest được liên hệ, không bắt buộc tài khoản |
| `name` | `text` | NN |  |
| `email` | `text` | NN |  |
| `subject` | `text` | NN |  |
| `body` | `text` | NN |  |
| `status` | `text` | NN | new / in_review / resolved |
| `created_at` | `timestamptz` | NN |  |
| `updated_at` | `timestamptz` | NN |  |

- PK: `(id)`
- FK: `(user_id) -> users(id)`
- CHECK / validation: name/email/subject/body không rỗng; status IN (new,in_review,resolved).
- Quy tắc nghiệp vụ: P0 lưu DB để admin xử lý; gửi mail là P2 không thêm mail queue. Không thưởng vì gửi contact. Chỉ admin và người có quyền đọc được PII.

## 03 Aura/Streak/Wallet

### `reward_policy_versions` [P1]

| Trường | PostgreSQL | NULL | Vai trò / ý nghĩa |
|---|---|---|---|
| `id` | `uuid` | NN | PK |
| `version` | `integer` | NN | UQ; > 0 |
| `config_json` | `jsonb` | NN | XP/caps, level/rank, weekly icon, generator/offline cap khi P2 |
| `status` | `text` | NN | draft / published / retired |
| `effective_at` | `timestamptz` | NN |  |
| `created_by` | `uuid` | NN | FK |
| `created_at` | `timestamptz` | NN |  |

- PK: `(id)`
- UQ: `(version)`
- FK: `(created_by) -> users(id)`
- CHECK / validation: version > 0; jsonb_typeof(config_json)=object; status IN (draft,published,retired).
- Quy tắc nghiệp vụ: Published immutable: tạo version mới thay vì sửa quá khứ; quyền ghi hạn chế + audit. Service xác thực schema JSON, asset reward ID, thời gian hiệu lực và một policy áp dụng cho một event. Không vẽ FK vào đường dẫn JSON.

### `user_progress` [P1]

| Trường | PostgreSQL | NULL | Vai trò / ý nghĩa |
|---|---|---|---|
| `user_id` | `uuid` | NN | PK; FK |
| `aura_xp_earned` | `bigint` | NN | Cache SUM(base_xp), dùng rank và odds |
| `aura_xp_bonus` | `bigint` | NN | Cache SUM(bonus_xp), chỉ level/khung |
| `aura_xp_total` | `bigint` | NN | GENERATED ALWAYS AS earned + bonus STORED |
| `level_cached` | `integer` | NN | >= 1, tính từ tổng |
| `fair_level_cached` | `integer` | NN | >= 1, tính từ gốc |
| `streak_days` | `integer` | NN | >= 0 |
| `last_checkin_day` | `date` | NULL | Chưa điểm danh |
| `updated_at` | `timestamptz` | NN |  |

- PK: `(user_id)`
- FK: `(user_id) -> users(id)`
- CHECK / validation: aura_xp_earned >= 0; aura_xp_bonus >= 0; level_cached/fair_level_cached >= 1; streak_days >= 0.
- Quy tắc nghiệp vụ: DB bảo đảm users 1:0..1; service tạo cùng khởi tạo P1, tương tự wallets. Rebuild từ signed ledger và daily_checkins; generated total không cộng bonus hai lần. Level/fair-level cache tính theo policy đã công bố, không tin client.

### `aura_ledger` [P1]

| Trường | PostgreSQL | NULL | Vai trò / ý nghĩa |
|---|---|---|---|
| `id` | `uuid` | NN | PK |
| `user_id` | `uuid` | NN | FK |
| `event_key` | `text` | NN | UQ(user_id,event_key); namespace server |
| `event_type` | `text` | NN | post / reaction / comment / checkin / adjustment / reversal |
| `source_actor_id` | `uuid` | NULL | FK; System reward không có actor người dùng |
| `source_post_id` | `uuid` | NULL | FK; Check-in/manual không có post |
| `source_comment_id` | `uuid` | NULL | FK; Không phải comment event |
| `policy_id` | `uuid` | NN | FK |
| `base_xp` | `bigint` | NN | Signed delta; reward dương, reversal âm |
| `bonus_xp` | `bigint` | NN | Signed delta, không nhân lại |
| `tier_at_event` | `text` | NN | FREE / PLUS / PRIME |
| `multiplier_at_event` | `smallint` | NN | 1 / 2 / 3 snapshot |
| `reverses_id` | `uuid` | NULL | FK; NULL cho event gốc; reversal trỏ event cùng user |
| `occurred_at` | `timestamptz` | NN | Thời điểm server, UTC |

- PK: `(id)`
- UQ: `(user_id,event_key)`
- UQ: `(user_id,id)`
- UQ: `(reverses_id)`
- FK: `(user_id) -> users(id)`
- FK: `(source_actor_id) -> users(id)`
- FK: `(source_post_id) -> posts(id)`
- FK: `(source_comment_id) -> comments(id)`
- FK: `(policy_id) -> reward_policy_versions(id)`
- FK: `(user_id,reverses_id) -> aura_ledger(user_id,id)` — MATCH SIMPLE: không reversal thì reverses_id NULL
- CHECK / validation: event_type/tier theo allowlist; reward thông thường: tier/multiplier FREE=1,PLUS=2,PRIME=3, base_xp >= 0 AND bonus_xp=base_xp*(multiplier-1); adjustment: base_xp >= 0, bonus_xp=0,multiplier=1; reversal: base_xp <= 0 AND bonus_xp <= 0; (event_type=reversal) = (reverses_id IS NOT NULL); base_xp<>0 OR bonus_xp<>0; reverses_id<>id.
- Quy tắc nghiệp vụ: Append-only committed ledger; không xóa/sửa reward. Thiết kế full reversal một lần/event (UQ reverses_id), phải đối chiếu đúng số âm và tier/multiplier event gốc tại service. Không tạo pending rows vào tổng: chỉ ghi khi qualified. FK source_comment→post nhất quán kiểm service. Manual adjustment không tự nhân VIP. P1 chỉ FREE; P2 snapshot tier từ entitlement server. Không FK sang P2 làm P1 phụ thuộc P2.

### `daily_checkins` [P1]

| Trường | PostgreSQL | NULL | Vai trò / ý nghĩa |
|---|---|---|---|
| `user_id` | `uuid` | NN | PK; FK |
| `effective_day` | `date` | NN | PK; Ngày server theo mốc 07:00 VN |
| `aura_ledger_id` | `uuid` | NN | FK; Một reward event |
| `wallet_transaction_id` | `uuid` | NN | FK; Một credit Khí Vận |
| `claimed_at` | `timestamptz` | NN | UTC |

- PK: `(user_id,effective_day)`
- UQ: `(aura_ledger_id)`
- UQ: `(wallet_transaction_id)`
- FK: `(user_id) -> users(id)`
- FK: `(user_id,aura_ledger_id) -> aura_ledger(user_id,id)`
- FK: `(user_id,wallet_transaction_id) -> wallet_transactions(user_id,id)`
- CHECK / validation: effective_day = ((claimed_at AT TIME ZONE 'Asia/Ho_Chi_Minh') - interval '7 hours')::date.
- Quy tắc nghiệp vụ: Không lặp base/bonus/currency amount ở checkin, đọc ledger qua FK cùng owner. Claim/checkin/2 ledger/cache trong một transaction, conflict trả kết quả cũ. Streak tuần: icon 7/7 từ inventory_grants event_key weekly:YYYY-MM-DD (thứ Hai).

### `wallets` [P1]

| Trường | PostgreSQL | NULL | Vai trò / ý nghĩa |
|---|---|---|---|
| `user_id` | `uuid` | NN | PK; FK |
| `khi_van_balance` | `bigint` | NN | >= 0 |
| `updated_at` | `timestamptz` | NN |  |

- PK: `(user_id)`
- FK: `(user_id) -> users(id)`
- CHECK / validation: khi_van_balance >= 0.
- Quy tắc nghiệp vụ: Logical 1:1 khi user bật P1, FK chỉ cưỡng chế 0..1. Cache = SUM(wallet_transactions.delta_khi_van). Không transfer/cash-out. Update balance và ledger cùng transaction với row lock/conditional debit.

### `wallet_transactions` [P1]

| Trường | PostgreSQL | NULL | Vai trò / ý nghĩa |
|---|---|---|---|
| `id` | `uuid` | NN | PK |
| `user_id` | `uuid` | NN | FK |
| `event_key` | `text` | NN | UQ(user_id,event_key); checkin:/case:/generator:/reversal: |
| `delta_khi_van` | `bigint` | NN | Signed; credit >0, debit <0 |
| `reason` | `text` | NN | checkin / case_open / generator / adjustment / reversal |
| `policy_id` | `uuid` | NN | FK |
| `reverses_id` | `uuid` | NULL | FK; Chỉ reversal; giữ lịch sử |
| `created_at` | `timestamptz` | NN |  |

- PK: `(id)`
- UQ: `(user_id,event_key)`
- UQ: `(user_id,id)`
- UQ: `(reverses_id)`
- FK: `(user_id) -> wallets(user_id)`
- FK: `(policy_id) -> reward_policy_versions(id)`
- FK: `(user_id,reverses_id) -> wallet_transactions(user_id,id)` — MATCH SIMPLE: event gốc không có reverses_id
- CHECK / validation: delta_khi_van <> 0; reason theo allowlist; (reason=reversal) = (reverses_id IS NOT NULL); reverses_id<>id; reason IN (checkin,generator) => delta>0; reason=case_open => delta<0.
- Quy tắc nghiệp vụ: Append-only. UQ reverses_id: full reversal một lần, service kiểm delta = -delta gốc và không làm âm ví. Key nghiệp vụ server có namespace, không nhận event key tùy ý từ client. Free case không tạo transaction giá trị 0.

## 04 Vault/Inventory

### `asset_items` [P1]

| Trường | PostgreSQL | NULL | Vai trò / ý nghĩa |
|---|---|---|---|
| `id` | `uuid` | NN | PK |
| `slug` | `text` | NN | UQ; import một catalog JSON chuẩn |
| `kind` | `text` | NN | avatar / frame / icon / effect / generator |
| `collection` | `text` | NN |  |
| `rarity` | `text` | NN | D / C / B / A / S |
| `media_key` | `text` | NN | Asset do catalog quản lý, không phải upload user |
| `source_rights` | `jsonb` | NN | source/author/license/attribution/review_status |
| `active` | `boolean` | NN |  |
| `created_at` | `timestamptz` | NN |  |
| `updated_at` | `timestamptz` | NN |  |

- PK: `(id)`
- UQ: `(slug)`
- UQ: `(id,kind)`
- UQ: `(id,rarity)`
- CHECK / validation: kind/rarity theo allowlist; jsonb_typeof(source_rights)=object; slug/media_key không rỗng.
- Quy tắc nghiệp vụ: Một nguồn catalog; kind/rarity immutable khi đã referenced. Chỉ active và có quyền sử dụng mới được publish pool. generator chỉ dùng P2; sound chưa chốt không thêm vội. Asset media_key không FK media_uploads vì là tài sản catalog khác upload user.

### `case_definitions` [P1]

| Trường | PostgreSQL | NULL | Vai trò / ý nghĩa |
|---|---|---|---|
| `id` | `uuid` | NN | PK |
| `slug` | `text` | NN | UQ; common / d / c / b / a / s |
| `label` | `text` | NN |  |
| `cost_khi_van` | `bigint` | NN | >= 0, giá hiện hành đề xuất |
| `status` | `text` | NN | draft / active / retired |
| `created_at` | `timestamptz` | NN |  |
| `updated_at` | `timestamptz` | NN |  |

- PK: `(id)`
- UQ: `(slug)`
- CHECK / validation: cost_khi_van >= 0; status IN (draft,active,retired).
- Quy tắc nghiệp vụ: P1 chỉ rương chung; rương D/C/B/A/S triển khai P2 sau mô phỏng, dùng cùng bảng. Giá/quota/cooldown là cần chốt trước triển khai; không seed con số production ở M0.3.

### `case_loot_tables` [P1]

| Trường | PostgreSQL | NULL | Vai trò / ý nghĩa |
|---|---|---|---|
| `id` | `uuid` | NN | PK; Một pool cụ thể cho một case/version/band |
| `case_id` | `uuid` | NN | FK |
| `odds_version` | `integer` | NN |  |
| `band_no` | `smallint` | NN |  |
| `min_earned_xp` | `bigint` | NN | Cận dưới bao gồm, chỉ Aura gốc |
| `max_earned_xp` | `bigint` | NULL | NULL cho band cuối; cận trên loại trừ |
| `policy_id` | `uuid` | NN | FK; Policy mức công bằng tại thời điểm publish |
| `status` | `text` | NN | draft / published / retired |
| `active_from` | `timestamptz` | NN |  |
| `created_at` | `timestamptz` | NN |  |

- PK: `(id)`
- UQ: `(case_id,odds_version,band_no)`
- UQ: `(case_id,id)`
- FK: `(case_id) -> case_definitions(id)`
- FK: `(policy_id) -> reward_policy_versions(id)`
- CHECK / validation: odds_version > 0; band_no > 0; min_earned_xp >= 0; max IS NULL OR max > min; status theo allowlist.
- Quy tắc nghiệp vụ: Mỗi ID xác định đúng case + version + band, không phải một dòng rarity lỏng lẻo. Publish transaction kiểm band không chồng/lỗ cho cùng case/version, đủ rarity/pool, version immutable. case_opens giữ ID này nên không thể lẫn version. Odds V0 test-only, chưa cân bằng production.

### `case_loot_rarities` [P1]

| Trường | PostgreSQL | NULL | Vai trò / ý nghĩa |
|---|---|---|---|
| `loot_table_id` | `uuid` | NN | PK; FK |
| `rarity` | `text` | NN | PK; D / C / B / A / S |
| `weight_bps` | `integer` | NN | 0..10000; 10000 = 100% |

- PK: `(loot_table_id,rarity)`
- FK: `(loot_table_id) -> case_loot_tables(id)`
- CHECK / validation: rarity theo allowlist; weight_bps BETWEEN 0 AND 10000.
- Quy tắc nghiệp vụ: Tầng 1 chọn rarity. Tổng 5 rarity/pool = 10000; mọi rarity weight>0 phải có item hợp lệ. Đây là aggregate invariant khi publish, không phải CHECK cross-table. Rương chung S bắt đầu <100 bps, <=1000 bps; bands chính xác cần chốt trước triển khai.

### `case_pool_items` [P1]

| Trường | PostgreSQL | NULL | Vai trò / ý nghĩa |
|---|---|---|---|
| `loot_table_id` | `uuid` | NN | PK; FK |
| `asset_id` | `uuid` | NN | PK; FK |
| `rarity` | `text` | NN | FK; FK phải đồng nhất rarity của asset và bucket |
| `item_weight` | `integer` | NN | > 0 trong bucket |

- PK: `(loot_table_id,asset_id)`
- FK: `(loot_table_id,rarity) -> case_loot_rarities(loot_table_id,rarity)`
- FK: `(asset_id,rarity) -> asset_items(id,rarity)`
- CHECK / validation: item_weight > 0.
- Quy tắc nghiệp vụ: Tầng 2 chọn item theo weight trong rarity. Hai composite FK buộc đúng version/bucket và đúng rarity catalog; không dùng version text rời case_id. Published rows immutable kể cả weight.

### `case_opens` [P1]

| Trường | PostgreSQL | NULL | Vai trò / ý nghĩa |
|---|---|---|---|
| `id` | `uuid` | NN | PK |
| `user_id` | `uuid` | NN | FK |
| `request_key` | `text` | NN | UQ(user_id,request_key); retry giữ nguyên payload |
| `case_id` | `uuid` | NN | FK |
| `loot_table_id` | `uuid` | NN | FK; FK ràng buộc case và phiên bản cụ thể |
| `reward_asset_id` | `uuid` | NN | FK; Phải có trong đúng pool |
| `earned_xp_at_open` | `bigint` | NN | Snapshot gốc, không cộng VIP |
| `cost_khi_van` | `bigint` | NN | Chi phí đã trừ, snapshot |
| `wallet_transaction_id` | `uuid` | NULL | FK; NULL chỉ khi cost=0 |
| `is_daily_free` | `boolean` | NN | Thiết kế rương chung 1 lượt/ngày |
| `effective_day` | `date` | NN | Ngày 07:00 VN |
| `decision_trace` | `jsonb` | NN | Bucket/draw audit; không log secret/RNG seed runtime |
| `created_at` | `timestamptz` | NN |  |

- PK: `(id)`
- UQ: `(user_id,request_key)`
- UQ: `(user_id,id)`
- UQ: `(wallet_transaction_id)`
- FK: `(user_id) -> users(id)`
- FK: `(case_id,loot_table_id) -> case_loot_tables(case_id,id)`
- FK: `(loot_table_id,reward_asset_id) -> case_pool_items(loot_table_id,asset_id)`
- FK: `(user_id,wallet_transaction_id) -> wallet_transactions(user_id,id)` — MATCH SIMPLE: free open không có debit
- CHECK / validation: earned_xp_at_open >= 0; cost_khi_van >= 0; (cost=0 AND wallet_transaction_id IS NULL) OR (cost>0 AND wallet_transaction_id IS NOT NULL); effective_day = VN07(created_at); is_daily_free => cost=0.
- Quy tắc nghiệp vụ: Một transaction: lock user/progress/ví/quota theo thứ tự toàn cục → server chọn published pool theo gốc → CSPRNG → debit ledger → case_open → inventory_grant/quantity. Service kiểm wallet delta=-cost, reason=case_open, loot band bao gồm earned snapshot, không nhận reward/cost từ client. Partial UQ(user_id,case_id,effective_day) WHERE is_daily_free; quy tắc quota cuối cùng mục 9 — Bảo Khố.

### `user_inventory` [P1]

| Trường | PostgreSQL | NULL | Vai trò / ý nghĩa |
|---|---|---|---|
| `user_id` | `uuid` | NN | PK; FK |
| `asset_id` | `uuid` | NN | PK; FK |
| `quantity` | `integer` | NN | >= 0; số bản sở hữu, chưa chốt xử lý duplicate |
| `acquired_at` | `timestamptz` | NN | Lần đầu có item |
| `updated_at` | `timestamptz` | NN |  |

- PK: `(user_id,asset_id)`
- FK: `(user_id) -> users(id)`
- FK: `(asset_id) -> asset_items(id)`
- CHECK / validation: quantity >= 0.
- Quy tắc nghiệp vụ: Sở hữu tách khỏi trang bị. Quantity tái tính từ inventory_grants cho phát đồ; không tự thêm sell/burn/transfer. Khi quantity=0, không được equip, kể cả FK vẫn tồn tại; service/trigger khi cập nhật.

### `inventory_grants` [P1]

| Trường | PostgreSQL | NULL | Vai trò / ý nghĩa |
|---|---|---|---|
| `id` | `uuid` | NN | PK |
| `user_id` | `uuid` | NN | FK |
| `asset_id` | `uuid` | NN | FK |
| `event_key` | `text` | NN | UQ(user_id,event_key); case:/weekly:/level:/admin: |
| `quantity` | `integer` | NN | > 0 |
| `source_type` | `text` | NN | case_open / weekly_streak / level / admin |
| `case_open_id` | `uuid` | NULL | FK; Chỉ có cho nguồn case_open |
| `policy_id` | `uuid` | NN | FK |
| `granted_at` | `timestamptz` | NN |  |

- PK: `(id)`
- UQ: `(user_id,event_key)`
- UQ: `(case_open_id)`
- FK: `(user_id,asset_id) -> user_inventory(user_id,asset_id)`
- FK: `(user_id,case_open_id) -> case_opens(user_id,id)` — MATCH SIMPLE: reward khác không có case_open
- FK: `(policy_id) -> reward_policy_versions(id)`
- CHECK / validation: quantity > 0; source_type theo allowlist; (source_type=case_open) = (case_open_id IS NOT NULL).
- Quy tắc nghiệp vụ: Sổ cấp item append-only, chống cấp icon 7/7 hoặc khung level hai lần. FK inventory phải tạo/upsert trong cùng transaction. Case grant phải quantity=1 và asset đúng kết quả open (service/trigger). Duplicate policy cần chốt trước triển khai, chưa tự đổi vật phẩm trùng thành tiền.

### `user_equipment` [P1]

| Trường | PostgreSQL | NULL | Vai trò / ý nghĩa |
|---|---|---|---|
| `user_id` | `uuid` | NN | PK; FK |
| `slot_kind` | `text` | NN | PK; FK; avatar / frame / icon / effect |
| `asset_id` | `uuid` | NN | FK |
| `equipped_at` | `timestamptz` | NN |  |

- PK: `(user_id,slot_kind)`
- FK: `(user_id) -> users(id)`
- FK: `(user_id,asset_id) -> user_inventory(user_id,asset_id)`
- FK: `(asset_id,slot_kind) -> asset_items(id,kind)`
- CHECK / validation: slot_kind IN (avatar,frame,icon,effect).
- Quy tắc nghiệp vụ: Thiết kế một hàng cho mỗi ô cosmetic đang dùng, không có hàng = chưa trang bị. Composite FK(user_id,asset_id)→inventory và (asset_id,slot_kind)→catalog(id,kind) chặn đồ người khác/sai kind. Service kiểm quantity>0/active; avatar cosmetic ưu tiên ảnh upload khi đang equip (đề xuất cần owner duyệt).

## 05 Generator 3 slots [P2]

### `asset_generator_stats` [P2]

| Trường | PostgreSQL | NULL | Vai trò / ý nghĩa |
|---|---|---|---|
| `asset_id` | `uuid` | NN | PK; FK |
| `kind` | `text` | NN | FK; Luôn generator |
| `rate_khi_van_per_hour` | `integer` | NN | >= 0; không float |
| `created_at` | `timestamptz` | NN |  |

- PK: `(asset_id)`
- FK: `(asset_id,kind) -> asset_items(id,kind)`
- CHECK / validation: kind=generator; rate_khi_van_per_hour >= 0.
- Quy tắc nghiệp vụ: Thiết kế rate immutable khi asset đã cấp/equip; muốn đổi dùng policy mới và settle toàn bộ slot ở mốc đổi hoặc catalog item mới. Không thêm rate-history table trước khi có nhu cầu.

### `generator_slots` [P2]

| Trường | PostgreSQL | NULL | Vai trò / ý nghĩa |
|---|---|---|---|
| `user_id` | `uuid` | NN | PK; FK |
| `slot_no` | `smallint` | NN | PK; 1..3 |
| `asset_id` | `uuid` | NULL | FK; Slot trống |
| `equipped_at` | `timestamptz` | NULL | NULL khi trống |
| `accrual_cursor_at` | `timestamptz` | NN | Mốc server đã settle, kể cả slot trống |
| `updated_at` | `timestamptz` | NN |  |

- PK: `(user_id,slot_no)`
- FK: `(user_id) -> users(id)`
- FK: `(user_id,asset_id) -> user_inventory(user_id,asset_id)` — MATCH SIMPLE: slot trống
- FK: `(asset_id) -> asset_generator_stats(asset_id)`
- CHECK / validation: slot_no BETWEEN 1 AND 3; (asset_id IS NULL) = (equipped_at IS NULL); equipped_at IS NULL OR accrual_cursor_at >= equipped_at.
- Quy tắc nghiệp vụ: Tối đa 3 hàng/user. FK owner inventory + asset_generator_stats chặn sai chủ/sai kind. Thiết kế cùng asset có thể nhiều ô nếu quantity >= số ô sử dụng; service khóa inventory và các slot để kiểm tổng. mục 9 — Generator chốt lại trước P2. Đổi/tháo thẻ phải settle cursor cũ trước, không tính rate mới cho thời gian cũ.

### `generator_claims` [P2]

| Trường | PostgreSQL | NULL | Vai trò / ý nghĩa |
|---|---|---|---|
| `id` | `uuid` | NN | PK |
| `user_id` | `uuid` | NN | FK |
| `slot_no` | `smallint` | NN | FK |
| `asset_id` | `uuid` | NN | FK; Snapshot item sinh khoản claim này |
| `event_key` | `text` | NN | UQ(user_id,event_key); gồm request + slot |
| `accrual_from` | `timestamptz` | NN |  |
| `accrual_to` | `timestamptz` | NN |  |
| `rate_at_claim` | `integer` | NN | Snapshot integer/giờ |
| `delta_khi_van` | `bigint` | NN | > 0 |
| `policy_id` | `uuid` | NN | FK |
| `wallet_transaction_id` | `uuid` | NN | FK |
| `created_at` | `timestamptz` | NN |  |

- PK: `(id)`
- UQ: `(user_id,event_key)`
- UQ: `(user_id,slot_no,accrual_from)`
- UQ: `(wallet_transaction_id)`
- FK: `(user_id,slot_no) -> generator_slots(user_id,slot_no)`
- FK: `(asset_id) -> asset_generator_stats(asset_id)`
- FK: `(policy_id) -> reward_policy_versions(id)`
- FK: `(user_id,wallet_transaction_id) -> wallet_transactions(user_id,id)`
- CHECK / validation: slot_no BETWEEN 1 AND 3; accrual_to > accrual_from; rate_at_claim >= 0; delta_khi_van > 0.
- Quy tắc nghiệp vụ: Claim = 1 hàng/slot/cửa sổ có số nguyên trả được. Lock user→wallet→inventory→slot theo thứ tự toàn cục, đọc cursor DB, áp offline/day cap policy, floor số nguyên, giữ phần thời gian lẻ hoặc định nghĩa rõ rounding mục 9 — Generator. Cộng wallet + ledger + claim + advance cursor trong một transaction; replay trả hàng cũ. Không có khoản trả thì không tạo claim, cursor xử lý theo cap policy. Invariant không chồng thời gian do lock/cursor, UQ from chỉ là lớp phụ.

## 06 Membership/Payment [P2]

### `membership_plans` [P2]

| Trường | PostgreSQL | NULL | Vai trò / ý nghĩa |
|---|---|---|---|
| `code` | `text` | NN | PK; FREE / PLUS / PRIME |
| `name` | `text` | NN |  |
| `multiplier` | `smallint` | NN | 1 / 2 / 3 |
| `period` | `text` | NN | none / month / year |
| `price_amount` | `numeric(12,2)` | NN | 0.00 / 10.00 / 100.00 |
| `currency` | `char(3)` | NN | USD cho bảng giá đã chốt |
| `active` | `boolean` | NN |  |

- PK: `(code)`
- CHECK / validation: (FREE,1,none,0.00,USD) OR (PLUS,2,month,10.00,USD) OR (PRIME,3,year,100.00,USD).
- Quy tắc nghiệp vụ: ĐÃ CHỐT giá/period/multiplier; không tự chuyển Prime thành tháng. Free có thể là trạng thái mặc định không cần entitlement. Không cho sửa historical price/period; payment event lưu snapshot số tiền thực tế. Chưa tích hợp tiền thật.

### `subscription_entitlements` [P2]

| Trường | PostgreSQL | NULL | Vai trò / ý nghĩa |
|---|---|---|---|
| `id` | `uuid` | NN | PK |
| `user_id` | `uuid` | NN | FK |
| `plan_code` | `text` | NN | FK; PLUS / PRIME |
| `starts_at` | `timestamptz` | NN |  |
| `ends_at` | `timestamptz` | NN |  |
| `status` | `text` | NN | active / canceled / expired / revoked |
| `source` | `text` | NN | demo / provider_verified |
| `environment` | `text` | NN | FK; demo / sandbox / live; không trộn entitlement test với live |
| `verified_payment_event_id` | `uuid` | NULL | FK; NULL chỉ cho demo |
| `created_at` | `timestamptz` | NN |  |
| `updated_at` | `timestamptz` | NN |  |

- PK: `(id)`
- UQ: `(verified_payment_event_id)`
- FK: `(user_id) -> users(id)`
- FK: `(plan_code) -> membership_plans(code)`
- FK: `(user_id,verified_payment_event_id,environment) -> payment_events(user_id,id,environment)` — MATCH SIMPLE: demo không có event verified
- CHECK / validation: ends_at > starts_at; plan_code IN (PLUS,PRIME); source/status/environment theo allowlist; (source=provider_verified) = (verified_payment_event_id IS NOT NULL); (source=demo) = (environment=demo).
- Quy tắc nghiệp vụ: Entitlement dùng khoảng [starts_at,ends_at), trạng thái active chưa đủ nếu đã hết thời gian. Composite FK verified event đúng owner và environment; một event cấp tối đa một entitlement. Service kiểm chữ ký, status/amount/currency/plan và quyền subscription; live chỉ đọc entitlement live. Kiểm không chồng entitlement active trong cùng environment bằng lock user + kiểm overlap (hoặc exclusion constraint khi implement); upgrade/downgrade/refund mục 9 — Membership. Audit mọi thay đổi.

### `payment_events` [P2]

| Trường | PostgreSQL | NULL | Vai trò / ý nghĩa |
|---|---|---|---|
| `id` | `uuid` | NN | PK |
| `user_id` | `uuid` | NN | FK; Đã map từ order/customer phía server |
| `provider` | `text` | NN | Namespace provider |
| `environment` | `text` | NN | demo / sandbox / live |
| `provider_event_id` | `text` | NN | UQ(provider,environment,provider_event_id) |
| `plan_code` | `text` | NN | FK |
| `amount` | `numeric(12,2)` | NN | Không float |
| `currency` | `char(3)` | NN |  |
| `status` | `text` | NN | received / verified / applied / failed / refunded |
| `verified_at` | `timestamptz` | NULL | Chưa xác minh hoặc demo |
| `payload_digest` | `text` | NN | Digest đối chiếu retry, không lưu số thẻ/secret |
| `created_at` | `timestamptz` | NN |  |

- PK: `(id)`
- UQ: `(provider,environment,provider_event_id)`
- UQ: `(user_id,id,environment)`
- FK: `(user_id) -> users(id)`
- FK: `(plan_code) -> membership_plans(code)`
- CHECK / validation: amount >= 0; environment/status theo allowlist; currency uppercase ISO 4217; status IN (verified,applied,refunded) => verified_at IS NOT NULL AND environment<>demo.
- Quy tắc nghiệp vụ: Inbox webhook tối thiểu P2: append payload/digest audit; xử lý state transitions server, event key provider + môi trường. Event đã verify không tự nghĩa là tiền đã đến nếu provider loại event không phải payment settled; kiểm loại/status từ provider. Mỗi provider financial event là một row, refund không ghi đè event gốc. Callback frontend không cấp entitlement. Entitlement tham chiếu event đã xác minh cùng owner/environment; không vẽ mũi tên nghiệp vụ thay FK.

## 07 Admin/Audit

### `user_reports` [P1]

| Trường | PostgreSQL | NULL | Vai trò / ý nghĩa |
|---|---|---|---|
| `id` | `uuid` | NN | PK |
| `reporter_id` | `uuid` | NN | FK |
| `post_id` | `uuid` | NN | FK |
| `reason` | `text` | NN |  |
| `status` | `text` | NN | new / in_review / resolved / dismissed |
| `resolved_by` | `uuid` | NULL | FK; Chưa xử lý |
| `resolved_at` | `timestamptz` | NULL | Chưa xử lý |
| `created_at` | `timestamptz` | NN |  |

- PK: `(id)`
- FK: `(reporter_id) -> users(id)`
- FK: `(resolved_by) -> users(id)`
- FK: `(post_id) -> posts(id)`
- CHECK / validation: reason không rỗng; status theo allowlist; (status IN (resolved,dismissed)) = (resolved_at IS NOT NULL AND resolved_by IS NOT NULL); (resolved_at IS NULL) = (resolved_by IS NULL).
- Quy tắc nghiệp vụ: Thiết kế report bài P1 theo use case Resolve User Reports; không tự thêm report đa hình cho mọi entity. P0 báo lỗi/liên hệ qua contact. Server kiểm resolved_by có role ADMIN lúc hành động, log cùng transaction.

### `admin_audit_logs` [P0]

| Trường | PostgreSQL | NULL | Vai trò / ý nghĩa |
|---|---|---|---|
| `id` | `uuid` | NN | PK |
| `actor_id` | `uuid` | NN | FK |
| `action` | `text` | NN |  |
| `target_type` | `text` | NN | Tên resource từ allowlist server |
| `target_id` | `text` | NN | UUID/composite/business key biểu diễn; không FK đa hình |
| `before_json` | `jsonb` | NULL | Không có trạng thái trước khi tạo |
| `after_json` | `jsonb` | NULL | Không có trạng thái sau khi xóa/thu hồi |
| `created_at` | `timestamptz` | NN |  |

- PK: `(id)`
- FK: `(actor_id) -> users(id)`
- CHECK / validation: action/target_type/target_id không rỗng; before_json IS NOT NULL OR after_json IS NOT NULL.
- Quy tắc nghiệp vụ: Append-only audit quản lý user/role/post/category/contact P0; policy/catalog P1, entitlement P2. Actor FK users, role kiểm tại server ở thời điểm hành động. target_id đa hình cố ý KHÔNG vẽ FK; snapshot không chứa password_hash/token/PII không cần thiết. Retention/redaction mục 9 — Quyền riêng tư.

## 8. Chỉ mục và tính toàn vẹn giao dịch

PK/UQ tự có B-tree unique index. Tạo B-tree cho mỗi FK **nếu chưa có PK/UQ/index cùng prefix phù hợp**; PostgreSQL không tự tạo index phía referencing. FK tự tham chiếu cũng áp dụng. Các index thêm dưới đây là ĐỀ XUẤT, đo query plan khi có dữ liệu trước khi bổ sung nhiều index.

| Phase | Index / constraint thêm | Mục đích |
|---|---|---|
| P0 | posts(status,created_at DESC,id), posts(category_id,status,created_at DESC,id), posts(author_id,created_at DESC,id) | Feed/filter ổn định; cursor hoặc OFFSET pagination có tie-break id. |
| P0 | GIN(to_tsvector('simple', coalesce(title,'') || ' ' || coalesce(content,''))) trên posts | Tìm cả tiêu đề + nội dung, query dùng cùng expression; search tiếng Việt accent-insensitive chưa chốt, không hứa tự có từ full-text. |
| P0 | comments(post_id,status,created_at,id), media_uploads(owner_id,status,created_at,id) | Đọc list và lọc user upload. |
| P0 | users(status,created_at,id); auth_sessions(user_id,expires_at) WHERE revoked_at IS NULL | Admin danh sách/khóa tài khoản; thu hồi phiên. |
| P0 | contact_messages(status,created_at,id); admin_audit_logs(actor_id,created_at,id), (target_type,target_id,created_at,id) | Admin list và audit. PII không index công khai. |
| P1 | post_bookmarks(user_id,created_at DESC,post_id); post_reactions(user_id,created_at,post_id) | PK bắt đầu post_id không đủ cho list của user. |
| P1 | user_progress(aura_xp_earned DESC,user_id); aura_ledger(occurred_at,user_id) INCLUDE(base_xp), aura_ledger(user_id,occurred_at,id) | Lifetime rank từ earned, weekly từ signed base_xp theo mốc tuần VN07; bonus không tham gia. |
| P1 | wallet_transactions(user_id,created_at,id); inventory_grants(user_id,granted_at,id) | Audit, recompute và phân trang lịch sử. |
| P1 | case_loot_tables(case_id,status,active_from); case_opens(user_id,created_at,id) | Lấy pool published và lịch sử. |
| P1 | Partial UNIQUE case_opens(user_id,case_id,effective_day) WHERE is_daily_free | Phương án một lượt miễn phí/rương/ngày (mục 9 — Bảo Khố); không chặn lượt trả phí hợp lệ. Chỉ common được free do service kiểm. |
| P1 | user_reports(status,created_at,id); (reporter_id,created_at,id) | Moderation/list, chống spam bằng service thay vì tự cấm report mãi mãi. |
| P2 | generator_claims(user_id,slot_no,accrual_to); subscription_entitlements(user_id,starts_at,ends_at); payment_events(user_id,created_at,id) | Claim windows, thời hạn gói, audit payment. |

**Transaction contracts dự kiến (chưa implement):**

Thứ tự lock thống nhất: trước hết lock tất cả `users` liên quan theo UUID tăng (recipient/actor khi thưởng hai bên), rồi `user_progress` → `wallets` → `user_inventory` theo asset_id → `generator_slots` theo slot_no, bỏ qua resource không dùng. Không lấy thêm user lock sau resource lock. Cùng một user được serialize cho reward/money/equip/claim/revoke; tránh vòng deadlock giữa mở hòm, đổi thẻ và claim. Đây là lựa chọn đơn giản cho monolith, cần integration test khi implement.

1. Check-in: lấy giờ DB/server → tính VN07 → lock progress/wallet theo thứ tự ổn định → insert unique(user,day), insert XP/wallet events, update cache, check đủ 7 ngày tuần → grant weekly icon unique key tuần → commit. Race/unique conflict rollback toàn bộ rồi đọc kết quả cũ; không catch unique rồi tiếp tục transaction đã abort. Policy/checkin amount/sign/reason và claimed_at do server kiểm, FK không tự bảo đảm chúng.
2. XP event: stable business identity, actor≠owner theo policy khi tương tác; source phải khớp user/post/comment. Caps/cooldowns và moderation qualification khóa/serialize theo recipient/ngày, không chỉ kiểm count rồi insert không lock. Reward + progress + level item grant cùng transaction. P1 FREE; P2 tier snapshot chỉ theo entitlement hợp lệ tại event, không nhân XP cũ/hồi tố khi hết gói.
3. Reversal: lock event và cache, kiểm exact negative delta của event gốc/cùng owner; unique reverses_id; nếu vi phạm nonnegative cache/balance rollback và xử lý theo quy tắc owner chưa duyệt. Không xóa ledger hay tự bù âm bằng cách sửa số dư. Weekly rank reversal áp vào occurred_at của reversal (Thiết kế mục 9 — Aura), không tự sửa tuần cũ.
4. Publish case: validate 5 rarity tổng=10000 bps, weight dương có pool item active/đúng quyền/đúng rarity; bands không chồng/lỗ; giới hạn S rương chung theo V3; snapshot immutable header + buckets + items, audit. Service không lấy pool draft hoặc current version rồi gắn kết quả vào version khác.
5. Open case: server lock/conditional debit balance, bảo vệ quota qua partial unique/lock, bind request key với case/payload. Retry cùng key khác payload trả conflict, không tái quay. Bản ghi open, debit wallet, inventory_grant và quantity cùng commit; mất mạng sau commit trả đúng open cũ. FK không kiểm cost=-delta, đúng band, đúng policy hiện hành hay đúng asset grant: cần invariant service/trigger. Item pool/version đã publish không sửa/xóa.
6. Equip: khóa inventory/slots, kiểm quantity>0 và active. Composite FK chặn sai chủ/kind cả khi service bug; thay đổi quantity/deactivate/revoke cũng phải giữ invariant đang equip. Generator giới hạn tổng bản dùng across slots <= quantity; cursor/server time chống claim trùng/đổi thẻ ăn rate quá khứ. Không dùng browser timer hay expiry do client gửi.
7. Membership: nhận webhook, verify chữ ký/trạng thái provider phía server, unique provider/environment/event; persist digest và đối chiếu payload retry; lock user khi tạo entitlement không overlap; grant+event applied+audit cùng commit. Repeated delivery của một webhook không đồng nghĩa renewal mới. Demo tách riêng, live không được nhận demo/sandbox như thanh toán thật. Provider chưa chọn nên order/subscription/renewal protocol là mục 9 — Membership, không vẽ fake table để tuyên bố đã giải quyết payment thật.


## 9. Quyết định cấu hình cần khóa theo giai đoạn

Các điểm dưới đây là **tham số nghiệp vụ chưa phê duyệt chính thức**, không phải lỗi của ERD. Quyết định liên quan sẽ được chốt trước khi triển khai tính năng đó.

| Giai đoạn | Chủ đề | Quyết định cần khóa |
|---|---|---|
| P0 | Auth | Quy tắc email/username, khôi phục mật khẩu, OAuth, chính sách avatar công khai |
| P1 | Reaction | Một reaction hiện hành hay nhiều reaction trên mỗi bài/user |
| P1 | Aura | Điểm/caps, phạt spam, xét thưởng, ngưỡng level và rank, điều kiện cấp khung |
| P1 | Bảo Khố | Lượt miễn phí, giá hòm, bảng xác suất, cơ chế xử lý vật phẩm trùng |
| P2 | Generator | Tốc độ sinh Khí Vận, giới hạn offline, cách xử lý đổi thẻ và làm tròn |
| P2 | Membership | Cổng thanh toán, gia hạn, hủy/hoàn tiền và chính sách sandbox/live |
| P0–P2 | Quyền riêng tư | Hạn mức upload, thời gian lưu dữ liệu, phạm vi công khai hồ sơ |

## 10. Tài liệu tham chiếu

- `AURA_MEME_MASTER_PLAN_V3.md` — mục tiêu và phạm vi sản phẩm.
- `03-erd-aurameme.drawio` — sơ đồ dữ liệu chính thức (các tab theo phân hệ).
- [PostgreSQL — Constraints](https://www.postgresql.org/docs/current/ddl-constraints.html).
- [OWASP — Business Logic Security](https://cheatsheetseries.owasp.org/cheatsheets/Business_Logic_Security_Cheat_Sheet.html).
