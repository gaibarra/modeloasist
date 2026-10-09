# Redespliegue del CRUD de colaboradores

El script `infra/scripts/redeploy_colaboradores.sh` publica exactamente el commit
`25f5cb0fac455373dd4d650221269642727c59db` (`081026a`). Usa `git archive`:
los cambios sin commit y los commits posteriores no se incorporan a la publicación.
El script puede guardarse en un commit posterior sin cambiar la versión publicada.

Desde `/home/gaibarra/modeloasist`:

```bash
sudo bash infra/scripts/redeploy_colaboradores.sh --check
sudo bash infra/scripts/redeploy_colaboradores.sh --deploy
```

`--check` valida el commit, servicios activos, rutas de recuperación, RAM, espacio,
comandos de arranque y esquema PostgreSQL en solo lectura. No compila ni reinicia.
Se requieren 2 GiB de RAM disponible y 6 GiB libres en `/opt` y `/var/backups`.

`--deploy` bloquea despliegues concurrentes, respalda la versión y las unidades
actuales, prepara una versión independiente en `/opt/asistenciamodelo/releases`,
ejecuta pruebas del CRUD, autenticación y reportes, y compila el frontend con sus
dependencias bloqueadas. Comprueba servicios temporales en localhost antes de
reiniciar los dos servicios de producción. Luego verifica las rutas locales y
públicas y monitorea los servicios durante cinco minutos.

El esquema esperado es `20261007_0015`. No ejecuta migraciones, importaciones ni
cambios de datos. Tampoco cambia Nginx, certificados ni servicios de otras apps.
El respaldo contiene código, configuración de servicios y registros; no incluye
un volcado de PostgreSQL. Las pruebas usan SQLite aislado y las comprobaciones
contra producción no crean sesiones ni colaboradores.

## Reversión

Si falla la activación, retira los overrides creados por este despliegue y
restaura las rutas de la versión anterior. Si detecta modificaciones externas
en esos overrides, se detiene para conservarlas y solicitar revisión manual.

Al terminar imprime la ruta de un `rollback.sh` dentro de
`/var/backups/asistenciamodelo/<fecha>-colaboradores`. Para volver manualmente:

```bash
sudo bash /var/backups/asistenciamodelo/<fecha>-colaboradores/rollback.sh
```

La reversión restaura el código; conserva los datos, incluidas las modificaciones
que los usuarios hayan hecho después del despliegue.

## Validación funcional

Inicia sesión con `gaibarra@hotmail.com`, entra a **Gestionar colaboradores** y
comprueba búsqueda, filtros, ficha y edición. El CRUD está en `/colaboradores`.
Otra cuenta, incluso superadmin, no debe acceder: la API
`/employees/manage` debe devolver `403` para ella. Sin sesión, la página redirige
al login y las rutas de API devuelven `401`.

Las altas no crean credenciales de inicio de sesión. La eliminación protege
colaboradores con historial asociado y cuentas vinculadas al acceso staff.
