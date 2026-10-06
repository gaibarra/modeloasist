#!/usr/bin/env bash
# Scoped deployment of the explicitly approved commit. No migrations or data jobs.
# Run with sudo bash ... --check, then sudo bash ... --deploy.
set -Eeuo pipefail
umask 077

MODE=${1:---check}
[[ $# -le 1 && "$MODE" =~ ^--(check|deploy)$ ]] || { echo 'Uso: sudo bash redeploy_7bd4080.sh [--check|--deploy]' >&2; exit 2; }
[[ $EUID -eq 0 ]] || { echo 'Ejecuta este script con sudo desde tu terminal.' >&2; exit 1; }
REPO=/home/gaibarra/modeloasist
ACCOUNT=asistenciamodelo
BACKEND=asistenciamodelo-backend.service
FRONTEND=asistenciamodelo-frontend.service
PYTHON=$REPO/backend/.venv/bin/python
BACK_ENV=/etc/asistenciamodelo/backend.env
FRONT_ENV=/etc/asistenciamodelo/frontend.env
BACK_DROP=/etc/systemd/system/$BACKEND.d/90-release-7bd4080.conf
FRONT_DROP=/etc/systemd/system/$FRONTEND.d/90-release-7bd4080.conf
RELEASE=''
BACKUP=''
SWITCHED=0
FINISHED=0
SMOKE_BACK=''
SMOKE_FRONT=''

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
    # These two files were absent before deployment. Preserve them for diagnosis.
    [[ ! -f "$BACK_DROP" ]] || mv "$BACK_DROP" "$BACKUP/failed-backend-override.conf"
    [[ ! -f "$FRONT_DROP" ]] || mv "$FRONT_DROP" "$BACKUP/failed-frontend-override.conf"
    systemctl daemon-reload
    systemctl restart "$BACKEND"
    systemctl restart "$FRONTEND"
    if wait_http http://127.0.0.1:8184/health/ready 200 && wait_http http://127.0.0.1:3101/login 200; then
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

for tool in git runuser systemctl systemd-run curl tar node npm flock ss awk df; do
  command -v "$tool" >/dev/null || die "Falta $tool"
done
id "$ACCOUNT" >/dev/null
[[ -x "$PYTHON" && -r "$BACK_ENV" && -r "$FRONT_ENV" ]] || die 'Falta Python o configuración de producción.'
COMMIT=$(git_repo rev-parse '7bd4080^{commit}')
[[ $(git_repo rev-parse HEAD) == "$COMMIT" ]] || die 'HEAD ya no es el commit autorizado 7bd4080.'
[[ -z $(git_repo diff --name-only HEAD) ]] || die 'Hay cambios versionados sin commit. Revísalos antes de continuar.'
[[ ! -e "$BACK_DROP" && ! -e "$FRONT_DROP" ]] || die 'Ya existe un override de esta publicación; no se sobrescribirá.'
for unit in "$BACKEND" "$FRONTEND"; do
  systemctl is-active --quiet "$unit" || die "$unit no está activo; diagnosticar antes de desplegar."
  [[ $(systemctl show "$unit" -p User --value) == "$ACCOUNT" ]] || die "Usuario inesperado en $unit"
done
[[ $(systemctl show "$BACKEND" -p WorkingDirectory --value) == "$REPO/backend" ]] || die 'La ruta backend cambió; revisar estrategia de reversión.'
[[ $(systemctl show "$FRONTEND" -p WorkingDirectory --value) == "$REPO/frontend" ]] || die 'La ruta frontend cambió; revisar estrategia de reversión.'
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
[[ "$EXEC" == *"$REPO/backend/.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8184 --workers 2 --timeout-keep-alive 10 --limit-concurrency 200 ;"* ]] || die 'ExecStart backend difiere del esperado.'
[[ $(systemctl show "$FRONTEND" -p ExecStart --value) == *'npm run start -- --hostname 127.0.0.1 --port 3101 ;'* ]] || die 'ExecStart frontend difiere del esperado.'
echo "Commit validado: $COMMIT; ambos servicios responden 200."
echo 'Se conservarán Python, Nginx, certificados, firewall, datos y servicios ajenos.'
if [[ "$MODE" == --check ]]; then
  echo 'Comprobación inicial correcta. --deploy comprobará esquema, dependencias, pruebas y build antes de cambiar servicios.'
  exit 0
fi

exec 9>/run/lock/asistenciamodelo-redeploy.lock
flock -n 9 || die 'Hay otro redeploy en ejecución.'
STAMP=$(date -u +%Y%m%dT%H%M%SZ)
RELEASE=/opt/asistenciamodelo/releases/$STAMP-7bd4080
BACKUP=/var/backups/asistenciamodelo/$STAMP-7bd4080
[[ ! -e "$RELEASE" && ! -e "$BACKUP" ]] || die 'Ya existe esta carpeta de despliegue.'
install -d -m 0755 /opt/asistenciamodelo /opt/asistenciamodelo/releases
install -d -m 0700 "$BACKUP"
install -d -m 0755 "$RELEASE"
# Source release is exactly the approved commit, not the working tree.
git_repo archive "$COMMIT" | tar -x --exclude='backend/runtime.db' -C "$RELEASE"
printf '%s\n' "$COMMIT" > "$BACKUP/commit.txt"
systemctl cat "$BACKEND" > "$BACKUP/backend-unit.txt"
systemctl cat "$FRONTEND" > "$BACKUP/frontend-unit.txt"
systemctl show "$BACKEND" "$FRONTEND" -p WorkingDirectory -p ExecStart -p FragmentPath -p DropInPaths > "$BACKUP/previous-routes.txt"
tar -czf "$BACKUP/previous-artifacts.tar.gz" --exclude='frontend/.next/cache' \
  -C "$REPO" frontend/.next frontend/package.json frontend/package-lock.json backend/app backend/alembic backend/alembic.ini backend/pyproject.toml
"$PYTHON" -m pip freeze > "$BACKUP/python-dependencies.txt"
chmod -R go-rwx "$BACKUP"
# The active paths, node_modules and virtualenv remain untouched for rollback.
chown -R "$ACCOUNT":www-data "$RELEASE"
chmod 0755 "$RELEASE"

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
runuser -u "$ACCOUNT" -- env DATABASE_URL=sqlite:// STARTUP_BOOTSTRAP_ENABLED=false bash -c 'cd "$1/backend"; "$2" -m pytest tests/test_weekly_hours.py tests/test_attendance_identity_resolution.py tests/test_semester_file_import.py tests/test_staff_attendance_import.py -q --tb=short' _ "$RELEASE" "$PYTHON" > "$BACKUP/tests.log" 2>&1 || die "Fallaron pruebas; consulta $BACKUP/tests.log"
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
wait_http 'http://127.0.0.1:18184/staff/weekly-hours?department_id=1&start_date=2026-09-28&end_date=2026-10-04' 401
systemd-run --quiet --unit="$SMOKE_FRONT" --property=User="$ACCOUNT" --property=Group=www-data \
  --property=WorkingDirectory="$RELEASE/frontend" --property=EnvironmentFile="$FRONT_ENV" \
  --property=MemoryMax=768M --property=CPUQuota=100% --property=RuntimeMaxSec=180 \
  /usr/bin/env NEXT_DIST_DIR=.next API_BASE_URL=http://127.0.0.1:18184 /usr/bin/npm run start -- --hostname 127.0.0.1 --port 13101
wait_http http://127.0.0.1:13101/login 200
wait_http 'http://127.0.0.1:13101/staff/hours?department_id=1&start_date=2026-09-28&end_date=2026-10-04' 307
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
[[ \$(systemctl show $BACKEND -p WorkingDirectory --value) == '$RELEASE/backend' ]] || { echo 'Existe otro despliegue; no se revierte automáticamente.'; exit 1; }
mv '$BACK_DROP' '$BACKUP/reverted-backend.conf'
mv '$FRONT_DROP' '$BACKUP/reverted-frontend.conf'
systemctl daemon-reload
systemctl restart $BACKEND
systemctl restart $FRONTEND
echo 'Reversión solicitada. Verifica /health/ready en 8184 y /login en 3101.'
EOF
chmod 0700 "$BACKUP/rollback.sh"
echo 'Activando nueva versión. Comienza la interrupción breve.'
SWITCHED=1
install -m 0644 "$BACKUP/new-backend.conf" "$BACK_DROP"
systemctl daemon-reload
systemctl restart "$BACKEND"
wait_http http://127.0.0.1:8184/health/ready 200
wait_http 'http://127.0.0.1:8184/staff/weekly-hours?department_id=1&start_date=2026-09-28&end_date=2026-10-04' 401
install -m 0644 "$BACKUP/new-frontend.conf" "$FRONT_DROP"
systemctl daemon-reload
systemctl restart "$FRONTEND"
wait_http http://127.0.0.1:3101/login 200
wait_http https://asistenciamodelo.online/login 200
echo 'Monitoreando ambos servicios durante cinco minutos...'
for check in {1..30}; do
  systemctl is-active --quiet "$BACKEND"
  systemctl is-active --quiet "$FRONTEND"
  [[ $(http_code http://127.0.0.1:8184/health/ready) == 200 ]]
  [[ $(http_code http://127.0.0.1:3101/login) == 200 ]]
  sleep 10
done
journalctl -u "$BACKEND" -u "$FRONTEND" --since '-6 minutes' --no-pager > "$BACKUP/service-journal.log"
FINISHED=1
echo "Publicado $COMMIT en $RELEASE"
echo "Reversión manual: sudo bash $BACKUP/rollback.sh"
echo 'Pendiente validación humana: inicia sesión staff, abre Reporte de horas semanal e imprime una semana.'
echo 'No se ejecutaron migraciones, importaciones, reparaciones ni cambios de Nginx.'
