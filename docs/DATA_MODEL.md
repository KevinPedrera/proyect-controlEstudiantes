# DATA MODEL — Control Estudiantil

## 1. Propósito

Este documento define Departamento, el esquema ampliado de estudiantes/importación de Fase 3A y Movimiento persistente de Fase 5. No se implementará una entidad/tabla Evento persistente.

El modelo general es conceptual. La sección de Departamento incorpora la estructura concreta autorizada para Fase 2; Estudiante y sus entidades auxiliares tienen esquema en 3A y aplicación explícita autorizada en 3B; Movimiento pertenece a Fase 5.

Este documento responde principalmente a:

- Qué información representa el sistema.
- Qué entidades existen.
- Cómo se relacionan.
- Qué reglas importantes deben respetarse.
- Qué información debe conservarse para permitir futuras mejoras.

La estructura técnica definitiva de tablas será responsabilidad del backend y deberá respetar este modelo.

---

# 2. Principios generales

## 2.1 El backend controla las reglas

Toda validación relacionada con estudiantes, departamentos, movimientos y estados debe ejecutarse en el backend.

El frontend no debe decidir si una operación es válida.

Por ejemplo:

- El frontend puede solicitar enviar un estudiante al DECE.
- El backend comprueba si el estudiante ya tiene un movimiento activo, en camino o en atención, hacia cualquier departamento, incluido el mismo destino.
- Solo si la operación es válida, el backend crea el movimiento.

---

## 2.2 Un estudiante puede tener muchos movimientos históricos

Un estudiante puede visitar diferentes departamentos muchas veces durante el año.

Cada visita debe quedar registrada independientemente.

Ejemplo:

Pepito Pérez puede tener:

1. Una visita al DECE.
2. Otra visita al departamento médico.
3. Otra visita al DECE semanas después.

Cada una representa un movimiento diferente.

---

## 2.3 Un estudiante solo puede tener un movimiento activo

Un mismo estudiante no puede estar simultáneamente:

- en camino al DECE;
- y siendo atendido por Médico;
- o registrado simultáneamente en cualquier otro departamento.

Por tanto:

> Un estudiante puede tener muchos movimientos históricos, pero solamente un movimiento activo a la vez.

Esta regla debe protegerse mediante validación del backend, transacción y una restricción apropiada en SQLite. Son activos EN_CAMINO y EN_ATENCION, incluso cuando dos solicitudes tienen el mismo departamento de destino. La implementación pertenece a la fase de movimientos.

---

## 2.4 Un departamento puede manejar varios estudiantes

Un departamento sí puede tener varios estudiantes relacionados al mismo tiempo.

Ejemplo:

DECE podría tener:

- María en atención.
- Pedro en atención.
- Luis en camino.

No se limitará artificialmente el departamento a un único estudiante.

---

# 3. Entidad: Estudiante

Representa a un estudiante perteneciente al colegio.

Los estudiantes inicialmente serán importados desde el archivo Excel institucional.

El Excel funciona como fuente de importación, pero el sistema no trabajará directamente sobre el archivo durante su uso normal.

Los estudiantes serán almacenados en la base de datos local.

La primera importación será controlada: se detectan filas vacías, incompletas, inválidas y posibles duplicados. No se fusionan automáticamente homónimos. Nombre, curso y paralelo sirven para identificar coincidencias visualmente, pero no constituyen una garantía de identidad única. No se modifica el Excel original. Cualquier reimportación requiere revisar su correspondencia antes de actualizar registros; no se presupone una sincronización automática con Excel.

## Estructura de Fase 3A

| Entidad / tabla | Responsabilidad y restricciones |
| --- | --- |
| Institution / institution | Singleton id=1, nombre, FK opcional al año activo. No se configura desde preview. |
| AcademicPeriod / academic_periods | ID, etiqueta y period_key única; sin fechas académicas deducidas. |
| Student / students | ID interno; first_name/last_name obligatorios; middle_name/second_last_name/document/document_type opcionales; active; timestamps UTC; procedencia opcional. |
| StudentAcademicPlacement / student_academic_placements | FK estudiante/año, course/parallel obligatorios; recorded_from/recorded_to; índice único parcial estudiante/año cuando recorded_to es NULL. |
| StudentContact / student_contacts | FK estudiante, tipo, parentesco/nombres/teléfonos opcionales, active, procedencia. Una función vigente por padre/madre/representante; múltiples emergencias. |
| ImportBatch / import_batches | UUID, perfil/hash/alcance/fechas/status, propuesta JSON de institución/año/resumen/ausencias/revisión del snapshot. |
| ImportRow / import_rows | FK lote, fila única dentro del lote, categoría, payload JSON con valores, contactos, hoja/fila, advertencias, candidatos y diferencias. |

Mínimos operativos: nombre, apellido, curso y paralelo. Documento opcional y no único;
la comparación detecta duplicados, no fusiona ni usa documentos como primary key.
Nombres normalizados son candidatos, no identidad garantizada. No usar fila/# como ID.
StudentContact no comparte una Person global; emergencia source_slot solo vive en evidencia.

Student y StudentContact reservan source_baseline JSON opcional para la futura BASE aceptada;
no se llena desde preview y no depende de la retención del borrador. source_batch_id opcional
permite altas manuales futuras. Ningún endpoint de 3A crea o modifica estas entidades.

La versión académica representa cuándo se registra un cambio, no su fecha efectiva desconocida.
En 3B, cerrar versión anterior y crear nueva; Movement referencia la versión de su inicio.
Cambiar año activo no altera versiones históricas. Movement se incorpora en Fase 5.

Ausentes se interpretan como NULL; UI Sin registrar. Guiones se conservan y advierten.
Vacíos entrantes no borran existentes. No crear contactos por bloques totalmente vacíos.
El preview se conserva 24 horas; luego filas/propuesta se purgan, quedando lápida mínima sin datos personales.
Sin ficha completa, alta/edición manual, búsqueda operativa ni login. La aplicación de
importaciones pertenece exclusivamente a la confirmación explícita de 3B.

## Evolución autorizada de Fase 3B

La revisión concreta es `0003_import_apply`. El estado conceptual APLICADO se
persiste como `APPLIED` (junto a PREVIEW/EXPIRED). ImportBatch incorpora
`application_contract_version`, `applied_at` y `applied_result`; un CHECK exige
fecha y comprobante únicamente para APPLIED. El contrato actual es `3B-1`;
NULL identifica borradores anteriores no confirmables.

Student, StudentContact y StudentAcademicPlacement usan `source_baseline` JSON
por campo y `manual_protected_fields` JSON (lista de campos). Placement recibe
ambas columnas en 0003; Student/Contact ya tenían BASE desde 0002. El valor
operativo vive en su columna normal. Solo una escritura permitida avanza su BASE;
otros campos, incluidos los protegidos o divergentes, conservan la BASE anterior.
No se atribuye procedencia Excel a datos anteriores de origen desconocido.

La migración conserva los datos y referencias existentes. Su downgrade se
rechaza si existe algún APPLIED: 0002 no puede conservar el comprobante ni su
garantía de idempotencia. Las pruebas de reversión se limitan a bases desechables.

ImportBatch conserva el ID como identidad de la operación; añade contrato de aplicación,
estado APLICADO, fecha de aplicación y comprobante agregado sin datos personales. El
contenido personal de ImportRow/proposal mantiene su TTL original, aun después de aplicar.
El comprobante y las referencias source_batch_id sobreviven a esa purga.
La BASE aceptada se registra por campo en las entidades operativas y no se elimina al
purgar el borrador. Se prepara protección manual por campo, sin UI ni endpoints manuales.
Un campo de procedencia desconocida no se considera automáticamente propiedad de Excel.
Los cambios permitidos actualizan valor y BASE; vacíos y guiones no destruyen datos útiles.
SIN_CAMBIOS no altera entidades, procedencia, timestamps ni versiones.
Dentro del mismo periodo, cambiar curso/paralelo cierra la ubicación abierta y crea otra.
Un periodo nuevo conserva las versiones del anterior. Configurar institución/periodo
activo desde el preview requiere aceptación explícita; nunca se cambia silenciosamente.
Los contactos permanecen separados por estudiante y rol. Emergencias 1/2 no son claves
de identidad; solo coincidencias inequívocas permiten actualización. Sustituciones
ambiguas bloquean el lote. Ausencias no eliminan ni inactivan estudiantes o contactos.

---

# 4. Búsqueda de estudiantes

Para el MVP, la búsqueda se realizará solamente utilizando:

- nombres;
- apellidos.

El usuario no necesitará conocer ningún código o número de carnet.

Ejemplo:

Usuario escribe:

    "Juan Perez"

El sistema mostrará las coincidencias.

Cuando existan estudiantes con nombres similares o iguales, cada resultado deberá mostrar:

- nombre completo;
- curso;
- paralelo.

Ejemplo:

    Juan Pérez — 8.º EGB A
    Juan Pérez — 10.º EGB B

De esta manera el personal podrá identificar correctamente al estudiante.

---

# 5. Entidad: Departamento

Representa cada área del colegio que participa en el flujo de estudiantes.

Para el MVP se contemplan los siguientes grupos.

## Inspección

- Inspección General.
- Inspección Primaria.
- Inspección Bachillerato.

## DECE

- DECE Primaria.
- DECE Secundaria/Bachillerato.
- Psicopedagogía.

## Salud

- Departamento Médico.
- Departamento Odontológico.

La estructura exacta podrá ajustarse posteriormente sin cambiar el concepto de Departamento.

Cada departamento tiene ID interno, nombre, grupo, disponibilidad y condición activo/inactivo. Grupo representa Inspección, DECE o Salud; no requiere una entidad adicional en el MVP. Activo/inactivo no equivale a disponibilidad temporal.

## Estructura de Fase 2

La entidad SQLAlchemy Department corresponde a la tabla departments:

| Campo | Tipo | Regla |
| --- | --- | --- |
| id | Entero | Clave primaria generada por SQLite |
| name | Texto | Obligatorio, de 1 a 120 caracteres y sin espacios exteriores |
| group | Texto | INSPECCION, DECE o SALUD |
| active | Booleano | Obligatorio, inicialmente true |
| availability | Texto | DISPONIBLE o NO_DISPONIBLE, inicialmente DISPONIBLE |

La base protege los valores permitidos mediante CHECK y evita duplicados mediante unicidad de group/name. No se necesitan índices adicionales, timestamps ni campos de funciones posteriores.

La primera migración crea e inserta los ocho departamentos de esta sección; no se crean datos al arrancar FastAPI. El listado incluye inactivos, que se muestran como Inactivo y no pueden modificar disponibilidad. No hay endpoints de alta, eliminación ni activación/desactivación en Fase 2.

---

# 6. Estado del departamento

Cada departamento podrá indicar su disponibilidad operativa.

Los estados iniciales serán:

## DISPONIBLE

El departamento puede recibir estudiantes.

## NO_DISPONIBLE

El departamento temporalmente no puede recibir estudiantes.

Bloquea nuevos envíos y nuevas atenciones directas. No cancela ni modifica automáticamente movimientos activos: se puede confirmar su llegada y finalizar su atención.

Ejemplos:

- reunión;
- ausencia;
- actividad institucional;
- pausa temporal;
- otra situación interna.

La disponibilidad debe actualizarse en tiempo real para todos los dispositivos conectados.

---

# 7. Estado de estudiantes dentro de un departamento

La disponibilidad del departamento no debe confundirse con el estado de cada estudiante.

Un departamento puede estar disponible y, al mismo tiempo, estar atendiendo estudiantes.

Cada estudiante tendrá su propio estado asociado a su movimiento.

Los estados iniciales serán:

## EN_CAMINO

El estudiante fue enviado a un departamento, pero todavía no se ha confirmado su llegada.

## EN_ATENCION

El departamento confirmó que el estudiante llegó.

## FINALIZADO

La atención terminó y el estudiante deja de tener un movimiento activo.

---

# 8. Entidad: Movimiento

Movimiento es la entidad central del sistema.

Representa el recorrido de un estudiante hacia un departamento y su posterior atención, o una atención directa sin traslado.

Ejemplo:

    Pepito Pérez
        ↓
    enviado a DECE
        ↓
    en camino
        ↓
    llegó
        ↓
    en atención
        ↓
    finalizado

Todo ese proceso corresponde a un movimiento.

---

# 9. Información conceptual de un movimiento

Cada movimiento debe permitir conocer como mínimo:

- estudiante;
- departamento de destino;
- estado actual;
- fecha y hora de creación;
- fecha y hora de envío, únicamente si hubo envío;
- fecha y hora de llegada;
- fecha y hora de finalización.

Con esta información se podrán calcular automáticamente los tiempos.

El destino es obligatorio. El origen es opcional y se registra cuando existe contexto de departamento; para atención directa es NULL.

Todos los timestamps oficiales los genera el backend. La hora de llegada representa también el inicio de atención. Los timestamps de pasos todavía no ocurridos están ausentes. Para la atención directa no existe timestamp de envío; el traslado no es aplicable, nunca se registra artificialmente como cero segundos.

La persistencia se gestiona con SQLAlchemy y las migraciones con Alembic. SQLite reside únicamente en el servidor Windows y solo FastAPI accede directamente a ella, con claves foráneas habilitadas y respetadas. El esquema concreto se define en las fases correspondientes.

---

# 10. Tiempo de traslado

El tiempo de traslado comienza cuando el estudiante es enviado.

Ejemplo:

    10:05 — Estudiante enviado al DECE.
    10:09 — DECE confirma "Llegó".

Tiempo de traslado:

    4 minutos.

Mientras el estudiante esté en camino, el sistema deberá mostrar un contador visual.

No es necesario guardar el contador segundo por segundo.

El backend solamente guarda las fechas y horas.

El frontend calcula visualmente el tiempo transcurrido.

---

# 11. Tiempo de atención

El tiempo de atención comienza cuando el departamento confirma que el estudiante llegó.

Ejemplo:

    10:09 — Llegó.
    10:32 — Atención finalizada.

Tiempo de atención:

    23 minutos.

Al igual que el tiempo de traslado, debe calcularse utilizando las fechas registradas.

---

# 12. Atención iniciada directamente por un departamento

No todos los estudiantes llegarán enviados desde Inspección.

Puede ocurrir que:

- el estudiante vaya directamente al DECE;
- un docente lo envíe directamente al departamento médico;
- llegue directamente a odontología;
- otro departamento necesite registrarlo.

Por tanto, cualquier departamento deberá poder iniciar una atención directamente.

Ejemplo:

    Estudiante llega directamente a Médico.

Médico:

1. Busca al estudiante.
2. Lo selecciona.
3. Presiona "Iniciar atención".

En este caso:

- no existe tiempo de traslado registrado;
- la atención comienza inmediatamente.

El movimiento se crea directamente en EN_ATENCION, con timestamp de llegada/inicio generado por el backend. El destino debe aceptar nuevas entradas y el estudiante no debe tener otro movimiento activo.

---

# 13. Transferencias entre departamentos

Para el MVP no construiremos un sistema complejo de transferencias.

Si un estudiante termina en un departamento y posteriormente necesita ir a otro:

1. Se finaliza el movimiento actual.
2. Se crea un nuevo movimiento hacia el siguiente departamento.

Ejemplo:

    Movimiento 1
    Inspección → DECE
    FINALIZADO

    Movimiento 2
    DECE → Médico
    EN CAMINO

Esto permite mantener un historial claro y evita estados ambiguos.

---

# 14. Historial

El historial del MVP significa únicamente conservación de movimientos en la base de datos. No se implementará una pantalla de historial, básica ni avanzada.

Los movimientos finalizados NO deben eliminarse.

Esto permitirá en versiones futuras implementar:

- historial por estudiante;
- cantidad de visitas;
- tiempos promedio;
- reportes;
- estadísticas;
- detección de visitas frecuentes;
- análisis por departamento;
- análisis por curso;
- análisis por fechas.

No construiremos estas funcionalidades ahora, pero el modelo debe permitirlas posteriormente.

---

# 15. Mensajes de cambio, sin entidad Evento

No se utiliza una entidad ni tabla Evento persistente durante el MVP. Movimiento conserva el recorrido y los timestamps necesarios para calcular sus tiempos.

Los mensajes WebSocket solo comunican que ocurrió un cambio en movimientos o disponibilidad. Se emiten después de confirmar la transacción correspondiente. No requieren una tabla de eventos ni representan la fuente oficial del estado.

El cliente recupera el estado actual desde la API; no necesita reproducir un historial de mensajes para reconstruirlo.

---

# 16. Relaciones conceptuales

La relación principal puede representarse así:

    ESTUDIANTE
        │
        │ puede tener
        ▼
    MUCHOS MOVIMIENTOS
        │
        │ cada movimiento pertenece a
        ▼
    UN DEPARTAMENTO


Mientras que:

    DEPARTAMENTO
        │
        │ puede recibir
        ▼
    MUCHOS MOVIMIENTOS


Regla especial:

    ESTUDIANTE
        │
        └── máximo 1 MOVIMIENTO ACTIVO

---

# 17. Flujo conceptual completo

Ejemplo normal:

    Inspección
        │
        │ busca
        ▼
    Pepito Pérez
        │
        │ selecciona DECE
        ▼
    MOVIMIENTO CREADO
        │
        │
        ├── estado: EN CAMINO
        │
        └── inicia tiempo de traslado
                │
                ▼
            DECE recibe aviso
                │
                │ pulsa "Llegó"
                ▼
            estado: EN ATENCIÓN
                │
                ├── termina tiempo de traslado
                └── inicia tiempo de atención
                        │
                        │
                        ▼
                    "Finalizar"
                        │
                        ▼
                  estado: FINALIZADO

El estudiante queda nuevamente disponible para iniciar otro movimiento.

---

# 18. Tiempo real

Cuando ocurra una modificación importante:

- creación de movimiento;
- llegada;
- inicio de atención;
- finalización;
- cambio de disponibilidad de departamento;

el backend debe notificar a los clientes conectados.

La información deberá actualizarse sin necesidad de recargar manualmente la página.

WebSocket será utilizado para estas actualizaciones en tiempo real.

La base de datos sigue siendo la fuente oficial de información.

WebSocket únicamente comunica que existió un cambio.

El mensaje se emite después del commit, nunca antes de confirmar la persistencia.

---

# 19. Fuente oficial de datos

La base de datos será la única fuente oficial del estado actual del sistema.

Nunca se debe considerar al frontend como fuente oficial.

Ejemplo:

Si dos dispositivos muestran información diferente, ambos deberán poder recuperar el estado correcto consultando nuevamente al backend.

Esto evita depender exclusivamente de mensajes WebSocket.

Al abrir, recargar o reconectar, el frontend recupera el estado oficial mediante API/backend, incluidos los timestamps para reconstruir los cronómetros visibles.

---

# 20. Eliminación de información

Para el MVP:

- no se eliminarán movimientos históricos;
- no se eliminarán estudiantes por operaciones normales;
- no se eliminarán departamentos.

Cuando sea necesario dejar de utilizar un estudiante o departamento, podrá marcarse como inactivo.

Esto permite conservar correctamente el historial.

---

# 21. Fuera del modelo MVP

No forman parte actualmente del modelo:

- usuarios;
- perfiles;
- contraseñas;
- permisos avanzados;
- sanciones;
- amonestaciones;
- fichas completas de representantes;
- documentación;
- fichas médicas;
- expedientes;
- calificaciones;
- reportes;
- dashboards;
- estadísticas avanzadas;
- exportación Excel;
- exportación PDF;
- notificaciones externas;
- correo electrónico;
- WhatsApp;
- aplicación móvil nativa.

Estas funcionalidades no deberán ser implementadas por Codex durante el MVP.

---

# 22. Regla de crecimiento

Antes de agregar una nueva entidad al modelo se debe responder:

> ¿Esta entidad es necesaria para que funcione el flujo Buscar → Enviar → Llegar → Atender → Finalizar?

Si la respuesta es no, deberá evaluarse para una versión posterior.

La simplicidad tiene prioridad sobre la cantidad de funcionalidades.

El objetivo actual es demostrar que el sistema resuelve correctamente el seguimiento de estudiantes en tiempo real dentro del colegio.

## Proyección de consulta de Fase 4

Sin cambios de tablas, columnas ni índices; se conserva la revisión 0003_import_apply.
La búsqueda proyecta Student.id como student_id, first_name, middle_name, last_name,
second_last_name y los campos course/parallel de la ubicación abierta del periodo
activo. display_name se compone conservando los nombres originales. Solo Student
activo es elegible. No se devuelve documento, contactos, procedencia ni datos de
importación. No se guardan claves normalizadas; el cálculo es temporal en backend.
No se modifica Student ni Placement al consultar o seleccionar. Los homónimos
conservan IDs distintos y se distinguen visualmente mediante curso/paralelo.

## Operación autorizada de Fase 5

Flujo completo: envío EN_CAMINO, llegada EN_ATENCION, finalización FINALIZADO;
cancelación EN_CAMINO → CANCELADO; atención directa sin origen ni envío.
Historial persistido, FK a versión académica del inicio e índice único parcial
por estudiante activo. BEGIN IMMEDIATE antes de leer para escribir.
Disponibilidad con activos requiere confirmar recuentos autoritativos; si cambian,
se vuelve a preguntar. No altera movimientos existentes. WebSocket avisa después
del commit; API reconstruye paneles, selección y timers al abrir/recargar/reconectar.
Sin documentos/contactos en vistas operativas. No transferencias o envío múltiple.
Esquema, contratos y guía: [Movimientos de Fase 5](MOVEMENTS.md).
