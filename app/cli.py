"""Comandos de consola:  flask --app run init-db | seed-demo | crear-superadmin | crear-empresa | generar-schema"""
import getpass

import click
from sqlalchemy import text

from .extensions import db

VISTA_PRODUCCION = """
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
GROUP BY c.empresa_id, c.finca_id, c.lote_id, c.campana_id, c.cultivo_id, c.unidad_id
"""


def crear_vista():
    if db.engine.dialect.name in ("mysql", "mariadb"):
        db.session.execute(text(VISTA_PRODUCCION))
    else:
        db.session.execute(text("DROP VIEW IF EXISTS produccion"))
        db.session.execute(text(VISTA_PRODUCCION.replace("CREATE OR REPLACE VIEW", "CREATE VIEW")))
    db.session.commit()


def actualizar_esquema():
    """Agrega a las tablas existentes las columnas nuevas de los modelos (migración simple y segura:
    sólo ADD COLUMN, nunca borra). Permite actualizar el sistema sin perder datos."""
    from sqlalchemy import inspect
    inspector = inspect(db.engine)
    existentes = set(inspector.get_table_names())
    agregadas = []
    for tabla in db.metadata.sorted_tables:
        if tabla.name not in existentes:
            continue
        columnas = {c["name"] for c in inspector.get_columns(tabla.name)}
        for col in tabla.columns:
            if col.name in columnas:
                continue
            tipo = col.type.compile(dialect=db.engine.dialect)
            db.session.execute(text(f"ALTER TABLE {tabla.name} ADD COLUMN {col.name} {tipo} NULL"))
            if col.default is not None and getattr(col.default, "is_scalar", False):
                db.session.execute(text(f"UPDATE {tabla.name} SET {col.name} = :v WHERE {col.name} IS NULL"),
                                   {"v": col.default.arg})
            agregadas.append(f"{tabla.name}.{col.name}")
    db.session.commit()
    return agregadas


def registrar_comandos(app):
    @app.cli.command("init-db")
    @click.option("--borrar", is_flag=True, help="Borra todas las tablas antes de crearlas (¡se pierden los datos!).")
    def init_db(borrar):
        """Crea las tablas, la vista de producción y los roles."""
        from .services.seed import crear_roles
        if borrar:
            click.confirm("Se borrarán TODOS los datos. ¿Continuar?", abort=True)
            db.session.execute(text("DROP VIEW IF EXISTS produccion"))
            db.session.commit()
            db.drop_all()
        db.create_all()
        for columna in actualizar_esquema():
            click.echo(f"  columna agregada: {columna}")
        crear_vista()
        crear_roles()
        db.session.commit()
        click.echo("Base de datos lista.")

    @app.cli.command("seed-demo")
    @click.option("--clave", default="LaMesada2026", help="Contraseña de los usuarios de demostración.")
    def seed_demo(clave):
        """Carga la empresa La Mesada con datos FICTICIOS de demostración y el administrador del sistema."""
        from .models import Empresa
        from .services.seed import cargar_demo, crear_superadmin
        if db.session.scalar(db.select(Empresa).where(Empresa.slug == "la-mesada")):
            click.echo("La empresa 'La Mesada' ya existe. Use 'flask init-db --borrar' para empezar de cero.")
            return
        crear_superadmin("admin@lamesada.app", clave)
        cargar_demo(clave)
        click.echo("Datos de demostración cargados. Usuarios (contraseña: %s):" % clave)
        for email, rol in (("admin@lamesada.app", "Administrador del sistema"),
                           ("propietario@lamesada.com", "Propietario"), ("juan@lamesada.com", "Encargado fincas 1 y 2"),
                           ("pedro@lamesada.com", "Encargado fincas 3 y 4"), ("carlos@lamesada.com", "Trabajador")):
            click.echo(f"  {email:<28} {rol}")

    @app.cli.command("crear-superadmin")
    @click.argument("email")
    def crear_superadmin_cmd(email):
        """Crea (o resetea) el administrador del sistema."""
        from .services.seed import crear_superadmin
        from .utils.validacion import clave_segura
        clave = getpass.getpass("Contraseña (mín. 8, letras y números): ")
        if not clave_segura(clave):
            raise click.ClickException("La contraseña debe tener al menos 8 caracteres, letras y números.")
        crear_superadmin(email, clave)
        db.session.commit()
        click.echo("Administrador listo.")

    @app.cli.command("crear-empresa")
    @click.argument("nombre")
    @click.argument("email_propietario")
    @click.option("--propietario", default="Propietario", help="Nombre del propietario.")
    def crear_empresa_cmd(nombre, email_propietario, propietario):
        """Da de alta una empresa (explotación) vacía con su usuario propietario."""
        from .services.seed import crear_empresa
        from .utils.validacion import clave_segura
        clave = getpass.getpass("Contraseña del propietario: ")
        if not clave_segura(clave):
            raise click.ClickException("La contraseña debe tener al menos 8 caracteres, letras y números.")
        crear_empresa(nombre, propietario, email_propietario, clave)
        db.session.commit()
        click.echo(f"Empresa '{nombre}' creada.")

    @app.cli.command("generar-schema")
    @click.option("--salida", default="database/schema.sql")
    def generar_schema(salida):
        """Genera database/schema.sql (MySQL) a partir de los modelos."""
        from scripts.generar_schema import generar
        generar(salida)
        click.echo(f"Esquema escrito en {salida}")
