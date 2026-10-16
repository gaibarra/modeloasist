#!/usr/bin/env bash
# Isolated frontend-only hotfix over the verified active 9922732 release.
set -Eeuo pipefail
umask 077
MODE=${1:---check}
[[ $# -le 1 && "$MODE" =~ ^--(check|deploy)$ ]] || { echo 'Uso: sudo bash redeploy_email_origin_fix.sh [--check|--deploy]'; exit 2; }
[[ $EUID == 0 ]] || { echo 'Ejecuta con sudo'; exit 1; }
REPO=/home/gaibarra/modeloasist
UNIT=asistenciamodelo-frontend.service
OLD=/opt/asistenciamodelo/releases/20261009T154329Z-9922732/frontend
DROP=/etc/systemd/system/$UNIT.d/zzzzzzz-email-origin-fix.conf
ENVFILE=/etc/asistenciamodelo/frontend.env
die() { echo "ERROR: $*" >&2; exit 1; }
code() { curl -s -o /dev/null -w '%{http_code}' --max-time 10 "$@"; }
wait_http() { local i; for i in {1..30}; do [[ $(code "$1") == "$2" ]] && return 0; sleep 2; done; return 1; }
[[ $(systemctl show "$UNIT" -p WorkingDirectory --value) == "$OLD" ]] || die 'Cambió la versión activa; revisar.'
[[ $(systemctl show "$UNIT" -p User --value) == asistenciamodelo ]] || die 'Usuario inesperado.'
[[ -r "$ENVFILE" && -s "$OLD/.next/BUILD_ID" && ! -e "$DROP" ]] || die 'Falta configuración/build o existe el ajuste de este despliegue.'
[[ $(code http://127.0.0.1:3101/login) == 200 ]] || die 'Frontend no disponible.'
[[ $(awk '/MemAvailable:/ {print $2}' /proc/meminfo) -ge 2097152 ]] || die 'Se requieren 2 GiB de RAM libre.'
for dir in /opt /var/backups; do [[ $(df -Pk "$dir" | awk 'NR==2 {print $4}') -ge 6291456 ]] || die 'Se requieren 6 GiB libres.'; done
cd "$REPO"
sha256sum --check --status <<'HASHES' || die 'Cambió el arreglo revisado; no se desplegará.'
68dea2b4181fc2efaf2598a9b49d4f611a98532e0eb2014b6998771a6c05d01b  frontend/src/lib/collaborator-origin.ts
a5a90839ae83c073259d6c137120afee9c50e270b981d9a0ab63cf9424e0d9e9  frontend/src/app/api/colaboradores/[[...path]]/route.ts
3bbe7059882f7050d9a52a98585973e63f63f20991ee33163a3c5e498b494689  frontend/tests/collaborator-origin.test.cjs
HASHES
[[ "$MODE" == --deploy ]] || { echo 'CHECK correcto: base 9922732 + arreglo verificado; solo frontend. Sin cambios.'; exit 0; }
exec 9>/run/lock/asistenciamodelo-redeploy.lock
flock -n 9 || die 'Otro despliegue está en curso.'
STATE=$(systemctl cat "$UNIT" | sha256sum)
STAMP=$(date -u +%Y%m%dT%H%M%SZ)
RELEASE=/opt/asistenciamodelo/releases/$STAMP-email-origin-fix
BACKUP=/var/backups/asistenciamodelo/$STAMP-email-origin-fix
SMOKE=asistenciamodelo-email-smoke-$STAMP.service
SWITCHED=0
DONE=0
cleanup() {
  local result=$?
  trap - EXIT
  set +e
  systemctl stop "$SMOKE" >/dev/null 2>&1
  if [[ $SWITCHED == 1 && $DONE == 0 ]]; then
    if cmp -s "$DROP" "$BACKUP/new-frontend.conf"; then
      mv "$DROP" "$BACKUP/failed-frontend.conf"
      systemctl daemon-reload
      systemctl restart "$UNIT"
      wait_http http://127.0.0.1:3101/login 200 || echo 'ATENCIÓN: verificar recuperación manualmente.'
    else
      echo 'Override modificado externamente; no se sobrescribe. Revisar manualmente.'
    fi
  fi
  echo "Respaldo y logs: $BACKUP"
  exit "$result"
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM
[[ ! -e "$RELEASE" && ! -e "$BACKUP" ]] || die 'La carpeta ya existe.'
install -d -m 0700 "$BACKUP"
install -d -m 0755 "$RELEASE" "$RELEASE/frontend"
systemctl cat "$UNIT" > "$BACKUP/previous-unit.txt"
tar -czf "$BACKUP/previous-unit-files.tgz" -C /etc/systemd/system "$UNIT" "$UNIT.d"
tar -czf "$BACKUP/previous-frontend.tgz" --exclude='./.next/cache' -C "$OLD" .
tar -C "$OLD" --exclude='./.next' --exclude='./node_modules' --exclude='./.next-dev' -cf - . | tar -C "$RELEASE/frontend" -xf -
for file in src/lib/collaborator-origin.ts 'src/app/api/colaboradores/[[...path]]/route.ts' tests/collaborator-origin.test.cjs; do
  install -D -m 0644 "$REPO/frontend/$file" "$RELEASE/frontend/$file"
done
chown -R asistenciamodelo:www-data "$RELEASE"
(
  set -a; source "$ENVFILE"; set +a
  systemd-run --scope --quiet -p MemoryMax=1536M -p CPUQuota=100% runuser -u asistenciamodelo -- env NEXT_DIST_DIR=.next NEXT_TELEMETRY_DISABLED=1 NODE_OPTIONS=--max-old-space-size=1024 npm_config_cache="$RELEASE/.npm-cache" bash -c '
    set -e
    cd "$1/frontend"
    npm ci --include=dev
    node --test tests/collaborator-origin.test.cjs
    npm run lint
    npx --no-install tsc --noEmit --incremental false
    npm run build -- --webpack
  ' _ "$RELEASE"
) > "$BACKUP/build.log" 2>&1 || die "Build/pruebas fallaron: $BACKUP/build.log"
[[ -s "$RELEASE/frontend/.next/BUILD_ID" ]] || die 'No existe build.'
python3 - <<'PY'
import socket
with socket.socket() as sock:
    sock.bind(('127.0.0.1', 13102))
PY
systemd-run --quiet --unit="$SMOKE" -p User=asistenciamodelo -p Group=www-data -p WorkingDirectory="$RELEASE/frontend" -p EnvironmentFile="$ENVFILE" -p RuntimeMaxSec=180 -p MemoryMax=768M /usr/bin/env NEXT_DIST_DIR=.next /usr/bin/npm run start -- --hostname 127.0.0.1 --port 13102
wait_http http://127.0.0.1:13102/login 200
for method in POST PUT DELETE; do
  [[ $(code -X "$method" -H 'Origin: https://asistenciamodelo.online' http://127.0.0.1:13102/api/colaboradores/0) == 401 ]] || die 'Origen legítimo no llega a autenticación.'
  [[ $(code -X "$method" -H 'Origin: https://evil.example' http://127.0.0.1:13102/api/colaboradores/0) == 403 ]] || die 'Origen externo no bloqueado.'
done
systemctl stop "$SMOKE"
cat > "$BACKUP/new-frontend.conf" <<EOF
[Service]
WorkingDirectory=$RELEASE/frontend
ReadWritePaths=$RELEASE/frontend/.next
EOF
cat > "$BACKUP/rollback.sh" <<EOF
#!/usr/bin/env bash
set -euo pipefail
[[ \$EUID == 0 ]] || exit 1
exec 9>/run/lock/asistenciamodelo-redeploy.lock
flock -n 9
[[ \$(systemctl show '$UNIT' -p WorkingDirectory --value) == '$RELEASE/frontend' ]] || { echo 'Existe otro despliegue; detenerse.'; exit 1; }
cmp -s '$DROP' '$BACKUP/new-frontend.conf'
mv '$DROP' '$BACKUP/reverted-frontend.conf'
systemctl daemon-reload
systemctl restart '$UNIT'
echo 'Ruta anterior restaurada; verificar /login.'
EOF
chmod 0700 "$BACKUP/rollback.sh"
[[ $(systemctl cat "$UNIT" | sha256sum) == "$STATE" && ! -e "$DROP" ]] || die 'La configuración cambió durante el build.'
install -m 0644 "$BACKUP/new-frontend.conf" "$DROP"
SWITCHED=1
systemctl daemon-reload
[[ $(systemctl show "$UNIT" -p WorkingDirectory --value) == "$RELEASE/frontend" ]] || die 'Override sin precedencia.'
systemctl restart "$UNIT"
wait_http http://127.0.0.1:3101/login 200
wait_http https://asistenciamodelo.online/login 200
[[ $(code -X PUT -H 'Origin: https://asistenciamodelo.online' https://asistenciamodelo.online/api/colaboradores/0) == 401 ]] || die 'Falló validación pública de origen legítimo.'
[[ $(code -X PUT -H 'Origin: https://evil.example' https://asistenciamodelo.online/api/colaboradores/0) == 403 ]] || die 'Falló protección pública de origen.'
for attempt in {1..12}; do systemctl is-active --quiet "$UNIT"; [[ $(code http://127.0.0.1:3101/login) == 200 ]]; sleep 5; done
DONE=1
echo "Publicado arreglo de origen. Reversión: sudo bash $BACKUP/rollback.sh"
echo 'Solo frontend. Sin migraciones, escrituras de datos ni cambios en Nginx. Pendiente: guardar con sesión legítima del propietario.'
