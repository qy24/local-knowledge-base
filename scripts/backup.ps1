# 本地知识库系统 - 备份脚本（Windows / PowerShell）
# 备份内容：SQLite 数据库 + 文档原件 + 向量库/图谱本地持久化文件
# 用法：.\scripts\backup.ps1 [-DataDir ..\backend\data] [-OutDir ..\backups]
param(
    [string]$DataDir = (Join-Path $PSScriptRoot '..\backend\data'),
    [string]$OutDir = (Join-Path $PSScriptRoot '..\backups')
)

$ErrorActionPreference = 'Stop'
$stamp = Get-Date -Format 'yyyyMMdd_HHmmss'
$outFile = Join-Path $OutDir "kb_backup_$stamp.zip"

if (-not (Test-Path $DataDir)) { Write-Error "数据目录不存在: $DataDir"; exit 1 }
New-Item -ItemType Directory -Force -Path $OutDir | Out-Null

Write-Host "备份中: $DataDir -> $outFile"

# 使用 .NET ZipFile 压缩（无需外部工具）
Add-Type -AssemblyName System.IO.Compression.FileSystem
$tmp = Join-Path $env:TEMP "kb_backup_$stamp"
if (Test-Path $tmp) { Remove-Item $tmp -Recurse -Force }
Copy-Item $DataDir $tmp -Recurse -Force
[System.IO.Compression.ZipFile]::CreateFromDirectory($tmp, $outFile, [System.IO.Compression.CompressionLevel]::Optimal, $false)
Remove-Item $tmp -Recurse -Force

$size = [math]::Round((Get-Item $outFile).Length / 1MB, 2)
Write-Host "备份完成: $outFile ($size MB)"

# 生产组件（Qdrant / Neo4j / PostgreSQL）备份命令示例：
#   PostgreSQL:  pg_dump -h localhost -U kb_user kb > kb_pg_$stamp.sql
#   Qdrant:      请求 POST /collections/kb_chunks/snapshot
#   Neo4j:       neo4j-admin database dump neo4j --to-path=...
# 建议结合 Windows 任务计划程序每日执行本脚本
