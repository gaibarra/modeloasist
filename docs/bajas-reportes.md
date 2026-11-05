# Exclusión actual de bajas en reportes

BAJAS y BAJAS NOMINA son asignaciones exclusivas. La detección normaliza acentos,
mayúsculas y separadores, y revisa departamento/campus de la ficha y nombre,
código y campus de todas las asignaciones. Una asignación antigua de baja basta
para excluir a la persona, aunque también conserve departamentos operativos.

La exclusión se aplica antes de totales y paginación, incluso al consultar fechas
anteriores. Abarca consulta por periodo e individual, indicadores, horas semanales,
reporte ejecutivo, conciliación y sus impresiones/exportaciones. Los enlaces
individuales antiguos responden 404 con un mensaje de indisponibilidad. Las
exclusiones adicionales del reporte ejecutivo mantienen su alcance anterior.

El directorio conserva las bajas y muestra «Baja · Fuera de reportes». Al elegir
un departamento operativo se retiran ambas categorías de baja. No se restauran
asignaciones anteriores automáticamente. El servidor rechaza selecciones mixtas.
La confirmación de baja explica el efecto sobre los reportes históricos.

Las checadas importadas se conservan, pero no cambian las asignaciones de una
baja. No se eliminan personas ni se modifican credenciales, permisos staff,
contratos, horarios o exenciones. Los correos provisionales existentes pueden
conservarse al editar una baja; no se permite asignarlos a otro registro.

Las claves de caché de analítica incluyen el estado actual del catálogo y sus
asignaciones. Las consultas nuevas reflejan una baja o reincorporación sin
esperar a que expire la caché. Las pestañas ya abiertas necesitan una consulta
nueva para actualizar su contenido.

## Publicación

Ejecutar desde la terminal del administrador:

```bash
sudo bash /home/gaibarra/modeloasist/infra/scripts/redeploy_bajas.sh --check
sudo bash /home/gaibarra/modeloasist/infra/scripts/redeploy_bajas.sh --deploy
```

El script comprueba las bases activas:

- Backend: `20261026T142227Z-vacaciones/backend`.
- Frontend: `20261103T150239Z-department-auto/frontend`.

Si alguna cambió, se detiene. Copia cada base por separado y aplica únicamente
los archivos del manifiesto SHA-256. Conserva dependencias y esquema
`20261015_0016`, construye y prueba en otra carpeta, y prueba servicios temporales
en localhost. Publica primero backend (8184) y después frontend (3101).

Los respaldos restringidos quedan en `/var/backups/asistenciamodelo/<fecha>-bajas`;
la versión nueva en `/opt/asistenciamodelo/releases/<fecha>-bajas`.
El respaldo contiene `rollback.sh`, que solo permite retirar los ajustes de esta
publicación si no existe un despliegue posterior. No restaura ni modifica datos.
No se cambian Nginx, certificados, firewall ni servicios ajenos.

## Verificación autenticada posterior

Con una sesión legítima, consultar una baja existente en el directorio y comprobar
que no aparece en consulta histórica, selector individual, horas, conciliación,
impresión ni CSV. Comprobar también un departamento vacío y un enlace individual
antiguo. La reincorporación se prueba en la base aislada; en producción solo debe
realizarse cuando corresponda a un cambio real autorizado, nunca sobre una cuenta
real únicamente para probar.

Pruebas locales: `backend/tests/test_report_eligibility.py`, suite backend,
`frontend/tests/department-selection.test.cjs`, TypeScript, lint, build aislado y
`infra/tests/test_redeploy_bajas.py` (incluye reversión simulada).
