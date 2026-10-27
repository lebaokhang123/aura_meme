using AuraMeme.Api.Data;
using Microsoft.EntityFrameworkCore;

var builder = WebApplication.CreateBuilder(args);

builder.Services.AddControllers();
builder.Services.AddOpenApi();

// Keep the SQLite file in the API project, regardless of the shell directory.
var connection = new Microsoft.Data.Sqlite.SqliteConnectionStringBuilder(
    builder.Configuration.GetConnectionString("DefaultConnection"));
connection.DataSource = Path.GetFullPath(connection.DataSource, builder.Environment.ContentRootPath);
builder.Services.AddDbContext<AppDbContext>(options => options.UseSqlite(connection.ToString()));

builder.Services.AddCors(options => options.AddPolicy("FrontendDev", policy => policy
    .WithOrigins("http://localhost:5173", "http://127.0.0.1:5173",
                 "http://localhost:5174", "http://127.0.0.1:5174")
    .WithMethods("GET", "POST", "PUT", "DELETE")
    .WithHeaders("Content-Type")));

var app = builder.Build();

if (app.Environment.IsDevelopment())
{
    app.MapOpenApi();
    app.UseCors("FrontendDev");
}

app.MapControllers();

app.Run();
