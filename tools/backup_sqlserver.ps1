param(
    [string]$ContainerName = "mssql_server",
    [string]$DatabaseName = "Conversor_DB",
    [string]$BackupDir = ".\backups"
)

$ErrorActionPreference = "Stop"

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
$rootEnv = Join-Path $repoRoot ".env"

if (-not (Test-Path $rootEnv)) {
    throw "No encontre .env en la raiz del proyecto: $rootEnv"
}

$dbPassword = (Get-Content $rootEnv | Where-Object { $_ -match "^\s*DB_PASSWORD\s*=" } | Select-Object -First 1) -replace "^\s*DB_PASSWORD\s*=\s*", ""
if ([string]::IsNullOrWhiteSpace($dbPassword)) {
    throw "DB_PASSWORD esta vacio o no existe en .env"
}

$timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
$backupName = "$DatabaseName`_$timestamp.bak"
$containerBackupPath = "/var/opt/mssql/backup/$backupName"
$localBackupDir = Join-Path $repoRoot $BackupDir
$localBackupPath = Join-Path $localBackupDir $backupName

New-Item -ItemType Directory -Force -Path $localBackupDir | Out-Null

docker exec $ContainerName mkdir -p /var/opt/mssql/backup | Out-Null
docker exec $ContainerName /opt/mssql-tools18/bin/sqlcmd `
    -S localhost `
    -U sa `
    -P $dbPassword `
    -C `
    -Q "BACKUP DATABASE [$DatabaseName] TO DISK = N'$containerBackupPath' WITH INIT, COMPRESSION, STATS = 10"

docker cp "$ContainerName`:$containerBackupPath" $localBackupPath

Write-Host "Backup creado: $localBackupPath"
