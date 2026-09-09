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

Fase 2 — departamentos y disponibilidad en tiempo real, implementada y pendiente de validación manual en dos dispositivos. Fase 1 aprobada. Fase 3 no iniciada.

## Ejecución local

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

Abrir `http://127.0.0.1:4200`. La pantalla muestra los departamentos agrupados en Inspección, DECE y Salud. Permite establecer su disponibilidad y consultar el estado oficial después de guardar, recibir un aviso o reconectar. Los departamentos inactivos se conservan visibles y no permiten cambiar disponibilidad.

Antes de arrancar el backend actualizado, aplicar `alembic upgrade head` con el comando anterior: la primera migración crea e inserta los ocho departamentos. Repetir el upgrade o reiniciar FastAPI no duplica ni restablece datos. El downgrade elimina la tabla y sus datos; las pruebas de reversión deben hacerse solo sobre bases desechables.

El backend se ejecuta en un solo proceso. SQLite se guarda localmente en `backend/data/`; no debe versionarse. `backend/.env.example` documenta las variables opcionales, que deben definirse en el entorno del proceso; no se carga un archivo `.env` automáticamente.

## Verificación automática

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

No hay una tarea de lint ni pruebas e2e configuradas. Las pruebas del backend usan bases temporales y cubren la migración de departamentos, API, integridad y avisos WebSocket. No deben apuntar a la base de desarrollo.

## API de Fase 2

- `GET /api/health`: comprobación del proceso.
- `GET /api/departments`: listado completo con id, name, group, active y availability.
- `PUT /api/departments/{department_id}/availability`: cuerpo con únicamente availability, DISPONIBLE o NO_DISPONIBLE. Devuelve el departamento confirmado. Es idempotente; un valor ya establecido no emite avisos.
- `/ws`: aviso `departments_changed` después de confirmar un cambio real. La API es la fuente oficial del estado.

No hay CRUD general, activación/desactivación, estudiantes ni movimientos. Un departamento inactivo responde 409 al intentar modificarlo; uno inexistente, 404; una entrada inválida, 422.

## Validación manual pendiente de Fase 2

Validación técnica de cierre: 43 pruebas de backend y 12 de frontend aprobadas;
`pip check`, compilación Python y build de producción correctos. Alembic verificó
`upgrade`, `current`, `heads`, `check` y el ciclo `downgrade`/`upgrade` únicamente
en bases desechables. La integración local con dos clientes comprobó GET, PUT,
idempotencia, avisos WebSocket, persistencia tras reiniciar y recuperación automática.
Estas comprobaciones no sustituyen la siguiente prueba manual en la red del colegio.

En el servidor, iniciar FastAPI en `127.0.0.1:8000`. Para permitir la prueba desde otros dispositivos, ejecutar desde `frontend/`:

```powershell
npm start -- --host 0.0.0.0
```

Desde dos dispositivos de la misma red, abrir `http://IP-DEL-SERVIDOR:4200`. Sustituir IP-DEL-SERVIDOR por la dirección local real de esa computadora. El proxy mantiene FastAPI en loopback y SQLite permanece únicamente en disco local. Este servidor Angular es para desarrollo y validación local.

1. Confirmar los ocho departamentos y los tres grupos.
2. Cambiar disponibilidad en un dispositivo y comprobar la actualización automática en el otro; repetir en sentido inverso.
3. Recargar ambas pantallas y comprobar que recuperan el estado guardado.
4. Interrumpir la conexión de un cliente, cambiar desde el otro y reconectar: verificar el aviso de desconexión y la recuperación automática.
5. Reiniciar FastAPI y comprobar que conserva los cambios y los clientes se recuperan.
6. Verificar lectura y botones en PC y celular.

No se han abierto puertos ni creado reglas permanentes de firewall automáticamente. Si Windows bloquea el acceso, revisar el permiso de red privada del servidor de desarrollo antes de la prueba. La validación manual debe registrarse antes de aprobar completamente Fase 2.

## Documentación oficial

- [Alcance del MVP](docs/MVP.md)
- [Arquitectura](docs/ARCHITECTURE.md)
- [Modelo de datos](docs/DATA_MODEL.md)
- [Decisiones](docs/DECISIONS.md)
- [Roadmap](docs/ROADMAP.md)
- [Reglas de agentes](AGENTS.md)

La configuración del proyecto está en `.codex/config.toml`; las configuraciones de sus cuatro agentes están en `.codex/agents/`.
