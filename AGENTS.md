# AGENTS — Control Estudiantil

## 1. Propósito

Este archivo define las reglas generales que deben seguir todos los agentes que trabajen en el proyecto Control Estudiantil.

Los agentes no tienen autoridad para redefinir el producto.

Su función es implementar, revisar o analizar únicamente lo que ya haya sido definido en la documentación oficial del proyecto.

---

# 2. Documentación oficial

Antes de modificar código, todo agente debe revisar como mínimo:

- README.md
- docs/MVP.md
- docs/ARCHITECTURE.md
- docs/DATA_MODEL.md
- docs/DECISIONS.md
- docs/ROADMAP.md

Estos documentos representan las decisiones oficiales del proyecto.

Si existe contradicción entre el código y la documentación, el agente debe informar la diferencia antes de realizar cambios importantes.

---

# 3. Regla principal

No implementar funcionalidades que no pertenezcan a la fase actual.

El desarrollo debe seguir el orden establecido en docs/ROADMAP.md. La fase autorizada es exclusivamente Fase 3B: confirmación explícita y aplicación segura de previews compatibles. Fases 2 y 3A están validadas manualmente. No implementar resolución individual, alta o edición manual, búsqueda de Fase 4 ni movimientos. Generar preview solo escribe ImportBatch/ImportRow y nunca altera datos operativos; únicamente confirmar un preview válido aplica datos mediante una transacción atómica. No aplicar el Excel institucional real durante el desarrollo. No modificar migraciones 0001 ni 0002; usar una nueva 0003. La autorización específica del usuario prevalece sobre las referencias históricas de fase en las configuraciones de agentes.

Un agente no debe adelantarse a fases futuras.

---

# 4. Alcance actual

El proyecto actual es un MVP para uso interno en un colegio.

La prioridad es:

1. Simplicidad.
2. Estabilidad.
3. Claridad.
4. Funcionamiento en red local.
5. Tiempo real.
6. Facilidad de mantenimiento.

No se busca construir todavía un sistema empresarial completo.

---

# 5. Arquitectura obligatoria

La arquitectura definida actualmente es:

Frontend:
Angular

Backend:
FastAPI

Base de datos:
SQLite

Persistencia y migraciones:
SQLAlchemy y Alembic.

Tiempo real:
WebSocket

Servidor:
Computadora Windows dentro de la red local del colegio.

SQLite reside únicamente en el servidor y solo FastAPI accede directamente a ella. El backend se ejecutará inicialmente como un único proceso. Las claves foráneas de SQLite deben habilitarse y respetarse.

---

# 6. Responsabilidades del backend

Toda lógica de negocio debe vivir en el backend.

El backend debe controlar:

- validaciones;
- movimientos;
- estados;
- reglas de estudiantes;
- reglas de departamentos;
- integridad de datos;
- acceso a SQLite;
- eventos en tiempo real;
- manejo de errores.

El frontend no debe contener reglas críticas de negocio.

---

# 7. Responsabilidades del frontend

El frontend debe:

- mostrar información;
- enviar acciones al backend;
- actualizar la interfaz;
- representar estados;
- mostrar cronómetros;
- recibir eventos WebSocket;
- funcionar correctamente en PC y celular.

El frontend no debe decidir si una operación de negocio es válida.

---

# 8. Fuente oficial de datos

La base de datos y el backend representan la fuente oficial del estado del sistema.

WebSocket se utiliza únicamente para informar cambios.

El sistema debe poder reconstruir correctamente su estado consultando nuevamente al backend.

El frontend consulta el estado oficial al abrir, recargar o reconectar. Los mensajes WebSocket se emiten después de confirmar la transacción. No se usa entidad/tabla Evento persistente durante el MVP.

---

# 9. Regla de movimientos

Un estudiante puede tener muchos movimientos históricos.

Un estudiante solo puede tener UN movimiento activo simultáneamente.

Un departamento sí puede manejar varios estudiantes al mismo tiempo.

Esta regla debe protegerse mediante validación del backend, transacción y una restricción apropiada en base de datos. La implementación y su prueba de concurrencia pertenecen a la fase de movimientos.

---

# 10. Estados del movimiento

Los estados principales del MVP son:

- EN_CAMINO
- EN_ATENCION
- FINALIZADO

No agregar estados adicionales sin aprobación.

EN_CAMINO y EN_ATENCION son movimientos activos. La atención directa pertenece al MVP, comienza en EN_ATENCION y no tiene traslado ni un traslado ficticio de cero segundos. Movimiento requiere destino; no se exige origen.

---

# 11. Disponibilidad de departamentos

Los departamentos pueden estar:

- DISPONIBLE
- NO_DISPONIBLE

La disponibilidad del departamento es independiente de los movimientos de estudiantes.

No interpretar automáticamente que un departamento que atiende estudiantes está "ocupado".

NO_DISPONIBLE bloquea nuevas entradas, incluidos envíos y atenciones directas. No cancela ni modifica movimientos activos; su llegada y finalización pueden continuar.

---

# 12. Cronómetros

No almacenar contadores segundo por segundo.

Guardar timestamps oficiales generados por el backend; no persistir duraciones independientes.

Los tiempos visibles se calculan a partir de:

- hora de envío;
- hora de llegada;
- hora de finalización.

Esto aplica tanto al tiempo de traslado como al tiempo de atención.

---

# 13. Base de datos

No usar DELETE físico para datos históricos importantes durante el MVP.

Preferir:

- activo;
- inactivo;
- estados;
- conservación del historial.

Los movimientos finalizados deben conservarse.

El historial significa conservación en base de datos. No se implementa una pantalla de historial en el MVP.

---

# 14. Excel

El archivo Excel institucional se utiliza únicamente como fuente de importación.

El sistema no debe depender del Excel durante su operación cotidiana.

No modificar automáticamente el archivo original.

La importación es controlada y no fusiona homónimos automáticamente. La búsqueda utiliza solo nombres y apellidos, mostrando curso y paralelo. No se requiere carnet ni código institucional.

---

# 15. Dependencias

No agregar librerías innecesarias.

Antes de agregar una dependencia nueva:

1. Verificar si realmente es necesaria.
2. Comprobar si el stack actual ya permite resolver el problema.
3. Evitar dependencias que solo simplifiquen tareas pequeñas.
4. Documentar dependencias importantes.

---

# 16. Seguridad del alcance

Durante el MVP no implementar:

- login;
- usuarios;
- roles;
- permisos;
- reportes;
- PDF;
- dashboards;
- notificaciones por WhatsApp;
- correo;
- aplicación móvil nativa;
- despliegue en nube;
- PostgreSQL;
- sanciones;
- fichas completas;
- fichas de representantes (su almacenamiento y preview sí pertenecen a Fase 3A);
- expedientes médicos;
- funcionalidades académicas.

Estas funciones pertenecen a posibles versiones futuras.

---

# 17. Cambios arquitectónicos

Ningún agente puede cambiar por su cuenta:

- Angular;
- FastAPI;
- SQLite;
- WebSocket;
- estructura general frontend/backend;
- filosofía de servidor local;
- reglas centrales del MVP.

Si considera necesario un cambio, debe:

1. explicar el problema;
2. proponer alternativas;
3. describir ventajas y riesgos;
4. esperar una decisión.

---

# 18. Forma de trabajo

Cada tarea debe ser pequeña y verificable.

Antes de implementar:

1. identificar la fase actual;
2. revisar documentación relevante;
3. revisar el código relacionado;
4. explicar brevemente el plan.

Después de implementar:

1. ejecutar pruebas relevantes;
2. revisar errores;
3. informar archivos modificados;
4. indicar qué se verificó;
5. señalar cualquier pendiente.

---

# 19. No realizar cambios masivos

Evitar refactorizaciones grandes no solicitadas.

No modificar archivos fuera del alcance de la tarea salvo que sea técnicamente necesario.

Si una tarea requiere una modificación adicional importante, informar primero.

---

# 20. Calidad

El código debe priorizar:

- claridad;
- nombres descriptivos;
- funciones pequeñas;
- separación de responsabilidades;
- manejo explícito de errores;
- mantenibilidad;
- pruebas donde aporten valor.

No priorizar abstracciones complejas ni patrones avanzados sin necesidad real.

---

# 21. UX

La interfaz está dirigida a personal del colegio.

Será una sola interfaz general para PC y celular, agrupada en Inspección, DECE y Salud, sin login ni perfiles. Se conoce el departamento que atiende, no la identidad de un funcionario.

Debe ser fácil de comprender sin capacitación técnica.

Priorizar:

- botones claros;
- estados visibles;
- textos simples;
- buena lectura;
- funcionamiento móvil;
- pocas acciones por flujo.

Evitar:

- menús complejos;
- configuraciones innecesarias;
- elementos decorativos que dificulten el uso;
- exceso de información.

---

# 22. Errores y dudas

Si el agente encuentra una decisión no definida que cambie producto, arquitectura, alcance, integridad, modelo conceptual o roadmap:

NO debe inventarla silenciosamente.

Debe indicar:

- qué falta definir;
- por qué afecta la implementación;
- cuáles son las opciones razonables.

Una decisión nueva debe registrarse en docs/DECISIONS.md antes de implementarse.

Las decisiones técnicas rutinarias que no alteren estos aspectos pueden resolverse con la solución más simple y documentarse brevemente cuando sea útil, conforme a la autorización de la fase actual.

---

# 23. Git

Los cambios deben mantenerse pequeños y coherentes.

No incluir:

- bases de datos reales;
- archivos Excel institucionales;
- secretos;
- credenciales;
- archivos temporales;
- configuraciones locales sensibles.

Estos elementos deben excluirse mediante .gitignore cuando corresponda.

---

# 24. Definición de terminado

Una tarea solo está terminada cuando:

- la funcionalidad solicitada existe;
- las pruebas relevantes pasan;
- no rompe funcionalidades anteriores;
- respeta la arquitectura;
- respeta el MVP;
- no introduce funcionalidades fuera de alcance;
- puede explicarse claramente qué cambió.

---

# 25. Regla final

Cuando exista una elección entre:

A) una solución simple que cumple correctamente el MVP;

y

B) una solución más sofisticada preparada para necesidades hipotéticas futuras;

se debe preferir A.

Primero debemos conseguir un sistema pequeño que funcione bien en el colegio.

Después se evoluciona.
