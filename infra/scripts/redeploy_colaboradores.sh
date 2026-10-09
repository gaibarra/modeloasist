#!/usr/bin/env bash
# Publish owner-only collaborator CRUD: pinned commit 25f5cb0.
# No database migrations or data imports; production services change only with --deploy.
# Run with sudo bash ... --check, then sudo bash ... --deploy.
set -Eeuo pipefail
umask 077

MODE=${1:---check}
[[ $# -le 1 && "$MODE" =~ ^--(check|deploy)$ ]] || { echo 'Uso: sudo bash redeploy_colaboradores.sh [--check|--deploy]' >&2; exit 2; }
[[ $EUID -eq 0 ]] || { echo 'Ejecuta este script con sudo desde tu terminal.' >&2; exit 1; }
REPO=/home/gaibarra/modeloasist
ACCOUNT=asistenciamodelo
BACKEND=asistenciamodelo-backend.service
FRONTEND=asistenciamodelo-frontend.service
PYTHON=$REPO/backend/.venv/bin/python
BACK_ENV=/etc/asistenciamodelo/backend.env
FRONT_ENV=/etc/asistenciamodelo/frontend.env
# Sort after previous release overrides; retain them for rollback.
BACK_DROP=/etc/systemd/system/$BACKEND.d/zzzz-release-colaboradores.conf
FRONT_DROP=/etc/systemd/system/$FRONTEND.d/zzzz-release-colaboradores.conf
OLD_BACK=''
OLD_FRONT=''
PREVIOUS_ROOT=''
RELEASE=''
BACKUP=''
SWITCHED=0
FINISHED=0
SMOKE_BACK=''
SMOKE_FRONT=''
UNIT_STATE=''

unit_state() {
  systemctl cat "$BACKEND" "$FRONTEND" | sha256sum | awk '{print $1}'
}

# Uses service credentials, never prints them, and starts no application lifespan.
verify_database() (
  set -a
  source "$BACK_ENV"
  set +a
  cd "$REPO/backend"
  export STARTUP_BOOTSTRAP_ENABLED=false PYTHONDONTWRITEBYTECODE=1
  runuser -u "$ACCOUNT" -- "$PYTHON" - <<'PY'
import json
from sqlalchemy import create_engine, inspect, text
from app.core.config import get_settings
engine = create_engine(get_settings().database_url)
if engine.dialect.name != 'postgresql':
    raise SystemExit('No se permite SQLite en producción.')
with engine.connect() as connection:
    connection.execute(text('SET TRANSACTION READ ONLY'))
    revisions = connection.execute(text('SELECT version_num FROM alembic_version')).scalars().all()
    if revisions != ['20261007_0015']:
        raise SystemExit('Versión de base inesperada; no se ejecutarán migraciones.')
    schema = inspect(connection)
    required = {
        'employees': {'id', 'nombre', 'email', 'departamento', 'campus', 'division', 'external_employee_id'},
        'employee_departments': {'employee_id', 'department_id', 'is_primary'},
        'departments': {'id', 'name', 'campus', 'active'},
        'staff_users': {'id', 'email', 'employee_id', 'is_active'},
        'employee_credentials': {'employee_id', 'password_hash'},
    }
    for table, columns in required.items():
        if not columns <= {c['name'] for c in schema.get_columns(table)}:
            raise SystemExit(f'Esquema incompatible: {table}')
    print(json.dumps({'revision': revisions, 'schema': 'collaborator-crud-compatible'}, sort_keys=True))
engine.dispose()
PY
)

die() { echo "ERROR: $*" >&2; exit 1; }
git_repo() { runuser -u gaibarra -- git -C "$REPO" "$@"; }
http_code() { curl --silent --output /dev/null --write-out '%{http_code}' --max-time 5 "$1"; }
wait_http() {
  local url=$1 expected=$2 attempt code
  for attempt in {1..30}; do
    code=$(http_code "$url") || code=000
    [[ "$code" == "$expected" ]] && return 0
    sleep 2
  done
  echo "No respondió $expected: $url (última respuesta $code)" >&2
  return 1
}
cleanup() {
  local result=$?
  trap - EXIT INT TERM
  set +e
  [[ -z "$SMOKE_FRONT" ]] || systemctl stop "$SMOKE_FRONT" >/dev/null 2>&1
  [[ -z "$SMOKE_BACK" ]] || systemctl stop "$SMOKE_BACK" >/dev/null 2>&1
  if [[ $SWITCHED == 1 && $FINISHED == 0 ]]; then
    echo 'Falló la publicación; restaurando las unidades anteriores.' >&2
    for item in backend frontend; do
      if [[ "$item" == backend ]]; then target=$BACK_DROP; else target=$FRONT_DROP; fi
      if [[ -f "$target" ]] && ! cmp -s "$target" "$BACKUP/new-$item.conf"; then
        echo "ATENCIÓN: $target cambió externamente. No se retirará ni se reiniciarán servicios; revisar manualmente." >&2
        exit 1
      fi
    done
    # These two files were absent before deployment. Preserve them for diagnosis.
    [[ ! -f "$BACK_DROP" ]] || mv "$BACK_DROP" "$BACKUP/failed-backend-override.conf"
    [[ ! -f "$FRONT_DROP" ]] || mv "$FRONT_DROP" "$BACKUP/failed-frontend-override.conf"
    systemctl daemon-reload
    systemctl restart "$BACKEND"
    systemctl restart "$FRONTEND"
    if [[ $(systemctl show "$BACKEND" -p WorkingDirectory --value) == "$OLD_BACK" && $(systemctl show "$FRONTEND" -p WorkingDirectory --value) == "$OLD_FRONT" ]] && wait_http http://127.0.0.1:8184/health/ready 200 && wait_http http://127.0.0.1:3101/login 200; then
      echo 'Versión anterior restaurada; datos y Nginx no se modificaron.' >&2
    else
      echo "ATENCIÓN: recuperación no confirmada. Consulta systemctl status y $BACKUP." >&2
    fi
    result=1
  fi
  [[ -z "$BACKUP" ]] || echo "Respaldo y registros: $BACKUP"
  exit "$result"
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

for tool in git runuser systemctl systemd-run curl tar node npm flock ss awk df sha256sum cmp timeout; do
  command -v "$tool" >/dev/null || die "Falta $tool"
done
id "$ACCOUNT" >/dev/null
if [[ "$MODE" == --deploy ]]; then
  exec 9>/run/lock/asistenciamodelo-redeploy.lock
  flock -n 9 || die 'Hay otro redeploy en ejecución.'
fi
[[ -x "$PYTHON" && -r "$BACK_ENV" && -r "$FRONT_ENV" ]] || die 'Falta Python o configuración de producción.'
COMMIT=$(git_repo rev-parse '25f5cb0fac455373dd4d650221269642727c59db^{commit}')
# Deploy the pinned commit even if HEAD later contains this script or documentation.
[[ ! -e "$BACK_DROP" && ! -e "$FRONT_DROP" ]] || die 'Ya existe un override de esta publicación; no se sobrescribirá.'
for unit in "$BACKEND" "$FRONTEND"; do
  systemctl is-active --quiet "$unit" || die "$unit no está activo; diagnosticar antes de desplegar."
  [[ $(systemctl show "$unit" -p User --value) == "$ACCOUNT" ]] || die "Usuario inesperado en $unit"
done
OLD_BACK=$(systemctl show "$BACKEND" -p WorkingDirectory --value)
OLD_FRONT=$(systemctl show "$FRONTEND" -p WorkingDirectory --value)
PREVIOUS_ROOT=${OLD_BACK%/backend}
[[ "$PREVIOUS_ROOT" == /opt/asistenciamodelo/releases/* && "$PREVIOUS_ROOT" != *..* && "$OLD_FRONT" == "$PREVIOUS_ROOT/frontend" ]] || die 'La versión activa cambió; revisar antes de desplegar.'
[[ -d "$OLD_BACK" && -s "$OLD_FRONT/.next/BUILD_ID" ]] || die 'No se localizan artefactos activos para reversión.'
[[ $(http_code http://127.0.0.1:8184/health/ready) == 200 ]] || die 'Backend no está listo.'
[[ $(http_code http://127.0.0.1:3101/login) == 200 ]] || die 'Frontend no está listo.'
AVAILABLE_KB=$(awk '/^MemAvailable:/ {print $2}' /proc/meminfo)
[[ "$AVAILABLE_KB" -ge 2097152 ]] || die 'Se requieren al menos 2 GiB de RAM disponible para no presionar otros proyectos.'
for directory in /opt /var/backups; do
  FREE_KB=$(df -Pk "$directory" | awk 'NR == 2 {print $4}')
  [[ "$FREE_KB" -ge 6291456 ]] || die "Se requieren al menos 6 GiB libres en $directory para build y respaldo."
done
# Refuse an unexpected backend startup command rather than discard custom flags.
EXEC=$(systemctl show "$BACKEND" -p ExecStart --value)
[[ "$EXEC" == *"$REPO/backend/.venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8184 --workers 2 --timeout-keep-alive 10 --limit-concurrency 200 ;"* ]] || die 'ExecStart backend difiere del esperado.'
[[ $(systemctl show "$FRONTEND" -p ExecStart --value) == *'npm run start -- --hostname 127.0.0.1 --port 3101 ;'* ]] || die 'ExecStart frontend difiere del esperado.'
echo "Commit validado: $COMMIT; ambos servicios responden 200."
echo 'Se conservarán Python, Nginx, certificados, firewall, datos y servicios ajenos.'
UNIT_STATE=$(unit_state)
[[ $(systemctl show "$BACKEND" -p WorkingDirectory --value) == "$OLD_BACK" && $(systemctl show "$FRONTEND" -p WorkingDirectory --value) == "$OLD_FRONT" ]] || die 'Cambió la versión activa durante la comprobación.'
echo 'Verificando compatibilidad del esquema en solo lectura...'
DB_STATE=$(verify_database) || die 'No se pudo verificar el esquema con las credenciales del servicio.'
echo 'Base 20261007_0015 compatible con CRUD; no se modificaron datos.'
if [[ "$MODE" == --check ]]; then
  echo 'Comprobación inicial correcta. --deploy hará respaldo, pruebas y build aislados antes de cambiar servicios.'
  exit 0
fi

STAMP=$(date -u +%Y%m%dT%H%M%SZ)
RELEASE=/opt/asistenciamodelo/releases/$STAMP-colaboradores
BACKUP=/var/backups/asistenciamodelo/$STAMP-colaboradores
[[ ! -e "$RELEASE" && ! -e "$BACKUP" ]] || die 'Ya existe esta carpeta de despliegue.'
install -d -m 0755 /opt/asistenciamodelo /opt/asistenciamodelo/releases
install -d -m 0700 "$BACKUP"
install -d -m 0755 "$RELEASE"
# Build exactly the pinned commit; ignore working-tree changes and later commits.
git_repo archive "$COMMIT" | tar -x --exclude='backend/runtime.db' --exclude='*.xlsx' --exclude='reportes' -C "$RELEASE"
printf '%s\n' "$COMMIT" > "$BACKUP/commit.txt"
systemctl cat "$BACKEND" > "$BACKUP/backend-unit.txt"
systemctl cat "$FRONTEND" > "$BACKUP/frontend-unit.txt"
systemctl show "$BACKEND" "$FRONTEND" -p WorkingDirectory -p ExecStart -p FragmentPath -p DropInPaths > "$BACKUP/previous-routes.txt"
tar -czf "$BACKUP/previous-units.tar.gz" -C /etc/systemd/system "$BACKEND" "$FRONTEND" "$BACKEND.d" "$FRONTEND.d"
printf '%s\n' "$DB_STATE" > "$BACKUP/database-before.json"
tar -czf "$BACKUP/previous-release.tar.gz" --exclude='./frontend/.next/cache' --exclude='./.npm-cache' -C "$PREVIOUS_ROOT" .
"$PYTHON" -m pip freeze > "$BACKUP/python-dependencies.txt"
chmod -R go-rwx "$BACKUP"
# The active paths, node_modules and virtualenv remain untouched for rollback.
chown -R "$ACCOUNT":www-data "$RELEASE"
chmod 0755 "$RELEASE"
cmp -s "$RELEASE/backend/pyproject.toml" "$OLD_BACK/pyproject.toml" || die 'Cambian dependencias Python; no se modificará el virtualenv compartido.'
cmp -s "$RELEASE/frontend/package-lock.json" "$OLD_FRONT/package-lock.json" || die 'El lockfile difiere de producción; se requiere revisar dependencias.'

echo 'Comprobando esquema existente, sin aplicar migraciones...'
(
  set -a
  source "$BACK_ENV"
  set +a
  cd "$RELEASE/backend"
  export STARTUP_BOOTSTRAP_ENABLED=false
  export PYTHONDONTWRITEBYTECODE=1
  runuser -u "$ACCOUNT" -- "$PYTHON" - <<'PY'
from sqlalchemy import create_engine, inspect, text
from alembic.config import Config
from alembic.script import ScriptDirectory
from alembic.runtime.migration import MigrationContext
from app.core.config import get_settings
settings = get_settings()
if not settings.database_url.startswith(('postgresql', 'postgres')):
    raise SystemExit('Se esperaba PostgreSQL de producción; no se permite fallback SQLite.')
engine = create_engine(settings.database_url)
with engine.connect() as connection:
    connection.execute(text('SET TRANSACTION READ ONLY'))
    current = set(MigrationContext.configure(connection).get_current_heads())
    expected = set(ScriptDirectory.from_config(Config('alembic.ini')).get_heads())
    if current != expected:
        raise SystemExit('Migraciones pendientes o divergentes. No se desplegó ni migró nada.')
    if 'external_employee_id' not in {c['name'] for c in inspect(connection).get_columns('employees')}:
        raise SystemExit('Falta employees.external_employee_id. Requiere revisión separada.')
engine.dispose()
print('Esquema compatible; cero escrituras realizadas.')
PY
) > "$BACKUP/schema-check.log" 2>&1 || die "Esquema incompatible; revisa $BACKUP/schema-check.log"

echo 'Ejecutando pruebas y compilación aislada (puede tardar varios minutos)...'
systemd-run --scope --quiet --property=MemoryMax=1536M --property=CPUQuota=100% runuser -u "$ACCOUNT" -- env DATABASE_URL=sqlite:// STARTUP_BOOTSTRAP_ENABLED=false bash -c 'cd "$1/backend"; timeout 180 "$2" -m pytest tests/test_employee_management.py tests/test_auth.py tests/test_campus_hours.py tests/test_labor_contracts.py tests/test_weekly_hours.py tests/test_attendance_identity_resolution.py tests/test_semester_file_import.py tests/test_staff_attendance_import.py -q --tb=short' _ "$RELEASE" "$PYTHON" > "$BACKUP/tests.log" 2>&1 || die "Fallaron pruebas; consulta $BACKUP/tests.log"
(
  set -a
  source "$FRONT_ENV"
  set +a
  export NEXT_DIST_DIR=.next
  export npm_config_cache="$RELEASE/.npm-cache"
  export NEXT_TELEMETRY_DISABLED=1
  export NODE_OPTIONS=--max-old-space-size=1024
  systemd-run --scope --quiet --property=MemoryMax=1536M --property=CPUQuota=100% runuser -u "$ACCOUNT" -- bash -c '
    set -e
    cd "$1/frontend"
    npm ci --include=dev
    npm run lint
    npx --no-install tsc --noEmit --incremental false
    npm run build
  ' _ "$RELEASE"
) > "$BACKUP/frontend-build.log" 2>&1 || die "Falló compilación; consulta $BACKUP/frontend-build.log"
[[ -s "$RELEASE/frontend/.next/BUILD_ID" ]] || die 'No existe un build válido.'

# Temporary services are restricted to this app and localhost.
"$PYTHON" - <<'PY'
import socket
for port in (18184, 13101):
    with socket.socket() as sock:
        sock.bind(('127.0.0.1', port))
PY
SMOKE_BACK=asistenciamodelo-smoke-back-$STAMP.service
SMOKE_FRONT=asistenciamodelo-smoke-front-$STAMP.service
systemd-run --quiet --unit="$SMOKE_BACK" --property=User="$ACCOUNT" --property=Group=www-data \
  --property=WorkingDirectory="$RELEASE/backend" --property=EnvironmentFile="$BACK_ENV" \
  --property=MemoryMax=768M --property=CPUQuota=100% --property=RuntimeMaxSec=180 \
  /usr/bin/env STARTUP_BOOTSTRAP_ENABLED=false "$PYTHON" -m uvicorn app.main:app --host 127.0.0.1 --port 18184
wait_http http://127.0.0.1:18184/health/ready 200
wait_http http://127.0.0.1:18184/employees/manage 401
wait_http http://127.0.0.1:18184/employees/manage/departments 401
wait_http 'http://127.0.0.1:18184/staff/weekly-hours?department_id=1&start_date=2026-09-28&end_date=2026-10-04' 401
wait_http http://127.0.0.1:18184/staff/labor-contracts 401
wait_http 'http://127.0.0.1:18184/staff/campus-hours?campus=Valladolid&start_date=2026-09-28&end_date=2026-10-04' 401
systemd-run --quiet --unit="$SMOKE_FRONT" --property=User="$ACCOUNT" --property=Group=www-data \
  --property=WorkingDirectory="$RELEASE/frontend" --property=EnvironmentFile="$FRONT_ENV" \
  --property=MemoryMax=768M --property=CPUQuota=100% --property=RuntimeMaxSec=180 \
  /usr/bin/env NEXT_DIST_DIR=.next API_BASE_URL=http://127.0.0.1:18184 /usr/bin/npm run start -- --hostname 127.0.0.1 --port 13101
wait_http http://127.0.0.1:13101/login 200
wait_http http://127.0.0.1:13101/colaboradores 307
wait_http http://127.0.0.1:13101/api/colaboradores 401
wait_http 'http://127.0.0.1:13101/staff/hours?department_id=1&start_date=2026-09-28&end_date=2026-10-04' 307
wait_http http://127.0.0.1:13101/staff/contracts 307
wait_http http://127.0.0.1:13101/staff/campus-hours 307
wait_http http://127.0.0.1:13101/api/staff/campus-hours 401
wait_http http://127.0.0.1:13101/api/staff/labor-contracts 401
systemctl stop "$SMOKE_FRONT" "$SMOKE_BACK"
SMOKE_FRONT=''
SMOKE_BACK=''

# Override only the two existing units. All other hardening/env settings survive.
install -d -m 0755 "/etc/systemd/system/$BACKEND.d" "/etc/systemd/system/$FRONTEND.d"
cat > "$BACKUP/new-backend.conf" <<EOF
[Service]
WorkingDirectory=$RELEASE/backend
ExecStart=
ExecStart=/usr/bin/env STARTUP_BOOTSTRAP_ENABLED=false $PYTHON -m uvicorn app.main:app --host 127.0.0.1 --port 8184 --workers 2 --timeout-keep-alive 10 --limit-concurrency 200
ReadWritePaths=$RELEASE/backend
EOF
cat > "$BACKUP/new-frontend.conf" <<EOF
[Service]
WorkingDirectory=$RELEASE/frontend
ExecStart=
ExecStart=/usr/bin/env NEXT_DIST_DIR=.next /usr/bin/npm run start -- --hostname 127.0.0.1 --port 3101
ReadWritePaths=$RELEASE/frontend/.next
EOF
# Save an operator rollback script; never delete the release or original files.
cat > "$BACKUP/rollback.sh" <<EOF
#!/usr/bin/env bash
set -euo pipefail
[[ \$EUID -eq 0 ]] || { echo 'Ejecuta con sudo'; exit 1; }
exec 9>/run/lock/asistenciamodelo-redeploy.lock
flock -n 9 || { echo 'Hay un despliegue en curso'; exit 1; }
[[ \$(systemctl show $BACKEND -p WorkingDirectory --value) == '$RELEASE/backend' ]] || { echo 'Existe otro despliegue; no se revierte automáticamente.'; exit 1; }
[[ \$(systemctl show $FRONTEND -p WorkingDirectory --value) == '$RELEASE/frontend' ]] || { echo 'El frontend pertenece a otro despliegue; no se revierte.'; exit 1; }
cmp -s '$BACK_DROP' '$BACKUP/new-backend.conf' && cmp -s '$FRONT_DROP' '$BACKUP/new-frontend.conf' || { echo 'Los overrides cambiaron; revisar manualmente.'; exit 1; }
mv '$BACK_DROP' '$BACKUP/reverted-backend.conf'
mv '$FRONT_DROP' '$BACKUP/reverted-frontend.conf'
systemctl daemon-reload
systemctl restart $BACKEND
systemctl restart $FRONTEND
[[ \$(systemctl show $BACKEND -p WorkingDirectory --value) == '$OLD_BACK' && \$(systemctl show $FRONTEND -p WorkingDirectory --value) == '$OLD_FRONT' ]] || { echo 'No se recuperaron las rutas anteriores'; exit 1; }
for attempt in {1..30}; do
  if [[ \$(curl -s -o /dev/null -w '%{http_code}' --max-time 5 http://127.0.0.1:8184/health/ready) == 200 && \$(curl -s -o /dev/null -w '%{http_code}' --max-time 5 http://127.0.0.1:3101/login) == 200 ]]; then
    echo 'Versión anterior recuperada. Los datos permanecen en la base.'
    exit 0
  fi
  sleep 2
done
echo 'ATENCIÓN: disponibilidad no confirmada tras reversión.' >&2
exit 1
EOF
chmod 0700 "$BACKUP/rollback.sh"
echo 'Activando nueva versión. Comienza la interrupción breve.'
[[ $(unit_state) == "$UNIT_STATE" ]] || die 'La configuración de servicios cambió durante el build; no se publicará.'
[[ $(verify_database) == "$DB_STATE" ]] || die 'Cambió el esquema durante el build; revisar antes de publicar.'
SWITCHED=1
install -m 0644 "$BACKUP/new-backend.conf" "$BACK_DROP"
systemctl daemon-reload
[[ $(systemctl show "$BACKEND" -p WorkingDirectory --value) == "$RELEASE/backend" ]] || die 'Otro override tiene precedencia sobre el backend.'
systemctl restart "$BACKEND"
wait_http http://127.0.0.1:8184/health/ready 200
wait_http 'http://127.0.0.1:8184/staff/weekly-hours?department_id=1&start_date=2026-09-28&end_date=2026-10-04' 401
wait_http http://127.0.0.1:8184/staff/labor-contracts 401
wait_http 'http://127.0.0.1:8184/staff/campus-hours?campus=Valladolid&start_date=2026-09-28&end_date=2026-10-04' 401
install -m 0644 "$BACKUP/new-frontend.conf" "$FRONT_DROP"
systemctl daemon-reload
[[ $(systemctl show "$FRONTEND" -p WorkingDirectory --value) == "$RELEASE/frontend" ]] || die 'Otro override tiene precedencia sobre el frontend.'
systemctl restart "$FRONTEND"
wait_http http://127.0.0.1:3101/login 200
wait_http https://asistenciamodelo.online/login 200
wait_http https://asistenciamodelo.online/colaboradores 307
wait_http https://asistenciamodelo.online/api/colaboradores 401
wait_http https://asistenciamodelo.online/staff/contracts 307
wait_http https://asistenciamodelo.online/staff/campus-hours 307
wait_http https://asistenciamodelo.online/api/staff/campus-hours 401
wait_http https://asistenciamodelo.online/api/staff/labor-contracts 401
BACK_RESTARTS=$(systemctl show "$BACKEND" -p NRestarts --value)
FRONT_RESTARTS=$(systemctl show "$FRONTEND" -p NRestarts --value)
echo 'Monitoreando ambos servicios durante cinco minutos...'
for check in {1..30}; do
  systemctl is-active --quiet "$BACKEND"
  systemctl is-active --quiet "$FRONTEND"
  [[ $(systemctl show "$BACKEND" -p NRestarts --value) == "$BACK_RESTARTS" ]]
  [[ $(systemctl show "$FRONTEND" -p NRestarts --value) == "$FRONT_RESTARTS" ]]
  [[ $(http_code http://127.0.0.1:8184/health/ready) == 200 ]]
  [[ $(http_code http://127.0.0.1:3101/login) == 200 ]]
  sleep 10
done
journalctl -u "$BACKEND" -u "$FRONTEND" --since '-6 minutes' --no-pager > "$BACKUP/service-journal.log"
if grep -Ei 'Traceback \(most recent call last\)|Error:|ERROR|FATAL|out of memory| 500 ' "$BACKUP/service-journal.log" > "$BACKUP/errors-to-review.log"; then
  echo "ADVERTENCIA: hay mensajes de error para revisar en $BACKUP/errors-to-review.log; no se declara validación funcional completa."
fi
verify_database > "$BACKUP/database-after.json"
cmp -s "$BACKUP/database-before.json" "$BACKUP/database-after.json" || die 'Cambió el esquema durante la publicación; revisar.'
wait_http https://asistenciamodelo.online/login 200
wait_http https://asistenciamodelo.online/colaboradores 307
wait_http https://asistenciamodelo.online/api/colaboradores 401
FINISHED=1
echo "Publicado CRUD: commit $COMMIT en $RELEASE"
echo "Reversión manual: sudo bash $BACKUP/rollback.sh"
echo 'Validación autenticada pendiente: gaibarra@hotmail.com debe ver Gestionar colaboradores, buscar, consultar ficha y editar. Otra cuenta, incluso superadmin, debe recibir 403 de /employees/manage. No se crearán usuarios, sesiones ni colaboradores durante el despliegue.'
echo 'No se ejecutaron migraciones, importaciones, reparaciones ni cambios de Nginx.'
