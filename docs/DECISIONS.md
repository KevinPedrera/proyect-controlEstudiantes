# DECISIONS.md

# Decisiones del Proyecto

Este documento registra todas las decisiones importantes del proyecto para mantener un criterio único durante el desarrollo.

Las decisiones siguientes incorporan el saneamiento aprobado en Fase 0.1. Su registro no autoriza iniciar Fase 1 ni implementar las fases posteriores.

---

## DEC-001
**Decisión:** El sistema será una aplicación web local.

**Motivo:**
No depender de Internet y garantizar rapidez dentro del colegio.

---

## DEC-002
**Decisión:** El backend se desarrollará con FastAPI.

**Motivo:**
Alto rendimiento, facilidad para crear APIs y soporte nativo para WebSockets.

---

## DEC-003
**Decisión:** El frontend se desarrollará con Angular.

**Motivo:**
Permite una interfaz moderna, modular y fácil de mantener.

---

## DEC-004
**Decisión:** La base de datos inicial será SQLite.

**Motivo:**
Es sencilla de administrar, no requiere instalación adicional y es suficiente para el MVP.

---

## DEC-005
**Decisión:** La comunicación en tiempo real utilizará WebSockets.

**Motivo:**
Todos los departamentos recibirán actualizaciones inmediatamente, sin necesidad de recargar la página.

---

## DEC-006
**Decisión:** Toda la lógica de negocio estará únicamente en el backend.

**Motivo:**
Centraliza las reglas del sistema, mejora la seguridad y facilita el mantenimiento.

---

## DEC-007
**Decisión:** El frontend solo mostrará información y enviará acciones al backend.

**Motivo:**
Mantener responsabilidades separadas y evitar lógica duplicada.

---

## DEC-008
**Decisión:** El MVP solo incluirá el flujo principal del estudiante.

**Incluye:**
- Buscar estudiante.
- Enviar a un departamento.
- Estado "En camino".
- Confirmar llegada.
- Estado "En atención".
- Cronómetro de traslado.
- Cronómetro de atención.
- Finalizar atención.
- Iniciar atención directa en EN_ATENCION, sin envío ni tiempo de traslado.
- Cambiar disponibilidad de departamentos y conservar movimientos sin pantalla de historial.

**Motivo:**
Validar primero el proceso principal antes de agregar nuevas funciones.

---

## DEC-009
**Decisión:** Los estudiantes se buscarán por nombres y apellidos.

**Motivo:**
Es el método más rápido y natural para el personal del colegio. En caso de nombres repetidos, se mostrará el curso y el paralelo para diferenciarlos.

---

## DEC-010
**Decisión:** Un estudiante solo puede tener un movimiento activo (EN_CAMINO o EN_ATENCION), incluso si las solicitudes apuntan al mismo departamento. Un departamento puede manejar varios estudiantes simultáneamente.

**Motivo:**
Garantizar la integridad de la información y evitar inconsistencias.

---

## DEC-011
**Decisión:** Se registrarán por separado el tiempo de traslado y el tiempo de atención.

**Motivo:**
Permite conocer cuánto tarda el estudiante en llegar al departamento y cuánto dura la atención.

---

## DEC-012
**Decisión:** Cada recorrido/atención se conserva como un Movimiento independiente, con destino, estado y timestamps. No se utiliza una entidad/tabla Evento persistente durante el MVP.

**Motivo:**
Conservar el historial operativo sin duplicar persistencia. WebSocket no necesita una tabla Evento. No se requiere departamento de origen ni pantalla de historial en el MVP.

---

## DEC-013 — Estructura documental y fase actual

**Decisión:** Los documentos oficiales de alcance, arquitectura, modelo, decisiones y roadmap están en docs/MVP.md, docs/ARCHITECTURE.md, docs/DATA_MODEL.md, docs/DECISIONS.md y docs/ROADMAP.md, con rutas expresadas desde la raíz del proyecto. README.md y AGENTS.md permanecen en la raíz. La configuración está en .codex/.

**Motivo:** Mantener una única ubicación y referencias válidas. Fase 0.1 solo sanea documentación, configuración y .gitignore. Fase 1 requiere autorización posterior.

## DEC-014 — Disponibilidad independiente

**Decisión:** Departamento tiene disponibilidad DISPONIBLE o NO_DISPONIBLE, independiente de sus movimientos. NO_DISPONIBLE bloquea nuevas entradas, incluidos envíos y atenciones directas; no cancela ni modifica movimientos activos y permite continuar su llegada/finalización.

**Motivo:** Atender estudiantes no vuelve automáticamente indisponible un departamento.

## DEC-015 — Estados y atención directa

**Decisión:** Los únicos estados de Movimiento son EN_CAMINO, EN_ATENCION y FINALIZADO. La atención directa comienza en EN_ATENCION, registra llegada/inicio y no tiene timestamp de envío ni tiempo de traslado. No se inventa un traslado de cero segundos.

**Motivo:** Representar estudiantes que llegan directamente sin crear estados ni recorridos ficticios.

## DEC-016 — Timestamps oficiales

**Decisión:** El backend genera los timestamps oficiales de creación, envío cuando corresponda, llegada/inicio y finalización. Los cronómetros y duraciones se calculan desde ellos; no se persisten contadores ni duraciones independientes.

**Motivo:** Mantener tiempos reconstruibles tras una recarga y evitar que los relojes de los dispositivos definan los datos oficiales.

## DEC-017 — Servidor y persistencia

**Decisión:** SQLite reside únicamente en el servidor Windows de la red local. Solo FastAPI accede directamente a ella. El backend se ejecuta inicialmente como un único proceso. Se usan SQLAlchemy para persistencia y Alembic para migraciones; las claves foráneas de SQLite se habilitan y respetan en cada conexión.

**Motivo:** Una base local con cambios de esquema versionados y relaciones protegidas satisface el MVP. Alembic es la dependencia aprobada para las migraciones requeridas en Fase 1; no se instala durante Fase 0.1.

## DEC-018 — Concurrencia e integridad

**Decisión:** La garantía de un movimiento activo combina validación del backend, transacción y restricción apropiada en la base de datos. La implementación concreta corresponde a Fase 5, con prueba concurrente desde esa fase y aplicación también a atención directa en Fase 8.

**Motivo:** Una comprobación previa o un botón deshabilitado no protegen frente a solicitudes simultáneas.

## DEC-019 — WebSocket y recuperación

**Decisión:** WebSocket solo comunica cambios después de confirmar la transacción. La API/backend, respaldada por SQLite, es la fuente oficial del estado. Al abrir, recargar o reconectar, los clientes recuperan el estado por API. Las fases que incorporan recursos implementan también su consulta y recuperación.

**Motivo:** No depender de mensajes transitorios para reconstruir movimientos, disponibilidad y cronómetros.

## DEC-020 — Importación controlada

**Decisión:** La primera versión importa estudiantes desde Excel de forma controlada, revisando filas vacías, incompletas, inválidas y posibles duplicados. No fusiona homónimos automáticamente ni modifica el archivo original. El sistema opera desde SQLite, sin dependencia cotidiana del Excel.

**Motivo:** Nombre, curso y paralelo permiten distinguir coincidencias visualmente, pero no garantizan identidad única. No se presupone actualización automática mediante reimportación.

## DEC-021 — Interfaz y alcance visible

**Decisión:** Habrá una sola interfaz general para PC y celular, agrupada en Inspección, DECE y Salud. Sin login, usuarios ni perfiles. Se identifica el departamento que atiende, no un funcionario. La búsqueda solo usa nombres y apellidos; curso y paralelo acompañan los resultados. Carnet y código institucional no pertenecen al MVP.

**Motivo:** Mantener una operación sencilla sin introducir entidades ni funcionalidades ajenas al alcance.

## DEC-022 — Desarrollo incremental verificable

**Decisión:** Cada fase incluye la interfaz mínima, acceso LAN básico y recuperación por API que necesite para verificarse. Fase 9 consolida la interfaz, Fase 10 valida tiempo real completo, Fase 11 integra pruebas y Fase 12 valida integralmente la red local. No se pospone a esas fases la integridad necesaria en fases anteriores.

**Motivo:** Evitar dependencias hacia funcionalidades todavía no implementadas, respetando el orden del roadmap.

## DEC-023 — Codex y archivos locales

**Decisión:** Mantener los roles backend_specialist, frontend_angular, product_ux y qa_reviewer con propiedades compatibles con el CLI instalado. Product UX y QA son revisores de solo lectura. La configuración del proyecto reside en .codex/config.toml y las configuraciones de roles en .codex/agents/.

**Motivo:** Mantener responsabilidades claras y configuración verificable. .gitignore excluye datos reales, SQLite local, Excel institucional, secretos, entornos, dependencias, artefactos, cachés y temporales antes de generar código. No se realizan commits en Fase 0.1.

---

## DEC-024 — Implementación autorizada de Fase 1

**Decisión:** El usuario autoriza exclusivamente el esqueleto técnico de Fase 1. Se implementan GET /api/health con respuesta {"status":"ok"}, WebSocket /ws sin eventos de negocio, configuración SQLite/SQLAlchemy/Alembic, errores HTTP básicos y una página Angular de comprobación de conexiones. No se crean tablas del dominio ni se inicia Fase 2.

**Motivo:** Validar las tecnologías y su comunicación antes de introducir entidades del colegio. Las decisiones técnicas rutinarias pueden resolverse sin alterar producto, arquitectura, integridad, modelo conceptual o roadmap.

## DEC-025 — Desarrollo local de Fase 1

**Decisión técnica:** Angular 21 standalone, sin SSR, router, formularios ni librerías UI, compatible con el Node 24.14 instalado. El frontend utiliza HttpClient y WebSocket nativo con rutas relativas al mismo origen. El servidor Angular de desarrollo escucha por defecto en 127.0.0.1:4200 y proxifica /api/** y /ws hacia FastAPI en 127.0.0.1:8000. CORS enumera los orígenes locales permitidos; no utiliza comodines.

**Motivo:** Facilitar pruebas de desarrollo y preparar acceso LAN posterior sin fijar localhost como destino en el código del navegador. El proxy es de desarrollo y no representa un despliegue de producción. El arranque documentado usa un único proceso FastAPI.

**Validación:** La página consulta health con timeout y muestra el estado WebSocket. Permite desconectar y volver a comprobar manualmente. No hay recuperación de entidades ni eventos de negocio porque todavía no existen; estas capacidades se incorporan en las fases previstas. Las versiones resueltas del frontend quedan en package-lock.json; las dependencias directas del backend se fijan en sus archivos requirements.

**Referencias:** [Compatibilidad Angular](https://angular.dev/reference/versions), [proxy de desarrollo](https://angular.dev/tools/cli/serve), [pruebas Angular](https://angular.dev/guide/testing).

---

## DEC-026 — Fase 2 autorizada: departamentos

**Decisión:** Implementar exclusivamente Department en la tabla departments: id, name, group, active y availability. Los grupos son INSPECCION, DECE y SALUD; la disponibilidad admite DISPONIBLE y NO_DISPONIBLE. La primera migración de dominio crea la tabla e inserta los ocho departamentos definidos en DATA_MODEL.md, activos y disponibles, con IDs generados por SQLite. Se aplican CHECK y unicidad por grupo/nombre. No hay timestamps ni otras tablas de dominio.

**Operación:** GET /api/departments devuelve todos los departamentos ordenados por grupo (Inspección, DECE, Salud) e ID. PUT /api/departments/{department_id}/availability establece el valor explícito; responde 200 sin modificar ni avisar si ya coincide. Errores 404 para inexistente, 409 para inactivo y 422 para entrada inválida. Los inactivos siguen visibles, sin control habilitado. No hay CRUD general ni activación/desactivación.

## DEC-027 — Disponibilidad persistente y sincronización simple

**Decisión:** Las escrituras usan transacciones cortas; prevalece la última escritura confirmada. Después del commit de un cambio real se difunde únicamente {"type":"departments_changed"} por /ws. Un fallo de difusión no revierte el commit. No hay eventos persistentes, replay, IDs o timestamps de eventos ni objetos Department dentro del mensaje.

**Frontend:** Recuperar el listado al abrir, recibir un aviso y reconectar. Usar un solo socket y temporizador de reconexión, evitar respuestas antiguas y conservar el estado confirmado mientras se guarda. Un PUT correcto provoca nueva consulta oficial. No hay actualización optimista ni reintentos automáticos de escrituras. La recuperación debe ser pequeña y comprensible.

**Alcance y validación:** No se agregan dependencias UI ni funciones de Fase 3. Se preservan .codex/config.toml y los archivos de agentes por instrucción expresa; sus referencias de Fase 1 son históricas. Se prueban migraciones solo con retrocesos sobre bases desechables. La comprobación manual LAN del usuario queda pendiente tras la implementación; FastAPI puede seguir en loopback detrás del proxy Angular. No se abren reglas permanentes de firewall ni se realizan commits.

## Regla general

Toda nueva decisión importante deberá registrarse en este documento antes de implementarse en el código.


## DEC-028 — Fase 3A autorizada

Fase 2 está completada y validada por el usuario en PC/celular LAN, base 882af13.
Fase 3 se divide en 3A (esquema, parser, validación, comparación y preview) y
3B (resoluciones y aplicación), con revisión humana intermedia. Solo 3A está autorizada.
Se incorporan Institution, AcademicPeriod, Student, StudentAcademicPlacement,
StudentContact, ImportBatch e ImportRow. El preview nunca crea/modifica datos operativos.
Student usa ID interno y documento opcional. Mínimos: nombre, apellido, curso y paralelo.
Procedencia de importación opcional para futuras altas manuales. No hay alta/edición manual ahora.
Ubicaciones académicas versionadas: máximo una abierta por estudiante/año; no inventar fechas efectivas.
Contactos por función, múltiples emergencias, sin Person global. Año activo explícito, institución única.
Guardar documentos/contactos no autoriza mostrar fichas; el panel operativo conserva información básica.

## DEC-029 — Perfil y preview

Perfil idukay_listado_filtrado_v1: encabezados agrupados de estudiante, representante,
padre, madre y dos bloques de emergencia. Reconocimiento por encabezados y combinaciones,
no coordenadas rígidas. Referencia inspeccionada: una hoja, 863 filas, institución y año en bloque superior.
Vacíos a NULL, trim; guion literal conservado con advertencia. UI: Sin registrar.
Documento/nombres proponen candidatos; nunca fusionan. Vacíos no proponen borrar valores existentes.
Categorías excluyentes NUEVO, SIN_CAMBIOS, ACTUALIZACION, REQUIERE_REVISION;
etiquetas de cambio y advertencias separadas. PADRON_COMPLETO declarado permite ausencias;
SUBCONJUNTO no. Ambigüedades impiden conclusiones de ausencia. Ausencia no altera datos.
Solo POST preview y GET lote/rows/absences paginados; no confirm ni resolutions.

## DEC-030 — Privacidad y borradores

TTL aprobado: 24 horas desde creación. Expirados no recuperables (410); se eliminan
filas, propuestas, candidatos y ausencias personales; se conserva una lápida mínima del lote.
Limpieza al acceder a importaciones y periódicamente cada minuto mientras FastAPI está activo;
al reiniciar se limpia antes de servir. Sin servidor activo, limpieza en el siguiente arranque.
No conservar Excel binario; cerrar carga temporal ante éxito/error. No logs con documentos/teléfonos.
Las pruebas usan libros sintéticos. El Excel real solo se lee localmente y no se copia ni versiona.
openpyxl y python-multipart son dependencias autorizadas para XLSX y multipart. No pandas.
Se conserva evidencia recibida y procedencia; la BASE importada aceptada se registrará en 3B,
no se actualiza al generar preview. No login/roles, búsqueda, movimientos ni nuevas funciones futuras.

## DEC-031 — Calidad separada de clasificación de importación

Corrección autorizada tras validación manual de 3A: warnings de calidad no determinan
la categoría. Un guion literal en campo opcional se conserva y advierte, sin convertirlo
a NULL ni elevar por sí solo un registro a REQUIERE_REVISION. Lo mismo aplica a un
contacto incompleto no bloqueante. La categoría depende de razones bloqueantes explícitas:
mínimos inválidos, institución incompatible, duplicados, correspondencia ambigua/conflictiva
o varias filas hacia un mismo Student. Documento opcional no elegible sin coincidencias
es advertencia; una correspondencia no segura sigue requiriendo resolución humana.
El payload separa warnings de blocking_review_reasons; conflicts permanece como alias
compatible para clientes anteriores. Los borradores existentes conservan su snapshot;
la clasificación corregida se obtiene generando una nueva previsualización.
