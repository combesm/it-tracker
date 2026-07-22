import os

def patch_vigil():
    vigil_dir = 'vigil365/src/M365SecurityDashboard.Api'
    if not os.path.exists(vigil_dir):
        print("-> Vigil365 directory not found, skipping patch.")
        return

    # 1. Update csproj to include Microsoft.EntityFrameworkCore.Sqlite
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

    # 2. Fix AppDbContext.cs HasColumnType("nvarchar(max)") for SQLite
    appdbcontext_path = os.path.join(vigil_dir, 'Data/AppDbContext.cs')
    if os.path.exists(appdbcontext_path):
        with open(appdbcontext_path, 'r') as f:
            content = f.read()
        if 'HasColumnType("nvarchar(max)")' in content:
            content = content.replace('.HasColumnType("nvarchar(max)");', ';')
            with open(appdbcontext_path, 'w') as f:
                f.write(content)
            print("-> Removed T-SQL nvarchar(max) from AppDbContext.cs for SQLite compatibility.")

    # 3. Update Program.cs for dual SQLite / SQL Server support
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

        with open(program_path, 'w') as f:
            f.write(content)
        print("-> Patched Program.cs for SQLite compatibility.")

if __name__ == '__main__':
    patch_vigil()
