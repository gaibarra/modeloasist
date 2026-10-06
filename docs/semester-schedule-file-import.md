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
