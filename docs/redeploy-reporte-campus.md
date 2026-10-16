# Despliegue del reporte ejecutivo por campus

Ejecutar desde la terminal del VPS:

```bash
sudo bash /home/gaibarra/modeloasist/infra/scripts/redeploy_reporte_campus.sh --check
sudo bash /home/gaibarra/modeloasist/infra/scripts/redeploy_reporte_campus.sh --deploy
```

La comprobación inicial es de solo lectura. El despliegue parte exclusivamente de
`/opt/asistenciamodelo/releases/20261016T142210Z-campus-report` y añade cuatro
archivos verificados por SHA-256. Si cambian los archivos o la versión activa,
se detiene: no publica automáticamente HEAD ni otros cambios locales.

El ajuste excluye BAJAS, BAJAS NOMINA, Pasantes, Soluciones Castro y Consma Clean del reporte, totales y CSV, y muestra
el departamento bajo el nombre en pantalla e impresión.

Se ejecutan pruebas, lint, TypeScript, compilación y pruebas de disponibilidad
en una carpeta nueva antes de reiniciar exclusivamente los dos servicios de
asistenciamodelo. Se mantienen los puertos 8184/3101, variables y entorno Python.
No se ejecutan migraciones ni importaciones y no se modifica Nginx.

La publicación requiere varios minutos y tiene una interrupción breve durante
el cambio de servicios, seguida de cinco minutos de monitoreo. Los registros,
artefactos anteriores y unidades quedan en una carpeta privada
`/var/backups/asistenciamodelo/<fecha>-campus-report-exclusions`.

Esta revisión conserva el override del primer reporte (`zzzzzzzzz-campus-report.conf`)
y crea uno posterior, `zzzzzzzzzz-campus-report-exclusions.conf`. La reversión
retira solo este nuevo ajuste y recupera el reporte publicado el 16 de octubre.

Ante un fallo esencial después del cambio, se restauran los ajustes anteriores.
El script también imprime el comando `sudo bash <respaldo>/rollback.sh` para
reversión manual, que rechaza sobrescribir un despliegue posterior. No revierte datos.

Queda pendiente la comprobación visual con una sesión legítima de
gaibarra@hotmail.com o duchliz@modelo.edu.mx: exclusiones, departamento,
orden alfabético, totales, CSV e impresión. Las pruebas sin sesión verifican
que las rutas protegidas sigan rechazando acceso anónimo.
