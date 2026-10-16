# La Mesada — Sistema de Gestión Agrícola
## Documento de análisis y diseño

Este documento responde a los puntos 1 a 11 del requerimiento: análisis, arquitectura, base de datos,
relaciones, flujos de campaña / siembra / cosecha / venta, cálculo de costos y rentabilidad, y estructura
de carpetas.

---

## 1. Análisis de requisitos

**Qué es:** un sistema de gestión para una explotación agrícola familiar (La Mesada, 4 fincas, un
propietario y dos hijos encargados) que tiene que responder, con números, *cuánto costó producir cada
cultivo, cuánto se vendió y cuánto se ganó*, por finca, por cultivo, por campaña y en total.

**Requisito que cambia la arquitectura:** el sistema no será sólo para La Mesada; se ofrecerá a otros
finqueros. Por eso se diseñó **multi-empresa (multi-tenant)** desde el primer día:

* Tabla `empresas`: cada explotación agrícola es una empresa (La Mesada es la primera).
* **Todas** las tablas de negocio tienen `empresa_id` y **todas** las consultas se filtran por la empresa
  del usuario logueado (servicio `app/services/tenant.py`). Un usuario de una empresa nunca ve datos de otra.
* Un rol extra, **Administrador del sistema** (`superadmin`), da de alta empresas nuevas y su propietario.
* Cada empresa tiene su nombre, logo y datos propios. Catálogos como cultivos, unidades o categorías de
  gasto son **por empresa**, así cada cliente los adapta sin tocar el código.

Así, sumar un cliente nuevo es: *Administración → Nueva empresa*. No hay que instalar nada nuevo.

**Principios que guían el diseño**

1. **Una sola fuente de verdad para los costos:** la tabla `gastos`. Cada módulo que genera un costo
   (siembra, fertilización, agroquímicos, riego, maquinaria, combustible, trabajos, etc.) crea o actualiza
   automáticamente su gasto vinculado (`gastos.origen` + `gastos.origen_id`). La rentabilidad suma una sola
   tabla, sin riesgo de contar dos veces.
2. **Imputación:** cualquier costo o ingreso puede asociarse opcionalmente a
   **Finca + Lote + Campaña + Cultivo**. Es la clave para saber cuánto costó cada cultivo.
3. **Nada fijo en el código:** fincas, cultivos, unidades, campañas, categorías, empleados y máquinas se
   cargan desde la aplicación.
4. **Pensado para el campo:** formularios cortos, botones grandes, botón "+" de carga rápida en el
   celular, y listados que primero piden filtros antes de traer datos.

---

## 2. Arquitectura

**Arquitectura en capas (MVC):**

| Capa | Carpeta | Responsabilidad |
|---|---|---|
| Modelo | `app/models/` | Tablas (SQLAlchemy ORM → MySQL). Sin lógica de pantalla. |
| Servicios | `app/services/` | Reglas de negocio: inventario, gastos automáticos, cuentas a pagar, rentabilidad, reportes, alertas, calendario, auditoría. |
| Controladores | `app/routes/` | Blueprints de Flask: reciben el pedido, verifican permisos, llaman servicios, devuelven vistas. |
| Vistas | `app/templates/` | Jinja2 (HTML5) con escape automático (anti-XSS). |
| Utilidades | `app/utils/` | Permisos, formatos ($ argentino, fechas), validaciones, exportación. |
| Estático | `app/static/` | CSS responsive, JS propio, Chart.js local (funciona sin internet en la red de la finca). |

**Motor CRUD declarativo (`app/crud/`)** — decisión clave de la arquitectura. Hay más de 25 módulos de
alta/baja/modificación (fincas, lotes, cultivos, empleados, gastos…). En lugar de 25 copias casi iguales de
rutas y plantillas, cada módulo se **declara** en `app/crud/modulos.py`: campos, validaciones, filtros,
columnas, permisos y "ganchos" de negocio (por ejemplo: al guardar una aplicación de fertilizante →
descontar stock y generar el gasto). Un único controlador (`app/crud/engine.py`) y tres plantillas genéricas
resuelven listado con filtros + paginación + totales + exportación CSV/Excel, formulario, detalle y
eliminación. Ventajas:

* Agregar un módulo nuevo = declarar sus campos. Menos código, menos errores.
* Todo módulo hereda automáticamente seguridad (empresa, fincas permitidas, CSRF, validación), auditoría,
  filtros y exportación.

Los módulos con pantallas especiales tienen controladores y plantillas propias: dashboards, fincas
(dashboard por finca), ventas y compras (con renglones), cuentas a pagar (pagos), inventario (stock),
caja/finanzas, rentabilidad, reportes, calendario, alertas, documentos, configuración y administración.

**Seguridad** (punto 38):

* Contraseñas con hash `scrypt`/`pbkdf2` de Werkzeug. Bloqueo temporal tras 5 intentos fallidos.
* Sesión con cookie `HttpOnly`, `SameSite=Lax`, `Secure` configurable; token de sesión que se invalida
  al cambiar la contraseña o desactivar el usuario.
* CSRF en todos los formularios (Flask-WTF `CSRFProtect`).
* ORM con consultas parametrizadas (anti SQL injection). Nunca se arma SQL concatenando texto.
* Escape automático de Jinja + cabecera Content-Security-Policy estricta (sin JS en línea) anti XSS.
* Roles y permisos por módulo/acción (`app/utils/permisos.py`), control de empresa y de fincas asignadas
  en cada registro que se lee o modifica. Los `id` que llegan en formularios se validan contra las opciones
  permitidas del usuario (no se puede "inyectar" un id de otra empresa).
* Archivos subidos: extensiones permitidas, tamaño máximo, nombres aleatorios, se sirven sólo a usuarios
  autenticados de la misma empresa.
* Configuración sensible en `.env`. Páginas de error propias (403/404/500) sin exponer detalles.

**Roles**

| Rol | Alcance |
|---|---|
| Administrador del sistema | Alta de empresas (clientes) y sus propietarios. |
| Propietario | Todo dentro de su empresa: las 4 fincas, finanzas, reportes, configuración, usuarios, eliminar. |
| Encargado | Registra todo (siembras, trabajos, gastos, cosechas, ventas…) **sólo en sus fincas asignadas**; ve dashboards y reportes de sus fincas. No elimina ni configura. |
| Trabajador | "Mi panel": sus trabajos, sus pagos, su saldo, sus tareas y el calendario de su finca. |

---

## 3. Diseño de la base de datos

36 tablas + 1 vista, normalizadas (3FN), InnoDB, `utf8mb4`. Todas con PK autoincremental, FKs con
integridad referencial (RESTRICT por defecto: no se puede borrar una finca con siembras; los renglones
de ventas/compras se borran en CASCADA con su cabecera), UNIQUE por empresa donde corresponde
(ej. `UNIQUE(empresa_id, nombre)` en fincas) e índices sobre las columnas de filtro
(empresa, fecha, finca, campaña, cultivo, origen).

### Tablas por área

**Seguridad y sistema:** `empresas`, `roles`, `usuarios`, `usuario_fincas` (N a N: qué fincas maneja cada
encargado), `historial_actividades`, `alertas` (tareas y recordatorios manuales), `documentos`.

**Estructura productiva:** `fincas`, `lotes`, `campanas`, `cultivos`, `unidades_medida`.

**Producción:** `siembras`, `actividades_cultivo`, `riegos`, `cosechas` y la vista `produccion`
(producción agregada por finca/lote/campaña/cultivo calculada desde `cosechas`).

**Insumos:** `insumos` (catálogo único de semillas, fertilizantes, agroquímicos, repuestos, combustible y
otros), `inventario` (stock actual y costo promedio por insumo), `movimientos_inventario`,
`aplicaciones_fertilizantes`, `aplicaciones_agroquimicos`.

> **Nota de normalización:** el requerimiento sugería tablas `fertilizantes` y `agroquimicos`. Se unificaron
> en `insumos` con una columna `categoria`, porque tienen exactamente los mismos atributos (nombre, tipo,
> unidad, stock mínimo, proveedor) y separarlas duplicaría la lógica de stock y compras. Las pantallas
> "Fertilizantes" y "Agroquímicos" existen igual (son vistas filtradas del catálogo, con su historial de
> aplicaciones en tablas propias).

**Maquinaria:** `maquinaria`, `uso_maquinaria`, `combustibles` (cargas de combustible).

**Personal:** `empleados`, `trabajos` (mano de obra devengada), `pagos_empleados`.

**Comercial:** `clientes`, `ventas`, `detalle_ventas`, `ingresos` (cobros y otros ingresos).

**Compras y deudas:** `proveedores`, `compras`, `detalle_compras`, `cuentas_pagar`, `pagos_proveedores`.

**Finanzas:** `categorias_gasto`, `gastos`.

El script completo está en `database/schema.sql` (generado desde los modelos, para que nunca haya
diferencias entre el código y la base).

### Decisiones de normalización

* **Superficie cultivada y sin cultivar de una finca** no se guardan: se calculan de las siembras en curso.
  Guardarlas generaría datos contradictorios.
* **Estado de una venta (cobrada/parcial/pendiente)** y **estado de una cuenta a pagar
  (pagada/parcial/pendiente/vencida)** se calculan con los cobros/pagos y la fecha de vencimiento.
* **Cantidad comercializable** = cantidad cosechada − merma, calculada.
* **Excepción consciente:** los registros operativos guardan `finca_id` además de `lote_id` porque el lote
  es opcional (hay fincas que no se dividen en lotes). El sistema valida que el lote pertenezca a la finca.
* **Totales** de venta/compra se guardan en la cabecera por rendimiento, pero sólo los escribe el servicio
  que suma los renglones.

---

## 4. Relaciones principales

```
empresas 1──N usuarios N──N fincas (usuario_fincas)
empresas 1──N fincas 1──N lotes
empresas 1──N campanas, cultivos, unidades_medida, categorias_gasto, insumos, empleados, maquinaria,
              clientes, proveedores
cultivos N──1 unidades_medida            (la unidad de producción es configurable)

"Imputación"  (finca obligatoria u opcional, lote / campaña / cultivo opcionales):
   siembras, actividades_cultivo, riegos, aplicaciones_fertilizantes, aplicaciones_agroquimicos,
   uso_maquinaria, combustibles, trabajos, pagos_empleados, cosechas, ingresos, gastos,
   movimientos_inventario  ──N──1──  fincas / lotes / campanas / cultivos

insumos 1──1 inventario ; insumos 1──N movimientos_inventario
compras 1──N detalle_compras N──1 insumos
ventas 1──N detalle_ventas N──1 cultivos ; ventas 1──N ingresos ; ventas N──1 clientes
cuentas_pagar 1──N pagos_proveedores ; cuentas_pagar N──1 proveedores
empleados 1──N trabajos, pagos_empleados, uso_maquinaria (operador) ; empleados 0..1──1 usuarios
maquinaria 1──N uso_maquinaria, combustibles
cosechas N──1 siembras (opcional)
gastos.origen + origen_id  →  registro que generó el gasto (siembra, trabajo, aplicación…)
documentos.entidad + entidad_id → finca, empleado, máquina, proveedor, cliente, compra o venta
```

---

## 5. Flujo de una campaña

1. **Configuración → Campañas → Nueva:** "Campaña 2026/2027", fechas de inicio/fin, estado *Activa*.
   La campaña activa queda preseleccionada en todos los formularios.
2. Durante la campaña todo se imputa a ella: siembras, actividades, aplicaciones, riego, maquinaria,
   combustible, trabajos, gastos, cosechas y ventas.
3. **Cierre:** se pasa a *Cerrada*. Los reportes y la rentabilidad permiten comparar campañas
   (ej. *Papa 2025/2026 vs. Papa 2026/2027* en *Rentabilidad → agrupar por campaña y cultivo*).

## 6. Flujo de una siembra

1. Se elige **finca → lote** (el lote se filtra por finca), campaña, cultivo, variedad, fecha, hectáreas.
2. Semilla: **desde el inventario** (se descuenta stock y el costo se calcula a costo promedio) **o comprada
   directo** (se carga el costo). Se valida que haya stock suficiente.
3. Se guarda la fecha estimada de cosecha y el rendimiento esperado (para "próximas cosechas" y
   "producción estimada").
4. **Automático:** gasto categoría *Semillas* imputado a finca/lote/campaña/cultivo, movimiento de
   inventario, registro en historial ("Juan registró una siembra de Papa en Finca 1 — 8 ha"), evento en
   el calendario y hectáreas cultivadas de la finca actualizadas.

## 7. Flujo de una cosecha

1. Se elige la **siembra** (autocompleta finca, lote, campaña, cultivo y hectáreas) o se cargan a mano.
2. Cantidad cosechada (en la unidad del cultivo), merma y calidad → **comercializable = cosechado − merma**.
3. **Automático:** la siembra pasa a *Cosechada*; la producción y el rendimiento por hectárea se recalculan
   (150 t / 10 ha = 15 t/ha); la mano de obra de cosecha se carga en *Trabajos* (así queda en el costo).

## 8. Flujo de una venta

1. Se elige **cliente**, finca, campaña, forma de pago y vencimiento de cobro.
2. Renglones: cultivo, calidad, cantidad, unidad (se puede vender en bolsas aunque se coseche en toneladas;
   las unidades convierten por su factor), precio unitario → subtotal → total.
3. Flete: si lo paga el vendedor, genera automáticamente un gasto *Transporte*.
4. Si es de contado se puede registrar el cobro en el mismo paso; si no, queda **pendiente de cobro**.
5. **Cobros** (`ingresos`): uno o varios pagos parciales. Estado calculado: *Pendiente / Parcial / Cobrada*.
   "¿Cuánto tenemos que cobrar?" = Σ ventas − Σ cobros acreditados.

---

## 9. Cómo se calculan los costos

**Regla:** todo costo termina en `gastos`, con categoría e imputación.

| Origen | Cuándo genera gasto | Categoría | Monto |
|---|---|---|---|
| Gasto manual | Siempre | La elegida | Monto cargado |
| Siembra | Al guardar | Semillas | Costo cargado, o cantidad × costo promedio del stock |
| Aplicación de fertilizante | Al aplicar (no al comprar) | Fertilizantes | Cantidad × costo promedio |
| Aplicación de agroquímico | Al aplicar | Agroquímicos | Cantidad × costo promedio |
| Salida manual de inventario imputada a una finca | Al registrar | Según tipo de insumo | Cantidad × costo promedio |
| Riego | Al guardar | Riego | Costo estimado |
| Actividad de cultivo | Si tiene costo | La elegida o según etapa | Costo adicional (servicios contratados, etc.) |
| Uso de maquinaria | Al guardar | Maquinaria (+ Combustible si se carga ahí) | Horas × costo/hora + mantenimiento (+ combustible) |
| Carga de combustible | Si "imputar como gasto" | Combustible | Litros × precio |
| Trabajo (mano de obra) | Al guardar | Mano de obra | Horas, jornales o unidades × precio |
| Pago a empleado | Sólo si "imputar como costo" (sueldos sin trabajos cargados) | Mano de obra | Monto |
| Venta con flete a cargo del vendedor | Al guardar | Transporte | Costo del flete |

**Las compras de insumos no son costo:** entran al stock (costo promedio ponderado) y, si son en cuenta
corriente, generan la cuenta a pagar. El costo aparece cuando el insumo **se usa** en un lote. Así el costo
del cultivo refleja lo que realmente se aplicó, y lo que quedó en el galpón sigue siendo stock.

**Evitar doble conteo:** los pagos a empleados cancelan lo devengado en Trabajos (saldo del empleado =
trabajos − pagos). El formulario de uso de maquinaria avisa que no se cargue el combustible si ya se
registró la carga.

**Costo total de producción de un cultivo** = Semillas + Fertilizantes + Agroquímicos + Combustible +
Mano de obra + Maquinaria + Reparaciones + Riego + Transporte + Alquileres + Servicios + Impuestos + Otros,
sumando los gastos imputados a ese cultivo (y opcionalmente finca/campaña).

* **Costo por hectárea** = costo total ÷ hectáreas sembradas de ese cultivo.
* **Costo por unidad** (t, kg, bolsa…) = costo total ÷ producción comercializable (en la unidad del cultivo).

**Gastos generales (estructura):** los gastos sin cultivo (impuestos, servicios, un gasto de la finca en
general) se muestran como "Estructura / sin asignar". En Rentabilidad existe la opción **prorratear
gastos generales por hectárea**: los gastos de una finca sin cultivo se reparten entre los cultivos de esa
finca según sus hectáreas, y los gastos sin finca entre todos los cultivos.

## 10. Cómo se calcula la rentabilidad

Para cada grupo (cultivo, finca, campaña o combinación):

* **Ingresos** = Σ renglones de ventas (cantidad × precio) + otros ingresos imputados (no rechazados).
  Se usa el criterio de lo **devengado** (la venta cuenta aunque no esté cobrada; lo pendiente se ve en
  Caja/Finanzas).
* **Costos** = Σ gastos imputados (ver punto 9).
* **Ganancia** = Ingresos − Costos. **Margen** = Ganancia ÷ Ingresos.
* **Superficie** = Σ hectáreas sembradas. **Costo/ha**, **Ingreso/ha**, **Ganancia/ha** = valor ÷ superficie.
* **Producción** = Σ cosechado; **comercializable** = Σ (cosechado − merma).
  **Rendimiento/ha** = producción ÷ superficie cosechada (o sembrada si no se cargó).
* **Costo por unidad** y **Ganancia por unidad** (ej. $/tonelada) = costos o ganancia ÷ comercializable.

Ejemplo (Papa, 20 ha): Ingresos $10.000.000 − Costos $6.000.000 = Ganancia $4.000.000; margen 40 %;
ganancia por hectárea $200.000.

Rankings: fincas y cultivos ordenados por ganancia (y margen) en el dashboard del propietario.

---

## 11. Estructura de carpetas

```
la_mesada/
├── app/
│   ├── __init__.py          # create_app(): fábrica de la aplicación, registro de blueprints, seguridad
│   ├── config.py            # configuración desde .env
│   ├── extensions.py        # db, login_manager, csrf
│   ├── cli.py               # comandos: init-db, seed-demo, crear-superadmin, generar-schema
│   ├── models/              # ORM por área: core, campo, insumos, maquinaria, personal, comercial, compras, finanzas
│   ├── crud/                # motor CRUD declarativo: engine.py (controlador), campos.py, modulos.py (declaraciones)
│   ├── routes/              # blueprints con pantallas propias: auth, dashboard, fincas, ventas, compras,
│   │                        # cuentas, inventario, finanzas, rentabilidad, reportes, calendario, alertas,
│   │                        # documentos, configuracion, admin, trabajador
│   ├── services/            # tenant, auditoria, inventario, gastos_auto, cuentas, operaciones, ventas,
│   │                        # compras, rentabilidad, dashboard, reportes, calendario, alertas, exportar, seed
│   ├── utils/               # permisos, formato, validacion, fechas
│   ├── templates/
│   │   ├── base.html, macros/, crud/ (list, form, detail genéricos), auth/, dashboard/, fincas/, ventas/,
│   │   ├── compras/, cuentas/, inventario/, finanzas/, rentabilidad/, reportes/, calendario/, alertas/,
│   │   └── documentos/, configuracion/, admin/, trabajador/, errors/
│   └── static/ css/ js/ img/ vendor/ (Chart.js local)
├── database/schema.sql      # DDL MySQL completo + vista produccion + roles
├── docs/ARQUITECTURA.md     # este documento
├── tests/test_app.py        # pruebas automáticas de humo y de cálculos
├── scripts/generar_schema.py
├── uploads/                 # documentos subidos (fuera de static, no accesibles sin login)
├── .env.example, requirements.txt, run.py, README.md
```

**Cambios respecto de la estructura propuesta y por qué:**

* Se agregó `app/crud/`: el motor declarativo evita 25 carpetas de plantillas casi idénticas
  (`templates/lotes/`, `templates/cultivos/`…). Los módulos simples usan `templates/crud/`; los que
  necesitan pantalla propia tienen su carpeta.
* `uploads/` fuera de `static/` para que los documentos no sean públicos.
* `cli.py` y `tests/` para instalar, cargar datos de prueba y verificar el sistema con un comando.

---

## 12. Mapa de lotes y siembra por sectores

* `lotes.forma` (circulo | rectangulo | poligono) y `lotes.geometria` (GeoJSON en texto). Un pivote se guarda como
  centro + radio (un círculo exacto); rectángulos y polígonos como anillos de coordenadas.
* `siembras.geometria`: el **sector** del lote donde se sembró. Un pivote dividido en 3 gajos con variedades A, B, A
  son **3 siembras** del mismo lote, campaña y cultivo, cada una con su superficie, variedad, semilla y costo. Así la
  producción, los costos y la rentabilidad siguen funcionando igual, y además se puede comparar por variedad.
  Si `geometria` está vacía, la siembra ocupa el lote completo.
* La superficie **siempre la calcula el servidor** (`app/services/geo.py`, área geodésica sobre la esfera) y se
  valida el GeoJSON recibido (tipos, rangos de coordenadas, cantidad de vértices, radio).
* Frontend: Leaflet + Leaflet-Geoman (dibujo y edición), incluidos localmente en `static/vendor/leaflet`. La
  división en gajos (por porcentajes y ángulo de inicio) y en franjas de igual área (recorte Sutherland–Hodgman con
  búsqueda binaria) se calcula en el navegador para mostrar la vista previa; el servidor recalcula las hectáreas.
* Permisos: ver el mapa = ver lotes; dibujar = editar lotes (sólo fincas asignadas); sembrar por sectores = crear
  siembras. Endpoints: `GET /mapa/`, `GET /mapa/datos.json`, `POST /mapa/lotes`, `POST /mapa/lotes/<id>/quitar`,
  `POST /mapa/sectores` (JSON con token CSRF en la cabecera `X-CSRFToken`).
* Migración: `flask init-db` agrega las columnas nuevas a bases existentes (sólo `ADD COLUMN`, nunca borra).

### Franjas, caminos y surcos

* `caminos_lote` (lote_id, nombre, ancho en m, longitud en m, geometría LineString). Superficie = largo × ancho.
* Al sembrar por sectores, cada franja se corta en el servidor-cliente con recorte de semiplanos (Sutherland–Hodgman)
  en coordenadas locales en metros, a partir del ángulo de los surcos y de los anchos en metros (o por superficie).
  El servidor calcula para cada franja la superficie bruta, los metros de camino que la cruzan (muestreo cada 0,5 m)
  × ancho, y guarda en la siembra la superficie neta, `superficie_caminos`, `distancia_surcos` y `orientacion_surcos`.

### Siembras en días distintos y gestión posterior de los sectores

* Cada sector enviado a `POST /mapa/sectores` trae su propio `estado` (`en_curso` = sembrado, `planificada` =
  pendiente de siembra) y su `fecha_siembra` (si falta, se usa la fecha general).
* Una siembra `planificada` **no descuenta semilla ni genera gasto** (`operaciones.guardar_siembra` sale antes), no
  cuenta para la superficie de rentabilidad y genera la alerta "Siembra pendiente" cuando su fecha está a ≤ 3 días.
* Endpoints de gestión (JSON, con CSRF y control de finca del usuario):
  * `POST /mapa/siembras/<id>/sembrar` — fecha real (no futura), variedad, semilla/cantidad/costo → `en_curso`,
    descuenta stock y crea el gasto.
  * `POST /mapa/siembras/<id>/pendiente` — deshace: vuelve a `planificada` (si no tiene cosechas).
  * `POST /mapa/siembras/<id>/forma` — nueva geometría del sector: recalcula hectáreas brutas − caminos y el gasto.
  * `POST /mapa/siembras/<id>/eliminar` — misma regla que el ABM (no se borra si tiene cosechas).
* Los demás datos (fechas, rendimiento, surcos, observaciones) se corrigen desde el formulario de la siembra
  (`/m/siembras/<id>/editar`), que conserva la geometría.

### Semilla propia y semilla comprada

* `insumos.propia` marca una semilla producida en la explotación (ej. "Semilla de papa Spunta propia"). Su stock
  entra desde las cosechas y siempre vale $ 0: no se puede comprar, y los ingresos manuales se registran sin precio.
* `siembras.origen_semilla` = `propia` | `comprada`. `operaciones.normalizar_semilla` lo deduce del insumo elegido
  y rechaza combinaciones contradictorias. Propia ⇒ `costo_semilla = 0` y ningún gasto; comprada ⇒ costo promedio
  del inventario o el precio cargado a mano (gasto automático "semillas").
* `cosechas.semilla_guardada` (en la unidad del cultivo) + `cosechas.insumo_semilla_id`: genera una entrada de
  inventario (`origen = cosecha`) convertida a la unidad del insumo por `factor_base` (ej. 30 t → 30.000 kg).
  Comercializable = cantidad − merma − semilla guardada (modelo, vista `produccion` y rentabilidad). Una cosecha
  cuya semilla ya se usó no se puede borrar (quedaría stock negativo).
