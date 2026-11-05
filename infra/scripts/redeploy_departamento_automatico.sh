#!/usr/bin/env bash
# Frontend-only release. No database access, migrations, or backend restarts.
set -Eeuo pipefail
umask 077
MODE=${1:---check}
[[ $# -le 1 && "$MODE" =~ ^--(check|deploy)$ ]] || { echo 'Uso: sudo bash redeploy_departamento_automatico.sh [--check|--deploy]' >&2; exit 2; }
[[ $EUID -eq 0 ]] || { echo 'Ejecuta con sudo desde tu terminal.' >&2; exit 1; }
REPO=/home/gaibarra/modeloasist
UNIT=asistenciamodelo-frontend.service
ACCOUNT=asistenciamodelo
OLD=/opt/asistenciamodelo/releases/20261026T142227Z-vacaciones/frontend
ENV_FILE=/etc/asistenciamodelo/frontend.env
DROP=/etc/systemd/system/$UNIT.d/zzzzzzzzzzzzz-department-auto.conf
RELEASE=''
BACKUP=''
SMOKE=''
SWITCHED=0
FINISHED=0
die() { echo "ERROR: $*" >&2; exit 1; }
unit_state() { systemctl cat "$UNIT" | sha256sum | awk '{print $1}'; }
http_code() { curl -s -o /dev/null -w '%{http_code}' --max-time 5 "$1"; }
wait_http() {
  local code attempt
  for attempt in {1..30}; do
    code=$(http_code "$1") || code=000
    [[ "$code" == "$2" ]] && return 0
    sleep 2
  done
  echo "No respondió $2: $1 (respuesta $code)" >&2
  return 1
}
manifest() {
  cat <<'SOURCE_HASHES'
3c5f1696519572eb2a613ea739aeade922eda5a67013070d12f6bb487a3e2fb8  frontend/src/app/staff/page.tsx
b7c7764eda6b962cc12c80237a2e3701f515fad4957debedddda97d5ae2d9552  frontend/src/components/auto-submit-select.tsx
08709ca9ae2c21470c0b004a3db4ba681eb8fac352263bf2b64ba22bb8d902ba  frontend/tests/auto-submit-select.test.cjs
SOURCE_HASHES
}
cleanup() {
  local result=$?
  trap - EXIT INT TERM
  set +e
  [[ -z "$SMOKE" ]] || systemctl stop "$SMOKE" >/dev/null 2>&1
  if [[ $SWITCHED == 1 && $FINISHED == 0 ]]; then
    if [[ -f "$DROP" ]] && ! cmp -s "$DROP" "$BACKUP/new-frontend.conf"; then
      echo 'El override cambió externamente; no se retirará ni se reiniciará el servicio.' >&2
      exit 1
    fi
    [[ ! -f "$DROP" ]] || mv "$DROP" "$BACKUP/failed-frontend.conf"
    systemctl daemon-reload
    systemctl restart "$UNIT"
    if [[ $(systemctl show "$UNIT" -p WorkingDirectory --value) == "$OLD" ]] && wait_http http://127.0.0.1:3101/login 200; then
      echo 'Frontend anterior recuperado; backend y datos intactos.' >&2
    else
      echo "ATENCIÓN: recuperación no confirmada. Revisa $BACKUP." >&2
    fi
    result=1
  fi
  [[ -z "$BACKUP" ]] || echo "Respaldo y registros: $BACKUP"
  exit "$result"
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM
for tool in systemctl systemd-run runuser curl tar sha256sum cmp flock awk df node npm timeout; do
  command -v "$tool" >/dev/null || die "Falta $tool"
done
if [[ "$MODE" == --deploy ]]; then
  exec 9>/run/lock/asistenciamodelo-redeploy.lock
  flock -n 9 || die 'Hay otro despliegue en curso.'
fi
[[ ! -e "$DROP" ]] || die 'Ya existe el override de esta publicación; no se sobrescribirá.'
[[ -r "$ENV_FILE" && -s "$OLD/.next/BUILD_ID" ]] || die 'Falta configuración o build activo.'
systemctl is-active --quiet "$UNIT" || die 'Frontend inactivo; revisar antes de desplegar.'
[[ $(systemctl show "$UNIT" -p WorkingDirectory --value) == "$OLD" ]] || die 'La versión activa cambió.'
[[ $(systemctl show "$UNIT" -p User --value) == "$ACCOUNT" && $(systemctl show "$UNIT" -p Group --value) == www-data ]] || die 'Usuario o grupo inesperado.'
[[ $(systemctl show "$UNIT" -p ExecStart --value) == *'/usr/bin/env NEXT_DIST_DIR=.next /usr/bin/npm run start -- --hostname 127.0.0.1 --port 3101 ;'* ]] || die 'Comando de arranque inesperado.'
(cd "$REPO"; manifest | sha256sum --check --status) || die 'Los archivos autorizados cambiaron; revisar manifiesto.'
[[ $(http_code http://127.0.0.1:3101/login) == 200 ]] || die 'Frontend no responde 200.'
[[ $(http_code http://127.0.0.1:8184/health/ready) == 200 ]] || die 'Backend no está listo; no se reiniciará.'
[[ $(awk '/^MemAvailable:/ {print $2}' /proc/meminfo) -ge 2097152 ]] || die 'Se requieren 2 GiB de memoria disponible.'
for directory in /opt /var/backups; do
  [[ $(df -Pk "$directory" | awk 'NR==2 {print $4}') -ge 6291456 ]] || die "Se requieren 6 GiB libres en $directory."
done
STATE=$(unit_state)
echo "Base verificada: $OLD. Tres archivos autorizados; frontend y backend responden 200."
if [[ "$MODE" == --check ]]; then
  echo 'Comprobación inicial correcta. --deploy hará pruebas y build aislados antes de activar.'
  exit 0
fi
STAMP=$(date -u +%Y%m%dT%H%M%SZ)
RELEASE=/opt/asistenciamodelo/releases/$STAMP-department-auto
BACKUP=/var/backups/asistenciamodelo/$STAMP-department-auto
[[ ! -e "$RELEASE" && ! -e "$BACKUP" ]] || die 'Ya existe la ruta de esta publicación.'
install -d -m 0700 "$BACKUP"
install -d -m 0755 "$RELEASE/frontend"
systemctl cat "$UNIT" > "$BACKUP/frontend-unit.txt"
systemctl show "$UNIT" -p WorkingDirectory -p ExecStart -p FragmentPath -p DropInPaths > "$BACKUP/previous-routes.txt"
tar -czf "$BACKUP/frontend-units.tar.gz" -C /etc/systemd/system "$UNIT" "$UNIT.d"
tar -czf "$BACKUP/active-frontend.tar.gz" --exclude='./.next/cache' -C "$OLD" .
manifest > "$BACKUP/source.sha256"
# Never copy unrelated working-tree changes or mutate the active build.
tar -C "$OLD" --exclude='./.next' --exclude='./node_modules' --exclude='.env*' --exclude='.npm-cache' -cf - . | tar -xf - -C "$RELEASE/frontend"
while read -r hash path; do
  install -D -m 0644 "$REPO/$path" "$RELEASE/$path"
done < "$BACKUP/source.sha256"
(cd "$RELEASE"; sha256sum --check --status "$BACKUP/source.sha256") || die 'La copia no coincide con los hashes.'
cmp -s "$RELEASE/frontend/package-lock.json" "$OLD/package-lock.json" || die 'Cambió el lockfile.'
chown -R "$ACCOUNT":www-data "$RELEASE"
echo 'Ejecutando pruebas, TypeScript, lint y compilación aislada...'
(
  set -a
  source "$ENV_FILE"
  set +a
  export NEXT_DIST_DIR=.next NEXT_TELEMETRY_DISABLED=1
  export npm_config_cache="$RELEASE/.npm-cache" NODE_OPTIONS=--max-old-space-size=1024
  systemd-run --scope --quiet --property=MemoryMax=1536M --property=CPUQuota=100% runuser -u "$ACCOUNT" -- timeout 1800 bash -c '
    set -e
    cd "$1/frontend"
    npm ci --include=dev
    node --test tests/auto-submit-select.test.cjs tests/collaborator-origin.test.cjs
    npx --no-install tsc --noEmit --incremental false
    npm run lint
    npm run build -- --webpack
  ' _ "$RELEASE"
) > "$BACKUP/build.log" 2>&1 || die "Fallaron pruebas o build; consulta $BACKUP/build.log"
[[ -s "$RELEASE/frontend/.next/BUILD_ID" ]] || die 'No existe build válido.'
# Check a private temporary port without opening firewall rules.
node -e 'const s=require("net").createServer();s.on("error",()=>process.exit(1));s.listen(13101,"127.0.0.1",()=>s.close())' || die 'Puerto temporal 13101 ocupado.'
SMOKE=asistenciamodelo-smoke-front-$STAMP.service
systemd-run --quiet --unit="$SMOKE" --property=User="$ACCOUNT" --property=Group=www-data \
  --property=WorkingDirectory="$RELEASE/frontend" --property=EnvironmentFile="$ENV_FILE" \
  --property=MemoryMax=768M --property=CPUQuota=100% --property=RuntimeMaxSec=180 \
  /usr/bin/env NEXT_DIST_DIR=.next /usr/bin/npm run start -- --hostname 127.0.0.1 --port 13101
wait_http http://127.0.0.1:13101/login 200
wait_http 'http://127.0.0.1:13101/staff?view=period&department_id=3' 307
wait_http http://127.0.0.1:13101/api/staff/campus-hours 401
systemctl stop "$SMOKE"
SMOKE=''
cat > "$BACKUP/new-frontend.conf" <<EOF
[Service]
WorkingDirectory=$RELEASE/frontend
ExecStart=
ExecStart=/usr/bin/env NEXT_DIST_DIR=.next /usr/bin/npm run start -- --hostname 127.0.0.1 --port 3101
ReadWritePaths=$RELEASE/frontend/.next
EOF
cat > "$BACKUP/rollback.sh" <<EOF
#!/usr/bin/env bash
set -euo pipefail
[[ \$EUID -eq 0 ]] || { echo 'Ejecuta con sudo'; exit 1; }
exec 9>/run/lock/asistenciamodelo-redeploy.lock
flock -n 9 || { echo 'Hay un despliegue en curso'; exit 1; }
[[ \$(systemctl show '$UNIT' -p WorkingDirectory --value) == '$RELEASE/frontend' ]] || { echo 'Existe otra versión activa; no se revierte.'; exit 1; }
cmp -s '$DROP' '$BACKUP/new-frontend.conf' || { echo 'El override cambió; revisar manualmente.'; exit 1; }
mv '$DROP' '$BACKUP/reverted-frontend.conf'
systemctl daemon-reload
systemctl restart '$UNIT'
[[ \$(systemctl show '$UNIT' -p WorkingDirectory --value) == '$OLD' ]] || { echo 'No se recuperó la ruta anterior'; exit 1; }
for attempt in {1..30}; do
  if [[ \$(curl -s -o /dev/null -w '%{http_code}' --max-time 5 http://127.0.0.1:3101/login) == 200 ]]; then
    echo 'Frontend anterior recuperado. Backend y datos intactos.'
    exit 0
  fi
  sleep 2
done
echo 'Recuperación no confirmada; revisar servicio.' >&2
exit 1
EOF
chmod 0700 "$BACKUP/rollback.sh"
[[ $(unit_state) == "$STATE" && $(systemctl show "$UNIT" -p WorkingDirectory --value) == "$OLD" && ! -e "$DROP" ]] || die 'Cambió la configuración durante el build.'
echo 'Activando únicamente el frontend; comienza la interrupción breve.'
SWITCHED=1
install -m 0644 "$BACKUP/new-frontend.conf" "$DROP"
systemctl daemon-reload
[[ $(systemctl show "$UNIT" -p WorkingDirectory --value) == "$RELEASE/frontend" ]] || die 'Otro override tiene precedencia.'
systemctl restart "$UNIT"
wait_http http://127.0.0.1:3101/login 200
wait_http https://asistenciamodelo.online/login 200
wait_http https://asistenciamodelo.online/staff 307
RESTARTS=$(systemctl show "$UNIT" -p NRestarts --value)
echo 'Monitoreando durante cinco minutos...'
for check in {1..30}; do
  systemctl is-active --quiet "$UNIT"
  [[ $(systemctl show "$UNIT" -p NRestarts --value) == "$RESTARTS" ]]
  [[ $(http_code http://127.0.0.1:3101/login) == 200 ]]
  [[ $(http_code http://127.0.0.1:8184/health/ready) == 200 ]]
  sleep 10
done
journalctl -u "$UNIT" --since '-6 minutes' --no-pager > "$BACKUP/frontend-journal.log"
if grep -Ei 'Error:|ERROR|FATAL|out of memory| 500 ' "$BACKUP/frontend-journal.log" > "$BACKUP/errors-to-review.log"; then
  echo "ADVERTENCIA: revisar errores en $BACKUP/errors-to-review.log; validación funcional pendiente."
fi
wait_http https://asistenciamodelo.online/login 200
FINISHED=1
echo "Frontend publicado: $RELEASE/frontend"
echo "Reversión manual: sudo bash $BACKUP/rollback.sh"
echo 'Pendiente con sesión staff: cambio automático de departamento, fechas/filtros conservados, Consultar e impresión. No se fabricaron sesiones.'
echo 'No se reinició backend ni se modificaron datos, migraciones, Nginx u otras aplicaciones.'
