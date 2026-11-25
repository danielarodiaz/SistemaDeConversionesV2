# Recuperacion de Docker y SQL Server local

Este proyecto usa SQL Server en Docker. La parte persistente de la base esta en el volumen Docker `sql_server_data`, definido en `docker-compose.yml`.

## Que se puede recuperar

- El codigo del sistema, los CSV semilla, `uploads` y `outputs` siguen en carpetas normales del proyecto.
- La estructura de tablas se puede regenerar desde `backend/models.py`.
- Los catalogos y datos base se pueden recargar con `backend/seed_db.py`.
- El estado exacto anterior de la base solo se puede recuperar si existe un backup `.bak`, `.bacpac`, `.mdf/.ldf` o si el volumen Docker todavia existe.

## Recrear la base cuando Docker vuelva a funcionar

Desde la raiz del proyecto:

```powershell
docker compose up -d
```

Luego inicializar tablas y datos base:

```powershell
cd backend
python seed_db.py
```

## Backup recomendado

Crear un backup de `Conversor_DB`:

```powershell
.\tools\backup_sqlserver.ps1
```

El archivo queda en `backups\Conversor_DB_YYYYMMDD_HHMMSS.bak`.

## Restaurar un backup

Con el contenedor levantado:

```powershell
.\tools\restore_sqlserver.ps1 -BackupPath .\backups\Conversor_DB_YYYYMMDD_HHMMSS.bak
```

## Regla practica

Un volumen Docker no es un backup. Es persistencia local para que el contenedor pueda apagarse y prenderse sin perder datos, pero si se borra el volumen, se resetea Docker Desktop, se purgan datos, o se rompe la VM de WSL, la base desaparece salvo que tengas un backup fuera de Docker.
