# Control Estudiantil

## Descripción

Control Estudiantil es un proyecto de sistema web para optimizar el seguimiento de estudiantes entre los diferentes departamentos del colegio mediante información en tiempo real.

El sistema permitirá consultar el departamento de destino, el estado registrado del movimiento y el tiempo transcurrido. Durante el MVP no se registra la identidad del funcionario que atiende al estudiante.

---

# Objetivo

Desarrollar un sistema local, rápido, sencillo y confiable para el monitoreo de estudiantes entre:

- Inspección General
- Inspección Primaria
- Inspección Bachillerato
- DECE Primaria
- DECE Secundaria/Bachillerato
- Psicopedagogía
- Médico
- Odontología

El sistema funcionará inicialmente únicamente dentro de la red local del colegio.

---

# Tecnologías

## Backend

- FastAPI
- SQLite
- SQLAlchemy
- Alembic para migraciones
- WebSockets

## Frontend

- Angular
- TypeScript

---

# Objetivos del MVP

La primera versión únicamente permitirá:

- Buscar estudiantes solo por nombres y apellidos, mostrando curso y paralelo para distinguir coincidencias.
- Enviar estudiantes a un departamento.
- Recibir la notificación en tiempo real.
- Confirmar la llegada del estudiante.
- Finalizar la atención.
- Iniciar atención directa en un departamento, sin traslado.
- Calcular por separado los tiempos de traslado y atención desde timestamps generados por el backend.
- Cambiar la disponibilidad de departamentos entre DISPONIBLE y NO_DISPONIBLE.
- Conservar movimientos en la base de datos, sin pantalla de historial.

La interfaz será una sola página general, utilizable desde PC y celular. Un departamento puede manejar varios estudiantes; cada estudiante solo puede tener un movimiento activo (EN_CAMINO o EN_ATENCION). Al finalizar pasa a FINALIZADO.

La disponibilidad es independiente de los movimientos. NO_DISPONIBLE bloquea nuevas entradas, incluidas atenciones directas, sin cancelar ni modificar movimientos activos.

FastAPI se ejecutará inicialmente como un único proceso en una computadora Windows de la red local. Solo el backend accede al archivo SQLite del servidor. Los estudiantes se importan de forma controlada desde Excel; el archivo original no se modifica ni se consulta durante la operación cotidiana. No se fusionan homónimos automáticamente.

La API/backend, respaldada por SQLite, proporciona el estado oficial. WebSocket comunica cambios después de confirmar las transacciones. Al abrir, recargar o reconectar, la interfaz recupera el estado mediante API.

No incluirá en esta etapa:

- Usuarios.
- Roles.
- Reportes.
- Estadísticas.
- Exportación a Excel o PDF.
- Administración.

---

# Filosofía del proyecto

Este proyecto prioriza:

- Simplicidad.
- Rapidez.
- Estabilidad.
- Facilidad de uso.
- Desarrollo incremental.

Cada nueva funcionalidad deberá aportar valor al flujo diario del colegio antes de incorporarse al sistema.

---

# Estado

Fases 2 y 3A completadas y validadas manualmente en PC/celular LAN. Fase 3B implementada y utilizada para cargar el alumnado operacional. Fase 4 implementada, aprobada por QA y pendiente de validación manual: búsqueda y selección de estudiantes. Fase 5 no iniciada.

## Ejecución local

Requisitos usados en la validación: Python 3.12 y Node.js 24.14 con npm. Ejecutar desde dos terminales de PowerShell.

Backend, desde `backend/` (crear el entorno e instalar dependencias solo en la preparación inicial):

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe -m alembic upgrade head
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --ws websockets-sansio
```

Frontend, desde `frontend/`:

```powershell
npm ci
npm start
```

Abrir `http://127.0.0.1:4200`. La pantalla muestra los departamentos agrupados en Inspección, DECE y Salud. Permite establecer su disponibilidad y consultar el estado oficial después de guardar, recibir un aviso o reconectar. Los departamentos inactivos se conservan visibles y no permiten cambiar disponibilidad.

Antes de arrancar el backend actualizado, aplicar `alembic upgrade head` con el comando anterior: la primera migración crea e inserta los ocho departamentos. Repetir el upgrade o reiniciar FastAPI no duplica ni restablece datos. El downgrade elimina la tabla y sus datos; las pruebas de reversión deben hacerse solo sobre bases desechables.

El backend se ejecuta en un solo proceso. SQLite se guarda localmente en `backend/data/`; no debe versionarse. `backend/.env.example` documenta las variables opcionales, que deben definirse en el entorno del proceso; no se carga un archivo `.env` automáticamente.

## Verificación automática

Desde `backend/`:

```powershell
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m pip check
.\.venv\Scripts\python.exe -m alembic check
```

Desde `frontend/`:

```powershell
npm test -- --watch=false
npm run build
```

No hay una tarea de lint ni pruebas e2e configuradas. Las pruebas del backend usan bases temporales y cubren la migración de departamentos, API, integridad y avisos WebSocket. No deben apuntar a la base de desarrollo.

## API de Fase 2

- `GET /api/health`: comprobación del proceso.
- `GET /api/departments`: listado completo con id, name, group, active y availability.
- `PUT /api/departments/{department_id}/availability`: cuerpo con únicamente availability, DISPONIBLE o NO_DISPONIBLE. Devuelve el departamento confirmado. Es idempotente; un valor ya establecido no emite avisos.
- `/ws`: aviso `departments_changed` después de confirmar un cambio real. La API es la fuente oficial del estado.

No hay CRUD general, activación/desactivación ni movimientos. El esquema de estudiantes existe desde 3A, sin endpoints operativos. Un departamento inactivo responde 409 al intentar modificarlo; uno inexistente, 404; una entrada inválida, 422.

## Validación de Fase 2

Validación técnica de cierre: 43 pruebas de backend y 12 de frontend aprobadas;
`pip check`, compilación Python y build de producción correctos. Alembic verificó
`upgrade`, `current`, `heads`, `check` y el ciclo `downgrade`/`upgrade` únicamente
en bases desechables. La integración local con dos clientes comprobó GET, PUT,
idempotencia, avisos WebSocket, persistencia tras reiniciar y recuperación automática.
El usuario confirmó además la validación manual en PC y celular dentro de la LAN. Los pasos siguientes se conservan para regresión.

En el servidor, iniciar FastAPI en `127.0.0.1:8000`. Para permitir la prueba desde otros dispositivos, ejecutar desde `frontend/`:

```powershell
npm start -- --host 0.0.0.0
```

Desde dos dispositivos de la misma red, abrir `http://IP-DEL-SERVIDOR:4200`. Sustituir IP-DEL-SERVIDOR por la dirección local real de esa computadora. El proxy mantiene FastAPI en loopback y SQLite permanece únicamente en disco local. Este servidor Angular es para desarrollo y validación local.

1. Confirmar los ocho departamentos y los tres grupos.
2. Cambiar disponibilidad en un dispositivo y comprobar la actualización automática en el otro; repetir en sentido inverso.
3. Recargar ambas pantallas y comprobar que recuperan el estado guardado.
4. Interrumpir la conexión de un cliente, cambiar desde el otro y reconectar: verificar el aviso de desconexión y la recuperación automática.
5. Reiniciar FastAPI y comprobar que conserva los cambios y los clientes se recuperan.
6. Verificar lectura y botones en PC y celular.

No se han abierto puertos ni creado reglas permanentes de firewall automáticamente. Si Windows bloquea el acceso, revisar el permiso de red privada del servidor de desarrollo antes de la prueba. La validación manual de Fase 2 ya fue confirmada.

## Documentación oficial

- [Alcance del MVP](docs/MVP.md)
- [Arquitectura](docs/ARCHITECTURE.md)
- [Modelo de datos](docs/DATA_MODEL.md)
- [Decisiones](docs/DECISIONS.md)
- [Roadmap](docs/ROADMAP.md)
- [Reglas de agentes](AGENTS.md)

La configuración del proyecto está en `.codex/config.toml`; las configuraciones de sus cuatro agentes están en `.codex/agents/`.


## Fase 3A: previsualización de importaciones

Aplicar `alembic upgrade head` antes de iniciar la versión actual. La revisión
0002_import_preview añade siete tablas sin cambiar datos de departamentos.
No crea institución, periodo, estudiantes ni contactos reales.

La sección de importación permite seleccionar XLSX (máximo 5 MB), declarar
PADRON_COMPLETO o SUBCONJUNTO y generar un preview. En 3B, la aplicación requiere una confirmación explícita adicional sobre un preview compatible y sin bloqueos.
Se muestra institución/año como propuesta, resumen, advertencias, candidatos,
diferencias y páginas de diez filas. El ID permite recuperar el borrador durante 24 horas.
Los detalles personales solo aparecen dentro de la revisión de importación.

Contrato, límites y limpieza: [Preview de Fase 3A](docs/IMPORT_PREVIEW.md).

La validación manual de 3A ya fue confirmada. La validación manual de 3B queda
pendiente tras su cierre técnico. Generar preview sigue sin aplicar datos; confirmar
es una acción diferente que modifica datos operativos y devuelve un comprobante.
El Excel real se valida solo localmente y nunca se copia al repositorio.

## Fase 3B: confirmación y comprobante

La revisión 0003 añade soporte para contrato de aplicación, resultado permanente y
protección de procedencia. Aplicar `alembic upgrade head` antes de iniciar la versión
3B en la validación manual. Las revisiones 0001 y 0002 no cambian. Durante el desarrollo
solo se migran bases desechables; no se aplica el listado institucional en la base local.

Generar preview no crea estudiantes. Confirmar es otra acción: requiere un borrador
nuevo compatible, sin bloqueos, y aceptación explícita de cambios operativos y de
cualquier configuración institucional/académica propuesta. Los warnings no bloquean.
Confirmar aplica todo o nada; repetir el mismo ID devuelve el mismo comprobante.
Si se pierde la conexión, recuperar el ID para conocer el resultado antes de repetir.
Un borrador obsoleto o incompatible requiere generar otro, sin resolución individual.
Filas y detalles temporales vencen a las 24 horas; el comprobante aplicado permanece.

Validación manual de 3B, después de revisar su cierre técnico:

1. Iniciar backend y frontend actualizados y comprobar el panel de departamentos.
2. Generar un preview nuevo. Los IDs de 3A no son confirmables.
3. Revisar institución, año, alcance, categorías y warnings. Sobre la base sin estudiantes,
   el listado institucional debe dar 863 NUEVO, 59 warnings en 30 filas y cero bloqueos.
4. Aceptar explícitamente la configuración propuesta y la aplicación del lote.
5. Confirmar una vez y verificar el comprobante agregado sin datos personales.
6. Recuperar ese ID desde PC/celular: debe mostrar el mismo resultado aplicado.
7. Generar otro preview del mismo listado sin modificar la base: debe dar 863 SIN_CAMBIOS,
   sin nuevos estudiantes, contactos ni versiones académicas.
8. Comprobar que cambios de disponibilidad y WebSocket siguen funcionando.

Las pruebas automatizadas cubren rollback, concurrencia, vencimiento y respuesta perdida
con datos sintéticos; no provocar fallos destructivos sobre la base institucional real.
El alcance de 3B no incluye búsqueda, edición/alta manual, movimientos ni bajas.

## Fase 4: buscar y seleccionar estudiantes

La sección «Buscar estudiante», antes de los departamentos, consulta únicamente
alumnado activo con ubicación abierta en el periodo académico activo del backend.
Escribe dos letras útiles o más; tras 300 ms aparecen hasta cinco coincidencias.
Se toleran mayúsculas, tildes, espacios y orden de nombres/apellidos. La respuesta
conserva la escritura original. Tocar un resultado muestra nombre, curso y paralelo;
«Cambiar estudiante» permite buscar otra vez sin recargar. No hay acciones posteriores.

`GET /api/students/search?q=<texto>&limit=5` devuelve una lista con student_id,
first_name, middle_name, last_name, second_last_name, display_name, course y parallel.
El ID no se muestra. No contiene documentos, teléfonos ni contactos. q es obligatorio,
admite hasta 120 caracteres; consultas con menos de dos letras devuelven []. limit
admite enteros de 1 a 5. Parámetros inválidos: 422; sin periodo activo: 409; consulta
fallida: mensaje seguro 500/503. Las respuestas son no-store y el access log de
Uvicorn omite los parámetros del endpoint para no registrar nombres consultados.

No hubo migración ni nuevas dependencias. Alembic continúa en 0003_import_apply.
La normalización, relevancia y límites se detallan en decisiones DEC-037 a DEC-039.
La búsqueda no lee Excel ni previews y no modifica estudiantes. La selección es
temporal, solo en UI; desaparece al recargar. Fase 5 no está implementada.

Validación manual: probar en PC y celular búsquedas por dos componentes en ambos
órdenes, selección/cambio, ausencia de resultados y recuperación tras un error de
conexión. En PC usar Tab y Enter para seleccionar y Escape para limpiar resultados.
En celular comprobar teclado virtual, desplazamiento vertical y pulsación con una
mano. No volver a importar el Excel para probar esta fase.

Validación técnica de Fase 4: backend 202/202 y frontend 44/44, cero fallos;
build de producción correcto (213.27 kB). pip check, compilación Python y Alembic
upgrade/current/heads/check correctos sobre base desechable; sin cambios de migraciones.
Regresión HTTP GET/PUT de departamentos y avisos WebSocket comprobada también con
dos clientes sobre datos sintéticos. Las suites preservan preview, confirmación y
recuperación de comprobantes de 3A/3B.

Revisión real de navegador con datos sintéticos: 1280×900, 768×1024, 390×844,
320×740 y altura reducida 390×400. Sin overflow horizontal, nombres/cursos largos
legibles, campo de 52 px y resultados de al menos 72 px. Tab/Enter, Escape,
selección y retorno del foco verificados. La altura reducida simula espacio limitado;
no sustituye la prueba del teclado virtual en un teléfono físico.
Medición en backend con 863 alumnos sintéticos, veinte consultas: mediana 35.47 ms,
máximo 43.88 ms, cinco resultados. Es una medición local, no una garantía de latencia LAN.

QA independiente de Fase 4: APROBADO, sin defectos funcionales pendientes. Revisión
propia de 43 pruebas backend de búsqueda y 44 frontend, además de interfaz real
en escritorio, tablet y teléfono estrecho. Las dos advertencias de deprecación
preexistentes de Starlette/httpx y anyio no bloquean esta fase. Sin cambios de
dependencias por ellas. Sin commit/push; Fase 5 no iniciada.
