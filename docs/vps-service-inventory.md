# Inventario de Servicios del VPS

Inventario operativo inicial del VPS compartido para sostener la cohabitación ordenada de varias aplicaciones.

## Alcance
- Host: `srv438239`
- Fecha base del inventario: `2026-04-06`
- Fuente: `systemd`, `ss`, `nginx` y scripts de `infra/scripts/`

## Matriz de servicios

| Servicio | Tipo | Ruta base | Ejecución | Puerto/socket interno | Dominio(s) | Responsable | Estado | Riesgo principal | Acción recomendada |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `asistenciamodelo-backend.service` | FastAPI | `/home/gaibarra/modeloasist/backend` | `uvicorn` | `127.0.0.1:8184` | `asistenciamodelo.online` | Por confirmar | Activo | Dependencia directa de PostgreSQL y uso compartido del host | Mantener límites `systemd`, revisar logs semanalmente |
| `asistenciamodelo-frontend.service` | Next.js | `/home/gaibarra/modeloasist/frontend` | `npm run start` | `127.0.0.1:3101` | `asistenciamodelo.online` | Por confirmar | Activo | Compite por RAM con otros procesos Node/Next | Mantener build productivo y monitorear memoria |
| `finiquitos.service` | Node.js backend | `/home/gaibarra/finiquitos/server` | `node index.js` | `127.0.0.1:5000` | `finiquitos.online`, `www.finiquitos.online` | Por confirmar | Activo | Sin límites visibles de `systemd` ni endurecimiento | Replicar límites mínimos y documentar health check |
| `gunicorn.service` | Django/Gunicorn | `/home/gaibarra/contrato` | `gunicorn` | `unix:/run/gunicorn/gunicorn.sock` | `contratosmodelo.site` | Por confirmar | Activo | Comparte Nginx y logs fuera de `/var/log/nginx` | Revisar rotación de logs y recursos |
| `gunicorn_motel.service` | Backend Python/Gunicorn | `/home/gaibarra/motel/backend` | `gunicorn` | `unix:/home/gaibarra/motel/gunicorn.sock` | `moteleltarachi.click`, `moteleltarachi.online` | Por confirmar | Activo | Comparte stack con `nextjs.service` y configuración CORS compleja | Documentar puertos/flujo y revisar endurecimiento |
| `nextjs.service` | Next.js | `/home/gaibarra/motel/frontend` | `npm run start` | `127.0.0.1:3008` | `moteleltarachi.online` | Por confirmar | Activo | Otra app Next.js residente en el mismo host | Aplicar límites homogéneos y confirmar owner |
| `uipc-backend.service` | Node.js backend | `/home/gaibarra/uipcmodelo/server` | `node index.js` | `127.0.0.1:3000` | `proteccioncivil.pro`, `www.proteccioncivil.pro` | Por confirmar | Activo | Logs dedicados pero sin endurecimiento equivalente al de `modeloasist` | Añadir límites y revisar política de restart |
| `reportes.click` vía Nginx + Gunicorn socket | Frontend estático + backend por socket | `/home/gaibarra/reportesmodelo` | `nginx` + `gunicorn.sock` | `unix:/home/gaibarra/reportesmodelo/gunicorn.sock` | `reportes.click`, `www.reportes.click`, `rerportes.click` | Por confirmar | Parcialmente documentado | No se identificó una unidad `systemd` en este levantamiento | Confirmar servicio backend y owner real |

## Dominios y ruteo actual

| Dominio | Entrada pública | Upstream interno |
| --- | --- | --- |
| `asistenciamodelo.online` | `nginx` | Frontend `127.0.0.1:3101`, health backend `127.0.0.1:8184` |
| `contratosmodelo.site` | `nginx` | `unix:/run/gunicorn/gunicorn.sock` |
| `finiquitos.online` | `nginx` | API `127.0.0.1:5000`, frontend estático en `/home/gaibarra/finiquitos/dist` |
| `moteleltarachi.click` | `nginx` | `unix:/home/gaibarra/motel/gunicorn.sock` |
| `moteleltarachi.online` | `nginx` | Frontend `127.0.0.1:3008`, API `unix:/home/gaibarra/motel/gunicorn.sock` |
| `proteccioncivil.pro` | `nginx` | API `127.0.0.1:3000`, frontend estático en `/home/gaibarra/uipcmodelo/dist` |
| `reportes.click` | `nginx` | Sitio estático + puente a `https://rerportes.click` para `/tasks/api/` |
| `rerportes.click` | `nginx` | `unix:/home/gaibarra/reportesmodelo/gunicorn.sock` |

## Hallazgos operativos
- `modeloasist` es la única app del conjunto con límites explícitos de `systemd`, rate limiting en `nginx` y playbook operativo ya integrado al repo.
- El VPS convive con varios stacks: `Node.js`, `Next.js`, `Gunicorn`, `PostgreSQL`, `Docker` y `Supervisor`.
- No se detectan choques reales de `server_name` entre archivos `nginx`, pero sí existe alta densidad de aplicaciones en un solo host.
- Hay servicios activos cuyo responsable no queda explícito en la configuración revisada; eso dificulta incident response y cambios seguros.
- `reportes.click`/`rerportes.click` requieren una revisión adicional para identificar su unidad de proceso backend y formalizar su inventario.

## Checklist semanal del inventario
- Ejecutar `sudo bash infra/scripts/vps_inventory_report.sh --markdown`.
- Ejecutar `sudo bash infra/scripts/nginx_server_name_audit.sh --strict`.
- Confirmar `sudo systemctl --failed` sin unidades fallidas.
- Revisar que cada servicio crítico tenga owner confirmado.
- Registrar puertos, dominios o rutas nuevas antes de cualquier despliegue.

## Campos por completar
- Responsable técnico de cada aplicación.
- Health check operativo de `finiquitos`, `contratosmodelo`, `motel`, `uipcmodelo` y `reportesmodelo`.
- Límites de recursos y políticas de restart homogéneas en todos los servicios.
- Runbook de rollback individual por aplicación.
