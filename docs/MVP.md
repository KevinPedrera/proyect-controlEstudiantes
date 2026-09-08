# MVP - Control Estudiantil

# Objetivo

Desarrollar la primera versión funcional del sistema Control Estudiantil para uso interno del colegio.

El objetivo del MVP es optimizar el seguimiento de estudiantes entre los diferentes departamentos mediante información en tiempo real, reduciendo llamadas, mensajes y consultas manuales.

La primera versión prioriza simplicidad, rapidez, estabilidad y facilidad de uso.

---

# Alcance

Esta versión permitirá controlar el recorrido de un estudiante entre departamentos dentro de la red local del colegio.

No busca reemplazar todos los procesos administrativos, sino validar el flujo operativo diario.

---

# Flujo principal

## 1. Buscar estudiante

El usuario podrá buscar solamente por:

- Apellidos
- Nombres

La información será consultada desde la base de datos local previamente importada desde el archivo Excel institucional.

---

## 2. Seleccionar estudiante

Al seleccionar un estudiante se visualizará únicamente:

- Nombres
- Apellidos
- Curso
- Paralelo

Curso y paralelo permiten distinguir coincidencias. No se requiere carnet ni código institucional.

---

## 3. Seleccionar departamento de destino

Cualquier departamento podrá enviar un estudiante a cualquier otro departamento.

Ejemplos:

- Inspección → DECE
- Inspección → Médico
- Médico → DECE
- DECE → Odontología

No existirá dependencia exclusiva de Inspección.

---

## 4. Enviar estudiante

Al enviar:

- El departamento destino recibe una notificación inmediata.
- El movimiento se crea en estado **EN_CAMINO**.
- Inicia automáticamente el cronómetro de traslado.

---

## 5. Llegada

Cuando el estudiante llegue al departamento destino:

- Se presiona el botón **Llegó**.
- Finaliza el tiempo de traslado.
- Inicia automáticamente el tiempo de atención.
- El movimiento cambia a **EN_ATENCION**.

---

## 6. Finalizar atención

Al finalizar:

- Se registra la hora de salida.
- Se conserva el timestamp de finalización; el tiempo de atención se calcula a partir de los timestamps.
- El movimiento cambia a FINALIZADO.
- El estudiante queda disponible para futuros movimientos.

---

# Atención directa

Cualquier departamento puede buscar y seleccionar a un estudiante e iniciar su atención directamente en EN_ATENCION. Se registra inmediatamente el timestamp de llegada/inicio generado por el backend.

No existe envío ni tiempo de traslado: no se inventa un traslado de cero segundos. Se aplica la misma regla de un único movimiento activo y el destino debe aceptar nuevas entradas.

---

# Estados del movimiento

- EN_CAMINO
- EN_ATENCION
- FINALIZADO

---

# Estados del departamento

Cada departamento indica su disponibilidad operativa:

- DISPONIBLE: puede recibir nuevas entradas.
- NO_DISPONIBLE: bloquea nuevos envíos y nuevas atenciones directas.

La disponibilidad es independiente de los movimientos: un departamento disponible puede atender varios estudiantes. Marcarlo NO_DISPONIBLE no cancela ni modifica movimientos activos; estos pueden continuar su llegada y finalización.

---

# Validaciones

## Permitido

- Varios estudiantes pueden estar asignados al mismo departamento.

## No permitido

- Un estudiante no puede tener más de un movimiento activo, incluso si ambos tienen el mismo destino. Son activos EN_CAMINO y EN_ATENCION.

El backend protegerá esta regla mediante validación, transacción y una restricción apropiada en SQLite, también ante solicitudes simultáneas de diferentes dispositivos.

---

# Departamentos incluidos

## Inspección

- General
- Primaria
- Bachillerato

## DECE

- Primaria
- Secundaria/Bachillerato
- Psicopedagogía

## Salud

- Médico
- Odontología

---

# Funcionalidades incluidas

- Buscar estudiante.
- Enviar estudiante.
- Notificaciones en tiempo real.
- Cronómetro de traslado.
- Cronómetro de atención.
- Confirmar llegada.
- Finalizar atención.
- Estados de departamentos.
- Validación de duplicidad.
- Atención directa sin traslado.
- Conservación de movimientos en la base de datos, sin pantalla de historial.

Los timestamps oficiales los genera el backend. No se almacenan contadores segundo por segundo ni duraciones independientes. Los cronómetros visibles se calculan desde los timestamps.

La aplicación tendrá una sola interfaz general para PC y celular, sin perfiles. Los departamentos se agrupan visualmente en Inspección, DECE y Salud.

WebSocket únicamente comunica cambios después del commit. Al abrir, recargar o reconectar, la interfaz recupera el estado oficial mediante API/backend. No existe una tabla Evento persistente en el MVP.

La importación desde Excel es controlada: se revisan datos incompletos, inválidos y posibles duplicados; no se fusionan estudiantes homónimos automáticamente ni se modifica el original.

---

# Funcionalidades NO incluidas

- Inicio de sesión.
- Roles.
- Permisos.
- Dashboard.
- Reportes.
- Estadísticas.
- Exportación a Excel.
- Exportación a PDF.
- Fotografías.
- Pantalla de historial.
- Información disciplinaria.
- Observaciones.
- Información del representante.
- Carnet digital.
- Integración con otros sistemas.

---

# Criterios de éxito

El MVP será considerado exitoso cuando:

- El flujo completo funcione en tiempo real.
- El envío entre departamentos sea inmediato.
- El personal pueda utilizar el sistema sin capacitación extensa.
- El tiempo de traslado y atención se registre correctamente.
- No existan estudiantes duplicados entre departamentos.
- La aplicación funcione correctamente en la red local del colegio.

---

# Versiones futuras

Una vez validado el MVP se evaluará incorporar:

- Inicio de sesión.
- Roles por departamento.
- Reportes.
- Dashboard.
- Fotografías.
- Información disciplinaria.
- Pantalla de historial del estudiante.
- Integración con otros sistemas institucionales.
- Aplicación móvil.
