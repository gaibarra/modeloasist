# Redeploy de motivos de exención

Añade Vacaciones y conserva Cita Médica/Enfermedad, Asunto Personal y Retardo Justificado en captura,
validación, historial, tarjetas y reportes. No requiere migraciones ni importaciones.

```bash
sudo bash /home/gaibarra/modeloasist/infra/scripts/redeploy_motivos_exencion.sh --check
sudo bash /home/gaibarra/modeloasist/infra/scripts/redeploy_motivos_exencion.sh --deploy
```

Ejecutar `--deploy` únicamente después de que `--check` termine correctamente.
La base fijada es `/opt/asistenciamodelo/releases/20261023T154732Z-exemption-reasons`.
Se copian solo seis archivos locales con hashes verificados; no se publica todo HEAD.
Se conservan dependencias, variables, puertos 8184/3101 y configuración de otras aplicaciones.

Antes de la interrupción breve se respaldan unidades y artefactos y se ejecutan
pruebas, TypeScript, lint, build y comprobaciones temporales en localhost.
La prueba de cambios masivos usa ahora una semana completa, como exige la API;
no se cambió esa regla de producción. Para Vacaciones se validaron 48 pruebas de
exenciones y horas, TypeScript, lint y siete pruebas del script. La suite ampliada
y la compilación de producción se ejecutan durante `--deploy`.

El nuevo override `zzzzzzzzzzzz-vacaciones.conf` conserva los anteriores.
Respaldo privado: `/var/backups/asistenciamodelo/<fecha>-vacaciones`.
Se monitorea cinco minutos y se genera `rollback.sh` dentro del respaldo.
La reversión automática o manual retira únicamente el nuevo override; rechaza
alteraciones externas y no restaura ni modifica datos.

Validación manual pendiente con sesión staff legítima: comprobar Vacaciones y los motivos anteriores
en el selector y su presentación en historial, tarjeta e impresión. No crear
exenciones ficticias en producción para probar el despliegue.
