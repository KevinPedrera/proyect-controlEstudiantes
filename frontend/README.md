# Frontend de Control Estudiantil

Angular muestra los departamentos agrupados en Inspección, DECE y Salud. Consulta el estado oficial por HTTP y vuelve a consultarlo al abrir WebSocket, reconectar, recibir un aviso o terminar un cambio de disponibilidad. No actualiza disponibilidades de forma optimista ni repite escrituras automáticamente.

Desde esta carpeta:

```powershell
npm ci
npm start
```

Abrir http://127.0.0.1:4200. FastAPI debe estar iniciado en 127.0.0.1:8000; el proxy de desarrollo dirige /api y /ws al backend. Para probar desde otro dispositivo de la red local, iniciar con `npm start -- --host 0.0.0.0` y acceder a la IP del servidor en el puerto 4200. SQLite permanece únicamente en el servidor.

```powershell
npm test -- --watch=false
npm run build
```

No hay una tarea de lint ni suite e2e configuradas. Los comandos de preparación del backend están en el [README principal](../README.md).
