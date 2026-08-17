# Importacion de attendance_events desde Excel

## Objetivo

Este documento describe el flujo real de carga de `attendance_events` implementado en esta aplicacion. Su proposito es permitir replicar el comportamiento de forma identica en otra app, sin depender de interpretaciones generales.

El flujo actual:

- inicia en una pantalla web para superadministradores
- recibe un archivo `.xlsx`
- detecta columnas por encabezado y por contenido real
- normaliza filas y resuelve ambiguedades tipicas de Excel
- auto-crea empleados y relaciones faltantes cuando hace falta
- evita duplicados logicos
- persiste eventos y un lote de auditoria

## Componentes involucrados

Frontend:

- `frontend/src/app/staff/admin/page.tsx`
- `frontend/src/components/staff-admin-panel.tsx`
- `frontend/src/app/api/staff/attendance-imports/route.ts`

Backend:

- `backend/app/api/routes/staff.py`
- `backend/app/services/attendance_import.py`
- `backend/app/dependencies/auth.py`
- `backend/app/dependencies/services.py`

Modelos y schemas:

- `backend/app/models/attendance_event.py`
- `backend/app/models/attendance_import_batch.py`
- `backend/app/models/employee.py`
- `backend/app/models/employee_credential.py`
- `backend/app/models/staff_access.py`
- `backend/app/schemas/staff.py`
- `backend/app/schemas/attendance_event.py`

Pruebas de referencia:

- `backend/tests/test_staff_attendance_import.py`

## Flujo de punta a punta

1. Un usuario staff con rol `is_superadmin = true` entra a la pantalla administrativa.
2. Selecciona un archivo `.xlsx` y envia el formulario.
3. El frontend crea `FormData` con el campo `file`.
4. Next.js recibe el request en `/api/staff/attendance-imports`.
5. El proxy extrae la cookie `modeloasist_session` y reenvia el request al backend FastAPI con `Authorization: Bearer <token>`.
6. El backend valida autenticacion, rol superadmin, extension `.xlsx`, archivo no vacio y tamano maximo de 10 MB.
7. El backend abre el workbook con `openpyxl`, toma `workbook.active`, usa la fila 1 como encabezados y procesa datos desde la fila 2.
8. El backend analiza hasta 25 filas de preview para inferir columnas por contenido real.
9. Cada fila se convierte a `ParsedAttendanceRow`.
10. Si una fila no tiene `employee_id` utilizable, se intenta resolver por `nombre + departamento` o se genera uno nuevo.
11. Se auto-crean `employees`, `employee_credentials`, `departments`, `department_aliases` y `employee_departments` segun corresponda.
12. Se insertan `attendance_events` validos y no duplicados.
13. Se registra un `attendance_import_batch` con metricas y empleados nuevos.
14. Se hace un solo `commit`.
15. El frontend muestra el resumen del lote y las observaciones por fila, si existen.

## Origen de datos

Fuente soportada:

- archivo Excel `.xlsx`
- solo la hoja activa del workbook

No soportado:

- `.csv`
- multiples hojas con seleccion manual
- preview previa a persistencia

Validaciones iniciales:

- nombre de archivo debe terminar en `.xlsx`
- contenido no puede venir vacio
- tamano maximo `10 * 1024 * 1024` bytes

## Encabezados y deteccion de columnas

La importacion no depende solo de encabezados exactos. Primero normaliza encabezados y despues elige columnas por contenido si hay ambiguedades.

Normalizacion aplicada:

- elimina acentos y caracteres no ASCII
- convierte puntuacion a espacios
- colapsa espacios
- pasa a minusculas

Ejemplos:

- `N.º de serie del dispositivo` -> `n o de serie del dispositivo`
- `Codigo de empleado` -> `codigo de empleado`

### Campos internos requeridos

El servicio requiere mapear estas columnas internas:

- `employee_id`
- `nombre`
- `departamento_raw`
- `fecha`
- `tiempo`
- `source`
- `device_name`
- `device_serial`

### Aliases soportados

`employee_id`:

- `id`
- `employee id`
- `id de empleado`
- `codigo`
- `codigo de empleado`
- `codigo empleado`
- `matricula`
- `numero de empleado`
- `numero empleado`
- `num de empleado`
- `num empleado`
- `n`
- `n de empleado`
- `n o`
- `n o de empleado`
- `no de empleado`
- `no empleado`
- `enroll id`
- `enroll no`
- `enrol id`
- `employee no`
- `no`
- `numero`
- `num`

`fecha`:

- `fecha`
- `date`

`tiempo`:

- `tiempo`
- `hora`
- `time`

`source`:

- `fuente de datos`
- `fuente de datoss`

`device_serial`:

- `no de serie del dispositivo`
- `n de serie del dispositivo`
- `n o de serie del dispositivo`

### Seleccion por contenido

Si hay multiples columnas candidatas o encabezados confusos, el servicio puntua columnas por contenido real en las primeras 25 filas.

Reglas:

- `employee_id`: gana la columna con mas valores parseables como entero
- `fecha`: gana la columna con mas valores parseables como fecha
- `tiempo`: gana la columna con mas valores parseables como hora, excluyendo la columna ya elegida como `fecha`

Esto permite soportar casos como:

- `ID` que en realidad trae `MTJ-Imagen`
- `No.` que trae el numero real del empleado
- `Fecha` que en realidad trae horas
- otra columna no estandar que trae la fecha real

## Formato de filas esperado

Ejemplo operativo basico:

```text
nombre | ID | departamento | Fecha | Tiempo | Fuente de datos | Nombre del dispositivo | N.º de serie del dispositivo
CANCHE MAY ROGER | 3074 | Escuela Modelo/Montejo/MTJ-Imagen | 19-04-2026 | 06:01 | Dispositivo | CVA EDIFICIO PRINCIPAL | FQ8321320
REJON CAPILLA CARMEN DOLORES | 5005789865 | CME-Soluciones Castro | 19-04-2026 | 07:17 | Dispositivo | CME EXTERNOS | FQ2661487
```

Campos con valor obligatorio por fila:

- `nombre`
- `departamento`
- `fecha`
- `tiempo`

Campos con encabezado obligatorio pero valor por fila opcional:

- `ID`
- `Fuente de datos`
- `Nombre del dispositivo`
- `N.º de serie del dispositivo`

## Reglas de parseo y normalizacion

### employee_id

`employee_id` se intenta parsear como entero positivo. Soporta:

- enteros puros: `3074`
- miles con coma: `3,074`
- miles con punto: `3.074`
- decimal con ceros: `3074.0`, `3074,0`
- miles y decimal: `3,074.00`, `5.005.789.865,00`
- notacion cientifica: `5.005789865E+9`
- digitos Unicode normalizados
- texto de formula simple luego de limpiar `=` y comillas

Si el valor esta vacio o no es utilizable, no se invalida automaticamente la fila. Se deja `employee_id = None` temporalmente.

### fecha

`fecha` acepta:

- `date`
- `datetime`
- serial numerico de Excel
- string

Formatos de string soportados:

- `%d-%m-%Y`
- `%Y-%m-%d`
- `%d/%m/%Y`
- `%Y/%m/%d`
- `%d.%m.%Y`
- `%m/%d/%Y`

Si el string incluye fecha y hora, el parser usa solo la parte de fecha.

Si la columna elegida como `fecha` trae algo como `06:01` y la columna elegida como `tiempo` trae `19-04-2026`, la fila puede recuperarse invirtiendo ambos valores.

### tiempo

`tiempo` acepta:

- `time`
- `datetime`
- string `HH:MM`
- string `HH:MM:SS`

### textos opcionales

Para `source`, `device_name` y `device_serial` se hace:

- `str(value).strip()`
- si queda vacio, se guarda `None`

## Resolucion del empleado

Una vez parseadas las filas, el sistema resuelve `employee_id` faltantes o invalidos.

Algoritmo:

1. si la fila ya trae `employee_id` valido, se conserva
2. si no lo trae, se arma una clave por identidad:

```text
(normalize(nombre), normalize(departamento_raw))
```

3. si ya existe un `Employee` con esa identidad, se reutiliza su `id`
4. si no existe, se genera un `id` consecutivo nuevo
5. si varias filas del mismo lote representan a la misma persona, reutilizan el mismo `id` generado dentro del lote

La generacion del siguiente `employee_id` usa:

```text
max(
  ids numericos del lote,
  max(Employee.id) en base
) + 1
```

## Auto-creacion de empleados y relaciones

Cuando una fila valida queda asociada a un `employee_id` que no existe en `employees`, el sistema crea:

- un `Employee`
- un `EmployeeCredential`
- un `Department` si no existe alias equivalente
- un `DepartmentAlias` con `source = "excel_import"` si hace falta
- un `EmployeeDepartment` con `is_primary = true`

Reglas exactas del `Employee` auto-creado:

- `id = employee_id resuelto`
- `nombre = row.nombre`
- `departamento = row.departamento_raw`
- `campus = segunda parte del string departamento separado por /`
- `division = primera parte del string departamento separado por /`
- `email = emp-<employee_id>@pendiente.local`

Credencial creada:

- `employee_id = employee.id`
- `password_hash = hash_password(settings.auth_default_password)`
- `must_change_password = true`

## Transformacion final a attendance_events

Cada fila valida termina persistida en `attendance_events` con estos campos:

- `employee_id`
- `nombre`
- `departamento_raw`
- `device_name`
- `device_serial`
- `source`
- `fecha`
- `tiempo`
- `event_ts`

`event_ts` no viene del archivo. Se construye como:

```python
datetime.combine(fecha, tiempo)
```

`source` se transforma con prefijo:

- si `source = "Dispositivo"`, se guarda `excel:Dispositivo`
- si `source` viene vacio, se guarda `excel:excel`

## Duplicados

La deduplicacion se hace a nivel de aplicacion, no por upsert ni por constraint SQL visible.

Llave de duplicado:

```text
(employee_id, fecha, tiempo)
```

Se controlan dos tipos:

- duplicados ya existentes en base
- duplicados dentro del mismo archivo

Comportamiento:

- si una fila duplica esa llave, se ignora
- no se persiste
- no genera row error
- incrementa `skipped_duplicates`

No hay:

- `upsert`
- actualizacion del registro ya existente
- merge de `source`, `device_name` o `device_serial`

## Persistencia

Tablas afectadas directamente:

- `attendance_events`
- `attendance_import_batches`
- `employees`
- `employee_credentials`
- `departments`
- `department_aliases`
- `employee_departments`

Patron de persistencia:

- `db.add(...)` por entidad
- `db.flush()` cuando se necesita `id` intermedio
- un solo `db.commit()` al final del lote

No hay:

- vista previa
- staging table
- procesamiento asincrono
- bulk insert SQL

## Modelo de datos

### attendance_events

Campos ORM:

- `id: BigInteger` PK
- `employee_id: BigInteger` FK a `employees.id`
- `nombre: Text`
- `departamento_raw: Text | None`
- `device_name: Text | None`
- `device_serial: Text | None`
- `source: String(64) | None`
- `fecha: Date`
- `tiempo: Time`
- `event_ts: datetime`
- `created_at: now()`

### attendance_import_batches

Campos ORM:

- `id: String(36)` UUID string
- `uploaded_by_staff_user_id: BigInteger | None`
- `original_filename: Text`
- `uploaded_at: DateTime`
- `total_rows: Integer`
- `imported_rows: Integer`
- `skipped_duplicates: Integer`
- `invalid_rows: Integer`
- `auto_created_employees: JSON`

## Respuesta al usuario

### Exito

Si la importacion concluye con al menos una fila valida, el backend responde `201` con:

- resumen del lote
- empleados auto-creados
- filas con observaciones no bloqueantes

Ejemplo:

```json
{
  "batch": {
    "id": "2cb91d2c-89b2-4d30-9ef3-7c8c34b1f17e",
    "original_filename": "asistencia.xlsx",
    "uploaded_at": "2026-05-06T14:13:39",
    "uploaded_by": "Staff Demo",
    "total_rows": 3,
    "imported_rows": 2,
    "skipped_duplicates": 1,
    "invalid_rows": 0,
    "auto_created_employees": [
      {
        "employee_id": 5005789865,
        "nombre": "REJON CAPILLA CARMEN DOLORES",
        "departamento": "CME-Soluciones Castro",
        "email": "emp-5005789865@pendiente.local"
      }
    ]
  },
  "row_errors": []
}
```

### Error total del archivo

Si todas las filas son invalidas, responde `400` con detalle estructurado:

```json
{
  "detail": {
    "message": "No se pudieron procesar filas válidas del archivo",
    "row_errors": [
      {
        "row_number": 2,
        "message": "Fecha tiene un formato inválido (valor: 06:01)"
      }
    ]
  }
}
```

La UI actual muestra bien el resumen y los `row_errors` cuando la respuesta es `201`, pero en error total solo muestra el mensaje general y no despliega la lista de `row_errors` del `400`.

## Casos especiales soportados

La suite de pruebas actual cubre estos escenarios:

- importacion basica con auto-creacion de empleado faltante
- rechazo a usuarios no superadmin
- historial de lotes
- `employee_id` como texto con comas
- `employee_id` con puntos o miles localizados
- `employee_id` con decimales en cero
- columna `ID` que en realidad trae codigos como `MTJ-Imagen` y numero real en `No.`
- archivo sin numero de empleado utilizable y asignacion automatica de consecutivos
- fecha con strings tipo datetime
- fecha y tiempo cruzados entre columnas
- fecha real en columna no estandar

Archivo de referencia:

- `backend/tests/test_staff_attendance_import.py`

## SQL de verificacion operativa

Ultimo batch:

```sql
SELECT
  id,
  original_filename,
  uploaded_at,
  total_rows,
  imported_rows,
  skipped_duplicates,
  invalid_rows,
  auto_created_employees
FROM attendance_import_batches
ORDER BY uploaded_at DESC
LIMIT 1;
```

Eventos del dia:

```sql
SELECT
  id,
  employee_id,
  nombre,
  departamento_raw,
  fecha,
  tiempo,
  event_ts,
  source,
  device_name,
  device_serial
FROM attendance_events
WHERE fecha = DATE '2026-04-19'
ORDER BY employee_id, tiempo;
```

Duplicados logicos persistidos:

```sql
SELECT
  employee_id,
  fecha,
  tiempo,
  COUNT(*) AS total
FROM attendance_events
GROUP BY employee_id, fecha, tiempo
HAVING COUNT(*) > 1;
```

Empleados auto-creados:

```sql
SELECT
  id,
  nombre,
  departamento,
  campus,
  division,
  email
FROM employees
WHERE email LIKE 'emp-%@pendiente.local'
ORDER BY id DESC;
```

## Dependencias

Dependencias backend involucradas:

- `fastapi`
- `sqlalchemy`
- `python-multipart`
- `openpyxl`
- `pydantic`
- `psycopg`
- `alembic`

Declaradas en `backend/pyproject.toml`.

## Pruebas minimas para clonar el comportamiento

Para garantizar compatibilidad funcional en otra app, implementar pruebas para:

1. importacion exitosa con empleado nuevo
2. rechazo a no superadmin
3. historial de lotes
4. ids numericos con formatos de Excel variados
5. ids no numericos resueltos por otra columna
6. asignacion automatica de employee_id
7. fechas con datetime string
8. fecha y tiempo cruzados
9. fecha real en columna no estandar
10. deduplicacion por `(employee_id, fecha, tiempo)`

## Limites y supuestos

Lo siguiente no esta implementado o no es explicito en el codigo actual:

- no hay timezone explicita
- no hay preview previa a persistencia
- no hay hash o checksum del archivo
- no hay idempotencia por nombre de archivo
- no hay upsert
- no hay migracion visible de `attendance_events` en el repo actual
- no hay constraint SQL visible para reforzar duplicados por `(employee_id, fecha, tiempo)`

## Referencias principales

- `backend/app/services/attendance_import.py`
- `backend/app/api/routes/staff.py`
- `backend/app/models/attendance_event.py`
- `backend/app/models/attendance_import_batch.py`
- `backend/tests/test_staff_attendance_import.py`
- `frontend/src/components/staff-admin-panel.tsx`