IF DB_ID(N'Conversor_DB') IS NULL
BEGIN
    CREATE DATABASE [Conversor_DB];
END
GO

USE [Conversor_DB];
GO

IF OBJECT_ID(N'dbo.auditoria_proveedores', N'U') IS NULL
BEGIN
    CREATE TABLE dbo.auditoria_proveedores (
        id INT IDENTITY(1,1) NOT NULL PRIMARY KEY,
        cod_prov VARCHAR(50) NOT NULL,
        razon_social VARCHAR(255) NULL,
        marca VARCHAR(100) NULL,
        created_at DATETIME NOT NULL DEFAULT GETUTCDATE()
    );
    CREATE INDEX IX_auditoria_proveedores_cod_prov ON dbo.auditoria_proveedores(cod_prov);
    CREATE INDEX IX_auditoria_proveedores_marca ON dbo.auditoria_proveedores(marca);
END
GO

IF OBJECT_ID(N'dbo.auditoria_documentos', N'U') IS NULL
BEGIN
    CREATE TABLE dbo.auditoria_documentos (
        id INT IDENTITY(1,1) NOT NULL PRIMARY KEY,
        origen VARCHAR(50) NOT NULL,
        codigo_documento VARCHAR(100) NOT NULL,
        documento_relacionado VARCHAR(100) NULL,
        cegid_naturaleza VARCHAR(10) NULL,
        cegid_souche VARCHAR(20) NULL,
        cegid_numero VARCHAR(50) NULL,
        cegid_indice VARCHAR(20) NULL DEFAULT '0',
        ref_interna VARCHAR(100) NULL,
        ref_externa VARCHAR(100) NULL,
        ref_siguiente VARCHAR(150) NULL,
        proveedor_id INT NULL,
        deposito VARCHAR(50) NULL,
        fecha_documento DATETIME NULL,
        fecha_entrega_prevista DATETIME NULL,
        estado VARCHAR(50) NULL DEFAULT 'PENDIENTE',
        moneda VARCHAR(10) NULL,
        total_cantidad NUMERIC(18,4) NULL DEFAULT 0,
        total_importe NUMERIC(18,4) NULL DEFAULT 0,
        metadata_json VARCHAR(MAX) NULL,
        created_at DATETIME NOT NULL DEFAULT GETUTCDATE(),
        updated_at DATETIME NOT NULL DEFAULT GETUTCDATE(),
        CONSTRAINT UQ_auditoria_documento_origen_codigo UNIQUE (origen, codigo_documento),
        CONSTRAINT FK_auditoria_documentos_proveedor FOREIGN KEY (proveedor_id)
            REFERENCES dbo.auditoria_proveedores(id)
    );
    CREATE INDEX IX_auditoria_documentos_codigo ON dbo.auditoria_documentos(codigo_documento);
    CREATE INDEX IX_auditoria_documentos_cegid ON dbo.auditoria_documentos(cegid_naturaleza, cegid_souche, cegid_numero, cegid_indice);
    CREATE INDEX IX_auditoria_documentos_fecha_entrega ON dbo.auditoria_documentos(fecha_entrega_prevista);
    CREATE INDEX IX_auditoria_documentos_ref_siguiente ON dbo.auditoria_documentos(ref_siguiente);
END
GO

IF OBJECT_ID(N'dbo.auditoria_documento_lineas', N'U') IS NULL
BEGIN
    CREATE TABLE dbo.auditoria_documento_lineas (
        id INT IDENTITY(1,1) NOT NULL PRIMARY KEY,
        documento_id INT NOT NULL,
        numero_linea VARCHAR(50) NULL,
        numero_orden VARCHAR(50) NULL,
        ean VARCHAR(50) NULL,
        codigo_articulo VARCHAR(100) NULL,
        descripcion VARCHAR(255) NULL,
        talle VARCHAR(50) NULL,
        color VARCHAR(100) NULL,
        deposito VARCHAR(50) NULL,
        marca VARCHAR(100) NULL,
        genero VARCHAR(50) NULL,
        cantidad NUMERIC(18,4) NULL DEFAULT 0,
        cantidad_conciliada NUMERIC(18,4) NULL DEFAULT 0,
        precio_unitario NUMERIC(18,4) NULL,
        importe NUMERIC(18,4) NULL,
        estado VARCHAR(50) NULL DEFAULT 'PENDIENTE',
        pieza_precedente VARCHAR(150) NULL,
        pieza_origen VARCHAR(150) NULL,
        linea_precedente_key VARCHAR(150) NULL,
        linea_origen_key VARCHAR(150) NULL,
        metadata_json VARCHAR(MAX) NULL,
        created_at DATETIME NOT NULL DEFAULT GETUTCDATE(),
        CONSTRAINT FK_auditoria_lineas_documento FOREIGN KEY (documento_id)
            REFERENCES dbo.auditoria_documentos(id)
            ON DELETE CASCADE
    );
    CREATE INDEX IX_auditoria_lineas_documento ON dbo.auditoria_documento_lineas(documento_id);
    CREATE INDEX IX_auditoria_lineas_ean ON dbo.auditoria_documento_lineas(ean);
    CREATE INDEX IX_auditoria_lineas_articulo ON dbo.auditoria_documento_lineas(codigo_articulo);
    CREATE INDEX IX_auditoria_lineas_marca ON dbo.auditoria_documento_lineas(marca);
    CREATE INDEX IX_auditoria_lineas_deposito ON dbo.auditoria_documento_lineas(deposito);
    CREATE INDEX IX_auditoria_lineas_origen ON dbo.auditoria_documento_lineas(linea_origen_key);
    CREATE INDEX IX_auditoria_lineas_precedente ON dbo.auditoria_documento_lineas(linea_precedente_key);
END
GO

IF OBJECT_ID(N'dbo.auditoria_matches', N'U') IS NULL
BEGIN
    CREATE TABLE dbo.auditoria_matches (
        id INT IDENTITY(1,1) NOT NULL PRIMARY KEY,
        propuesta_linea_id INT NULL,
        pedido_linea_id INT NULL,
        notificacion_linea_id INT NULL,
        recepcion_linea_id INT NULL,
        ean VARCHAR(50) NULL,
        cantidad_pedida NUMERIC(18,4) NULL DEFAULT 0,
        cantidad_facturada NUMERIC(18,4) NULL DEFAULT 0,
        cantidad_notificada NUMERIC(18,4) NULL DEFAULT 0,
        cantidad_recibida NUMERIC(18,4) NULL DEFAULT 0,
        estado VARCHAR(50) NULL DEFAULT 'PENDIENTE',
        regla VARCHAR(100) NULL,
        confianza NUMERIC(5,2) NULL,
        observacion VARCHAR(MAX) NULL,
        created_at DATETIME NOT NULL DEFAULT GETUTCDATE()
    );
    CREATE INDEX IX_auditoria_matches_ean ON dbo.auditoria_matches(ean);
    CREATE INDEX IX_auditoria_matches_estado ON dbo.auditoria_matches(estado);
END
GO
