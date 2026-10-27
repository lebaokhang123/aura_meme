using AuraMeme.Api.Data;
using AuraMeme.Api.Models;
using Microsoft.AspNetCore.Mvc;
using Microsoft.EntityFrameworkCore;

namespace AuraMeme.Api.Controllers;

[ApiController]
[Route("api/posts")]
public class PostsController(AppDbContext db) : ControllerBase
{
    [HttpGet]
    public async Task<ActionResult<List<Post>>> GetPosts()
    {
        return await db.Posts.AsNoTracking().OrderByDescending(post => post.Id).ToListAsync();
    }

    [HttpGet("{id:int}")]
    public async Task<ActionResult<Post>> GetPost(int id)
    {
        var post = await db.Posts.AsNoTracking().FirstOrDefaultAsync(post => post.Id == id);
        if (post is null) return NotFound();
        return post;
    }

    [HttpPost]
    public async Task<ActionResult<Post>> CreatePost(Post input)
    {
        // Only copy editable fields; Id and CreatedAt belong to the server.
        var post = new Post
        {
            Title = input.Title.Trim(),
            Content = input.Content.Trim(),
            Author = input.Author.Trim()
        };
        db.Posts.Add(post);
        await db.SaveChangesAsync();
        return CreatedAtAction(nameof(GetPost), new { id = post.Id }, post);
    }

    [HttpPut("{id:int}")]
    public async Task<IActionResult> UpdatePost(int id, Post input)
    {
        var post = await db.Posts.FindAsync(id);
        if (post is null) return NotFound();
        post.Title = input.Title.Trim();
        post.Content = input.Content.Trim();
        post.Author = input.Author.Trim();
        await db.SaveChangesAsync();
        return NoContent();
    }

    [HttpDelete("{id:int}")]
    public async Task<IActionResult> DeletePost(int id)
    {
        var post = await db.Posts.FindAsync(id);
        if (post is null) return NotFound();
        db.Posts.Remove(post);
        await db.SaveChangesAsync();
        return NoContent();
    }
}
