# Frontend — Control Estudiantil

Esqueleto Angular de Fase 1. La pantalla inicial muestra el estado del servidor y de la conexión en tiempo real.

## Desarrollo local

Desde esta carpeta, con Node.js 24.14 y npm:

```powershell
npm ci
npm start
```

Abrir `http://127.0.0.1:4200`. FastAPI debe estar iniciado en `127.0.0.1:8000`. El proxy de desarrollo envía `/api/**` y `/ws` al backend.

La preparación del backend está documentada en el [README del proyecto](../README.md).

## Validaciones disponibles

```powershell
npm test -- --watch=false
npm run build
```

Las pruebas unitarias usan Vitest. La compilación de producción genera archivos en `dist/`. No hay una tarea de lint ni pruebas e2e configuradas.

Fase 2 no iniciada.
