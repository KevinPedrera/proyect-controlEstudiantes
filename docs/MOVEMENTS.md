# Movimientos — Fase 5

## Alcance y persistencia

El flujo completo está autorizado en esta fase. No incluye transferencias, envío
múltiple, motivos, notas, reportes, historial visual, edición manual o login.
La base institucional se mantiene sin migrar durante desarrollo; solo se prueban
bases desechables con datos sintéticos. No se consulta ni importa Excel.

La revisión `0004_movements` añade `movements` sobre `0003_import_apply`.
No modifica 0001–0003. Columnas: id PK, student_id FK, academic_placement_id FK,
origin_department_id FK nullable, destination_department_id FK obligatorio, status,
sent_at, arrived_at, finished_at, cancelled_at, created_at y updated_at.
Las primeras cuatro fechas pueden ser NULL según el estado; las dos últimas son
obligatorias. UTC generado por backend, serializado con zona explícita.

`uq_movement_active_student`: índice único parcial por student_id cuando status
es EN_CAMINO o EN_ATENCION. `ix_movement_destination_active`: destino/estado.
CHECK de estados, coherencia de fechas, cronología y origen NULL si no hubo envío.
Las claves foráneas impiden referencias inexistentes. El servicio comprueba que
la ubicación abierta corresponde al alumno y al periodo activo en la creación.
Ese FK se conserva aunque posteriormente se abra otra versión académica.

## Transiciones

| Acción | Estado inicial | Estado final | Fecha oficial |
| --- | --- | --- | --- |
| Enviar | Alumno libre | EN_CAMINO | sent_at |
| Atención directa | Alumno libre | EN_ATENCION | arrived_at; sent_at/origen NULL |
| Llegó | EN_CAMINO | EN_ATENCION | arrived_at |
| Finalizar | EN_ATENCION | FINALIZADO | finished_at |
| Cancelar envío | EN_CAMINO | CANCELADO | cancelled_at |

Finalizar/cancelar liberan al alumno, retiran la tarjeta activa y conservan el
registro. No DELETE HTTP. Repetir la transición ya alcanzada devuelve el mismo
resultado sin modificar fechas ni emitir otro aviso. Otros estados incompatibles
dan 409. Repetir creación con alumno activo da conflicto, sin segundo movimiento.
BEGIN IMMEDIATE se obtiene antes de las validaciones y se libera al commit.

## HTTP

| Método/ruta | Contrato |
| --- | --- |
| POST /api/movements | student_id, destination_department_id, origin_department_id opcional |
| POST /api/movements/direct | student_id, destination_department_id |
| POST /api/movements/{id}/arrive | Registra llegada |
| POST /api/movements/{id}/finish | Finaliza atención |
| POST /api/movements/{id}/cancel | Cancela envío |
| GET /api/departments/{id}/active-movements | items mínimos y server_now |
| GET /api/students/{id}/operational-status | active_movement nullable y server_now |
| GET /api/students/search | Conserva reglas de Fase 4; añade active_movement nullable |

active_movement contiene únicamente status y destination_name. El panel presenta
nombre, curso/paralelo de la versión asociada, estado y tiempos; no documentos,
contactos ni datos del preview. Respuestas operativas no-store. Errores de dominio
usan detail con code/message: inexistentes 404; conflictos 409; validación 422;
base no disponible 503; error seguro 500. No detalles SQL en respuestas de movimientos.

## Disponibilidad con activos

El PUT existente admite confirmed_active_counts opcional con en_camino y en_atencion.
Pasar a NO_DISPONIBLE con activos devuelve 409 CONFIRMAR_ACTIVOS y recuentos actuales.
Angular muestra advertencia y solicita aceptación; no cambia estado optimistamente.
La confirmación reenvía recuentos: el backend los recalcula bajo bloqueo. Si cambiaron,
incluso si ahora son cero, pide confirmación nuevamente. No hace reintentos automáticos.
Al cerrar, todos los movimientos permanecen y pueden llegar, finalizar o cancelarse.
Solo se bloquean nuevas entradas. Disponibilidad y estado de movimiento son distintos.

## Interfaz y recuperación

Buscador reutilizado con máximo cinco coincidencias. Un alumno activo se puede
seleccionar para conocer estado/destino, pero no admite otro movimiento. El contexto
de departamento es local, sin usuario ni perfil; para enviar puede omitirse, para
atención directa se selecciona explícitamente. Destinos son tarjetas de los grupos
Inspección, DECE y Salud, provenientes de API. No disponibles: grises y deshabilitados.
Paneles por destino: EN_ATENCION primero, después EN_CAMINO, antigüedad e ID.

Confirmaciones nativas para finalizar/cancelar/cierre con activos; conflictos en
diálogo informativo. Escape cancela de forma segura, foco contenido y restaurado.
Éxitos inline. Botones deshabilitados durante escrituras y estado desactualizado.
WebSocket emite movements_changed/departments_changed únicamente tras commit.
Clientes recuperan mediante API, cancelando lecturas antiguas. Reconexion consulta
departamentos, paneles y seleccionado; una respuesta perdida no dispara otro POST.

Los cronómetros se anclan en server_now y avanzan con reloj monotónico local. Se
reconstruyen desde sent_at/arrived_at, en MM:SS o HH:MM:SS; no escriben segundos.
F5 retira selección/contexto local, conserva movimientos y recupera sus tiempos.

## Validación manual posterior

Con el backend detenido, el usuario aplica 0004 con `alembic upgrade head` desde
backend usando su entorno virtual, antes de arrancar la nueva versión. No ejecutar
downgrade sobre la base institucional. El desarrollo no realiza movimientos reales.

1. Abrir PC y celular, buscar y seleccionar; elegir destino y enviar.
2. Comprobar aparición EN_CAMINO en el otro dispositivo y timer de traslado.
3. Marcar Llegó, comprobar EN_ATENCION y timer; finalizar con confirmación.
4. Buscar nuevamente: el alumno está libre. Probar cancelación de otro envío.
5. Seleccionar contexto y probar atención directa sin traslado.
6. Buscar un alumno activo: muestra destino y bloquea un segundo movimiento.
7. Cerrar destino con activos: revisar recuentos y confirmar; sus acciones continúan.
8. Probar recuentos cambiantes desde el otro dispositivo antes de confirmar cierre.
9. Verificar destino gris, desconexión/reconexión, F5 y reinicio backend.
10. Comprobar teclado virtual, foco, Escape y lectura en PC, tablet y teléfono.


## Cierre técnico de Fase 5

HEAD de referencia: `cc19ef7c57b09a1044a5b0608c02138527cf6a2f`. Cambios conservados
en el working tree, sin commit ni push. Implementación terminada; validación manual
posterior del usuario pendiente. No se inicia otra fase.

### Validación automática final

- Backend completo: **243 aprobadas**, cero fallos. Incluye 41 casos de movimientos,
  concurrencia, transiciones, rollback, privacidad, disponibilidad y persistencia;
  regresiones de departamentos, preview, confirmación y búsqueda incluidas.
- `pip check`: sin requisitos incompatibles. `compileall` de app y Alembic: correcto.
- Frontend completo: **66 aprobadas en 7 archivos**, cero fallos.
- Angular production build: correcto; 232.38 kB iniciales y 64.82 kB estimados
  de transferencia. No hay una tarea de lint configurada.
- Alembic: upgrade/current/heads/check correctos; única cabeza `0004_movements`.
  Ciclo 0003 → 0004 → 0003 → 0004 únicamente sobre base desechable, comparando
  todas las tablas previas con datos sintéticos antes/después: datos preservados,
  claves foráneas válidas y sin diferencias entre metadata y esquema final.
  La suite también cubre upgrade/downgrade/base/upgrade en bases temporales.
- Migraciones 0001–0003 sin cambios. `git diff --check` correcto, sin archivos
  staged; DB, Excel, entornos, dependencias, artefactos y cachés excluidos de Git.

### Evidencia de navegador conservada

Pruebas realizadas sobre seis alumnos ficticios y una base aislada. No se repitieron
innecesariamente durante el cierre final:

- Envío → Llegó → Finalizar; cancelación EN_CAMINO; atención directa.
- Estudiante activo visible en búsqueda, con nuevo movimiento bloqueado; destino
  cerrado deshabilitado. Doble pulsación produjo una sola tarjeta.
- Dos clientes: envío aparece, llegada actualiza y finalización retira sin F5.
- Cierre con activos muestra recuentos; una llegada desde el segundo cliente
  cambió los recuentos y exigió otra confirmación. Los activos continuaron después
  del cierre, incluida cancelación y finalización.
- F5 en EN_CAMINO y EN_ATENCION; reinicio sobre la misma base conserva movimientos.
  Caída real del backend bloqueó acciones; reinicio recuperó automáticamente el
  estado por API, una sola tarjeta y el cronómetro reconstruido.
- Escritorio 1280×900, tablet 768×1024, teléfono 390×844, estrecho 320×740 y altura
  reducida 390×400: destinos, tarjetas, tiempos y diálogos sin scroll horizontal.
  Botones de diálogos/acciones de al menos 48 px; destinos revisados de 76 px.
- Navegación por teclado, foco contenido en diálogo, Escape seguro y retorno
  al control invocador al cancelar. Estados expresados con texto además del color.

### QA independiente y observaciones

`qa_reviewer_phase5` revisó el estado integrado en solo lectura y emitió **APROBADO**,
sin defectos reproducibles bloqueantes ni de prioridad alta. Ejecutó por separado
los 41 casos backend de movimientos, todos aprobados. Revisó contratos, integridad,
concurrencia, recuperación, interfaz, privacidad y documentación; aprovechó la
evidencia de navegador ya obtenida sin repetirla. No fueron necesarias correcciones
funcionales después de esa revisión.

Observaciones no bloqueantes: dos advertencias de deprecación preexistentes en
Starlette/httpx y AnyIO; no se cambiaron dependencias. La emulación de altura reducida
no sustituye el teclado virtual de un teléfono físico. Sigue pendiente la validación
manual del usuario en dispositivos reales/LAN. El build no implica despliegue.

### Protección del entorno y alcance

Base institucional real **no migrada**; los 863 estudiantes reales **no modificados**;
ningún movimiento real creado; Excel institucional no reimportado; ninguna PII real
introducida en tests, logs o documentación de esta fase. Solo datos sintéticos.
Sin commit, push, transferencias, envío múltiple, reportes ni avance de fase.


### Inventario final de archivos

Rutas desde la raíz del repositorio.

Nuevos (13):

- `backend/alembic/versions/0004_movements.py`
- `backend/app/movement_api.py`
- `backend/app/movement_models.py`
- `backend/app/movements.py`
- `backend/tests/test_movements.py`
- `docs/MOVEMENTS.md`
- `frontend/src/app/core/availability-confirm.spec.ts`
- `frontend/src/app/core/dialog.ts`
- `frontend/src/app/movements/movement-panel.ts`
- `frontend/src/app/movements/movements.service.ts`
- `frontend/src/app/movements/movements.spec.ts`
- `frontend/src/app/movements/operations.css`
- `frontend/src/app/movements/operations.ts`

Modificados (25):

- `AGENTS.md`
- `README.md`
- `backend/alembic/env.py`
- `backend/app/api.py`
- `backend/app/departments.py`
- `backend/app/main.py`
- `backend/app/schemas.py`
- `backend/app/student_search.py`
- `backend/app/websocket.py`
- `backend/tests/test_migrations.py`
- `backend/tests/test_student_search.py`
- `docs/ARCHITECTURE.md`
- `docs/DATA_MODEL.md`
- `docs/DECISIONS.md`
- `docs/MVP.md`
- `docs/ROADMAP.md`
- `frontend/src/app/app.html`
- `frontend/src/app/app.spec.ts`
- `frontend/src/app/app.ts`
- `frontend/src/app/core/api.service.ts`
- `frontend/src/app/core/departments.service.ts`
- `frontend/src/app/core/socket.service.ts`
- `frontend/src/app/students/student-search.html`
- `frontend/src/app/students/student-search.service.ts`
- `frontend/src/app/students/student-search.ts`
