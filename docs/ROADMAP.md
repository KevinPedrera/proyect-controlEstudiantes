# ROADMAP — Control Estudiantil

## 1. Objetivo

Este documento define el orden de desarrollo del MVP de Control Estudiantil.

El proyecto se desarrollará en fases pequeñas y verificables.

Una fase NO debe comenzar hasta que la anterior funcione correctamente.

Codex no debe adelantarse a fases posteriores ni implementar
funcionalidades que no estén contempladas en el MVP.

Estado actual: Fase 1 — esqueleto técnico completado y validado mediante pruebas automatizadas y comprobación manual de HTTP/WebSocket. Fase 0.1 completada. Fase 2 no iniciada.

Las rutas documentales mencionadas en este archivo se expresan desde la raíz del proyecto.

Cada fase incorpora la interfaz mínima incremental y las consultas de estado por API necesarias para sus criterios de finalización. Se habilita acceso LAN básico cuando la comprobación requiera otros dispositivos. Las fases 9, 10, 11 y 12 consolidan y validan lo ya construido; no posponen estas capacidades mínimas.

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

# FASE 3 — Importación de estudiantes

## Objetivo

Importar los estudiantes desde el Excel institucional a SQLite.

El Excel será una fuente de importación.

NO será utilizado directamente durante el funcionamiento normal
del sistema.

## Datos necesarios para el MVP

Importar únicamente los campos necesarios para obtener:

- nombres;
- apellidos;
- curso;
- paralelo.

También se generará un ID interno.

## Validaciones

La importación debe detectar y manejar:

- filas vacías;
- información incompleta;
- registros inválidos;
- posibles duplicados.

No modificar automáticamente el archivo Excel original.

La importación será controlada. No fusionar homónimos automáticamente ni asumir que nombre, curso y paralelo identifican unívocamente a una persona. Revisar posibles duplicados y correspondencias antes de cualquier reimportación; no implementar sincronización automática con Excel.

## Criterio de finalización

Los estudiantes pueden importarse y posteriormente consultarse
desde la base de datos.

---

# FASE 4 — Búsqueda de estudiantes

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

El personal puede escribir una parte del nombre o apellido
y encontrar rápidamente al estudiante correcto.

---

# FASE 5 — Crear movimiento

## Objetivo

Implementar la primera parte del flujo principal.

Flujo:

Buscar estudiante
      ↓
Seleccionar estudiante
      ↓
Seleccionar departamento
      ↓
Enviar
      ↓
EN CAMINO

Al realizar el envío:

1. El backend valida al estudiante.
2. Comprueba que no tenga otro movimiento activo.
3. Comprueba que el destino sea válido y acepte nuevas entradas.
4. Crea el movimiento.
5. Registra la hora de envío.
6. Marca el movimiento como EN CAMINO.
7. Confirma la transacción y después notifica el cambio mediante WebSocket.

La hora oficial la genera el backend. Movimiento requiere destino, no origen. No crear tabla Evento. Incluir interfaz mínima de envío y consulta de movimientos activos por API para abrir, recargar o reconectar.

## Regla obligatoria

Un estudiante NO puede tener dos movimientos activos.

Un departamento SÍ puede tener varios estudiantes.

La garantía combina validación, transacción y restricción apropiada en SQLite. EN_CAMINO y EN_ATENCION son activos; dos movimientos al mismo destino también están prohibidos para el mismo estudiante.

## Criterio de finalización

Intentar enviar dos veces al mismo estudiante debe ser rechazado
por el backend.

Probar desde esta fase dos solicitudes realmente concurrentes desde clientes independientes para el mismo estudiante: solo un movimiento activo puede quedar confirmado en la base. Verificar además que distintos estudiantes puedan compartir destino. No esperar a Fase 11 para comprobar integridad.

---

# FASE 6 — Llegada y tiempo de traslado

## Objetivo

Permitir que el departamento confirme la llegada del estudiante.

Mientras esté:

EN CAMINO

la interfaz mostrará el tiempo transcurrido desde el envío.

El departamento tendrá una acción:

"Llegó"

Al pulsarla:

EN CAMINO
     ↓
EN ATENCIÓN

Se registra la hora de llegada.

El tiempo de traslado queda determinado por:

hora_llegada - hora_envio

## Importante

No guardar un contador cada segundo en la base de datos.

Guardar únicamente timestamps.

Los genera el backend. Incluir consulta por API y reconstrucción del cronómetro tras recarga o reconexión, con una interfaz mínima de llegada. NO_DISPONIBLE no impide continuar la llegada de un movimiento ya activo.

La interfaz calcula el contador visual.

## Criterio de finalización

El cronómetro debe continuar mostrando un tiempo correcto incluso
si la página se recarga.

---

# FASE 7 — Atención y finalización

## Objetivo

Controlar el tiempo que el estudiante permanece en el departamento.

Cuando se confirma:

"Llegó"

comienza visualmente el tiempo de atención.

El departamento podrá seleccionar:

"Finalizar atención"

Entonces:

EN ATENCIÓN
      ↓
FINALIZADO

Se registra la fecha y hora de finalización.

El estudiante deja de tener un movimiento activo.

## Criterio de finalización

Después de finalizar la atención, el estudiante puede iniciar
un nuevo movimiento.

El movimiento anterior permanece almacenado como historial.

Historial significa conservación en la base de datos, sin pantalla de historial. Los avisos de llegada y finalización se emiten después del commit. La finalización de movimientos activos puede continuar aunque el departamento esté NO_DISPONIBLE.

---

# FASE 8 — Atención directa

## Objetivo

Permitir registrar estudiantes que llegan directamente a un
departamento sin haber pasado por Inspección.

Ejemplo:

Un estudiante llega directamente al Departamento Médico.

Flujo:

Buscar estudiante
      ↓
Seleccionar
      ↓
Iniciar atención
      ↓
EN ATENCIÓN

No existe tiempo de traslado para este movimiento.

Se crea directamente en EN_ATENCION, sin timestamp de envío ni traslado ficticio de cero segundos. El destino debe aceptar nuevas entradas; NO_DISPONIBLE bloquea iniciar esta nueva atención.

La hora de llegada/inicio se registra inmediatamente.

## Criterio de finalización

DECE, Médico u otro departamento puede registrar una atención
sin necesitar que Inspección haya creado previamente un movimiento.

La regla de un único movimiento activo continúa aplicándose.

Reutilizar su protección transaccional y de base de datos. Probar concurrencia entre atención directa y envío para el mismo estudiante. El backend genera el timestamp de inicio y avisa después del commit.

---

# FASE 9 — Panel general

## Objetivo

Construir la interfaz definitiva del MVP.

Consolidar las vistas mínimas incorporadas en fases anteriores; esta no es la primera fase con interfaz funcional. El panel general es la página operativa del flujo, no un dashboard estadístico.

Será UNA sola página.

No existirán perfiles ni diferentes paneles para cada usuario
durante el MVP.

La información estará separada visualmente por áreas.

Ejemplo conceptual:

CONTROL ESTUDIANTIL

INSPECCIÓN
--------------------------------
Inspección General
Inspección Primaria
Inspección Bachillerato

DECE
--------------------------------
DECE Primaria
DECE Secundaria/Bachillerato
Psicopedagogía

SALUD
--------------------------------
Médico
Odontología

Cada área deberá mostrar claramente:

- disponibilidad;
- estudiantes en camino;
- estudiantes en atención;
- tiempos correspondientes.

La prioridad será:

1. Claridad.
2. Rapidez.
3. Facilidad de aprendizaje.
4. Funcionamiento en PC y celular.

No priorizar animaciones ni elementos decorativos.

---

# FASE 10 — Tiempo real completo

## Objetivo

Validar conjuntamente todos los eventos WebSocket.

Deben actualizarse sin recargar:

- disponibilidad de departamentos;
- nuevos movimientos;
- estudiantes en camino;
- llegada;
- estudiantes en atención;
- finalización.

## Regla arquitectónica

WebSocket NO es la fuente oficial de datos.

SQLite/backend mantiene el estado real.

Si un dispositivo pierde temporalmente la conexión, debe poder
recuperar el estado correcto al reconectarse.

Validar conjuntamente la recuperación por API ya incorporada a cada recurso al abrir, recargar o reconectar, y la coordinación entre consultas y avisos para evitar pérdida de cambios o respuestas desactualizadas. No implementar una tabla Evento ni reproducción persistente de mensajes.

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
- representantes;
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

Las decisiones técnicas rutinarias pueden resolverse con la solución más simple y documentarse brevemente cuando sea útil, según la autorización de Fase 1.

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
