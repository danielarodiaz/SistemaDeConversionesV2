import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text

from database import engine


CREATE_TABLES = [
    """
    IF OBJECT_ID('dbo.abm_articulos_lotes', 'U') IS NULL
    BEGIN
        CREATE TABLE dbo.abm_articulos_lotes (
            id INT IDENTITY(1,1) NOT NULL PRIMARY KEY,
            uuid VARCHAR(50) NOT NULL,
            descripcion VARCHAR(255) NULL,
            estado VARCHAR(50) NULL CONSTRAINT DF_abm_articulos_lotes_estado DEFAULT 'activo',
            created_at DATETIME NOT NULL CONSTRAINT DF_abm_articulos_lotes_created_at DEFAULT GETDATE(),
            CONSTRAINT uq_abm_articulos_lotes_uuid UNIQUE (uuid)
        )
    END
    """,
    """
    IF OBJECT_ID('dbo.proveedor_marca', 'U') IS NULL
    BEGIN
        CREATE TABLE dbo.proveedor_marca (
            id INT IDENTITY(1,1) NOT NULL PRIMARY KEY,
            proveedor_id INT NOT NULL,
            marca_id INT NOT NULL,
            activo INT NOT NULL CONSTRAINT DF_proveedor_marca_activo DEFAULT 1,
            created_at DATETIME NOT NULL CONSTRAINT DF_proveedor_marca_created_at DEFAULT GETDATE(),
            CONSTRAINT FK_proveedor_marca_proveedor FOREIGN KEY (proveedor_id) REFERENCES dbo.proveedores(id),
            CONSTRAINT FK_proveedor_marca_marca FOREIGN KEY (marca_id) REFERENCES dbo.marcas(id),
            CONSTRAINT uq_proveedor_marca UNIQUE (proveedor_id, marca_id)
        )
    END
    """,
]

ALTERS = [
    ("articulos", "sector", "VARCHAR(50) NULL CONSTRAINT DF_articulos_sector DEFAULT 'base'"),
    ("articulos", "estado", "VARCHAR(50) NULL CONSTRAINT DF_articulos_estado DEFAULT 'borrador'"),
    ("articulos", "promo", "VARCHAR(50) NULL"),
    ("articulos", "descripcionPromo", "VARCHAR(255) NULL"),
    ("articulos", "lote_id", "INT NULL"),
    ("articulosComplementarios", "sector", "VARCHAR(50) NULL CONSTRAINT DF_articulosComplementarios_sector DEFAULT 'base'"),
    ("articulosComplementarios", "estado", "VARCHAR(50) NULL CONSTRAINT DF_articulosComplementarios_estado DEFAULT 'borrador'"),
    ("articulosComplementarios", "lote_id", "INT NULL"),
    ("preciosCompra", "lote_id", "INT NULL"),
    ("preciosVenta", "lote_id", "INT NULL"),
]

FOREIGN_KEYS = [
    ("articulos", "FK_articulos_abm_articulos_lotes", "lote_id"),
    ("articulosComplementarios", "FK_articulosComplementarios_abm_articulos_lotes", "lote_id"),
    ("preciosCompra", "FK_preciosCompra_abm_articulos_lotes", "lote_id"),
    ("preciosVenta", "FK_preciosVenta_abm_articulos_lotes", "lote_id"),
]


def agregar_columna_si_no_existe(conn, tabla, columna, definicion):
    sql = f"""
    IF COL_LENGTH('{tabla}', '{columna}') IS NULL
    BEGIN
        ALTER TABLE [{tabla}] ADD [{columna}] {definicion}
    END
    """
    conn.execute(text(sql))
    print(f"OK {tabla}.{columna}")


def agregar_fk_lote_si_no_existe(conn, tabla, constraint, columna):
    sql = f"""
    IF NOT EXISTS (SELECT 1 FROM sys.foreign_keys WHERE name = '{constraint}')
    BEGIN
        ALTER TABLE [{tabla}] WITH CHECK
        ADD CONSTRAINT [{constraint}] FOREIGN KEY ([{columna}]) REFERENCES dbo.abm_articulos_lotes(id)
    END
    """
    conn.execute(text(sql))
    print(f"OK {tabla}.{constraint}")


def migrar_lote_legacy(conn):
    sql = """
    IF NOT EXISTS (SELECT 1 FROM dbo.abm_articulos_lotes WHERE uuid = 'legacy-default')
    BEGIN
        INSERT INTO dbo.abm_articulos_lotes (uuid, descripcion, estado)
        VALUES ('legacy-default', 'Lote legacy para registros previos al manejo multiusuario', 'activo')
    END

    DECLARE @legacy_id INT = (SELECT TOP 1 id FROM dbo.abm_articulos_lotes WHERE uuid = 'legacy-default')

    UPDATE dbo.articulos SET lote_id = @legacy_id WHERE lote_id IS NULL
    UPDATE dbo.articulosComplementarios SET lote_id = @legacy_id WHERE lote_id IS NULL
    UPDATE dbo.preciosCompra SET lote_id = @legacy_id WHERE lote_id IS NULL
    UPDATE dbo.preciosVenta SET lote_id = @legacy_id WHERE lote_id IS NULL
    """
    conn.execute(text(sql))
    print("OK lote legacy")


def main():
    with engine.begin() as conn:
        for idx, sql in enumerate(CREATE_TABLES, start=1):
            conn.execute(text(sql))
            print(f"OK create table {idx}")
        for tabla, columna, definicion in ALTERS:
            agregar_columna_si_no_existe(conn, tabla, columna, definicion)
        migrar_lote_legacy(conn)
        for tabla, constraint, columna in FOREIGN_KEYS:
            agregar_fk_lote_si_no_existe(conn, tabla, constraint, columna)


if __name__ == "__main__":
    main()
