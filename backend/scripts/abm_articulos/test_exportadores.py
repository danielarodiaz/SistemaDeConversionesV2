from types import SimpleNamespace

from backend.scripts.abm_articulos.exportadores import (
    ITCC_HEADER,
    ITEC_HEADER,
    LCOC_HEADER,
    LPMC_HEADER,
    fila_comp,
    fila_itec,
)


def test_columnas_exportadores_abm():
    articulo = SimpleNamespace(
        codigo="ART1",
        descripcion="Articulo prueba",
        tipoProducto="TP",
        descripcionProducto="Tipo",
        grupo="GR",
        descripciongrupo="Grupo",
        grupoSAP="SAP",
        descripcionGrupoSAP="Grupo SAP",
        marca="M",
        descripcionMarca="Marca",
        genero="G",
        descripcionGenero="Genero",
        silueta="S",
        descripcionSilueta="Silueta",
        uso="U",
        descripcionUso="Uso",
        promo="P",
        descripcionPromo="Promo",
        codigoBarra="7790001",
        talle="T",
        descripcionTalle="Talle",
        valorTalle="42",
        descripcionValorTalle="42",
        color="NEG",
        descripcionColor="Negro",
        valor="001",
        descripcionValor="Negro",
        nombreProveedor="Proveedor",
        codigoMedida="CM",
        tipoMedida="Numerico",
        medida="AR",
        codigoGen="H",
        genero2="Hombre",
        canal="M",
        codigoCapsula="CAP",
        descripcionCapsula="Capsula",
        codigoDivision="DIV",
        descripcionDivision="Division",
        codigoTemporada="TEMP",
        descripcionTemporada="Temporada",
    )
    complementario = SimpleNamespace(
        codigo="ART1",
        codigoEdad="AD",
        codigoMaterial="MAT",
        codigoSegmentacionProveedor="SP",
        codigoSegmentacionMarathon="SM",
        codigoVidriera="V",
        codigoAnio="2026",
        codigoBarra="7790001",
        objetivoGeneral="OBJ",
    )

    assert len(fila_itec(articulo)) == len(ITEC_HEADER)
    art_row = fila_itec(articulo)
    assert art_row[ITEC_HEADER.index("Grupo")] == ""
    assert art_row[ITEC_HEADER.index("Desc_Grupo")] == ""
    assert art_row[ITEC_HEADER.index("CANAL")] == ""
    assert art_row[ITEC_HEADER.index("descripcionCapsula")] == ""
    assert art_row[ITEC_HEADER.index("descripcionDivision")] == ""
    assert art_row[ITEC_HEADER.index("descripcionTemporada")] == ""
    assert len(["LCOC1_", "PERMA", "LCMAR", "1,00", "ART1"]) == len(LCOC_HEADER)
    assert len(["LPMC1_", "ART1", "2,00"]) == len(LPMC_HEADER)
    assert len(fila_comp(complementario, "CEGID1")) == len(ITCC_HEADER)
