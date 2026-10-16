"""Genera database/schema.sql (MySQL 8 / MariaDB 10.6+) a partir de los modelos SQLAlchemy.

Uso:  python scripts/generar_schema.py      (o  flask --app run generar-schema)
Así el script SQL y el código nunca quedan desfasados.
"""
import os
import sys
from datetime import datetime

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from sqlalchemy.dialects import mysql  # noqa: E402
from sqlalchemy.schema import CreateIndex, CreateTable  # noqa: E402

CABECERA = """-- =====================================================================================
-- LA MESADA · Sistema de Gestión Agrícola
-- Esquema de base de datos MySQL 8 / MariaDB 10.6+   (generado {fecha})
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
"""

ROLES = """
-- Roles del sistema
INSERT INTO roles (codigo, nombre) VALUES
  ('superadmin', 'Administrador del sistema'),
  ('propietario', 'Propietario'),
  ('encargado', 'Encargado'),
  ('trabajador', 'Trabajador')
ON DUPLICATE KEY UPDATE nombre = VALUES(nombre);
"""


def generar(salida="database/schema.sql"):
    from app.cli import VISTA_PRODUCCION
    from app.extensions import db
    from app import models  # noqa: F401

    dialecto = mysql.dialect()
    partes = [CABECERA.format(fecha=datetime.now().strftime("%d/%m/%Y"))]
    tablas = db.metadata.sorted_tables
    for tabla in reversed(tablas):
        partes.append(f"DROP TABLE IF EXISTS `{tabla.name}`;")
    partes.append("DROP VIEW IF EXISTS `produccion`;\n")
    for tabla in tablas:
        ddl = str(CreateTable(tabla).compile(dialect=dialecto)).strip()
        partes.append(f"-- ----------------------------------------------------------------- {tabla.name}")
        partes.append(ddl + "\nENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;")
        for indice in sorted(tabla.indexes, key=lambda i: i.name):
            partes.append(str(CreateIndex(indice).compile(dialect=dialecto)).strip() + ";")
        partes.append("")
    partes.append("-- Vista de producción (agregada desde cosechas)")
    partes.append(VISTA_PRODUCCION.strip() + ";")
    partes.append(ROLES)
    partes.append("SET FOREIGN_KEY_CHECKS = 1;\n")
    os.makedirs(os.path.dirname(salida) or ".", exist_ok=True)
    with open(salida, "w", encoding="utf-8") as archivo:
        archivo.write("\n".join(partes))


if __name__ == "__main__":
    from app import create_app
    with create_app().app_context():
        generar(sys.argv[1] if len(sys.argv) > 1 else "database/schema.sql")
    print("database/schema.sql generado")
