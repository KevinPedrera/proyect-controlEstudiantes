# ARCHITECTURE.md

# Arquitectura del Sistema

## Objetivo

Construir un sistema web local para el control de estudiantes del colegio, priorizando velocidad, simplicidad, estabilidad y comunicación en tiempo real entre departamentos.

---

# Principios de arquitectura

- Toda la lógica de negocio reside en el backend.
- El frontend únicamente muestra información y envía acciones.
- La base de datos nunca es accedida directamente por el frontend.
- Toda validación ocurre en el backend.
- Cada movimiento importante del estudiante queda registrado.
- El sistema debe ser modular para facilitar futuras ampliaciones.

---

# Tecnologías

## Backend
- Python
- FastAPI
- SQLAlchemy
- Alembic para migraciones
- WebSockets

## Frontend
- Angular

## Base de datos
- SQLite (MVP)

SQLite reside únicamente en el disco local de la computadora Windows que actúa como servidor del colegio. Solo FastAPI accede directamente a la base; los demás dispositivos utilizan HTTP y WebSocket por la red local.

El backend se ejecutará inicialmente como un único proceso. No se requiere infraestructura distribuida para el MVP.

SQLAlchemy organiza la persistencia y Alembic versiona los cambios de esquema. Las claves foráneas de SQLite deben habilitarse en cada conexión y respetarse. No se crea ninguna base ni migración durante Fase 0.1.

## Comunicación

- HTTP para consultas y operaciones.
- WebSockets para actualización en tiempo real.

---

# Flujo de comunicación

Usuario

↓

Angular

↓

FastAPI

↓

SQLite

↓

FastAPI

↓

WebSockets

↓

Todos los clientes conectados

---

# Responsabilidades

## Frontend

- Buscar estudiantes.
- Mostrar departamentos.
- Mostrar estados.
- Mostrar cronómetros.
- Enviar acciones al backend.

Nunca toma decisiones de negocio.

## Backend

- Validar información.
- Gestionar estudiantes.
- Gestionar departamentos.
- Gestionar movimientos.
- Conservar movimientos y sus timestamps oficiales.
- Controlar reglas del negocio.
- Emitir eventos mediante WebSockets.

## Base de datos

Guardar únicamente la información persistente del sistema.

---

# Integridad y tiempo real

Un estudiante puede tener muchos movimientos históricos, pero solo uno activo (EN_CAMINO o EN_ATENCION). Un departamento puede tener varios estudiantes simultáneamente.

La garantía combina validación del backend, transacción y una restricción apropiada de base de datos. Se implementa y prueba al crear movimientos, no durante el saneamiento documental.

Los estados de movimiento son EN_CAMINO, EN_ATENCION y FINALIZADO. La disponibilidad DISPONIBLE / NO_DISPONIBLE es independiente. NO_DISPONIBLE bloquea nuevas entradas, incluidas atenciones directas, sin alterar movimientos existentes.

Los timestamps oficiales los genera el backend. La atención directa empieza en EN_ATENCION y no tiene tiempo de traslado.

La API/backend respaldada por SQLite es la fuente oficial del estado. WebSocket únicamente informa cambios después de confirmar la transacción correspondiente; no se usa una entidad o tabla Evento persistente.

Al abrir, recargar o reconectar, el frontend consulta el estado por API. La implementación debe coordinar la suscripción y las consultas para no perder cambios durante la sincronización ni aplicar respuestas antiguas sobre información más reciente. Los contratos concretos se verifican en las fases que introducen cada recurso.

La interfaz es una sola página general para PC y celular, sin login ni perfiles. El historial consiste en conservar movimientos en SQLite; no incluye una pantalla.

---

# Organización del proyecto

```text
control-estudiantil/
├── AGENTS.md
├── README.md
├── .gitignore
├── docs/
│   ├── MVP.md
│   ├── ARCHITECTURE.md
│   ├── DATA_MODEL.md
│   ├── DECISIONS.md
│   └── ROADMAP.md
├── .codex/
│   ├── config.toml
│   └── agents/
│       ├── backend_specialist.toml
│       ├── frontend_angular.toml
│       ├── product_ux.toml
│       └── qa_reviewer.toml
├── backend/
└── frontend/
```

Las carpetas backend y frontend contienen exclusivamente el esqueleto técnico autorizado en Fase 1; las entidades de dominio se implementarán en sus fases correspondientes.

---

# Escalabilidad

La arquitectura permitirá en el futuro:

- cambiar SQLite por PostgreSQL;
- agregar autenticación;
- incorporar reportes;
- crear aplicación móvil;
- integrar otros sistemas del colegio.

Sin modificar la lógica principal.

---

# Regla fundamental

Toda decisión de negocio debe implementarse únicamente en el backend.

El frontend nunca contendrá reglas de negocio.

La simplicidad tiene prioridad sobre la cantidad de funcionalidades. El flujo del MVP se construye incrementalmente según el roadmap; no se incorporan funcionalidades fuera de ese alcance antes de validar el MVP.
