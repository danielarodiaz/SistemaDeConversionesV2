param(
    [Parameter(Mandatory = $true)]
    [string]$BackupPath,
    [string]$ContainerName = "mssql_server",
    [string]$DatabaseName = "Conversor_DB"
)

$ErrorActionPreference = "Stop"

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
$rootEnv = Join-Path $repoRoot ".env"
$resolvedBackup = Resolve-Path $BackupPath
$backupName = Split-Path $resolvedBackup -Leaf
$containerBackupPath = "/var/opt/mssql/backup/$backupName"

if (-not (Test-Path $rootEnv)) {
    throw "No encontre .env en la raiz del proyecto: $rootEnv"
}

$dbPassword = (Get-Content $rootEnv | Where-Object { $_ -match "^\s*DB_PASSWORD\s*=" } | Select-Object -First 1) -replace "^\s*DB_PASSWORD\s*=\s*", ""
if ([string]::IsNullOrWhiteSpace($dbPassword)) {
    throw "DB_PASSWORD esta vacio o no existe en .env"
}

docker exec $ContainerName mkdir -p /var/opt/mssql/backup | Out-Null
docker cp $resolvedBackup "$ContainerName`:$containerBackupPath"

$fileList = docker exec $ContainerName /opt/mssql-tools18/bin/sqlcmd `
    -S localhost `
    -U sa `
    -P $dbPassword `
    -C `
    -h -1 `
    -W `
    -Q "RESTORE FILELISTONLY FROM DISK = N'$containerBackupPath'"

$logicalNames = $fileList |
    Where-Object { $_ -and $_ -notmatch "^\s*$" -and $_ -notmatch "rows affected" } |
    ForEach-Object { ($_ -split "\s+")[0] } |
    Select-Object -First 2

if ($logicalNames.Count -lt 2) {
    throw "No pude detectar los nombres logicos del backup."
}

$dataLogicalName = $logicalNames[0]
$logLogicalName = $logicalNames[1]

docker exec $ContainerName /opt/mssql-tools18/bin/sqlcmd `
    -S localhost `
    -U sa `
    -P $dbPassword `
    -C `
    -Q "IF DB_ID(N'$DatabaseName') IS NOT NULL BEGIN ALTER DATABASE [$DatabaseName] SET SINGLE_USER WITH ROLLBACK IMMEDIATE; END; RESTORE DATABASE [$DatabaseName] FROM DISK = N'$containerBackupPath' WITH REPLACE, MOVE N'$dataLogicalName' TO N'/var/opt/mssql/data/$DatabaseName.mdf', MOVE N'$logLogicalName' TO N'/var/opt/mssql/data/$DatabaseName`_log.ldf'; ALTER DATABASE [$DatabaseName] SET MULTI_USER;"

Write-Host "Backup restaurado en $DatabaseName desde: $resolvedBackup"
