# Horarios agosto–diciembre de 2026

El importador procesa las hojas CME (Mérida), CVA (Valladolid) y CCH
(Chetumal). `empleadoId` es un identificador externo: no se utiliza como ID
de asistencia. Solo se aplican coincidencias únicas de nombre completo
normalizado y campus. Las sugerencias aproximadas son informativas.

Desde `backend`, con el entorno de base de datos correspondiente:

```bash
./.venv/bin/python -m app.services.semester_file_import ../Horarios2doSemestre2026.xlsx --output ../reportes/horarios-2026-S2-preview
./.venv/bin/alembic upgrade head
./.venv/bin/python -m app.services.semester_file_import ../Horarios2doSemestre2026.xlsx --output ../reportes/horarios-2026-S2 --apply
```

La primera ejecución solo genera una vista previa. La segunda aplica la
migración aditiva de bitácora. La última reemplaza exclusivamente perfiles
semestrales agosto–diciembre 2026 de personas identificadas con seguridad.
Une intervalos superpuestos o consecutivos, elimina duplicados y conserva
huecos. Días sin bloques en un perfil importado quedan sin turno.

No modifica eventos, excepciones por fecha, exenciones, horarios legacy ni
otros semestres. Los pendientes conservan su horario operativo actual.

Antes de aplicar se crea un respaldo JSON con los perfiles anteriores.
La actualización y el registro de auditoría se confirman en una transacción.
`staff_schedule_file_imports` conserva SHA256, fecha y auditoría por persona
(ID interno, nombre, hojas, IDs externos, filas, bloques anteriores/nuevos).
No se atribuye la carga a un staff que no inició sesión. Repetir `--apply`
con el mismo archivo regenera el reporte sin reemplazar horarios nuevamente.

El Excel de seguimiento incluye confirmados por archivo, pendientes por
campus y departamento, correo, texto para solicitar información y casos
por revisar. “Pendiente” significa sin confirmación mediante este archivo,
no falta ni descanso. No se envía ningún correo automáticamente.

La bitácora describe la confirmación de esta carga, no es un indicador
automático de las confirmaciones recibidas posteriormente por otros medios.
Usar las columnas de seguimiento del reporte para documentarlas. Una carga
nueva debe partir de un archivo completo del semestre y revisarse en vista
previa. Guardar los reportes fuera de Git por contener datos personales.

## Revisión de hoja única (noviembre de 2026)

`app.services.revised_schedule_import` acepta `horariosactualizados.xlsx` y
prepara la revisión completa para agosto–diciembre 2026, incluidos reportes
históricos. No sustituye el importador de tres hojas.

Desde `backend`, generar únicamente la vista previa:

```bash
STARTUP_BOOTSTRAP_ENABLED=false PYTHONPATH=. .venv/bin/python -m app.services.revised_schedule_import \
  ../horariosactualizados.xlsx --output ../reportes/horarios_revision_20261123
```

El directorio privado contiene `revision.json` y `Revision_horarios.xlsx`.
La columna Anterior compara el perfil semestral almacenado; vacío significa
que no existe ese perfil, no que el colaborador carezca de un horario legacy.
No se alteran horarios legacy, contratos ni excepciones por fecha.

La revisión utiliza nombres normalizados y equivalencias de bitácoras previas.
Los identificadores externos no identifican cuentas por sí solos. Hasta dos
caracteres distintos solo se aceptan con apellidos y cantidad de palabras
iguales y candidato único. Las identidades ambiguas, las bajas y las semanas
con errores o solapamientos no son aplicables. Los duplicados idénticos se
eliminan, los bloques contiguos se unen y las pausas se conservan.

Después de aprobar el reporte, crear un JSON privado con la lista de IDs
internos aprobados. No se genera automáticamente una aprobación. Ejecutar:

```bash
STARTUP_BOOTSTRAP_ENABLED=false PYTHONPATH=. .venv/bin/python -m app.services.revised_schedule_import \
  ../horariosactualizados.xlsx --output ../reportes/horarios_revision_20261123/aplicacion \
  --apply-review ../reportes/horarios_revision_20261123/revision.json \
  --approved-ids ../reportes/horarios_revision_20261123/ids_aprobados.json \
  --authorization 'Referencia a la confirmación explícita del usuario'
```

La aplicación respalda PostgreSQL antes de escribir, bloquea las tablas
relevantes, compara nuevamente toda la revisión y revierte la transacción
ante errores. Si cambió el archivo, catálogo, contratos o perfiles, se debe
regenerar y revisar la vista previa. La bitácora usa una huella de operación
(archivo + revisión + IDs aprobados) y conserva la huella original del Excel
en `audit.file_sha256`; permite nuevas revisiones de pendientes del mismo
archivo sin editar recibos anteriores. Repetir la misma aplicación no cambia
los horarios. Un caso pendiente exige una revisión nueva una vez resuelto;
no se deben editar manualmente los estados del JSON para eludir controles.

Reversión explícita de una operación compatible, con respaldo previo:

```bash
STARTUP_BOOTSTRAP_ENABLED=false PYTHONPATH=. .venv/bin/python -m app.services.revised_schedule_import \
  ../horariosactualizados.xlsx --output ../reportes/horarios_revision_20261123/reversion \
  --rollback ID_OPERACION --authorization 'Referencia a la autorización de reversión'
```

Solo se restauran perfiles idénticos a la versión que dejó la operación,
incluida su fecha de modificación. Los modificados posteriormente se omiten
y quedan identificados en el recibo de reversión. No se restaura toda la base.
No requiere migración, despliegue ni reinicio de servicios.
