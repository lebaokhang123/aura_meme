# Bài thực hành ASP.NET Core – AuraMeme

## 1. Mục tiêu bài thực hành

Thực hành CRUD bài viết `Post`: Controller nhận HTTP request, EF Core đọc/ghi SQLite, React gọi API bằng Axios. Đây là bài nộp tạm thời, không phải triển khai production hay bước trong roadmap AuraMeme. Các trang prototype cũ vẫn dùng mock data.

## 2. Công nghệ

- React + TypeScript + Vite + Tailwind (giữ frontend hiện tại)
- Axios 1.20
- ASP.NET Core Web API .NET 10, dùng Controllers
- Entity Framework Core 10.0.10 (SQLite provider + Design)
- SQLite: file `backend/AuraMeme.Api/aurameme.db`

Máy cần Node.js 22.12+ và .NET SDK 10. Máy kiểm thử dùng Node 22.23.2, npm 10.9.8, .NET SDK 10.0.302.

## 3. Kiến trúc

```text
React (/api-practice)
  ↓ Axios HTTP
ASP.NET Core PostsController
  ↓ AppDbContext / EF Core
SQLite (aurameme.db)
```

Không có Repository Pattern, CQRS, authentication, JWT, Docker hay DevOps. Chỉ trang API Practice kết nối backend.

## 4. Backend structure

```text
backend/
  AuraMeme.Api/
    Controllers/PostsController.cs
    Data/AppDbContext.cs
    Models/Post.cs
    Migrations/
      20261027070631_InitialCreate.cs
      20261027070631_InitialCreate.Designer.cs
      AppDbContextModelSnapshot.cs
    Properties/launchSettings.json
    Program.cs
    appsettings.json
    appsettings.Development.json
    AuraMeme.Api.csproj
    AuraMeme.Api.http
    aurameme.db                  # tạo thật, không đưa vào Git
  Tests/
    PostsApi.Smoke.ps1
    PostApiClient.Smoke.ts
dotnet-tools.json                # local dotnet-ef 10.0.10
src/
  services/postApi.ts
  pages/ApiPracticePage.tsx
```

`Post` gồm Id, Title, Content, Author, CreatedAt. Id là khóa chính tự tăng. Title bắt buộc/tối đa 200 ký tự; Content bắt buộc/tối đa 10000; Author tối đa 80, không được rỗng nếu gửi vào. Không gửi Author thì dùng `Anonymous`. CreatedAt mặc định là thời gian UTC lúc tạo. Controller chỉ nhận giá trị Title/Content/Author để ghi; Id và CreatedAt do server quyết định, PUT giữ nguyên CreatedAt.

## 5. Các endpoint

| Method | Endpoint | Chức năng | Thành công |
|---|---|---|---|
| GET | /api/posts | lấy danh sách, Id mới trước | 200 + JSON array |
| GET | /api/posts/{id} | lấy chi tiết | 200 + JSON |
| POST | /api/posts | thêm | 201 + JSON + Location |
| PUT | /api/posts/{id} | cập nhật Title/Content/Author | 204 |
| DELETE | /api/posts/{id} | xóa | 204 |

GET/PUT/DELETE theo Id không tồn tại trả 404. Dữ liệu không hợp lệ trả 400 ValidationProblemDetails do `[ApiController]` và Data Annotations. Mỗi action dùng async/await và AppDbContext.

Ví dụ body POST/PUT:

```json
{
  "title": "Deadline còn hai tiếng",
  "content": "Vừa chạy xong bài CRUD!",
  "author": "Student"
}
```

## 6. EF Core

- **EF Core**: thư viện ánh xạ đối tượng C# sang bảng dữ liệu; tạo SQL để đọc/ghi SQLite.
- **DbContext**: đối tượng làm việc với database, theo dõi thay đổi và lưu qua `SaveChangesAsync()`.
- **DbSet<Post>**: biểu diễn tập bài viết/bảng `Posts`, dùng để query/Add/Remove.
- **Migration**: mã thay đổi schema do EF CLI sinh từ model; không phải file SQL/database tự viết tay.
- **database update**: áp dụng các migration còn thiếu vào database và ghi lịch sử trong `__EFMigrationsHistory`.

Connection string ở `appsettings.json`. Program đăng ký AppDbContext bằng `UseSqlite()` và cố định đường dẫn database theo ContentRoot của API. Migration InitialCreate tạo bảng và hai Post mẫu qua `HasData()` với ngày cố định. Dữ liệu giữ lại khi restart, không reset/seed lại mỗi lần chạy. Backend không tự apply migration khi startup; bản clone mới cần chạy `database update`.

## 7. Axios

`src/services/postApi.ts` tạo Axios instance trỏ đến `http://localhost:5080/api/posts`, timeout 10 giây. Năm hàm `getPosts()`, `getPost(id)`, `createPost(data)`, `updatePost(id, data)`, `deletePost(id)` đều dùng Axios, không dùng fetch.

```text
User thao tác React
→ Axios request
→ ASP.NET Controller
→ EF Core
→ Database
→ JSON response / HTTP status
→ React cập nhật UI
```

Trang tải danh sách qua GET; nút Sửa dùng GET theo Id để điền form, submit form dùng POST hoặc PUT. Xóa có confirm trước DELETE. Sau mỗi thay đổi, GET lại danh sách. Có loading, lỗi kết nối/validation và trạng thái thành công.

## 8. Cách chạy

Lần đầu sau khi clone, tạo database từ migration đã có:

```powershell
cd D:\dev\lap_trinh_web
dotnet tool restore
cd backend\AuraMeme.Api
dotnet restore
dotnet ef database update
```

Terminal 1:

```powershell
cd D:\dev\lap_trinh_web\backend\AuraMeme.Api
dotnet run
```

Terminal 2:

```powershell
cd D:\dev\lap_trinh_web
npm install
npm run dev
```

- Frontend: http://localhost:5173
- Trang demo: http://localhost:5173/api-practice (menu **API Practice**)
- Backend: http://localhost:5080
- Danh sách JSON: http://localhost:5080/api/posts
- OpenAPI JSON: http://localhost:5080/openapi/v1.json

Dùng `backend/AuraMeme.Api/AuraMeme.Api.http` trong IDE hỗ trợ HTTP requests để thử đủ CRUD: POST trước, sao chép Id trả về vào biến `postId` rồi GET/PUT/DELETE. Không cài thêm Swagger UI; OpenAPI JSON tích hợp và file `.http` đáp ứng phần thử API của bài lab.

Development CORS chỉ cho `localhost` và `127.0.0.1` ở cổng 5173/5174, các method GET/POST/PUT/DELETE và header Content-Type. Không AllowAnyOrigin. Nếu Vite chọn cổng cao hơn 5174, dừng server thừa để dùng lại 5173/5174 hoặc thêm chính xác origin cần thiết trong Program.cs. CORS không phải authentication.

`run.bat` cũ vẫn chỉ chạy frontend; bài lab cần backend chạy trong terminal riêng. Nhấn Ctrl+C ở từng terminal để dừng.

## 9. Migration commands

Các lệnh đã thực sự chạy, không tạo migration bằng tay:

```powershell
# Tại D:\dev\lap_trinh_web
dotnet new webapi --use-controllers --framework net10.0 --no-https --no-restore -o backend\AuraMeme.Api
dotnet add backend\AuraMeme.Api package Microsoft.EntityFrameworkCore.Sqlite --version 10.0.10
dotnet add backend\AuraMeme.Api package Microsoft.EntityFrameworkCore.Design --version 10.0.10
dotnet new tool-manifest
dotnet tool install dotnet-ef --version 10.0.10

# Tại backend\AuraMeme.Api
dotnet add package Microsoft.OpenApi --version 2.7.5
dotnet add package SQLitePCLRaw.bundle_e_sqlite3 --version 2.1.14
dotnet ef migrations add InitialCreate
dotnet ef database update
```

Migration đã tạo: **20261027070631_InitialCreate**. Không chạy `migrations add InitialCreate` lại khi clone; chỉ restore tool và `database update`.

Hai PackageReference cuối là bản vá tương thích cho dependencies gián tiếp có cảnh báo NU1903 của template, không phải thêm framework. `Microsoft.OpenApi` 2.7.5 và SQLitePCLRaw 2.1.14 giữ nguyên major/nhánh phù hợp. EF Design đặt `PrivateAssets=all`. Các file bin/obj/database được ignore; giữ source migration và dotnet-tools.json trong Git.

## 10. Các file quan trọng

| File | Nội dung để trình bày |
|---|---|
| Controllers/PostsController.cs | 5 action, HTTP status, async và EF query |
| Models/Post.cs | cấu trúc Post và validation |
| Data/AppDbContext.cs | DbSet và seed mẫu |
| Program.cs | DI DbContext, SQLite, Controllers, CORS và OpenAPI |
| appsettings.json | connection string |
| Migrations/20261027070631_InitialCreate.cs | bảng Posts và seed do EF sinh |
| src/services/postApi.ts | các request Axios GET/POST/PUT/DELETE |
| src/pages/ApiPracticePage.tsx | form, list, Edit, confirm Delete và loading/error |
| src/App.tsx | route /api-practice |
| src/components/Header.tsx | menu API Practice cho desktop/mobile |

## 11. Kiểm thử

Chạy hai server rồi mở trang demo. Tạo bài, chọn Sửa, lưu thay đổi và Xóa; kiểm tra danh sách tự cập nhật. Refresh trang hoặc restart API để xác nhận SQLite lưu dữ liệu thật.

Smoke tests (PowerShell 7 và Node 22.12+):

```powershell
cd D:\dev\lap_trinh_web
pwsh -NoProfile -File backend\Tests\PostsApi.Smoke.ps1
node --experimental-strip-types backend\Tests\PostApiClient.Smoke.ts
npm run build
npm run lint
dotnet build backend\AuraMeme.Api
```

Test chỉ tạo/xóa bản ghi do chính test tạo, không xóa seed hoặc dữ liệu của bạn. Đã kiểm chứng HTTP CRUD, 400/404/201/204, Location, server-owned Id/CreatedAt, CORS allow/deny, OpenAPI, các hàm Axios; trên browser đã thử GET/POST/PUT/DELETE, dữ liệu tồn tại qua restart và lỗi khi backend tắt. Build/lint frontend và build backend đã PASS. Git ban đầu sạch; không reset, commit hay push.

## 12. Giải thích nhanh khi giảng viên hỏi

1. **Controller** nhận HTTP request, gọi phần xử lý/database và trả HTTP response; PostsController nhóm các thao tác liên quan đến Post.
2. **GET/POST/PUT/DELETE** lần lượt đọc, tạo, cập nhật và xóa tài nguyên.
3. **Axios** giúp frontend gửi HTTP request và nhận response; nó không tự kết nối trực tiếp SQLite.
4. **EF Core** ánh xạ model C# sang bảng và sinh SQL, giúp ứng dụng thao tác database bằng đối tượng.
5. **DbContext** quản lý phiên làm việc với database và lưu thay đổi bằng SaveChangesAsync.
6. **DbSet<Post>** là tập đối tượng Post để truy vấn và thao tác bảng Posts.
7. **Migration** ghi lại thay đổi model/schema; database update áp dụng thay đổi đó vào database thật.
8. **Luồng request** là React → Axios → Controller → DbContext/EF Core → SQLite → HTTP response → React cập nhật state/UI.
9. **CORS** cho phép browser tại origin frontend đã khai báo đọc response từ API khác cổng; không thay thế đăng nhập/phân quyền.
10. **async/await** cho phép chờ thao tác database mà không giữ thread bị block trong lúc chờ I/O; không có nghĩa request nào cũng chạy trên thread mới.

Tham khảo: [ASP.NET Controllers](https://learn.microsoft.com/aspnet/core/tutorials/first-web-api?view=aspnetcore-10.0), [EF Core SQLite và migrations](https://learn.microsoft.com/ef/core/get-started/overview/first-app), [Axios API](https://axios-http.com/docs/api_intro).
