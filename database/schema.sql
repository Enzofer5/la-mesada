-- =====================================================================================
-- LA MESADA · Sistema de Gestión Agrícola
-- Esquema de base de datos MySQL 8 / MariaDB 10.6+   (generado 29/09/2026)
--
-- Diseño multi-empresa: todas las tablas de negocio tienen empresa_id.
-- Integridad referencial con FOREIGN KEY (RESTRICT por defecto; CASCADE en renglones).
-- Uso:
--   mysql -u root -p -e "CREATE DATABASE la_mesada CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
--   mysql -u root -p la_mesada < database/schema.sql
-- Luego:  flask --app run seed-demo     (datos de demostración, opcional)
-- =====================================================================================

SET NAMES utf8mb4;
SET FOREIGN_KEY_CHECKS = 0;

DROP TABLE IF EXISTS `uso_maquinaria`;
DROP TABLE IF EXISTS `cosechas`;
DROP TABLE IF EXISTS `combustibles`;
DROP TABLE IF EXISTS `trabajos`;
DROP TABLE IF EXISTS `siembras`;
DROP TABLE IF EXISTS `riegos`;
DROP TABLE IF EXISTS `pagos_proveedores`;
DROP TABLE IF EXISTS `pagos_empleados`;
DROP TABLE IF EXISTS `movimientos_inventario`;
DROP TABLE IF EXISTS `maquinaria`;
DROP TABLE IF EXISTS `ingresos`;
DROP TABLE IF EXISTS `gastos`;
DROP TABLE IF EXISTS `detalle_ventas`;
DROP TABLE IF EXISTS `detalle_compras`;
DROP TABLE IF EXISTS `caminos_lote`;
DROP TABLE IF EXISTS `aplicaciones_fertilizantes`;
DROP TABLE IF EXISTS `aplicaciones_agroquimicos`;
DROP TABLE IF EXISTS `actividades_cultivo`;
DROP TABLE IF EXISTS `ventas`;
DROP TABLE IF EXISTS `usuario_fincas`;
DROP TABLE IF EXISTS `lotes`;
DROP TABLE IF EXISTS `inventario`;
DROP TABLE IF EXISTS `empleados`;
DROP TABLE IF EXISTS `documentos`;
DROP TABLE IF EXISTS `cuentas_pagar`;
DROP TABLE IF EXISTS `compras`;
DROP TABLE IF EXISTS `alertas`;
DROP TABLE IF EXISTS `insumos`;
DROP TABLE IF EXISTS `historial_actividades`;
DROP TABLE IF EXISTS `fincas`;
DROP TABLE IF EXISTS `cultivos`;
DROP TABLE IF EXISTS `usuarios`;
DROP TABLE IF EXISTS `unidades_medida`;
DROP TABLE IF EXISTS `proveedores`;
DROP TABLE IF EXISTS `clientes`;
DROP TABLE IF EXISTS `categorias_gasto`;
DROP TABLE IF EXISTS `campanas`;
DROP TABLE IF EXISTS `roles`;
DROP TABLE IF EXISTS `empresas`;
DROP VIEW IF EXISTS `produccion`;

-- ----------------------------------------------------------------- empresas
CREATE TABLE empresas (
	id INTEGER NOT NULL AUTO_INCREMENT, 
	nombre VARCHAR(120) NOT NULL, 
	slug VARCHAR(60) NOT NULL, 
	cuit VARCHAR(13), 
	telefono VARCHAR(30), 
	email VARCHAR(120), 
	direccion VARCHAR(150), 
	localidad VARCHAR(80), 
	logo VARCHAR(255), 
	datos_demo BOOL NOT NULL, 
	activa BOOL NOT NULL, 
	creado_en DATETIME NOT NULL, 
	actualizado_en DATETIME NOT NULL, 
	PRIMARY KEY (id), 
	UNIQUE (slug)
)
ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ----------------------------------------------------------------- roles
CREATE TABLE roles (
	id INTEGER NOT NULL AUTO_INCREMENT, 
	codigo VARCHAR(20) NOT NULL, 
	nombre VARCHAR(50) NOT NULL, 
	PRIMARY KEY (id), 
	UNIQUE (codigo)
)
ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ----------------------------------------------------------------- campanas
CREATE TABLE campanas (
	id INTEGER NOT NULL AUTO_INCREMENT, 
	nombre VARCHAR(40) NOT NULL, 
	fecha_inicio DATE NOT NULL, 
	fecha_fin DATE NOT NULL, 
	estado VARCHAR(12) NOT NULL, 
	observaciones TEXT, 
	empresa_id INTEGER NOT NULL, 
	creado_en DATETIME NOT NULL, 
	actualizado_en DATETIME NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT uq_campana_empresa_nombre UNIQUE (empresa_id, nombre), 
	FOREIGN KEY(empresa_id) REFERENCES empresas (id)
)
ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
CREATE INDEX ix_campanas_empresa_id ON campanas (empresa_id);

-- ----------------------------------------------------------------- categorias_gasto
CREATE TABLE categorias_gasto (
	id INTEGER NOT NULL AUTO_INCREMENT, 
	codigo VARCHAR(30) NOT NULL, 
	nombre VARCHAR(60) NOT NULL, 
	orden INTEGER NOT NULL, 
	activa BOOL NOT NULL, 
	empresa_id INTEGER NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT uq_categoria_empresa_codigo UNIQUE (empresa_id, codigo), 
	FOREIGN KEY(empresa_id) REFERENCES empresas (id)
)
ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
CREATE INDEX ix_categorias_gasto_empresa_id ON categorias_gasto (empresa_id);

-- ----------------------------------------------------------------- clientes
CREATE TABLE clientes (
	id INTEGER NOT NULL AUTO_INCREMENT, 
	nombre VARCHAR(120) NOT NULL, 
	cuit VARCHAR(13), 
	dni VARCHAR(15), 
	telefono VARCHAR(30), 
	email VARCHAR(120), 
	direccion VARCHAR(150), 
	localidad VARCHAR(80), 
	tipo VARCHAR(20) NOT NULL, 
	estado VARCHAR(12) NOT NULL, 
	observaciones TEXT, 
	empresa_id INTEGER NOT NULL, 
	creado_en DATETIME NOT NULL, 
	actualizado_en DATETIME NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT uq_cliente_empresa_cuit UNIQUE (empresa_id, cuit), 
	FOREIGN KEY(empresa_id) REFERENCES empresas (id)
)
ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
CREATE INDEX ix_clientes_empresa_id ON clientes (empresa_id);
CREATE INDEX ix_clientes_nombre ON clientes (nombre);

-- ----------------------------------------------------------------- proveedores
CREATE TABLE proveedores (
	id INTEGER NOT NULL AUTO_INCREMENT, 
	razon_social VARCHAR(120) NOT NULL, 
	cuit VARCHAR(13), 
	telefono VARCHAR(30), 
	email VARCHAR(120), 
	direccion VARCHAR(150), 
	contacto VARCHAR(80), 
	tipo VARCHAR(20) NOT NULL, 
	estado VARCHAR(12) NOT NULL, 
	observaciones TEXT, 
	empresa_id INTEGER NOT NULL, 
	creado_en DATETIME NOT NULL, 
	actualizado_en DATETIME NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT uq_proveedor_empresa_cuit UNIQUE (empresa_id, cuit), 
	FOREIGN KEY(empresa_id) REFERENCES empresas (id)
)
ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
CREATE INDEX ix_proveedores_empresa_id ON proveedores (empresa_id);
CREATE INDEX ix_proveedores_razon_social ON proveedores (razon_social);

-- ----------------------------------------------------------------- unidades_medida
CREATE TABLE unidades_medida (
	id INTEGER NOT NULL AUTO_INCREMENT, 
	nombre VARCHAR(40) NOT NULL, 
	abreviatura VARCHAR(12) NOT NULL, 
	tipo VARCHAR(10) NOT NULL, 
	factor_base NUMERIC(14, 4) NOT NULL, 
	activa BOOL NOT NULL, 
	empresa_id INTEGER NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT uq_unidad_empresa_nombre UNIQUE (empresa_id, nombre), 
	FOREIGN KEY(empresa_id) REFERENCES empresas (id)
)
ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
CREATE INDEX ix_unidades_medida_empresa_id ON unidades_medida (empresa_id);

-- ----------------------------------------------------------------- usuarios
CREATE TABLE usuarios (
	id INTEGER NOT NULL AUTO_INCREMENT, 
	empresa_id INTEGER, 
	rol_id INTEGER NOT NULL, 
	nombre VARCHAR(100) NOT NULL, 
	email VARCHAR(120) NOT NULL, 
	password_hash VARCHAR(255) NOT NULL, 
	activo BOOL NOT NULL, 
	ultimo_acceso DATETIME, 
	intentos_fallidos INTEGER NOT NULL, 
	bloqueado_hasta DATETIME, 
	token_sesion VARCHAR(32) NOT NULL, 
	creado_en DATETIME NOT NULL, 
	actualizado_en DATETIME NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(empresa_id) REFERENCES empresas (id), 
	FOREIGN KEY(rol_id) REFERENCES roles (id), 
	UNIQUE (email)
)
ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
CREATE INDEX ix_usuarios_empresa_id ON usuarios (empresa_id);

-- ----------------------------------------------------------------- cultivos
CREATE TABLE cultivos (
	id INTEGER NOT NULL AUTO_INCREMENT, 
	nombre VARCHAR(60) NOT NULL, 
	tipo VARCHAR(30) NOT NULL, 
	unidad_id INTEGER NOT NULL, 
	descripcion TEXT, 
	color VARCHAR(7), 
	estado VARCHAR(12) NOT NULL, 
	empresa_id INTEGER NOT NULL, 
	creado_en DATETIME NOT NULL, 
	actualizado_en DATETIME NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT uq_cultivo_empresa_nombre UNIQUE (empresa_id, nombre), 
	FOREIGN KEY(unidad_id) REFERENCES unidades_medida (id), 
	FOREIGN KEY(empresa_id) REFERENCES empresas (id)
)
ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
CREATE INDEX ix_cultivos_empresa_id ON cultivos (empresa_id);

-- ----------------------------------------------------------------- fincas
CREATE TABLE fincas (
	id INTEGER NOT NULL AUTO_INCREMENT, 
	nombre VARCHAR(80) NOT NULL, 
	ubicacion VARCHAR(150), 
	superficie_total NUMERIC(10, 2) NOT NULL, 
	superficie_cultivable NUMERIC(10, 2) NOT NULL, 
	tipo_suelo VARCHAR(60), 
	observaciones TEXT, 
	responsable_id INTEGER, 
	estado VARCHAR(12) NOT NULL, 
	empresa_id INTEGER NOT NULL, 
	creado_en DATETIME NOT NULL, 
	actualizado_en DATETIME NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT uq_finca_empresa_nombre UNIQUE (empresa_id, nombre), 
	FOREIGN KEY(responsable_id) REFERENCES usuarios (id), 
	FOREIGN KEY(empresa_id) REFERENCES empresas (id)
)
ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
CREATE INDEX ix_fincas_empresa_id ON fincas (empresa_id);

-- ----------------------------------------------------------------- historial_actividades
CREATE TABLE historial_actividades (
	id INTEGER NOT NULL AUTO_INCREMENT, 
	empresa_id INTEGER, 
	usuario_id INTEGER, 
	fecha_hora DATETIME NOT NULL, 
	modulo VARCHAR(40) NOT NULL, 
	accion VARCHAR(20) NOT NULL, 
	registro_id INTEGER, 
	descripcion VARCHAR(255) NOT NULL, 
	ip VARCHAR(45), 
	PRIMARY KEY (id), 
	FOREIGN KEY(empresa_id) REFERENCES empresas (id), 
	FOREIGN KEY(usuario_id) REFERENCES usuarios (id) ON DELETE SET NULL
)
ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
CREATE INDEX ix_historial_actividades_modulo ON historial_actividades (modulo);
CREATE INDEX ix_historial_actividades_usuario_id ON historial_actividades (usuario_id);
CREATE INDEX ix_historial_empresa_fecha ON historial_actividades (empresa_id, fecha_hora);

-- ----------------------------------------------------------------- insumos
CREATE TABLE insumos (
	id INTEGER NOT NULL AUTO_INCREMENT, 
	nombre VARCHAR(100) NOT NULL, 
	categoria VARCHAR(15) NOT NULL, 
	tipo VARCHAR(40), 
	unidad_id INTEGER NOT NULL, 
	principio_activo VARCHAR(120), 
	stock_minimo NUMERIC(14, 3) NOT NULL, 
	proveedor_id INTEGER, 
	observaciones TEXT, 
	estado VARCHAR(12) NOT NULL, 
	propia BOOL, 
	empresa_id INTEGER NOT NULL, 
	creado_en DATETIME NOT NULL, 
	actualizado_en DATETIME NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT uq_insumo_empresa_nombre UNIQUE (empresa_id, nombre), 
	FOREIGN KEY(unidad_id) REFERENCES unidades_medida (id), 
	FOREIGN KEY(proveedor_id) REFERENCES proveedores (id), 
	FOREIGN KEY(empresa_id) REFERENCES empresas (id)
)
ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
CREATE INDEX ix_insumos_categoria ON insumos (categoria);
CREATE INDEX ix_insumos_empresa_id ON insumos (empresa_id);

-- ----------------------------------------------------------------- alertas
CREATE TABLE alertas (
	id INTEGER NOT NULL AUTO_INCREMENT, 
	titulo VARCHAR(150) NOT NULL, 
	descripcion TEXT, 
	tipo VARCHAR(20) NOT NULL, 
	prioridad VARCHAR(10) NOT NULL, 
	fecha DATE NOT NULL, 
	finca_id INTEGER, 
	asignado_id INTEGER, 
	estado VARCHAR(12) NOT NULL, 
	usuario_id INTEGER, 
	empresa_id INTEGER NOT NULL, 
	creado_en DATETIME NOT NULL, 
	actualizado_en DATETIME NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(finca_id) REFERENCES fincas (id), 
	FOREIGN KEY(asignado_id) REFERENCES usuarios (id), 
	FOREIGN KEY(usuario_id) REFERENCES usuarios (id), 
	FOREIGN KEY(empresa_id) REFERENCES empresas (id)
)
ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
CREATE INDEX ix_alertas_empresa_id ON alertas (empresa_id);
CREATE INDEX ix_alertas_fecha ON alertas (fecha);
CREATE INDEX ix_alertas_finca_id ON alertas (finca_id);

-- ----------------------------------------------------------------- compras
CREATE TABLE compras (
	id INTEGER NOT NULL AUTO_INCREMENT, 
	proveedor_id INTEGER NOT NULL, 
	fecha DATE NOT NULL, 
	comprobante VARCHAR(40), 
	finca_id INTEGER, 
	condicion VARCHAR(20) NOT NULL, 
	vencimiento DATE, 
	total NUMERIC(14, 2) NOT NULL, 
	observaciones TEXT, 
	usuario_id INTEGER, 
	empresa_id INTEGER NOT NULL, 
	creado_en DATETIME NOT NULL, 
	actualizado_en DATETIME NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(proveedor_id) REFERENCES proveedores (id), 
	FOREIGN KEY(finca_id) REFERENCES fincas (id), 
	FOREIGN KEY(usuario_id) REFERENCES usuarios (id), 
	FOREIGN KEY(empresa_id) REFERENCES empresas (id)
)
ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
CREATE INDEX ix_compras_empresa_id ON compras (empresa_id);
CREATE INDEX ix_compras_fecha ON compras (fecha);
CREATE INDEX ix_compras_finca_id ON compras (finca_id);
CREATE INDEX ix_compras_proveedor_id ON compras (proveedor_id);

-- ----------------------------------------------------------------- cuentas_pagar
CREATE TABLE cuentas_pagar (
	id INTEGER NOT NULL AUTO_INCREMENT, 
	proveedor_id INTEGER NOT NULL, 
	comprobante VARCHAR(40), 
	descripcion VARCHAR(200), 
	fecha DATE NOT NULL, 
	vencimiento DATE NOT NULL, 
	importe NUMERIC(14, 2) NOT NULL, 
	pagado NUMERIC(14, 2) NOT NULL, 
	finca_id INTEGER, 
	origen VARCHAR(30) NOT NULL, 
	origen_id INTEGER, 
	observaciones TEXT, 
	empresa_id INTEGER NOT NULL, 
	creado_en DATETIME NOT NULL, 
	actualizado_en DATETIME NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(proveedor_id) REFERENCES proveedores (id), 
	FOREIGN KEY(finca_id) REFERENCES fincas (id), 
	FOREIGN KEY(empresa_id) REFERENCES empresas (id)
)
ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
CREATE INDEX ix_cuenta_origen ON cuentas_pagar (origen, origen_id);
CREATE INDEX ix_cuentas_pagar_empresa_id ON cuentas_pagar (empresa_id);
CREATE INDEX ix_cuentas_pagar_proveedor_id ON cuentas_pagar (proveedor_id);
CREATE INDEX ix_cuentas_pagar_vencimiento ON cuentas_pagar (vencimiento);

-- ----------------------------------------------------------------- documentos
CREATE TABLE documentos (
	id INTEGER NOT NULL AUTO_INCREMENT, 
	entidad VARCHAR(20) NOT NULL, 
	entidad_id INTEGER, 
	tipo_documento VARCHAR(30) NOT NULL, 
	nombre VARCHAR(150) NOT NULL, 
	archivo VARCHAR(255) NOT NULL, 
	nombre_original VARCHAR(255) NOT NULL, 
	mime VARCHAR(100), 
	tamanio INTEGER NOT NULL, 
	fecha DATE NOT NULL, 
	fecha_vencimiento DATE, 
	finca_id INTEGER, 
	observaciones TEXT, 
	usuario_id INTEGER, 
	empresa_id INTEGER NOT NULL, 
	creado_en DATETIME NOT NULL, 
	actualizado_en DATETIME NOT NULL, 
	PRIMARY KEY (id), 
	UNIQUE (archivo), 
	FOREIGN KEY(finca_id) REFERENCES fincas (id), 
	FOREIGN KEY(usuario_id) REFERENCES usuarios (id), 
	FOREIGN KEY(empresa_id) REFERENCES empresas (id)
)
ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
CREATE INDEX ix_documentos_empresa_id ON documentos (empresa_id);
CREATE INDEX ix_documentos_entidad ON documentos (empresa_id, entidad, entidad_id);
CREATE INDEX ix_documentos_fecha_vencimiento ON documentos (fecha_vencimiento);

-- ----------------------------------------------------------------- empleados
CREATE TABLE empleados (
	id INTEGER NOT NULL AUTO_INCREMENT, 
	nombre VARCHAR(60) NOT NULL, 
	apellido VARCHAR(60) NOT NULL, 
	dni VARCHAR(15), 
	telefono VARCHAR(30), 
	puesto VARCHAR(60), 
	fecha_ingreso DATE, 
	tipo VARCHAR(20) NOT NULL, 
	estado VARCHAR(12) NOT NULL, 
	finca_id INTEGER, 
	modalidad_pago VARCHAR(15), 
	tarifa NUMERIC(14, 2), 
	usuario_id INTEGER, 
	observaciones TEXT, 
	empresa_id INTEGER NOT NULL, 
	creado_en DATETIME NOT NULL, 
	actualizado_en DATETIME NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT uq_empleado_empresa_dni UNIQUE (empresa_id, dni), 
	FOREIGN KEY(finca_id) REFERENCES fincas (id), 
	UNIQUE (usuario_id), 
	FOREIGN KEY(usuario_id) REFERENCES usuarios (id), 
	FOREIGN KEY(empresa_id) REFERENCES empresas (id)
)
ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
CREATE INDEX ix_empleados_empresa_id ON empleados (empresa_id);
CREATE INDEX ix_empleados_finca_id ON empleados (finca_id);
CREATE INDEX ix_empleados_tipo ON empleados (tipo);

-- ----------------------------------------------------------------- inventario
CREATE TABLE inventario (
	id INTEGER NOT NULL AUTO_INCREMENT, 
	insumo_id INTEGER NOT NULL, 
	cantidad NUMERIC(14, 3) NOT NULL, 
	costo_promedio NUMERIC(14, 4) NOT NULL, 
	actualizado_en DATETIME NOT NULL, 
	empresa_id INTEGER NOT NULL, 
	PRIMARY KEY (id), 
	UNIQUE (insumo_id), 
	FOREIGN KEY(insumo_id) REFERENCES insumos (id) ON DELETE CASCADE, 
	FOREIGN KEY(empresa_id) REFERENCES empresas (id)
)
ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
CREATE INDEX ix_inventario_empresa_id ON inventario (empresa_id);

-- ----------------------------------------------------------------- lotes
CREATE TABLE lotes (
	id INTEGER NOT NULL AUTO_INCREMENT, 
	finca_id INTEGER NOT NULL, 
	nombre VARCHAR(60) NOT NULL, 
	superficie NUMERIC(10, 2) NOT NULL, 
	tipo_suelo VARCHAR(60), 
	observaciones TEXT, 
	estado VARCHAR(12) NOT NULL, 
	forma VARCHAR(12), 
	geometria TEXT, 
	empresa_id INTEGER NOT NULL, 
	creado_en DATETIME NOT NULL, 
	actualizado_en DATETIME NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT uq_lote_finca_nombre UNIQUE (finca_id, nombre), 
	FOREIGN KEY(finca_id) REFERENCES fincas (id), 
	FOREIGN KEY(empresa_id) REFERENCES empresas (id)
)
ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
CREATE INDEX ix_lotes_empresa_id ON lotes (empresa_id);
CREATE INDEX ix_lotes_finca_id ON lotes (finca_id);

-- ----------------------------------------------------------------- usuario_fincas
CREATE TABLE usuario_fincas (
	usuario_id INTEGER NOT NULL, 
	finca_id INTEGER NOT NULL, 
	PRIMARY KEY (usuario_id, finca_id), 
	FOREIGN KEY(usuario_id) REFERENCES usuarios (id) ON DELETE CASCADE, 
	FOREIGN KEY(finca_id) REFERENCES fincas (id) ON DELETE CASCADE
)
ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ----------------------------------------------------------------- ventas
CREATE TABLE ventas (
	id INTEGER NOT NULL AUTO_INCREMENT, 
	cliente_id INTEGER NOT NULL, 
	fecha DATE NOT NULL, 
	finca_id INTEGER NOT NULL, 
	campana_id INTEGER, 
	forma_pago VARCHAR(20) NOT NULL, 
	fecha_vencimiento_cobro DATE, 
	comprobante VARCHAR(40), 
	transporte VARCHAR(120), 
	costo_flete NUMERIC(14, 2) NOT NULL, 
	flete_a_cargo VARCHAR(12) NOT NULL, 
	total NUMERIC(14, 2) NOT NULL, 
	observaciones TEXT, 
	usuario_id INTEGER, 
	empresa_id INTEGER NOT NULL, 
	creado_en DATETIME NOT NULL, 
	actualizado_en DATETIME NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(cliente_id) REFERENCES clientes (id), 
	FOREIGN KEY(finca_id) REFERENCES fincas (id), 
	FOREIGN KEY(campana_id) REFERENCES campanas (id), 
	FOREIGN KEY(usuario_id) REFERENCES usuarios (id), 
	FOREIGN KEY(empresa_id) REFERENCES empresas (id)
)
ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
CREATE INDEX ix_ventas_campana_id ON ventas (campana_id);
CREATE INDEX ix_ventas_cliente_id ON ventas (cliente_id);
CREATE INDEX ix_ventas_empresa_id ON ventas (empresa_id);
CREATE INDEX ix_ventas_fecha ON ventas (fecha);
CREATE INDEX ix_ventas_fecha_vencimiento_cobro ON ventas (fecha_vencimiento_cobro);
CREATE INDEX ix_ventas_finca_id ON ventas (finca_id);

-- ----------------------------------------------------------------- actividades_cultivo
CREATE TABLE actividades_cultivo (
	id INTEGER NOT NULL AUTO_INCREMENT, 
	tipo VARCHAR(30) NOT NULL, 
	fecha DATE NOT NULL, 
	estado VARCHAR(12) NOT NULL, 
	descripcion VARCHAR(200), 
	responsable_id INTEGER, 
	costo NUMERIC(14, 2) NOT NULL, 
	categoria_gasto_id INTEGER, 
	observaciones TEXT, 
	empresa_id INTEGER NOT NULL, 
	finca_id INTEGER NOT NULL, 
	lote_id INTEGER, 
	campana_id INTEGER, 
	cultivo_id INTEGER, 
	creado_en DATETIME NOT NULL, 
	actualizado_en DATETIME NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(responsable_id) REFERENCES usuarios (id), 
	FOREIGN KEY(categoria_gasto_id) REFERENCES categorias_gasto (id), 
	FOREIGN KEY(empresa_id) REFERENCES empresas (id), 
	FOREIGN KEY(finca_id) REFERENCES fincas (id), 
	FOREIGN KEY(lote_id) REFERENCES lotes (id), 
	FOREIGN KEY(campana_id) REFERENCES campanas (id), 
	FOREIGN KEY(cultivo_id) REFERENCES cultivos (id)
)
ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
CREATE INDEX ix_actividades_cultivo_campana_id ON actividades_cultivo (campana_id);
CREATE INDEX ix_actividades_cultivo_cultivo_id ON actividades_cultivo (cultivo_id);
CREATE INDEX ix_actividades_cultivo_empresa_id ON actividades_cultivo (empresa_id);
CREATE INDEX ix_actividades_cultivo_fecha ON actividades_cultivo (fecha);
CREATE INDEX ix_actividades_cultivo_finca_id ON actividades_cultivo (finca_id);
CREATE INDEX ix_actividades_cultivo_lote_id ON actividades_cultivo (lote_id);

-- ----------------------------------------------------------------- aplicaciones_agroquimicos
CREATE TABLE aplicaciones_agroquimicos (
	id INTEGER NOT NULL AUTO_INCREMENT, 
	insumo_id INTEGER NOT NULL, 
	fecha DATE NOT NULL, 
	superficie NUMERIC(10, 2), 
	dosis NUMERIC(14, 3), 
	unidad_dosis VARCHAR(15), 
	cantidad NUMERIC(14, 3) NOT NULL, 
	motivo VARCHAR(150), 
	costo_unitario NUMERIC(14, 4) NOT NULL, 
	costo_total NUMERIC(14, 2) NOT NULL, 
	responsable_id INTEGER, 
	observaciones TEXT, 
	empresa_id INTEGER NOT NULL, 
	finca_id INTEGER NOT NULL, 
	lote_id INTEGER, 
	campana_id INTEGER, 
	cultivo_id INTEGER, 
	creado_en DATETIME NOT NULL, 
	actualizado_en DATETIME NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(insumo_id) REFERENCES insumos (id), 
	FOREIGN KEY(responsable_id) REFERENCES usuarios (id), 
	FOREIGN KEY(empresa_id) REFERENCES empresas (id), 
	FOREIGN KEY(finca_id) REFERENCES fincas (id), 
	FOREIGN KEY(lote_id) REFERENCES lotes (id), 
	FOREIGN KEY(campana_id) REFERENCES campanas (id), 
	FOREIGN KEY(cultivo_id) REFERENCES cultivos (id)
)
ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
CREATE INDEX ix_aplicaciones_agroquimicos_campana_id ON aplicaciones_agroquimicos (campana_id);
CREATE INDEX ix_aplicaciones_agroquimicos_cultivo_id ON aplicaciones_agroquimicos (cultivo_id);
CREATE INDEX ix_aplicaciones_agroquimicos_empresa_id ON aplicaciones_agroquimicos (empresa_id);
CREATE INDEX ix_aplicaciones_agroquimicos_fecha ON aplicaciones_agroquimicos (fecha);
CREATE INDEX ix_aplicaciones_agroquimicos_finca_id ON aplicaciones_agroquimicos (finca_id);
CREATE INDEX ix_aplicaciones_agroquimicos_insumo_id ON aplicaciones_agroquimicos (insumo_id);
CREATE INDEX ix_aplicaciones_agroquimicos_lote_id ON aplicaciones_agroquimicos (lote_id);

-- ----------------------------------------------------------------- aplicaciones_fertilizantes
CREATE TABLE aplicaciones_fertilizantes (
	id INTEGER NOT NULL AUTO_INCREMENT, 
	insumo_id INTEGER NOT NULL, 
	fecha DATE NOT NULL, 
	superficie NUMERIC(10, 2), 
	cantidad NUMERIC(14, 3) NOT NULL, 
	costo_unitario NUMERIC(14, 4) NOT NULL, 
	costo_total NUMERIC(14, 2) NOT NULL, 
	responsable_id INTEGER, 
	observaciones TEXT, 
	empresa_id INTEGER NOT NULL, 
	finca_id INTEGER NOT NULL, 
	lote_id INTEGER, 
	campana_id INTEGER, 
	cultivo_id INTEGER, 
	creado_en DATETIME NOT NULL, 
	actualizado_en DATETIME NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(insumo_id) REFERENCES insumos (id), 
	FOREIGN KEY(responsable_id) REFERENCES usuarios (id), 
	FOREIGN KEY(empresa_id) REFERENCES empresas (id), 
	FOREIGN KEY(finca_id) REFERENCES fincas (id), 
	FOREIGN KEY(lote_id) REFERENCES lotes (id), 
	FOREIGN KEY(campana_id) REFERENCES campanas (id), 
	FOREIGN KEY(cultivo_id) REFERENCES cultivos (id)
)
ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
CREATE INDEX ix_aplicaciones_fertilizantes_campana_id ON aplicaciones_fertilizantes (campana_id);
CREATE INDEX ix_aplicaciones_fertilizantes_cultivo_id ON aplicaciones_fertilizantes (cultivo_id);
CREATE INDEX ix_aplicaciones_fertilizantes_empresa_id ON aplicaciones_fertilizantes (empresa_id);
CREATE INDEX ix_aplicaciones_fertilizantes_fecha ON aplicaciones_fertilizantes (fecha);
CREATE INDEX ix_aplicaciones_fertilizantes_finca_id ON aplicaciones_fertilizantes (finca_id);
CREATE INDEX ix_aplicaciones_fertilizantes_insumo_id ON aplicaciones_fertilizantes (insumo_id);
CREATE INDEX ix_aplicaciones_fertilizantes_lote_id ON aplicaciones_fertilizantes (lote_id);

-- ----------------------------------------------------------------- caminos_lote
CREATE TABLE caminos_lote (
	id INTEGER NOT NULL AUTO_INCREMENT, 
	lote_id INTEGER NOT NULL, 
	nombre VARCHAR(60) NOT NULL, 
	ancho NUMERIC(6, 2) NOT NULL, 
	longitud NUMERIC(10, 1) NOT NULL, 
	geometria TEXT NOT NULL, 
	empresa_id INTEGER NOT NULL, 
	creado_en DATETIME NOT NULL, 
	actualizado_en DATETIME NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(lote_id) REFERENCES lotes (id) ON DELETE CASCADE, 
	FOREIGN KEY(empresa_id) REFERENCES empresas (id)
)
ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
CREATE INDEX ix_caminos_lote_empresa_id ON caminos_lote (empresa_id);
CREATE INDEX ix_caminos_lote_lote_id ON caminos_lote (lote_id);

-- ----------------------------------------------------------------- detalle_compras
CREATE TABLE detalle_compras (
	id INTEGER NOT NULL AUTO_INCREMENT, 
	compra_id INTEGER NOT NULL, 
	insumo_id INTEGER NOT NULL, 
	cantidad NUMERIC(14, 3) NOT NULL, 
	precio_unitario NUMERIC(14, 4) NOT NULL, 
	subtotal NUMERIC(14, 2) NOT NULL, 
	empresa_id INTEGER NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(compra_id) REFERENCES compras (id) ON DELETE CASCADE, 
	FOREIGN KEY(insumo_id) REFERENCES insumos (id), 
	FOREIGN KEY(empresa_id) REFERENCES empresas (id)
)
ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
CREATE INDEX ix_detalle_compras_compra_id ON detalle_compras (compra_id);
CREATE INDEX ix_detalle_compras_empresa_id ON detalle_compras (empresa_id);
CREATE INDEX ix_detalle_compras_insumo_id ON detalle_compras (insumo_id);

-- ----------------------------------------------------------------- detalle_ventas
CREATE TABLE detalle_ventas (
	id INTEGER NOT NULL AUTO_INCREMENT, 
	venta_id INTEGER NOT NULL, 
	cultivo_id INTEGER NOT NULL, 
	lote_id INTEGER, 
	calidad VARCHAR(20), 
	cantidad NUMERIC(14, 3) NOT NULL, 
	unidad_id INTEGER NOT NULL, 
	precio_unitario NUMERIC(14, 2) NOT NULL, 
	subtotal NUMERIC(14, 2) NOT NULL, 
	empresa_id INTEGER NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(venta_id) REFERENCES ventas (id) ON DELETE CASCADE, 
	FOREIGN KEY(cultivo_id) REFERENCES cultivos (id), 
	FOREIGN KEY(lote_id) REFERENCES lotes (id), 
	FOREIGN KEY(unidad_id) REFERENCES unidades_medida (id), 
	FOREIGN KEY(empresa_id) REFERENCES empresas (id)
)
ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
CREATE INDEX ix_detalle_ventas_cultivo_id ON detalle_ventas (cultivo_id);
CREATE INDEX ix_detalle_ventas_empresa_id ON detalle_ventas (empresa_id);
CREATE INDEX ix_detalle_ventas_venta_id ON detalle_ventas (venta_id);

-- ----------------------------------------------------------------- gastos
CREATE TABLE gastos (
	id INTEGER NOT NULL AUTO_INCREMENT, 
	fecha DATE NOT NULL, 
	categoria_id INTEGER NOT NULL, 
	proveedor_id INTEGER, 
	descripcion VARCHAR(200) NOT NULL, 
	monto NUMERIC(14, 2) NOT NULL, 
	metodo_pago VARCHAR(20) NOT NULL, 
	vencimiento DATE, 
	comprobante VARCHAR(40), 
	usuario_id INTEGER, 
	origen VARCHAR(30) NOT NULL, 
	origen_id INTEGER, 
	observaciones TEXT, 
	empresa_id INTEGER NOT NULL, 
	finca_id INTEGER, 
	lote_id INTEGER, 
	campana_id INTEGER, 
	cultivo_id INTEGER, 
	creado_en DATETIME NOT NULL, 
	actualizado_en DATETIME NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(categoria_id) REFERENCES categorias_gasto (id), 
	FOREIGN KEY(proveedor_id) REFERENCES proveedores (id), 
	FOREIGN KEY(usuario_id) REFERENCES usuarios (id), 
	FOREIGN KEY(empresa_id) REFERENCES empresas (id), 
	FOREIGN KEY(finca_id) REFERENCES fincas (id), 
	FOREIGN KEY(lote_id) REFERENCES lotes (id), 
	FOREIGN KEY(campana_id) REFERENCES campanas (id), 
	FOREIGN KEY(cultivo_id) REFERENCES cultivos (id)
)
ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
CREATE INDEX ix_gasto_empresa_campana_cultivo ON gastos (empresa_id, campana_id, cultivo_id);
CREATE INDEX ix_gasto_empresa_fecha ON gastos (empresa_id, fecha);
CREATE INDEX ix_gasto_origen ON gastos (origen, origen_id);
CREATE INDEX ix_gastos_campana_id ON gastos (campana_id);
CREATE INDEX ix_gastos_categoria_id ON gastos (categoria_id);
CREATE INDEX ix_gastos_cultivo_id ON gastos (cultivo_id);
CREATE INDEX ix_gastos_empresa_id ON gastos (empresa_id);
CREATE INDEX ix_gastos_finca_id ON gastos (finca_id);
CREATE INDEX ix_gastos_lote_id ON gastos (lote_id);
CREATE INDEX ix_gastos_proveedor_id ON gastos (proveedor_id);

-- ----------------------------------------------------------------- ingresos
CREATE TABLE ingresos (
	id INTEGER NOT NULL AUTO_INCREMENT, 
	venta_id INTEGER, 
	cliente_id INTEGER, 
	fecha DATE NOT NULL, 
	concepto VARCHAR(120) NOT NULL, 
	monto NUMERIC(14, 2) NOT NULL, 
	metodo_pago VARCHAR(20) NOT NULL, 
	estado VARCHAR(12) NOT NULL, 
	usuario_id INTEGER, 
	observaciones TEXT, 
	empresa_id INTEGER NOT NULL, 
	finca_id INTEGER, 
	lote_id INTEGER, 
	campana_id INTEGER, 
	cultivo_id INTEGER, 
	creado_en DATETIME NOT NULL, 
	actualizado_en DATETIME NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(venta_id) REFERENCES ventas (id), 
	FOREIGN KEY(cliente_id) REFERENCES clientes (id), 
	FOREIGN KEY(usuario_id) REFERENCES usuarios (id), 
	FOREIGN KEY(empresa_id) REFERENCES empresas (id), 
	FOREIGN KEY(finca_id) REFERENCES fincas (id), 
	FOREIGN KEY(lote_id) REFERENCES lotes (id), 
	FOREIGN KEY(campana_id) REFERENCES campanas (id), 
	FOREIGN KEY(cultivo_id) REFERENCES cultivos (id)
)
ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
CREATE INDEX ix_ingresos_campana_id ON ingresos (campana_id);
CREATE INDEX ix_ingresos_cliente_id ON ingresos (cliente_id);
CREATE INDEX ix_ingresos_cultivo_id ON ingresos (cultivo_id);
CREATE INDEX ix_ingresos_empresa_id ON ingresos (empresa_id);
CREATE INDEX ix_ingresos_fecha ON ingresos (fecha);
CREATE INDEX ix_ingresos_finca_id ON ingresos (finca_id);
CREATE INDEX ix_ingresos_lote_id ON ingresos (lote_id);
CREATE INDEX ix_ingresos_venta_id ON ingresos (venta_id);

-- ----------------------------------------------------------------- maquinaria
CREATE TABLE maquinaria (
	id INTEGER NOT NULL AUTO_INCREMENT, 
	nombre VARCHAR(80) NOT NULL, 
	tipo VARCHAR(20) NOT NULL, 
	marca VARCHAR(50), 
	modelo VARCHAR(50), 
	anio INTEGER, 
	identificacion VARCHAR(30), 
	horas_uso NUMERIC(10, 1) NOT NULL, 
	estado VARCHAR(15) NOT NULL, 
	responsable_id INTEGER, 
	finca_id INTEGER, 
	costo_hora NUMERIC(14, 2) NOT NULL, 
	intervalo_mantenimiento_horas INTEGER, 
	ultimo_mantenimiento_horas NUMERIC(10, 1), 
	proximo_mantenimiento_fecha DATE, 
	observaciones TEXT, 
	empresa_id INTEGER NOT NULL, 
	creado_en DATETIME NOT NULL, 
	actualizado_en DATETIME NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT uq_maquina_identificacion UNIQUE (empresa_id, identificacion), 
	FOREIGN KEY(responsable_id) REFERENCES empleados (id), 
	FOREIGN KEY(finca_id) REFERENCES fincas (id), 
	FOREIGN KEY(empresa_id) REFERENCES empresas (id)
)
ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
CREATE INDEX ix_maquinaria_empresa_id ON maquinaria (empresa_id);

-- ----------------------------------------------------------------- movimientos_inventario
CREATE TABLE movimientos_inventario (
	id INTEGER NOT NULL AUTO_INCREMENT, 
	insumo_id INTEGER NOT NULL, 
	tipo VARCHAR(10) NOT NULL, 
	fecha DATE NOT NULL, 
	cantidad NUMERIC(14, 3) NOT NULL, 
	precio_unitario NUMERIC(14, 4) NOT NULL, 
	proveedor_id INTEGER, 
	responsable_id INTEGER, 
	origen VARCHAR(30) NOT NULL, 
	origen_id INTEGER, 
	observaciones TEXT, 
	empresa_id INTEGER NOT NULL, 
	finca_id INTEGER, 
	lote_id INTEGER, 
	campana_id INTEGER, 
	cultivo_id INTEGER, 
	creado_en DATETIME NOT NULL, 
	actualizado_en DATETIME NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(insumo_id) REFERENCES insumos (id), 
	FOREIGN KEY(proveedor_id) REFERENCES proveedores (id), 
	FOREIGN KEY(responsable_id) REFERENCES usuarios (id), 
	FOREIGN KEY(empresa_id) REFERENCES empresas (id), 
	FOREIGN KEY(finca_id) REFERENCES fincas (id), 
	FOREIGN KEY(lote_id) REFERENCES lotes (id), 
	FOREIGN KEY(campana_id) REFERENCES campanas (id), 
	FOREIGN KEY(cultivo_id) REFERENCES cultivos (id)
)
ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
CREATE INDEX ix_mov_insumo_fecha ON movimientos_inventario (insumo_id, fecha);
CREATE INDEX ix_mov_origen ON movimientos_inventario (origen, origen_id);
CREATE INDEX ix_movimientos_inventario_campana_id ON movimientos_inventario (campana_id);
CREATE INDEX ix_movimientos_inventario_cultivo_id ON movimientos_inventario (cultivo_id);
CREATE INDEX ix_movimientos_inventario_empresa_id ON movimientos_inventario (empresa_id);
CREATE INDEX ix_movimientos_inventario_finca_id ON movimientos_inventario (finca_id);
CREATE INDEX ix_movimientos_inventario_lote_id ON movimientos_inventario (lote_id);

-- ----------------------------------------------------------------- pagos_empleados
CREATE TABLE pagos_empleados (
	id INTEGER NOT NULL AUTO_INCREMENT, 
	empleado_id INTEGER NOT NULL, 
	fecha DATE NOT NULL, 
	concepto VARCHAR(100) NOT NULL, 
	periodo VARCHAR(20), 
	monto NUMERIC(14, 2) NOT NULL, 
	metodo_pago VARCHAR(20) NOT NULL, 
	imputar_costo BOOL NOT NULL, 
	usuario_id INTEGER, 
	observaciones TEXT, 
	empresa_id INTEGER NOT NULL, 
	finca_id INTEGER, 
	lote_id INTEGER, 
	campana_id INTEGER, 
	cultivo_id INTEGER, 
	creado_en DATETIME NOT NULL, 
	actualizado_en DATETIME NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(empleado_id) REFERENCES empleados (id), 
	FOREIGN KEY(usuario_id) REFERENCES usuarios (id), 
	FOREIGN KEY(empresa_id) REFERENCES empresas (id), 
	FOREIGN KEY(finca_id) REFERENCES fincas (id), 
	FOREIGN KEY(lote_id) REFERENCES lotes (id), 
	FOREIGN KEY(campana_id) REFERENCES campanas (id), 
	FOREIGN KEY(cultivo_id) REFERENCES cultivos (id)
)
ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
CREATE INDEX ix_pagos_empleados_campana_id ON pagos_empleados (campana_id);
CREATE INDEX ix_pagos_empleados_cultivo_id ON pagos_empleados (cultivo_id);
CREATE INDEX ix_pagos_empleados_empleado_id ON pagos_empleados (empleado_id);
CREATE INDEX ix_pagos_empleados_empresa_id ON pagos_empleados (empresa_id);
CREATE INDEX ix_pagos_empleados_fecha ON pagos_empleados (fecha);
CREATE INDEX ix_pagos_empleados_finca_id ON pagos_empleados (finca_id);
CREATE INDEX ix_pagos_empleados_lote_id ON pagos_empleados (lote_id);

-- ----------------------------------------------------------------- pagos_proveedores
CREATE TABLE pagos_proveedores (
	id INTEGER NOT NULL AUTO_INCREMENT, 
	cuenta_id INTEGER NOT NULL, 
	fecha DATE NOT NULL, 
	monto NUMERIC(14, 2) NOT NULL, 
	metodo_pago VARCHAR(20) NOT NULL, 
	observaciones TEXT, 
	usuario_id INTEGER, 
	empresa_id INTEGER NOT NULL, 
	creado_en DATETIME NOT NULL, 
	actualizado_en DATETIME NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(cuenta_id) REFERENCES cuentas_pagar (id), 
	FOREIGN KEY(usuario_id) REFERENCES usuarios (id), 
	FOREIGN KEY(empresa_id) REFERENCES empresas (id)
)
ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
CREATE INDEX ix_pagos_proveedores_cuenta_id ON pagos_proveedores (cuenta_id);
CREATE INDEX ix_pagos_proveedores_empresa_id ON pagos_proveedores (empresa_id);
CREATE INDEX ix_pagos_proveedores_fecha ON pagos_proveedores (fecha);

-- ----------------------------------------------------------------- riegos
CREATE TABLE riegos (
	id INTEGER NOT NULL AUTO_INCREMENT, 
	fecha DATE NOT NULL, 
	horas NUMERIC(8, 2) NOT NULL, 
	sistema VARCHAR(20) NOT NULL, 
	consumo NUMERIC(14, 3), 
	unidad_consumo VARCHAR(15), 
	costo NUMERIC(14, 2) NOT NULL, 
	responsable_id INTEGER, 
	observaciones TEXT, 
	empresa_id INTEGER NOT NULL, 
	finca_id INTEGER NOT NULL, 
	lote_id INTEGER, 
	campana_id INTEGER, 
	cultivo_id INTEGER, 
	creado_en DATETIME NOT NULL, 
	actualizado_en DATETIME NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(responsable_id) REFERENCES usuarios (id), 
	FOREIGN KEY(empresa_id) REFERENCES empresas (id), 
	FOREIGN KEY(finca_id) REFERENCES fincas (id), 
	FOREIGN KEY(lote_id) REFERENCES lotes (id), 
	FOREIGN KEY(campana_id) REFERENCES campanas (id), 
	FOREIGN KEY(cultivo_id) REFERENCES cultivos (id)
)
ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
CREATE INDEX ix_riegos_campana_id ON riegos (campana_id);
CREATE INDEX ix_riegos_cultivo_id ON riegos (cultivo_id);
CREATE INDEX ix_riegos_empresa_id ON riegos (empresa_id);
CREATE INDEX ix_riegos_fecha ON riegos (fecha);
CREATE INDEX ix_riegos_finca_id ON riegos (finca_id);
CREATE INDEX ix_riegos_lote_id ON riegos (lote_id);

-- ----------------------------------------------------------------- siembras
CREATE TABLE siembras (
	id INTEGER NOT NULL AUTO_INCREMENT, 
	fecha_siembra DATE NOT NULL, 
	superficie NUMERIC(10, 2) NOT NULL, 
	variedad VARCHAR(60), 
	insumo_id INTEGER, 
	cantidad_semilla NUMERIC(14, 3), 
	unidad_semilla_id INTEGER, 
	proveedor_id INTEGER, 
	costo_semilla NUMERIC(14, 2) NOT NULL, 
	responsable_id INTEGER, 
	fecha_cosecha_estimada DATE, 
	rendimiento_estimado NUMERIC(14, 3), 
	estado VARCHAR(12) NOT NULL, 
	observaciones TEXT, 
	geometria TEXT, 
	distancia_surcos NUMERIC(5, 2), 
	orientacion_surcos NUMERIC(5, 1), 
	superficie_caminos NUMERIC(10, 2), 
	origen_semilla VARCHAR(10), 
	empresa_id INTEGER NOT NULL, 
	finca_id INTEGER NOT NULL, 
	lote_id INTEGER, 
	campana_id INTEGER NOT NULL, 
	cultivo_id INTEGER NOT NULL, 
	creado_en DATETIME NOT NULL, 
	actualizado_en DATETIME NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(insumo_id) REFERENCES insumos (id), 
	FOREIGN KEY(unidad_semilla_id) REFERENCES unidades_medida (id), 
	FOREIGN KEY(proveedor_id) REFERENCES proveedores (id), 
	FOREIGN KEY(responsable_id) REFERENCES usuarios (id), 
	FOREIGN KEY(empresa_id) REFERENCES empresas (id), 
	FOREIGN KEY(finca_id) REFERENCES fincas (id), 
	FOREIGN KEY(lote_id) REFERENCES lotes (id), 
	FOREIGN KEY(campana_id) REFERENCES campanas (id), 
	FOREIGN KEY(cultivo_id) REFERENCES cultivos (id)
)
ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
CREATE INDEX ix_siembras_campana_id ON siembras (campana_id);
CREATE INDEX ix_siembras_cultivo_id ON siembras (cultivo_id);
CREATE INDEX ix_siembras_empresa_id ON siembras (empresa_id);
CREATE INDEX ix_siembras_estado ON siembras (estado);
CREATE INDEX ix_siembras_fecha_cosecha_estimada ON siembras (fecha_cosecha_estimada);
CREATE INDEX ix_siembras_fecha_siembra ON siembras (fecha_siembra);
CREATE INDEX ix_siembras_finca_id ON siembras (finca_id);
CREATE INDEX ix_siembras_lote_id ON siembras (lote_id);

-- ----------------------------------------------------------------- trabajos
CREATE TABLE trabajos (
	id INTEGER NOT NULL AUTO_INCREMENT, 
	fecha DATE NOT NULL, 
	empleado_id INTEGER NOT NULL, 
	tipo_trabajo VARCHAR(40) NOT NULL, 
	modalidad VARCHAR(15) NOT NULL, 
	horas NUMERIC(8, 2), 
	jornales NUMERIC(8, 2), 
	cantidad NUMERIC(14, 3), 
	precio_unitario NUMERIC(14, 2) NOT NULL, 
	total NUMERIC(14, 2) NOT NULL, 
	observaciones TEXT, 
	empresa_id INTEGER NOT NULL, 
	finca_id INTEGER NOT NULL, 
	lote_id INTEGER, 
	campana_id INTEGER, 
	cultivo_id INTEGER, 
	creado_en DATETIME NOT NULL, 
	actualizado_en DATETIME NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(empleado_id) REFERENCES empleados (id), 
	FOREIGN KEY(empresa_id) REFERENCES empresas (id), 
	FOREIGN KEY(finca_id) REFERENCES fincas (id), 
	FOREIGN KEY(lote_id) REFERENCES lotes (id), 
	FOREIGN KEY(campana_id) REFERENCES campanas (id), 
	FOREIGN KEY(cultivo_id) REFERENCES cultivos (id)
)
ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
CREATE INDEX ix_trabajos_campana_id ON trabajos (campana_id);
CREATE INDEX ix_trabajos_cultivo_id ON trabajos (cultivo_id);
CREATE INDEX ix_trabajos_empleado_id ON trabajos (empleado_id);
CREATE INDEX ix_trabajos_empresa_id ON trabajos (empresa_id);
CREATE INDEX ix_trabajos_fecha ON trabajos (fecha);
CREATE INDEX ix_trabajos_finca_id ON trabajos (finca_id);
CREATE INDEX ix_trabajos_lote_id ON trabajos (lote_id);

-- ----------------------------------------------------------------- combustibles
CREATE TABLE combustibles (
	id INTEGER NOT NULL AUTO_INCREMENT, 
	fecha DATE NOT NULL, 
	tipo_combustible VARCHAR(20) NOT NULL, 
	litros NUMERIC(14, 3) NOT NULL, 
	precio_litro NUMERIC(12, 2) NOT NULL, 
	total NUMERIC(14, 2) NOT NULL, 
	maquina_id INTEGER, 
	responsable_id INTEGER, 
	proveedor_id INTEGER, 
	metodo_pago VARCHAR(20) NOT NULL, 
	vencimiento DATE, 
	imputar_gasto BOOL NOT NULL, 
	observaciones TEXT, 
	empresa_id INTEGER NOT NULL, 
	finca_id INTEGER, 
	lote_id INTEGER, 
	campana_id INTEGER, 
	cultivo_id INTEGER, 
	creado_en DATETIME NOT NULL, 
	actualizado_en DATETIME NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(maquina_id) REFERENCES maquinaria (id), 
	FOREIGN KEY(responsable_id) REFERENCES usuarios (id), 
	FOREIGN KEY(proveedor_id) REFERENCES proveedores (id), 
	FOREIGN KEY(empresa_id) REFERENCES empresas (id), 
	FOREIGN KEY(finca_id) REFERENCES fincas (id), 
	FOREIGN KEY(lote_id) REFERENCES lotes (id), 
	FOREIGN KEY(campana_id) REFERENCES campanas (id), 
	FOREIGN KEY(cultivo_id) REFERENCES cultivos (id)
)
ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
CREATE INDEX ix_combustibles_campana_id ON combustibles (campana_id);
CREATE INDEX ix_combustibles_cultivo_id ON combustibles (cultivo_id);
CREATE INDEX ix_combustibles_empresa_id ON combustibles (empresa_id);
CREATE INDEX ix_combustibles_fecha ON combustibles (fecha);
CREATE INDEX ix_combustibles_finca_id ON combustibles (finca_id);
CREATE INDEX ix_combustibles_lote_id ON combustibles (lote_id);
CREATE INDEX ix_combustibles_maquina_id ON combustibles (maquina_id);

-- ----------------------------------------------------------------- cosechas
CREATE TABLE cosechas (
	id INTEGER NOT NULL AUTO_INCREMENT, 
	siembra_id INTEGER, 
	fecha DATE NOT NULL, 
	superficie NUMERIC(10, 2) NOT NULL, 
	cantidad NUMERIC(14, 3) NOT NULL, 
	unidad_id INTEGER NOT NULL, 
	calidad VARCHAR(20), 
	merma NUMERIC(14, 3) NOT NULL, 
	semilla_guardada NUMERIC(14, 3), 
	insumo_semilla_id INTEGER, 
	responsable_id INTEGER, 
	observaciones TEXT, 
	empresa_id INTEGER NOT NULL, 
	finca_id INTEGER NOT NULL, 
	lote_id INTEGER, 
	campana_id INTEGER NOT NULL, 
	cultivo_id INTEGER NOT NULL, 
	creado_en DATETIME NOT NULL, 
	actualizado_en DATETIME NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(siembra_id) REFERENCES siembras (id), 
	FOREIGN KEY(unidad_id) REFERENCES unidades_medida (id), 
	FOREIGN KEY(insumo_semilla_id) REFERENCES insumos (id), 
	FOREIGN KEY(responsable_id) REFERENCES usuarios (id), 
	FOREIGN KEY(empresa_id) REFERENCES empresas (id), 
	FOREIGN KEY(finca_id) REFERENCES fincas (id), 
	FOREIGN KEY(lote_id) REFERENCES lotes (id), 
	FOREIGN KEY(campana_id) REFERENCES campanas (id), 
	FOREIGN KEY(cultivo_id) REFERENCES cultivos (id)
)
ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
CREATE INDEX ix_cosechas_campana_id ON cosechas (campana_id);
CREATE INDEX ix_cosechas_cultivo_id ON cosechas (cultivo_id);
CREATE INDEX ix_cosechas_empresa_id ON cosechas (empresa_id);
CREATE INDEX ix_cosechas_fecha ON cosechas (fecha);
CREATE INDEX ix_cosechas_finca_id ON cosechas (finca_id);
CREATE INDEX ix_cosechas_lote_id ON cosechas (lote_id);
CREATE INDEX ix_cosechas_siembra_id ON cosechas (siembra_id);

-- ----------------------------------------------------------------- uso_maquinaria
CREATE TABLE uso_maquinaria (
	id INTEGER NOT NULL AUTO_INCREMENT, 
	maquina_id INTEGER NOT NULL, 
	fecha DATE NOT NULL, 
	horas NUMERIC(8, 2) NOT NULL, 
	operador_id INTEGER, 
	trabajo_realizado VARCHAR(150) NOT NULL, 
	combustible_litros NUMERIC(14, 3) NOT NULL, 
	costo_combustible NUMERIC(14, 2) NOT NULL, 
	costo_mantenimiento NUMERIC(14, 2) NOT NULL, 
	costo_hora NUMERIC(14, 2) NOT NULL, 
	costo_total NUMERIC(14, 2) NOT NULL, 
	observaciones TEXT, 
	empresa_id INTEGER NOT NULL, 
	finca_id INTEGER NOT NULL, 
	lote_id INTEGER, 
	campana_id INTEGER, 
	cultivo_id INTEGER, 
	creado_en DATETIME NOT NULL, 
	actualizado_en DATETIME NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(maquina_id) REFERENCES maquinaria (id), 
	FOREIGN KEY(operador_id) REFERENCES empleados (id), 
	FOREIGN KEY(empresa_id) REFERENCES empresas (id), 
	FOREIGN KEY(finca_id) REFERENCES fincas (id), 
	FOREIGN KEY(lote_id) REFERENCES lotes (id), 
	FOREIGN KEY(campana_id) REFERENCES campanas (id), 
	FOREIGN KEY(cultivo_id) REFERENCES cultivos (id)
)
ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
CREATE INDEX ix_uso_maquinaria_campana_id ON uso_maquinaria (campana_id);
CREATE INDEX ix_uso_maquinaria_cultivo_id ON uso_maquinaria (cultivo_id);
CREATE INDEX ix_uso_maquinaria_empresa_id ON uso_maquinaria (empresa_id);
CREATE INDEX ix_uso_maquinaria_fecha ON uso_maquinaria (fecha);
CREATE INDEX ix_uso_maquinaria_finca_id ON uso_maquinaria (finca_id);
CREATE INDEX ix_uso_maquinaria_lote_id ON uso_maquinaria (lote_id);
CREATE INDEX ix_uso_maquinaria_maquina_id ON uso_maquinaria (maquina_id);

-- Vista de producción (agregada desde cosechas)
CREATE OR REPLACE VIEW produccion AS
SELECT c.empresa_id, c.finca_id, c.lote_id, c.campana_id, c.cultivo_id, c.unidad_id,
       COUNT(*) AS cosechas,
       SUM(c.superficie) AS superficie_cosechada,
       SUM(c.cantidad) AS cantidad_cosechada,
       SUM(c.merma) AS merma,
       SUM(COALESCE(c.semilla_guardada, 0)) AS semilla_guardada,
       SUM(c.cantidad - c.merma - COALESCE(c.semilla_guardada, 0)) AS cantidad_comercializable,
       CASE WHEN SUM(c.superficie) > 0 THEN SUM(c.cantidad) / SUM(c.superficie) ELSE NULL END AS rendimiento_ha
FROM cosechas c
GROUP BY c.empresa_id, c.finca_id, c.lote_id, c.campana_id, c.cultivo_id, c.unidad_id;

-- Roles del sistema
INSERT INTO roles (codigo, nombre) VALUES
  ('superadmin', 'Administrador del sistema'),
  ('propietario', 'Propietario'),
  ('encargado', 'Encargado'),
  ('trabajador', 'Trabajador')
ON DUPLICATE KEY UPDATE nombre = VALUES(nombre);

SET FOREIGN_KEY_CHECKS = 1;
