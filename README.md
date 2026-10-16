# La Mesada · Sistema de Gestión Agrícola

Aplicación web para administrar explotaciones agrícolas: fincas, lotes, campañas, cultivos, siembras,
actividades, insumos y stock, maquinaria, combustible, personal, cosechas, ventas, gastos, cuentas a pagar,
rentabilidad, reportes, calendario y alertas.

Está pensada **multi-empresa**: La Mesada es la primera explotación, pero el mismo sistema puede dar servicio
a otros productores (cada uno con sus datos aislados, su logo y sus usuarios).

* **Backend:** Python 3.10+ · Flask 3 · SQLAlchemy 2 (arquitectura en capas / MVC)
* **Base de datos:** MySQL 8 o MariaDB 10.6+
* **Frontend:** HTML5, CSS3 y JavaScript propios (sin frameworks) · Chart.js (incluido, funciona sin internet)
* **Responsive:** PC, notebook, tablet y celular (en el celular las tablas se ven como tarjetas y hay un botón
  rojo "+" de carga rápida).

El análisis y diseño completo (arquitectura, base de datos, relaciones, flujos, cálculo de costos y
rentabilidad) está en **[docs/ARQUITECTURA.md](docs/ARQUITECTURA.md)**.

---

## 1. Instalación en Windows (paso a paso)

1. Instalar **Python 3.10 o superior** (python.org, marcar "Add Python to PATH").
2. Instalar **MySQL 8** (MySQL Installer) o **MariaDB**. Crear la base y un usuario (en MySQL Workbench o la consola):
   ```sql
   CREATE DATABASE la_mesada CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
   CREATE USER 'lamesada'@'localhost' IDENTIFIED BY 'una-clave-segura';
   GRANT ALL PRIVILEGES ON la_mesada.* TO 'lamesada'@'localhost';
   ```
3. Doble clic en **`instalar_windows.bat`** (crea el entorno e instala dependencias y copia `.env.example` a `.env`).
4. Abrir **`.env`** con el Bloc de notas y completar `SECRET_KEY`, `DB_USER` y `DB_PASSWORD`.
5. Crear las tablas (elegir una opción):
   ```bat
   venv\Scripts\activate
   flask --app run init-db
   ```
   o bien importar `database/schema.sql` en MySQL Workbench.
6. **Datos de demostración** (opcional, recomendado para conocer el sistema):
   ```bat
   flask --app run seed-demo
   ```
7. Doble clic en **`iniciar_windows.bat`** y abrir **http://localhost:8000**.
   Desde un celular en la misma red WiFi: `http://IP-de-la-PC:8000`.

### Linux / Mac

```bash
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env        # completar
flask --app run init-db
flask --app run seed-demo   # opcional
flask --app run run --debug # desarrollo  ·  producción: gunicorn -w 3 -b 0.0.0.0:8000 "run:crear()"
```

## 2. Usuarios de demostración

Contraseña de todos: **LaMesada2026** (cambiarla desde *Configuración → Mi contraseña*).

| Usuario | Rol | Ve |
|---|---|---|
| propietario@lamesada.com | Propietario (el padre) | Las 4 fincas, finanzas, reportes, configuración |
| juan@lamesada.com | Encargado (hijo) | Finca 1 y Finca 2 |
| pedro@lamesada.com | Encargado (hijo) | Finca 3 y Finca 4 |
| carlos@lamesada.com | Trabajador | Sus trabajos, pagos y tareas |
| admin@lamesada.app | Administrador del sistema | Alta de nuevas empresas (otros productores) |

> **Todos los montos de la demostración son ficticios.** La empresa demo muestra un aviso amarillo y los registros
> llevan la marca `[DEMO]`. Para empezar con datos reales: `flask --app run init-db --borrar` y luego
> `flask --app run crear-superadmin tu@email.com` y `flask --app run crear-empresa "La Mesada" padre@email.com`.

## 3. Cómo se usa (resumen)

1. **Configuración:** fincas (nombres editables), lotes, campaña activa, cultivos y su unidad (t, qq, bolsas…),
   usuarios y qué fincas maneja cada encargado.
2. **Insumos:** se cargan los productos y las **compras** (suben el stock a costo promedio; si son a plazo generan
   la cuenta a pagar).
3. **En el campo:** siembras, aplicaciones de fertilizantes y agroquímicos, riego, uso de maquinaria,
   combustible, trabajos (por jornal, hora o destajo) y actividades. Cada registro **genera su gasto
   automáticamente**, imputado a finca + lote + campaña + cultivo.
4. **Cosecha y venta:** cosechas (merma y comercializable), ventas con varios productos, flete y cobros parciales.
   Al registrar una cosecha se puede indicar cuánto se **guarda para semilla propia**: entra al stock de ese insumo
   (marcado como "Semilla propia", sin costo) y no se cuenta como comercializable.
5. **Análisis:** dashboard general y por finca, rentabilidad (por cultivo, finca, campaña, hectárea y unidad),
   costo de producción, reportes con exportación a PDF/Excel/CSV, calendario y alertas.

En *Reportes* están las preguntas frecuentes con un clic: "¿Cuánto gastamos este año en la papa de la Finca 2?",
"¿Cuánto le pagamos a los cargadores este mes?", "¿Cuál de las fincas es más rentable?", "¿Cuánto le debemos a
los proveedores?", etc.

### Mapa de lotes (Campo → Mapa)

* Imagen **satelital** (Esri World Imagery, gratuita, requiere internet) o mapa de calles (OpenStreetMap).
* **Dibujar lotes**: *Pivote* (tocar el centro y luego el borde; también se pueden escribir las hectáreas o el
  radio exactos), *Rectángulo* o *Polígono* libre. **Las hectáreas se calculan solas** (área geodésica, calculada
  en el servidor).
* **Caminos internos**: se marcan como líneas con su ancho en metros; su superficie se descuenta sola de lo sembrado.
* **Sembrar por sectores**: el lote (también el pivote) se divide en **franjas rectas** verticales (N-S), horizontales
  (E-O) o con el ángulo que se indique, midiendo cada franja en **metros de ancho**, hectáreas o porcentaje (la
  última es "el resto"), con la variedad/semilla de cada una (se puede repetir: A · B · A) y la **distancia entre
  surcos** (se muestran los surcos y su cantidad aproximada). Cada sector queda como una **siembra propia**
  con su superficie, su semilla (descuenta stock y genera el costo) y su fecha de cosecha estimada.
* **Siembra en días distintos:** cada sector tiene su propia fecha y estado. Un sector puede quedar
  **"Pendiente de siembra"** (se ve rayado y aparece en Alertas); cuando se siembra, se toca y **"Marcar como
  sembrado"** (fecha real, variedad y semilla: recién ahí descuenta stock y genera el costo). Cada sector se puede
  seguir gestionando: **Editar datos**, **Ajustar forma** (mover los bordes, recalcula las hectáreas),
  **Volver a pendiente** (devuelve la semilla y quita el costo) o **Eliminar**.
* **Semilla propia o comprada:** en cada siembra se indica el origen. **Propia** (la papa que guardan de su
  cosecha): no lleva precio, sólo se anota la cantidad. **Comprada**: lleva precio (sale del galpón al costo
  promedio de compra, o se escribe el precio pagado).
* Los lotes y sectores se pintan según la variedad sembrada en la campaña elegida. Al tocar uno se ve su ficha y
  los botones **Registrar cosecha** (con finca, lote, cultivo y hectáreas ya completos), Aplicación y Trabajo.
* Actualizar una instalación existente: `flask --app run init-db` agrega las columnas nuevas sin borrar datos.

## 4. Estructura del proyecto

```
la_mesada/
├── app/
│   ├── __init__.py        fábrica de la app, seguridad (CSP, login obligatorio), errores
│   ├── config.py          configuración desde .env
│   ├── extensions.py      db, login_manager, csrf
│   ├── cli.py             comandos: init-db, seed-demo, crear-superadmin, crear-empresa, generar-schema
│   ├── models/            ORM (core, campo, insumos, maquinaria, personal, comercial, compras, finanzas)
│   ├── crud/              motor ABM declarativo (engine.py) + declaración de los 25 módulos (modulos.py)
│   ├── routes/            pantallas propias: dashboard, fincas, ventas, compras, cuentas, inventario, finanzas,
│   │                      rentabilidad, reportes, calendario, alertas, documentos, configuración, admin, trabajador
│   ├── services/          reglas de negocio: tenant (multi-empresa), inventario, gastos automáticos, cuentas,
│   │                      operaciones, ventas, compras, rentabilidad, dashboard, reportes, calendario, alertas,
│   │                      exportar, auditoría, seed
│   ├── utils/             permisos, formato argentino, validaciones (CUIT), fechas
│   ├── templates/         Jinja2 (crud/ genérico + carpetas por módulo)
│   └── static/            css/app.css, js/app.js, img/ (logo), vendor/chart.umd.min.js
├── database/schema.sql    script MySQL completo (38 tablas + vista produccion + roles)
├── docs/ARQUITECTURA.md   análisis y diseño
├── scripts/generar_schema.py
├── tests/test_app.py      16 pruebas automáticas (todas las pantallas, roles, cálculos, aislamiento, mapa)
├── instalar_windows.bat · iniciar_windows.bat
├── .env.example · requirements.txt · run.py · README.md
```

**Por qué `app/crud/`:** en lugar de 25 controladores y plantillas casi idénticos, cada ABM se declara en
`app/crud/modulos.py` (campos, filtros, columnas, permisos y reglas). Un solo motor genera listado con filtros,
paginación, totales, exportación, formulario, detalle y baja, con la seguridad aplicada igual en todos.
Para agregar un módulo nuevo alcanza con declararlo.

## 5. Seguridad

Contraseñas con hash (Werkzeug scrypt/pbkdf2), bloqueo tras 5 intentos, sesiones con cookie HttpOnly/SameSite
(y Secure con HTTPS), token de sesión que se invalida al cambiar la clave, CSRF en todos los formularios,
ORM con consultas parametrizadas (anti SQL-injection), escape automático + Content-Security-Policy sin JavaScript
en línea (anti XSS), permisos por rol/módulo/acción, aislamiento por empresa y por finca en cada consulta,
validación de todos los datos (incluido que los ids elegidos pertenezcan a la empresa), archivos subidos fuera
de la carpeta pública y con nombre aleatorio, variables sensibles en `.env`, páginas de error propias.

## 6. Pruebas

```bash
pytest -q                                            # SQLite en memoria
TEST_DATABASE_URL="mysql+pymysql://usuario:clave@localhost/la_mesada_test" pytest -q   # MySQL real
```

## 7. Para ofrecerlo a otros productores

* Publicarlo en un servidor (VPS Linux con Nginx + Gunicorn + MySQL, o un hosting Python) con **HTTPS**
  (`SESSION_COOKIE_SECURE=1`).
* Ingresar como **Administrador del sistema** → *Empresas → Nueva empresa*: se crea la explotación con sus
  categorías y unidades, y su usuario propietario. Cada productor configura sus fincas, cultivos y usuarios.
* Para migraciones futuras de la base se recomienda incorporar Flask-Migrate (Alembic).
