# Control Estudiantil

## Descripción

Control Estudiantil es un proyecto de sistema web para optimizar el seguimiento de estudiantes entre los diferentes departamentos del colegio mediante información en tiempo real.

El sistema permitirá consultar el departamento de destino, el estado registrado del movimiento y el tiempo transcurrido. Durante el MVP no se registra la identidad del funcionario que atiende al estudiante.

---

# Objetivo

Desarrollar un sistema local, rápido, sencillo y confiable para el monitoreo de estudiantes entre:

- Inspección General
- Inspección Primaria
- Inspección Bachillerato
- DECE Primaria
- DECE Secundaria/Bachillerato
- Psicopedagogía
- Médico
- Odontología

El sistema funcionará inicialmente únicamente dentro de la red local del colegio.

---

# Tecnologías

## Backend

- FastAPI
- SQLite
- SQLAlchemy
- Alembic para migraciones
- WebSockets

## Frontend

- Angular
- TypeScript

---

# Objetivos del MVP

La primera versión únicamente permitirá:

- Buscar estudiantes solo por nombres y apellidos, mostrando curso y paralelo para distinguir coincidencias.
- Enviar estudiantes a un departamento.
- Recibir la notificación en tiempo real.
- Confirmar la llegada del estudiante.
- Finalizar la atención.
- Iniciar atención directa en un departamento, sin traslado.
- Calcular por separado los tiempos de traslado y atención desde timestamps generados por el backend.
- Cambiar la disponibilidad de departamentos entre DISPONIBLE y NO_DISPONIBLE.
- Conservar movimientos en la base de datos, sin pantalla de historial.

La interfaz será una sola página general, utilizable desde PC y celular. Un departamento puede manejar varios estudiantes; cada estudiante solo puede tener un movimiento activo (EN_CAMINO o EN_ATENCION). Al finalizar pasa a FINALIZADO.

La disponibilidad es independiente de los movimientos. NO_DISPONIBLE bloquea nuevas entradas, incluidas atenciones directas, sin cancelar ni modificar movimientos activos.

FastAPI se ejecutará inicialmente como un único proceso en una computadora Windows de la red local. Solo el backend accede al archivo SQLite del servidor. Los estudiantes se importan de forma controlada desde Excel; el archivo original no se modifica ni se consulta durante la operación cotidiana. No se fusionan homónimos automáticamente.

La API/backend, respaldada por SQLite, proporciona el estado oficial. WebSocket comunica cambios después de confirmar las transacciones. Al abrir, recargar o reconectar, la interfaz recupera el estado mediante API.

No incluirá en esta etapa:

- Usuarios.
- Roles.
- Reportes.
- Estadísticas.
- Exportación a Excel o PDF.
- Administración.

---

# Filosofía del proyecto

Este proyecto prioriza:

- Simplicidad.
- Rapidez.
- Estabilidad.
- Facilidad de uso.
- Desarrollo incremental.

Cada nueva funcionalidad deberá aportar valor al flujo diario del colegio antes de incorporarse al sistema.

---

# Estado

Fase 1 — esqueleto técnico completado y validado. Fase 2 no iniciada.

## Ejecución local de Fase 1

Requisitos usados en la validación: Python 3.12 y Node.js 24.14 con npm. Ejecutar desde dos terminales de PowerShell.

Backend, desde `backend/` (crear el entorno e instalar dependencias solo en la preparación inicial):

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe -m alembic upgrade head
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --ws websockets-sansio
```

Frontend, desde `frontend/`:

```powershell
npm ci
npm start
```

Abrir `http://127.0.0.1:4200`. La pantalla inicial comprueba HTTP y WebSocket mediante el proxy de desarrollo. El backend se ejecuta en un solo proceso. SQLite se guarda localmente en `backend/data/`; no debe versionarse. `backend/.env.example` documenta las variables opcionales, que deben definirse en el entorno del proceso; no se carga un archivo `.env` automáticamente.

## Verificación de Fase 1

Desde `backend/`:

```powershell
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m pip check
.\.venv\Scripts\python.exe -m alembic check
```

Desde `frontend/`:

```powershell
npm test -- --watch=false
npm run build
```

No hay una tarea de lint ni pruebas e2e configuradas. Alembic está preparado sin revisiones de dominio; estas corresponden a fases posteriores.

## Documentación oficial

- [Alcance del MVP](docs/MVP.md)
- [Arquitectura](docs/ARCHITECTURE.md)
- [Modelo de datos](docs/DATA_MODEL.md)
- [Decisiones](docs/DECISIONS.md)
- [Roadmap](docs/ROADMAP.md)
- [Reglas de agentes](AGENTS.md)

La configuración del proyecto está en `.codex/config.toml`; las configuraciones de sus cuatro agentes están en `.codex/agents/`.
