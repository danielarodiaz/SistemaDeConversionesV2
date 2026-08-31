import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text

from database import engine


CREATE_TABLES = [
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
    ("articulosComplementarios", "sector", "VARCHAR(50) NULL CONSTRAINT DF_articulosComplementarios_sector DEFAULT 'base'"),
    ("articulosComplementarios", "estado", "VARCHAR(50) NULL CONSTRAINT DF_articulosComplementarios_estado DEFAULT 'borrador'"),
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


def main():
    with engine.begin() as conn:
        for sql in CREATE_TABLES:
            conn.execute(text(sql))
            print("OK dbo.proveedor_marca")
        for tabla, columna, definicion in ALTERS:
            agregar_columna_si_no_existe(conn, tabla, columna, definicion)


if __name__ == "__main__":
    main()
