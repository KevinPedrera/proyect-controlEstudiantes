# ROADMAP — Control Estudiantil

## 1. Objetivo

Este documento define el orden de desarrollo del MVP de Control Estudiantil.

El proyecto se desarrollará en fases pequeñas y verificables.

Una fase NO debe comenzar hasta que la anterior funcione correctamente.

Codex no debe adelantarse a fases posteriores ni implementar
funcionalidades que no estén contempladas en el MVP.

Estado actual: Fases 2 y 3A completadas y validadas manualmente. Fase 3B implementada, con alumnado operacional cargado. Fase 4 cerrada en Git. Fase 5 implementada; cierre técnico aprobado y validación manual pendiente.

Las rutas documentales mencionadas en este archivo se expresan desde la raíz del proyecto.

Cada fase incorpora la interfaz mínima incremental y las consultas de estado por API necesarias para sus criterios de finalización. Se habilita acceso LAN básico cuando la comprobación requiera otros dispositivos. Las fases futuras 11 y 12 validan lo ya construido; no posponen estas capacidades mínimas.

---

# FASE 0 — Documentación y decisiones

## Objetivo

Definir el proyecto antes de escribir código.

## Documentos base

- README.md
- docs/MVP.md
- docs/ARCHITECTURE.md
- docs/DATA_MODEL.md
- docs/DECISIONS.md
- docs/ROADMAP.md

## Criterio de finalización

La fase termina cuando los documentos anteriores sean coherentes
entre sí y no existan decisiones fundamentales pendientes.

---

# FASE 0.1 — Saneamiento documental y configuración

## Objetivo

Aplicar las decisiones aprobadas de saneamiento a docs/, README.md, AGENTS.md, .codex/ y .gitignore.

## Criterio de finalización

- Referencias documentales válidas y contradicciones de la auditoría corregidas.
- Cuatro roles conservados y configuración verificada en la medida permitida por el CLI local.
- Product UX y QA configurados como revisores de solo lectura.
- Exclusiones de archivos locales definidas.
- Sin código de aplicación, dependencias instaladas, base de datos ni commits.

Completar esta fase no inicia automáticamente Fase 1.

---

# FASE 1 — Esqueleto técnico

## Objetivo

Crear una base mínima del proyecto sin implementar todavía
la lógica completa de negocio.

## Backend

Crear proyecto FastAPI.

Debe incluir:

- estructura organizada;
- configuración;
- conexión con SQLite mediante SQLAlchemy, únicamente desde FastAPI en el servidor Windows;
- claves foráneas habilitadas y respetadas;
- sistema inicial de migraciones con Alembic;
- endpoint de salud;
- soporte inicial para WebSocket;
- manejo básico de errores.

Ejemplo:

GET /api/health

Debe responder correctamente para confirmar que el backend funciona.

## Frontend

Crear proyecto Angular.

Debe incluir:

- estructura inicial;
- configuración de desarrollo;
- servicio para comunicarse con el backend;
- configuración de WebSocket;
- pantalla inicial mínima.

## Integración

Angular debe poder comunicarse correctamente con FastAPI.

El backend se ejecuta inicialmente como un único proceso. Se prepara la comunicación HTTP/WebSocket sin implementar movimientos ni tablas de fases posteriores. Los timestamps oficiales de los futuros recursos los generará el backend.

## Criterio de finalización

La fase termina cuando:

- FastAPI inicia correctamente;
- Angular inicia correctamente;
- SQLite funciona;
- frontend y backend se comunican;
- existe una conexión WebSocket funcional;
- no existen errores importantes al iniciar el sistema.

NO implementar todavía el flujo completo de estudiantes.

---

# FASE 2 — Departamentos

## Objetivo

Crear la estructura básica de departamentos.

Implementar los departamentos definidos en docs/DATA_MODEL.md.

El sistema debe poder conocer:

- nombre;
- grupo o tipo;
- disponibilidad;
- estado activo/inactivo.

## Funcionalidad

Cada departamento podrá marcarse como:

- DISPONIBLE.
- NO_DISPONIBLE.

Los cambios deben aparecer en tiempo real en los demás clientes.

Incluir una vista mínima de departamentos, su consulta por API y recuperación al abrir, recargar o reconectar. Emitir el aviso WebSocket después de confirmar la transacción. La disponibilidad es independiente de los movimientos. NO_DISPONIBLE bloquea nuevas entradas cuando estas se implementen; no altera movimientos activos.

## Criterio de finalización

Abrir el sistema simultáneamente en dos dispositivos.

Habilitar aquí el acceso LAN básico necesario; Fase 12 realizará la validación integral.

Cambiar el estado de un departamento en uno.

El segundo dispositivo debe reflejar el cambio sin recargar
manualmente la página.

---

# FASE 3A — Esquema y previsualización

Fase completada: Institution, AcademicPeriod, Student, StudentAcademicPlacement,
StudentContact, ImportBatch e ImportRow; parser idukay_listado_filtrado_v1,
validación, candidatos, comparación, preview persistido e interfaz mínima.
Solo ImportBatch/ImportRow reciben datos. TTL 24 horas con limpieza de contenido personal.
NULL interno, guiones conservados con advertencia, sin fusiones automáticas.
Los vacíos entrantes no borran valores existentes. PADRON_COMPLETO permite ausencias
solo si la identidad es concluyente; SUBCONJUNTO no calcula ausencias.
Documento opcional; mínimos nombre/apellido/curso/paralelo. Contactos por función;
ubicaciones académicas versionadas y año activo explícito. Sin fechas inventadas.

Cierre: perfil real reconoce 863 filas, institución/año y dos bloques de emergencia;
pruebas de parser, comparación, no destrucción, limpieza y regresión aprobadas;
build/migraciones/QA correctos. Validación manual de 3A confirmada por el usuario.

# FASE 3B — Confirmación y aplicación segura (IMPLEMENTADA; VALIDACIÓN MANUAL PENDIENTE)

Preview obligatorio con contrato de aplicación compatible. Confirmación explícita del
lote completo sin bloqueos; aplicación atómica, idempotente y protegida contra obsolescencia.
Corregir correspondencias débiles falsas y calcular cambios efectivos conservando vacíos,
guiones, contactos y procedencia. Institución/periodo propuestos requieren aceptación
explícita; historial académico preservado. Comprobante recuperable tras pérdida de
respuesta y después de purgar PII temporal a las 24 horas. Migración 0003 sin cambiar
0001/0002. No resolución individual, alta/edición manual, búsquedas, movimientos ni bajas.
Cierre: pruebas de aplicación sintética, reimportación, rollback, concurrencia, privacidad,
migración, regresión de 2/3A y QA independiente. La primera aplicación institucional real
queda reservada al usuario tras la validación técnica. No commit/push automático.

---

# FASE 4 — Búsqueda y selección de estudiantes

## Objetivo

Implementar una búsqueda sencilla y rápida.

La búsqueda será únicamente por:

- nombres;
- apellidos.

Cada resultado mostrará:

Nombre Apellido
Curso — Paralelo

Esto permitirá diferenciar estudiantes con nombres iguales.

## Criterio de finalización

Búsqueda incremental en backend, con hasta cinco coincidencias visibles; no descargar todo el alumnado. La comparación para búsqueda puede ignorar tildes, sin usarla para decidir identidad.

El personal puede escribir una parte del nombre o apellido
y encontrar rápidamente al estudiante correcto.

Implementación: GET /api/students/search sobre alumnos activos y ubicación abierta
del periodo activo, con normalización de tildes/mayúsculas y orden de términos.
Componente reutilizable con debounce de 300 ms, cancelación de consultas antiguas,
cinco resultados como máximo, selección local y «Cambiar estudiante». Sin migración.
Revisar escritorio, tablet, teléfono vertical/estrecho, foco y targets táctiles.
Fase 4 fue cerrada por el usuario. Fase 5 tiene autorización posterior explícita.

---

# FASE 5 — Flujo operativo completo de movimientos

Autorizada después de Fase 4 cerrada en cc19ef7. Consolida las capacidades antes
separadas en fases 5–10: envío, llegada, finalización, cancelación, atención directa,
paneles por destino, cronómetros, disponibilidad con advertencia y tiempo real.
Un solo activo global por estudiante, mediante transacción e índice SQLite.
Historial persistido y referencia a la versión académica del inicio.
Recuperación por API al abrir/recargar/reconectar; interfaz móvil y escritorio.
Nueva migración 0004; preservar 0001–0003. No migrar la base institucional durante
desarrollo. Pruebas sintéticas, navegador real y QA independiente de solo lectura.
No transferencias, envío múltiple, reportes ni historial visual.
Cierre técnico: 243 pruebas backend, 66 frontend, build y migración desechable correctos.
QA independiente aprobado. Validación manual del usuario pendiente; base institucional
sin migrar y sin movimientos reales. Contrato, evidencia y guía: [Movimientos](MOVEMENTS.md).

Las antiguas fases 6–10 quedan absorbidas por esta autorización. Las siguientes
etapas son futuras y no se inician automáticamente.

---

# FASE 11 — Pruebas funcionales

Probar como mínimo:

## Caso 1

Inspección envía estudiante a DECE.

Resultado esperado:

DECE lo visualiza inmediatamente como EN CAMINO.

## Caso 2

DECE confirma llegada.

Resultado esperado:

termina el tiempo de traslado y comienza el tiempo de atención.

## Caso 3

DECE finaliza atención.

Resultado esperado:

el estudiante queda nuevamente disponible.

## Caso 4

Intentar enviar un estudiante que ya tiene movimiento activo.

Resultado esperado:

operación rechazada.

## Caso 5

Varios estudiantes enviados al mismo departamento.

Resultado esperado:

todos pueden coexistir.

## Caso 6

Estudiante llega directamente a Médico.

Resultado esperado:

Médico puede iniciar atención directamente.

## Caso 7

Departamento cambia a NO DISPONIBLE.

Resultado esperado:

todos los dispositivos ven el cambio.

## Caso 8

Recargar una página mientras existen movimientos activos.

Resultado esperado:

el estado y los tiempos siguen siendo correctos.

## Caso 9

Dos dispositivos realizan acciones casi simultáneamente.

Resultado esperado:

el backend mantiene un estado consistente y no permite movimientos
activos duplicados.

---

# FASE 12 — Prueba en red local

## Objetivo

Ejecutar el sistema desde la computadora Windows destinada
temporalmente a servidor.

Esta fase es la validación integral de red local del MVP completo. El acceso LAN básico ya se utilizó en las fases cuyos criterios exigían varios dispositivos.

Otros dispositivos del colegio deberán acceder utilizando
la red local.

Probar:

- PC de Inspección;
- PC de DECE;
- celular;
- varios dispositivos simultáneos.

Verificar:

- conexión;
- estabilidad;
- actualización en tiempo real;
- tiempos;
- comportamiento al desconectar/reconectar un dispositivo.

---

# FASE 13 — Piloto real

Una vez superadas las pruebas técnicas, iniciar una prueba
controlada con personal del colegio.

Durante el piloto NO agregar funcionalidades inmediatamente.

Primero recopilar:

- problemas;
- errores;
- confusiones de interfaz;
- pasos innecesarios;
- necesidades reales;
- funciones que verdaderamente hacen falta.

El objetivo del piloto es responder:

> ¿El personal realmente utiliza el sistema y mejora el seguimiento
> de estudiantes?

---

# FASE 14 — Evaluación del MVP

Después del piloto clasificar las solicitudes en:

## Corrección

Algo existente no funciona correctamente.

Prioridad alta.

## Mejora

Algo existente funciona pero puede hacerse más sencillo.

Evaluar para siguiente versión.

## Nueva funcionalidad

Algo que actualmente no pertenece al MVP.

No implementar automáticamente.

Debe evaluarse antes de modificar la arquitectura.

---

# POS-MVP

Solo después de validar el sistema podrán estudiarse funcionalidades
como:

- usuarios;
- roles;
- permisos;
- historial avanzado;
- reportes;
- estadísticas;
- dashboards;
- exportación a Excel (la importación controlada pertenece a Fase 3);
- PDF;
- fichas ampliadas de estudiantes;
- sanciones;
- fichas de representantes (almacenamiento y preview ya incluidos en 3A);
- notificaciones externas (los avisos WebSocket pertenecen al MVP);
- despliegue fuera de la red local;
- PostgreSQL;
- aplicación móvil;
- otros colegios.

Ninguna de estas funcionalidades pertenece al desarrollo actual.

---

# REGLA PARA CODEX

Codex deberá trabajar solamente sobre la fase que se le indique.

No deberá:

- adelantar fases;
- implementar funcionalidades futuras;
- modificar decisiones arquitectónicas;
- agregar dependencias innecesarias;
- introducir usuarios o autenticación;
- implementar reportes;
- cambiar tecnologías sin autorización;
- rediseñar el alcance del producto.

Si durante una implementación descubre que necesita tomar una
decisión que cambie arquitectura, alcance, integridad, modelo conceptual o roadmap y no está definida en la documentación, deberá detenerse
y documentar la duda en lugar de decidir unilateralmente.

Las decisiones técnicas rutinarias pueden resolverse con la solución más simple y documentarse brevemente cuando sea útil, según la autorización de la fase actual.

---

# CRITERIO FINAL DEL MVP

El MVP estará terminado cuando podamos realizar de forma estable:

BUSCAR
   ↓
ENVIAR
   ↓
EN CAMINO
   ↓
LLEGÓ
   ↓
EN ATENCIÓN
   ↓
FINALIZAR

y también:

LLEGADA DIRECTA
   ↓
INICIAR ATENCIÓN
   ↓
FINALIZAR

con varios dispositivos conectados simultáneamente y actualizaciones
en tiempo real.

El éxito del MVP no se medirá por la cantidad de funcionalidades.

Se medirá por que este flujo sea:

- simple;
- rápido;
- estable;
- comprensible;
- útil para el personal del colegio.
