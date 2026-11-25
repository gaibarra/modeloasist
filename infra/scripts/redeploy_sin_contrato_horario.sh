#!/usr/bin/env bash
# Backend-only release: approved two-condition report exclusion.
set -Eeuo pipefail
umask 077
MODE=${1:---check}
[[ $# -le 1 && "$MODE" =~ ^--(check|deploy)$ ]] || { echo 'Uso: sudo bash redeploy_sin_contrato_horario.sh [--check|--deploy]' >&2; exit 2; }
[[ $EUID -eq 0 ]] || { echo 'Ejecuta con sudo desde tu terminal.' >&2; exit 1; }
REPO=/home/gaibarra/modeloasist
BASE=/opt/asistenciamodelo/releases/20261124T162120Z-exclusion-perfiles
FRONT_BASE=/opt/asistenciamodelo/releases/20261124T152349Z-horas-inhabiles
UNIT=asistenciamodelo-backend.service
FRONT=asistenciamodelo-frontend.service
ACCOUNT=asistenciamodelo
PYTHON=$REPO/backend/.venv/bin/python
ENV_FILE=/etc/asistenciamodelo/backend.env
DROP=/etc/systemd/system/$UNIT.d/zzzzzzzzzzzzzzzzz-sin-contrato-horario.conf
RELEASE='' BACKUP='' SMOKE='' SWITCHED=0 FINISHED=0
fail() { echo "ERROR: $*" >&2; exit 1; }
unit_state() { systemctl cat "$UNIT" "$FRONT" | sha256sum | awk '{print $1}'; }
code() { curl -s -o /dev/null -w '%{http_code}' --max-time 5 "$1"; }
wait_http() {
  local attempt status
  for attempt in {1..30}; do
    status=$(code "$1") || status=000
    [[ "$status" == "$2" ]] && return 0
    sleep 2
  done
  echo "Respuesta inesperada: $1 ($status; esperado $2)" >&2
  return 1
}
manifest() {
  cat <<'HASHES'
89e04f0a47d8ffb4cdb4e4a7a1561662c7ae1a34b0c214c469745e9b808e74b0  backend/app/services/report_eligibility.py
965a17fbf407e82d020c3b21beab0f7e61d9ad9e396615ea73384d8a2b83a67d  backend/tests/test_report_eligibility.py
7a99b723be78b59df6392df94fc13fec9c4d1883859a9a46e39622ea67889af5  backend/tests/test_campus_hours.py
717d0b62bf9b9913104fec72d8c5303908114ab9ef411beaec3b1f71c34def57  backend/tests/test_labor_contracts.py
b2e1a0d5d1d446e87292f319d46d6737ee6e204b31265267d36e35f8d79741cd  backend/tests/test_weekly_hours.py
HASHES
}
base_manifest() {
  cat <<'HASHES'
e96cde06ea275003df0896cf57727d0d96d88ed573907467283a078fbdb10928  backend/app/services/report_eligibility.py
07c9ffde1698d62ea4762f0181db19615b0b72f4324af5ccf1b8a1580e7ad764  backend/tests/test_report_eligibility.py
fb94a0cf66d64229678373557d3d5cb77adb3bbd712eea4bae7252f06159d6ac  backend/tests/test_campus_hours.py
eb96e5af84e787b121749f83d32908d06e6df65e931cf954a8fd7eb8fc306651  backend/tests/test_labor_contracts.py
48a73a3b71b562ff9e0a65f8b159e18b7e7a0e6c68e797e45b53fabe79ba7251  backend/tests/test_weekly_hours.py
HASHES
}
verify_db() (
  set -a; source "$ENV_FILE"; set +a
  cd "$1/backend"
  runuser -u "$ACCOUNT" -- env PYTHONDONTWRITEBYTECODE=1 STARTUP_BOOTSTRAP_ENABLED=false "$PYTHON" - <<'PY'
from sqlalchemy import create_engine, text, inspect
from app.core.config import get_settings
engine=create_engine(get_settings().database_url)
assert engine.dialect.name == 'postgresql', 'Se requiere PostgreSQL de producción'
with engine.connect() as c:
    c.execute(text('SET TRANSACTION READ ONLY'))
    assert c.execute(text('select version_num from alembic_version')).scalars().all()==['20261015_0016'], 'Esquema inesperado: no migrar'
    schema=inspect(c)
    for table in ['employees','labor_contracts','campus_labor_contracts','schedules','staff_semester_schedules','employee_departments']:
        assert schema.has_table(table), table
print('20261015_0016 compatible; lectura solamente')
PY
)
cleanup() {
  local result=$?
  trap - EXIT INT TERM
  set +e
  [[ -z "$SMOKE" ]] || systemctl stop "$SMOKE" >/dev/null 2>&1
  if [[ $SWITCHED == 1 && $FINISHED == 0 ]]; then
    if [[ -f "$DROP" ]] && cmp -s "$DROP" "$BACKUP/new-backend.conf"; then
      mv "$DROP" "$BACKUP/failed-backend.conf"
      systemctl daemon-reload
      systemctl restart "$UNIT"
      if [[ $(systemctl show "$UNIT" -p WorkingDirectory --value) == "$BASE/backend" ]] && wait_http http://127.0.0.1:8184/health/ready 200; then
        echo 'Backend anterior recuperado; frontend y datos sin cambios.' >&2
      else
        echo 'ATENCIÓN: recuperación no confirmada; revisar el servicio.' >&2
      fi
    else
      echo 'ATENCIÓN: el ajuste cambió externamente; no se sobrescribirá. Revisar manualmente.' >&2
    fi
    result=1
  fi
  [[ -z "$BACKUP" ]] || echo "Respaldo y registros: $BACKUP"
  exit "$result"
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM
for cmd in systemctl systemd-run runuser curl tar sha256sum awk df flock timeout cmp; do command -v "$cmd" >/dev/null || fail "Falta $cmd"; done
[[ -r "$ENV_FILE" && -x "$PYTHON" ]] || fail 'Falta configuración o Python de producción.'
[[ ! -e "$DROP" ]] || fail 'Ya existe el ajuste de esta publicación; no se sobrescribirá.'
for service in "$UNIT" "$FRONT"; do systemctl is-active --quiet "$service" || fail "$service no está activo"; done
[[ $(systemctl show "$UNIT" -p User --value) == "$ACCOUNT" ]] || fail 'Usuario inesperado'
[[ $(systemctl show "$UNIT" -p WorkingDirectory --value) == "$BASE/backend" && $(systemctl show "$FRONT" -p WorkingDirectory --value) == "$FRONT_BASE/frontend" ]] || fail 'Cambió la versión activa; revisar la base.'
[[ $(systemctl show "$UNIT" -p ExecStart --value) == *"$PYTHON -m uvicorn app.main:app --host 127.0.0.1 --port 8184 --workers 2 --timeout-keep-alive 10 --limit-concurrency 200 ;"* ]] || fail 'Comando del backend inesperado'
(cd "$REPO"; manifest | sha256sum --check --status) || fail 'Cambió el código aprobado'
(cd "$BASE"; base_manifest | sha256sum --check --status) || fail 'Cambió la base activa'
[[ $(code http://127.0.0.1:8184/health/ready) == 200 && $(code http://127.0.0.1:3101/login) == 200 ]] || fail 'Servicios no disponibles'
for directory in /opt /var/backups; do
  [[ $(df -Pk "$directory" | awk 'NR==2 {print $4}') -ge 2097152 ]] || fail "Se requieren 2 GiB libres en $directory"
done
[[ $(awk '/MemAvailable:/ {print $2}' /proc/meminfo) -ge 1048576 ]] || fail 'Se requiere 1 GiB de memoria disponible'
STATE=$(unit_state)
verify_db "$BASE"
if [[ "$MODE" == --check ]]; then
  echo 'Comprobación correcta. --deploy publicará únicamente el backend, sin migraciones.'
  exit 0
fi
exec 9>/run/lock/asistenciamodelo-redeploy.lock
flock -n 9 || fail 'Hay otro despliegue en ejecución'
STAMP=$(date -u +%Y%m%dT%H%M%SZ)
RELEASE=/opt/asistenciamodelo/releases/$STAMP-sin-contrato-horario
BACKUP=/var/backups/asistenciamodelo/$STAMP-sin-contrato-horario
[[ ! -e "$RELEASE" && ! -e "$BACKUP" ]] || fail 'Ya existe el directorio de publicación'
install -d -m 0755 "$RELEASE/backend"
install -d -m 0700 "$BACKUP"
systemctl cat "$UNIT" > "$BACKUP/backend-unit.txt"
systemctl cat "$FRONT" > "$BACKUP/frontend-unit.txt"
systemctl show "$UNIT" "$FRONT" -p WorkingDirectory -p ExecStart -p FragmentPath -p DropInPaths > "$BACKUP/previous-routes.txt"
tar -czf "$BACKUP/backend-units.tar.gz" -C /etc/systemd/system "$UNIT" "$UNIT.d"
tar -czf "$BACKUP/previous-backend.tar.gz" --exclude='__pycache__' --exclude='.pytest_cache' -C "$BASE" backend
manifest > "$BACKUP/overlay.sha256"
printf '%s\n' "$BASE" > "$BACKUP/base-release.txt"
tar -C "$BASE/backend" --exclude='__pycache__' --exclude='.pytest_cache' --exclude='.venv' --exclude='.env*' --exclude='*.db' --exclude='*.xlsx' --exclude='*.pdf' --exclude='reportes' -cf - . | tar -C "$RELEASE/backend" -xf -
while read -r hash file; do install -D -m 0644 "$REPO/$file" "$RELEASE/$file"; done < "$BACKUP/overlay.sha256"
(cd "$RELEASE"; manifest | sha256sum --check --status) || fail 'Copia diferente del manifiesto'
cmp -s "$RELEASE/backend/pyproject.toml" "$BASE/backend/pyproject.toml" || fail 'Cambio de dependencias no autorizado'
chown -R "$ACCOUNT":www-data "$RELEASE"
verify_db "$RELEASE" > "$BACKUP/schema-check.log" 2>&1
systemd-run --scope --quiet --property=CPUQuota=100% --property=MemoryMax=768M runuser -u "$ACCOUNT" -- env DATABASE_URL=sqlite:// STARTUP_BOOTSTRAP_ENABLED=false bash -c 'cd "$1/backend"; timeout 180 "$2" -m pytest tests/test_report_eligibility.py tests/test_weekly_hours.py tests/test_campus_hours.py tests/test_attendance_identity_resolution.py tests/test_labor_contracts.py -q --tb=short' _ "$RELEASE" "$PYTHON" > "$BACKUP/tests.log" 2>&1 || fail "Fallaron pruebas: $BACKUP/tests.log"
"$PYTHON" - <<'PY'
import socket
with socket.socket() as s: s.bind(('127.0.0.1',18184))
PY
SMOKE=asistenciamodelo-smoke-exclusion-$STAMP.service
systemd-run --quiet --unit="$SMOKE" --property=User="$ACCOUNT" --property=Group=www-data --property=WorkingDirectory="$RELEASE/backend" --property=EnvironmentFile="$ENV_FILE" --property=MemoryMax=768M --property=CPUQuota=100% --property=RuntimeMaxSec=180 /usr/bin/env STARTUP_BOOTSTRAP_ENABLED=false "$PYTHON" -m uvicorn app.main:app --host 127.0.0.1 --port 18184
wait_http http://127.0.0.1:18184/health/ready 200
wait_http 'http://127.0.0.1:18184/staff/weekly-hours?department_id=3&start_date=2026-11-16&end_date=2026-11-22' 401
wait_http 'http://127.0.0.1:18184/staff/campus-hours?campus=Montejo&start_date=2026-11-16&end_date=2026-11-22' 401
wait_http http://127.0.0.1:18184/employees/manage 401
systemctl stop "$SMOKE"; SMOKE=''
cat > "$BACKUP/new-backend.conf" <<EOF
[Service]
WorkingDirectory=$RELEASE/backend
ExecStart=
ExecStart=/usr/bin/env STARTUP_BOOTSTRAP_ENABLED=false $PYTHON -m uvicorn app.main:app --host 127.0.0.1 --port 8184 --workers 2 --timeout-keep-alive 10 --limit-concurrency 200
ReadWritePaths=$RELEASE/backend
EOF
cat > "$BACKUP/rollback.sh" <<EOF
#!/usr/bin/env bash
set -euo pipefail
[[ \$EUID -eq 0 ]] || { echo 'Ejecuta con sudo'; exit 1; }
exec 9>/run/lock/asistenciamodelo-redeploy.lock
flock -n 9 || { echo 'Hay otro despliegue'; exit 1; }
[[ \$(systemctl show '$UNIT' -p WorkingDirectory --value) == '$RELEASE/backend' ]] || { echo 'Existe otro despliegue; no se revierte'; exit 1; }
cmp -s '$DROP' '$BACKUP/new-backend.conf' || { echo 'Ajuste modificado; revisar'; exit 1; }
mv '$DROP' '$BACKUP/reverted-backend.conf'
systemctl daemon-reload
systemctl restart '$UNIT'
[[ \$(systemctl show '$UNIT' -p WorkingDirectory --value) == '$BASE/backend' ]] || { echo 'Ruta no recuperada'; exit 1; }
for attempt in {1..30}; do
  if [[ \$(curl -s -o /dev/null -w '%{http_code}' --max-time 5 http://127.0.0.1:8184/health/ready) == 200 ]]; then echo 'Backend anterior recuperado'; exit 0; fi
  sleep 2
done
echo 'Recuperación no confirmada'; exit 1
EOF
chmod 0700 "$BACKUP/rollback.sh"
[[ $(unit_state) == "$STATE" ]] || fail 'Unidades modificadas durante las pruebas'
verify_db "$RELEASE" > "$BACKUP/schema-before-switch.log"
SWITCHED=1
install -m 0644 "$BACKUP/new-backend.conf" "$DROP"
systemctl daemon-reload
[[ $(systemctl show "$UNIT" -p WorkingDirectory --value) == "$RELEASE/backend" ]] || fail 'Otro ajuste tiene precedencia'
systemctl restart "$UNIT"
wait_http http://127.0.0.1:8184/health/ready 200
wait_http http://127.0.0.1:3101/login 200
wait_http https://asistenciamodelo.online/login 200
wait_http https://asistenciamodelo.online/api/staff/campus-hours 401
wait_http https://asistenciamodelo.online/api/colaboradores 401
RESTARTS=$(systemctl show "$UNIT" -p NRestarts --value)
echo 'Monitoreando cinco minutos; solo se ha reiniciado el backend.'
for attempt in {1..30}; do
  systemctl is-active --quiet "$UNIT"
  [[ $(systemctl show "$UNIT" -p NRestarts --value) == "$RESTARTS" ]]
  [[ $(code http://127.0.0.1:8184/health/ready) == 200 ]]
  [[ $(code http://127.0.0.1:3101/login) == 200 ]]
  sleep 10
done
systemctl cat "$FRONT" > "$BACKUP/frontend-after.txt"
cmp -s "$BACKUP/frontend-unit.txt" "$BACKUP/frontend-after.txt" || fail 'La configuración frontend cambió externamente; revisar'
journalctl -u "$UNIT" --since '-6 minutes' --no-pager > "$BACKUP/service-journal.log"
if grep -Ei 'Traceback|ERROR|FATAL|out of memory| 500 ' "$BACKUP/service-journal.log" > "$BACKUP/errors-to-review.log"; then echo "Revisar mensajes: $BACKUP/errors-to-review.log"; fi
FINISHED=1
echo "Publicado: $RELEASE"
echo "Reversión: sudo bash $BACKUP/rollback.sh"
echo 'Sin migraciones, importaciones ni cambios en frontend, Nginx u otras aplicaciones.'
echo 'Validación visual pendiente con sesión autorizada: AGUILAR VALLES LORIE ELLEN no aparece en reportes, pero sí en Gestionar colaboradores. ALONSO CANTO GABRIELA ABYGAIL también queda excluida. El correo no afecta esta regla; un contrato activo o un horario registrado permite aparecer, salvo baja formal.'
