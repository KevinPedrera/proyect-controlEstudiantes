# Preview de importación — Fase 3A

Estado: 3A implementada, QA sin bloqueos y validación manual pendiente. No hay aplicación, resolución, alta/edición
manual ni búsqueda de Fase 4. La revisión humana de 3A precede a una autorización de 3B.

## Perfil idukay_listado_filtrado_v1

Referencia inspeccionada: una hoja `Listado de estudiantes`, 863 filas desde la 8,
institución en B1, título descriptivo en B2 y `Año Lectivo 2026 - 2027` en B3.
Grupos de la fila 5, campos de la fila 6 combinados verticalmente con la 7.
Estas posiciones son evidencia de referencia, no el único criterio del parser.

| Bloque observado | Columnas |
| --- | --- |
| Estudiante | C:J: documento, tipo, apellidos, nombres, curso, paralelo |
| Representante legal | K:Q: parentesco, apellidos, nombres, casa, celular |
| Padre | R:W: apellidos, nombres, casa, celular |
| Madre | X:AC: apellidos, nombres, casa, celular |
| Emergencia 1 | AD:AI: parentesco, nombre, apellido, celular, domicilio, trabajo |
| Emergencia 2 | AJ:AO: misma secuencia de seis campos |

El parser reconoce títulos de grupos, extensión de combinaciones, campos subordinados
y dos repeticiones completas de emergencia. Tolera desplazamientos inequívocos de filas.
Exige una única cabecera compatible en las primeras 40 filas. Reconstruye únicamente
encabezados; no rellena celdas de estudiantes. La numeración no identifica estudiantes.
Institución: celda única sobre el título y en su columna. Año: etiqueta explícita única.
Una estructura incompatible/ambigua se rechaza. No se interpreta un Excel universal.

Límites técnicos: XLSX 5 MB, multipart con 64 KiB de margen, ZIP 40 MB descomprimidos,
200 entradas, 10 hojas, 5007 filas y 80 columnas por hoja; valores de hasta 240 caracteres.
Se comprueban coordenadas y combinaciones antes de cargar el libro. No macros/XML con
entidades, fórmulas ni celdas de error. No se ejecutan fórmulas ni se guarda el original.
La carga multipart se cierra también al fallar; su temporal lo gestiona y elimina Starlette.
Solo se conserva la huella SHA-256 del binario, no su nombre ni su copia.

## Interpretación y comparación

Ausentes/cadenas vacías → NULL; trim seguro. `-` conserva evidencia con advertencia.
Celda numérica → texto sin rellenar ceros, con advertencia. Contactos incompletos se
conservan; bloques vacíos no crean contactos. Mínimos: nombre/apellido/curso/paralelo.
La UI usa Sin registrar, pero nunca persiste ese texto como sustituto del dato.

Documento opcional. Elegibilidad estructural: Cédula diez dígitos; Pasaporte 5–30
caracteres alfanuméricos. No certifica identidad ni verifica un registro oficial.
Documento coincidente, nombre completo o primer nombre/apellido iguales proponen candidatos.
Para clasificar una correspondencia como fuerte se requieren documento/tipo/nombre completo
coincidentes y elegibles, sin otros candidatos. Aun así no se vincula ni aplica nada.
Duplicados de documento/nombre dentro del archivo y varias filas hacia un candidato
requieren revisión. El origen manual del estudiante no lo excluye de la comparación.

Categorías excluyentes: NUEVO, SIN_CAMBIOS, ACTUALIZACION, REQUIERE_REVISION.
Etiquetas: DATOS_PERSONALES, DOCUMENTO, CURSO, PARALELO, CONTACTOS.
Cada diferencia conserva valor actual, recibido y acción propuesta; vacío conserva actual.
Los contactos se comparan como conjunto de funciones y datos, ignorando orden de emergencias;
una diferencia propone revisión del conjunto sin vincular ni reemplazar contactos por posición.
Guiones, celdas numéricas y documentos no elegibles se señalan como advertencias de
calidad. Las advertencias no elevan por sí solas la categoría. REQUIERE_REVISION depende
exclusivamente de blocking_review_reasons: mínimos inválidos, institución incompatible,
duplicados, correspondencia no segura o varias filas hacia el mismo estudiante.
conflicts conserva esas mismas razones como alias compatible. Un guion en un mínimo
sigue siendo inválido; un guion opcional se conserva literalmente con warning.
Un documento literal "-" tampoco se usa como señal compartida de identidad ni como
documento duplicado; su valor original y warning se conservan.
El resumen distingue quality_warning_count, rows_with_warnings y rows_with_blocking_reasons.

El usuario declara PADRON_COMPLETO o SUBCONJUNTO. Solo el primero permite calcular
ausencias del mismo periodo, y se suprimen si hay conflictos de identidad, mínimos o institución.
Una ausencia es informativa: no borra, desactiva ni cierra ubicaciones.
La comparación registra la huella del snapshot operativo, excluyendo departamentos/borradores.
La BASE aceptada futura reside en source_baseline opcional, nunca se actualiza desde preview.

## HTTP

| Método / ruta | Respuesta |
| --- | --- |
| POST /api/student-imports/preview | Multipart con exactamente file y scope. 201 con resumen e ID UUID |
| GET /api/student-imports/{id} | Resumen, institución/año propuestos, categorías, advertencias, vencimiento |
| GET /api/student-imports/{id}/rows | items/total/page/page_size; evidencia, candidatos y diferencias |
| GET /api/student-imports/{id}/absences | Mismo formato paginado, solo información básica de ausentes |

Paginación: page ≥ 1, page_size de 1 a 100 (por defecto 25; UI 10).
404 inexistente; 410 vencido; 415 extensión incompatible; 422 datos/perfil inválidos;
413 carga excesiva, también sin Content-Length; 400 multipart inválido. Los errores se rechazan sin conservar temporales.
Respuestas correctas no-store. Sin confirm/resolutions ni otros endpoints operativos.
Una nueva carga genera un nuevo borrador; no hay reenvío automático. Recuperación por ID.

## TTL y privacidad

24 horas exactas desde creación; tiempo del servidor UTC. Limpieza al arrancar,
cada minuto mientras FastAPI está activo y antes de operaciones sobre borradores.
Al vencer, API devuelve 410. Se borran ImportRow y proposal completo (incluidas
ausencias/candidatos); quedan ID, perfil, hash, alcance, fechas y status EXPIRED.
Si el servidor está apagado, la limpieza sucede al siguiente arranque antes de servir.
SQLite usa secure_delete; esto no modifica copias de respaldo externas preexistentes.
La UI retira el preview al alcanzar su vencimiento y no guarda datos personales en localStorage.

No hay login ni roles; conocer un ID no es autenticación. Los detalles personales están
limitados al preview y no se añaden al panel de departamentos. Evitar datos sensibles en
logs/errores; SQLAlchemy oculta parámetros SQL. La política de trazabilidad aplicada
y sus retenciones deberán revisarse en 3B, sin reutilizar un borrador vencido.

## Verificación

Pruebas automatizadas con libros sintéticos generados en memoria. Migraciones sobre bases
desechables; no tocar 0001_departments. La validación local del archivo real solo imprime
recuentos/estructura, no documentos, nombres personales ni teléfonos. No copiarlo al repositorio.
El parser validado obtiene 863 filas, dos emergencias, institución/año esperados,
cero faltantes mínimos y 59 advertencias (58 guiones y un contacto incompleto).
La validación manual en PC/celular de 3A queda pendiente del usuario.

Cierre automatizado del 9 de septiembre de 2026: backend 114 pruebas aprobadas y cero
fallidas; pip check y compilación Python correctos. Frontend 21 pruebas aprobadas y
cero fallidas; build de producción correcto. Alembic heads/current/check y paso desde
0001 preservan todos los departamentos y su disponibilidad; downgrade/upgrade sólo en
base desechable. Pruebas de TTL cubren el límite exacto de 24 horas, arranque, tarea
periódica, acceso por API y cierre de temporales volcados a disco en éxito/error.
QA independiente: aprobado con observación de validación manual pendiente, sin defectos
bloqueantes. Se corrigieron el error de carga excesiva sin tamaño declarado, la exclusión
accidental del código Angular por imports/ y el formato local de vencimiento.
Sin commit ni push durante la implementación y revisión.

Corrección de clasificación detectada en validación manual: las 29 filas antes marcadas
REQUIERE_REVISION tenían únicamente 58 advertencias de guion, sin mínimos inválidos ni
conflictos. Contra la base local sin estudiantes operativos, el Excel real ahora produce
863 NUEVO, 0 SIN_CAMBIOS, 0 ACTUALIZACION y 0 REQUIERE_REVISION. Se conservan las 59
advertencias en 30 registros (58 guiones y un contacto incompleto), con cero registros
con razones bloqueantes. El archivo original conserva su huella. QA independiente
aprobó la separación de calidad y bloqueos; las pruebas cubren también ambigüedad,
documentos conflictivos, warnings simultáneos a bloqueos y mínimos inválidos.
Los borradores previos conservan el resultado calculado al crearlos: reiniciar el backend
actualizado y generar una nueva previsualización para validar la corrección; recuperar
el ID anterior no recalcula ni modifica su snapshot. No se aplica ningún dato operativo.
