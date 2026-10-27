using AuraMeme.Api.Models;
using Microsoft.EntityFrameworkCore;

namespace AuraMeme.Api.Data;

public class AppDbContext(DbContextOptions<AppDbContext> options) : DbContext(options)
{
    public DbSet<Post> Posts => Set<Post>();

    protected override void OnModelCreating(ModelBuilder modelBuilder)
    {
        modelBuilder.Entity<Post>().HasData(
            new Post { Id = 1, Title = "Welcome to AuraMeme", Content = "Bài mẫu để thực hành GET, POST, PUT và DELETE.", Author = "AuraMeme", CreatedAt = new DateTime(2026, 10, 27, 0, 0, 0, DateTimeKind.Utc) },
            new Post { Id = 2, Title = "Deadline còn hai tiếng", Content = "Code đã chạy, giờ đến lúc viết tài liệu!", Author = "Campus Memer", CreatedAt = new DateTime(2026, 10, 27, 1, 0, 0, DateTimeKind.Utc) }
        );
    }
}
