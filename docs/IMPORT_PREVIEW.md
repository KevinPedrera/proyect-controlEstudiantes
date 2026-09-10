# Importación — Preview 3A y aplicación 3B

Estado: 3A validada manualmente y respaldada en c48da34. 3B implementada, pendiente de validación
manual real: confirmación y aplicación segura. No resolución individual, alta/edición
manual ni búsqueda de Fase 4. Generar preview sigue sin aplicar datos operativos.

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
coincidentes y elegibles. En 3B se prioriza esa correspondencia única frente a señales
débiles de otra identidad con otro documento válido y otro nombre completo; no se
descartan contradicciones documentales reales. Generar preview no vincula ni aplica datos.
Duplicados de documento/nombre dentro del archivo y varias filas hacia un candidato
requieren revisión. El origen manual del estudiante no lo excluye de la comparación.

Categorías excluyentes: NUEVO, SIN_CAMBIOS, ACTUALIZACION, REQUIERE_REVISION.
Etiquetas: DATOS_PERSONALES, DOCUMENTO, CURSO, PARALELO, CONTACTOS.
Cada diferencia conserva valor actual, recibido y acción propuesta; vacío conserva actual.
Los contactos se comparan dentro del estudiante y rol, ignorando orden de emergencias.
La planificación de 3B reconoce contactos inequívocos y calcula cambios efectivos campo
a campo, conservando vacíos y valores útiles ante guiones. No reemplaza por posición
ni fusiona por nombre/teléfono; una sustitución ambigua bloquea el lote.
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
La BASE aceptada reside en source_baseline y solo se actualiza al aplicar cambios
permitidos desde confirmación; nunca al generar preview.

## HTTP

| Método / ruta | Respuesta |
| --- | --- |
| POST /api/student-imports/preview | Multipart con exactamente file y scope. 201 con resumen e ID UUID |
| GET /api/student-imports/{id} | Resumen, institución/año propuestos, categorías, advertencias, vencimiento |
| GET /api/student-imports/{id}/rows | items/total/page/page_size; evidencia, candidatos y diferencias |
| GET /api/student-imports/{id}/absences | Mismo formato paginado, solo información básica de ausentes |
| POST /api/student-imports/{id}/confirm | JSON `confirm: true`, `accept_configuration: boolean` opcional; 200 con el mismo resumen APPLIED recuperable por GET |

Paginación: page ≥ 1, page_size de 1 a 100 (por defecto 25; UI 10).
404 inexistente; 410 vencido; 415 extensión incompatible; 422 datos/perfil inválidos;
413 carga excesiva, también sin Content-Length; 400 multipart inválido. Los errores se rechazan sin conservar temporales.
Respuestas correctas no-store. En 3B se añade POST /api/student-imports/{id}/confirm;
no resolutions ni CRUD de estudiantes.
Una nueva carga genera un nuevo borrador; no hay reenvío automático. Recuperación por ID.

## TTL y privacidad

24 horas exactas desde creación; tiempo del servidor UTC. Limpieza al arrancar,
cada minuto mientras FastAPI está activo y antes de operaciones sobre borradores.
Al vencer, API devuelve 410. Se borran ImportRow y proposal completo (incluidas
ausencias/candidatos); quedan ID, perfil, hash, alcance, fechas y status EXPIRED.
Si el servidor está apagado, la limpieza sucede al siguiente arranque antes de servir.
En 3B el lote aplicado conserva su estado y comprobante sin PII tras purgar filas/proposal.
GET del ID sigue devolviendo el comprobante; rows/absences dejan de estar disponibles.
SQLite usa secure_delete; esto no modifica copias de respaldo externas preexistentes.
La UI retira el preview al alcanzar su vencimiento y no guarda datos personales en localStorage.

No hay login ni roles; conocer un ID no es autenticación. Los detalles personales están
limitados al preview y no se añaden al panel de departamentos. Evitar datos sensibles en
logs/errores; SQLAlchemy oculta parámetros SQL. La procedencia aceptada operativa queda fuera del borrador; el comprobante aplicado
solo contiene identificación de la operación, fecha y recuentos, sin PII.

## Verificación

Pruebas automatizadas con libros sintéticos generados en memoria. Migraciones sobre bases
desechables; no tocar 0001_departments. La validación local del archivo real solo imprime
recuentos/estructura, no documentos, nombres personales ni teléfonos. No copiarlo al repositorio.
El parser validado obtiene 863 filas, dos emergencias, institución/año esperados,
cero faltantes mínimos y 59 advertencias (58 guiones y un contacto incompleto).
La validación manual en PC/celular de 3A ya fue confirmada por el usuario; 3B tendrá
su propia validación manual tras el cierre técnico.

Cierre histórico automatizado de 3A del 9 de septiembre de 2026: backend 114 pruebas aprobadas y cero
fallidas; pip check y compilación Python correctos. Frontend 21 pruebas aprobadas y
cero fallidas; build de producción correcto. Alembic heads/current/check y paso desde
0001 preservan todos los departamentos y su disponibilidad; downgrade/upgrade sólo en
base desechable. Pruebas de TTL cubren el límite exacto de 24 horas, arranque, tarea
periódica, acceso por API y cierre de temporales volcados a disco en éxito/error.
QA independiente de 3A: aprobado sin defectos bloqueantes; la validación manual
posterior ya fue confirmada. Se corrigieron el error de carga excesiva sin tamaño declarado, la exclusión
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

## Confirmación de Fase 3B

Solo un preview nuevo con contrato de aplicación compatible puede confirmarse. Los
borradores de 3A siguen consultables hasta vencer, pero no son confirmables. El perfil
del parser y la versión del contrato de aplicación tienen propósitos distintos.

El usuario revisa institución, periodo, alcance, categorías y advertencias; acepta
explícitamente que se modificarán datos operativos. Una configuración inicial o cambio
de periodo propuesto necesita aceptación expresa. Un solo bloqueo impide todo el lote.
La API no recibe nuevamente Excel, filas, estudiantes, contactos ni decisiones del cliente.

BEGIN IMMEDIATE serializa las confirmaciones. Tras obtener acceso de escritura se
validan estado, TTL, contrato, integridad del borrador, bloqueos y huella operativa.
Si la huella difiere, 409 y un nuevo preview; cambios de disponibilidad no la alteran.
Si el borrador estaba vigente al validarlo, puede terminar aunque venza durante la
transacción. Ningún commit intermedio: datos, procedencia y comprobante son atómicos.

Una confirmación repetida sobre el mismo ID aplicado devuelve el mismo comprobante
sin reaplicar. Un timeout o desconexión del navegador deja resultado incierto: Angular
consulta el ID por GET. Nunca afirma fallo de importación solo por perder la respuesta.
No reenvío automático de la confirmación. El comprobante puede recuperarse por ID
después de reiniciar el backend y después de purgar el borrador temporal.

Los tests de confirmación usan únicamente datos sintéticos y bases desechables. El
Excel institucional real se usa solo para lectura/preview; su primera aplicación en
la base operativa queda reservada al usuario. No se migra automáticamente esa base
durante el desarrollo. No commit ni push durante implementación y revisión.

Contrato concreto: `application_contract_version = 3B-1`. La API persiste APPLIED
y lo presenta como aplicado. El resumen aplicado contiene `applied_receipt` con
`import_id`, `status`, `applied_at` y `counts`; no incluye institución, nombres,
documentos ni contactos del preview. El POST rechaza campos adicionales y valores
de consentimiento que no sean booleanos. Cambiar el periodo activo, incluso a uno
ya existente, exige `accept_configuration: true` y se muestra antes de confirmar.

Errores de confirmación: 404 IMPORTACION_NO_ENCONTRADA; 410 PREVIEW_VENCIDO;
409 CONTRATO_INCOMPATIBLE, PREVIEW_INTEGRO_INVALIDO, BLOQUEOS_PRESENTES,
PREVIEW_OBSOLETO, INSTITUCION_INCOMPATIBLE, CONFIGURACION_REQUIERE_CONFIRMACION
o PROCEDENCIA_INCOMPATIBLE; 503 BASE_OCUPADA; 500 ERROR_APLICACION. El frontend
trata desconexión, timeout y errores de servidor como resultado incierto y recupera
por GET antes de atribuir éxito o fallo. Un APPLIED recuperado no se borra por el
temporizador de vencimiento del borrador.

Identidad: cambios de documento, tipo, nombres o apellidos se conservan como
conflictos explicados cuando no hay una asociación segura. Las diferencias de
contactos muestran valores efectivos; NULL y guion recibidos siguen disponibles
en la evidencia original. Reordenar contactos no cambia su identidad. La protección
manual preparada no dispone de endpoints ni pantalla en esta fase.

Validación técnica de 3B del 10 de septiembre de 2026: 159 pruebas backend y
31 pruebas frontend aprobadas; build de producción, pip check y compilación
Python correctos. Cuatro pruebas de migración verifican preservación desde 0002,
constraints, reversión y rollback ante fallo inyectado. Alembic upgrade/current/
heads/check y downgrade/upgrade pasan en bases desechables. No hay lint configurado.

El parser/comparador actual, leyendo el Excel institucional sin confirmarlo,
produce 863 NUEVO, cero bloqueos y 59 warnings en 30 registros. Una comparación
contra una representación idéntica construida solo en memoria produce 863
SIN_CAMBIOS y cero conflictos: corrige los seis falsos positivos anteriores.
Esto es una simulación de comparación, no una aplicación del archivo real ni
una validación manual de confirmación. El original permanece intacto y la base
local continúa en 0002 con ocho departamentos y cero estudiantes. La primera
aplicación real sigue reservada al usuario tras actualizar a 0003.

QA independiente final: APROBADO, sin hallazgos funcionales pendientes. Se corrigió
el caso de institución existente sin periodo: el preview ahora solicita aceptación
explícita también al crear el periodo faltante. QA repitió 155 pruebas backend antes
de ese ajuste y 45 pruebas relevantes después, además de las 31 pruebas frontend y
su build; la suite integrada final del responsable pasó 159/159. Solo permanecen
dos advertencias de deprecación de dependencias de pruebas (Starlette/httpx y anyio),
sin fallos. No se actualizaron dependencias por ellas. Fase 3B pendiente de validación
manual real en PC/celular; Fase 4 no iniciada. No commit ni push en este cierre.
