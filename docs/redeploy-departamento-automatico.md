# Despliegue: departamento automático

```bash
sudo bash /home/gaibarra/modeloasist/infra/scripts/redeploy_departamento_automatico.sh --check
sudo bash /home/gaibarra/modeloasist/infra/scripts/redeploy_departamento_automatico.sh --deploy
```

Ejecutar `--deploy` solo si `--check` termina correctamente. Requiere contraseña
sudo en la terminal del operador; no compartirla en el chat.

Parte del frontend activo `20261026T142227Z-vacaciones` y copia únicamente tres
archivos verificados por SHA-256. No publica HEAD ni cambios ajenos del workspace.
Conserva dependencias, variables y puerto 3101. No accede a PostgreSQL, no migra,
no reinicia backend y no modifica Nginx ni otros proyectos.

Construye en una carpeta aislada con límites de CPU/memoria. Ejecuta pruebas,
TypeScript, lint y build, y prueba temporalmente login y acceso anónimo en localhost.
El frontend anterior y sus unidades se respaldan con permisos restringidos en
`/var/backups/asistenciamodelo/<fecha>-department-auto`.

La activación provoca una interrupción breve solo del frontend. El override nuevo
`zzzzzzzzzzzzz-department-auto.conf` conserva los anteriores. Si falla una comprobación
esencial, se retira solo ese ajuste y se recupera el frontend anterior. Se genera
`rollback.sh` en el respaldo, protegido contra una versión posterior o cambios externos.
El despliegue termina después de cinco minutos de monitoreo.

Validación manual con sesión staff legítima: seleccionar otro departamento debe
consultarlo automáticamente, conservando fechas, búsqueda, filtro y orden. Verificar
que no se abre el reporte de horas por accidente y que Consultar e impresión funcionan.
No se crean cuentas ni sesiones de prueba. La validación visual no se da por realizada
solo por recibir 200 en login.
