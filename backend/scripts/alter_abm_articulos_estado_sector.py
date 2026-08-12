import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text

from database import engine


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
        for tabla, columna, definicion in ALTERS:
            agregar_columna_si_no_existe(conn, tabla, columna, definicion)


if __name__ == "__main__":
    main()
