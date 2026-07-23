import os

def patch_vigil():
    vigil_dir = 'vigil365/src/M365SecurityDashboard.Api'
    if not os.path.exists(vigil_dir):
        print("-> Vigil365 directory not found, skipping patch.")
        return

    # 1. Update vite.config.ts to use relative base path (base: "./") for subpath hosting (/vigil)
    vite_config_path = 'vigil365/src/m365-security-dashboard-client/vite.config.ts'
    if os.path.exists(vite_config_path):
        with open(vite_config_path, 'r') as f:
            content = f.read()
        if 'base:' not in content:
            target = 'export default defineConfig({'
            replacement = 'export default defineConfig({\n  base: "./",'
            content = content.replace(target, replacement)
            with open(vite_config_path, 'w') as f:
                f.write(content)
            print("-> Set relative base path (base: './') in vite.config.ts.")

    # 2. Patch main.tsx so apiBase points to /vigil when hosted under /vigil
    main_tsx_path = 'vigil365/src/m365-security-dashboard-client/src/main.tsx'
    if os.path.exists(main_tsx_path):
        with open(main_tsx_path, 'r') as f:
            content = f.read()
        target_apibase = 'const apiBase = import.meta.env.VITE_API_BASE ?? "";'
        replacement_apibase = 'const apiBase = import.meta.env.VITE_API_BASE ?? (window.location.pathname.startsWith("/vigil") ? "/vigil" : "");'
        if target_apibase in content:
            content = content.replace(target_apibase, replacement_apibase)
            with open(main_tsx_path, 'w') as f:
                f.write(content)
            print("-> Set dynamic apiBase (/vigil) in main.tsx.")

    # 3. Update csproj to include Microsoft.EntityFrameworkCore.Sqlite
    csproj_path = os.path.join(vigil_dir, 'M365SecurityDashboard.Api.csproj')
    if os.path.exists(csproj_path):
        with open(csproj_path, 'r') as f:
            content = f.read()
        if 'Microsoft.EntityFrameworkCore.Sqlite' not in content:
            target = '<PackageReference Include="Microsoft.EntityFrameworkCore.SqlServer" Version="8.0.11" />'
            replacement = target + '\n    <PackageReference Include="Microsoft.EntityFrameworkCore.Sqlite" Version="8.0.11" />'
            content = content.replace(target, replacement)
            with open(csproj_path, 'w') as f:
                f.write(content)
            print("-> Added SQLite EF Core package to csproj.")

    # 4. Fix AppDbContext.cs HasColumnType("nvarchar(max)") and add DateTimeOffset string conversion for SQLite
    appdbcontext_path = os.path.join(vigil_dir, 'Data/AppDbContext.cs')
    if os.path.exists(appdbcontext_path):
        with open(appdbcontext_path, 'r') as f:
            content = f.read()
        if 'HasColumnType("nvarchar(max)")' in content:
            content = content.replace('.HasColumnType("nvarchar(max)");', ';')
        
        if 'ConfigureConventions' not in content:
            target_class = 'public sealed class AppDbContext(DbContextOptions<AppDbContext> options) : DbContext(options)\n{'
            replacement_class = target_class + """
    protected override void ConfigureConventions(ModelConfigurationBuilder configurationBuilder)
    {
        configurationBuilder.Properties<DateTimeOffset>().HaveConversion<string>();
        configurationBuilder.Properties<DateTimeOffset?>().HaveConversion<string>();
    }
"""
            content = content.replace(target_class, replacement_class)

        with open(appdbcontext_path, 'w') as f:
            f.write(content)
        print("-> Added DateTimeOffset string conversion to AppDbContext.cs for SQLite compatibility.")

    # 5. Update Program.cs for dual SQLite / SQL Server support and in-memory trends grouping
    program_path = os.path.join(vigil_dir, 'Program.cs')
    if os.path.exists(program_path):
        with open(program_path, 'r') as f:
            content = f.read()
        
        target_db = """builder.Services.AddDbContext<AppDbContext>(options =>
    options.UseSqlServer(builder.Configuration.GetConnectionString("DefaultConnection")));"""
        
        replacement_db = """var connStr = builder.Configuration.GetConnectionString("DefaultConnection") ?? "";
builder.Services.AddDbContext<AppDbContext>(options =>
{
    if (connStr.Contains(".db") || connStr.Contains("Data Source="))
        options.UseSqlite(connStr);
    else
        options.UseSqlServer(connStr);
});"""

        if target_db in content:
            content = content.replace(target_db, replacement_db)

        target_ensure = "db.Database.ExecuteSqlRaw(AlertingSchema.EnsureTablesSql);"
        replacement_ensure = """try {
        if (!connStr.Contains(".db") && !connStr.Contains("Data Source="))
            db.Database.ExecuteSqlRaw(AlertingSchema.EnsureTablesSql);
    } catch {}"""

        if target_ensure in content and "try {" not in content:
            content = content.replace(target_ensure, replacement_ensure)

        # Patch trends GroupBy in Program.cs
        target_trends = """    var trends = await db.SecurityAlerts.AsNoTracking()
        .Where(a => a.DetectedAt >= since)
        .GroupBy(a => new { Date = a.DetectedAt.Date, a.Severity })
        .Select(g => new { date = g.Key.Date, severity = g.Key.Severity.ToString(), count = g.Count() })
        .OrderBy(x => x.date)
        .ToListAsync(ct);"""

        replacement_trends = """    var trendsRaw = await db.SecurityAlerts.AsNoTracking()
        .Where(a => a.DetectedAt >= since)
        .ToListAsync(ct);

    var trends = trendsRaw
        .GroupBy(a => new { Date = a.DetectedAt.Date, a.Severity })
        .Select(g => new { date = g.Key.Date, severity = g.Key.Severity.ToString(), count = g.Count() })
        .OrderBy(x => x.date)
        .ToList();"""

        if target_trends in content:
            content = content.replace(target_trends, replacement_trends)

        with open(program_path, 'w') as f:
            f.write(content)
        print("-> Patched Program.cs for SQLite compatibility & trends grouping.")

if __name__ == '__main__':
    patch_vigil()
