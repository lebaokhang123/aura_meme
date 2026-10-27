using System.ComponentModel.DataAnnotations;

namespace AuraMeme.Api.Models;

public class Post
{
    public int Id { get; set; }

    [Required, StringLength(200)]
    public string Title { get; set; } = string.Empty;

    [Required, StringLength(10000)]
    public string Content { get; set; } = string.Empty;

    [Required, StringLength(80)]
    public string Author { get; set; } = "Anonymous";

    public DateTime CreatedAt { get; set; } = DateTime.UtcNow;
}
