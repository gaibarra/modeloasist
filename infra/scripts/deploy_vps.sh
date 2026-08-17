#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd -- "$SCRIPT_DIR/../.." && pwd)"
APP_ROOT="${APP_ROOT:-$REPO_ROOT}"
BACKEND_DIR="$APP_ROOT/backend"
FRONTEND_DIR="$APP_ROOT/frontend"
SYSTEMD_DIR="/etc/systemd/system"
NGINX_AVAILABLE="/etc/nginx/sites-available"
NGINX_ENABLED="/etc/nginx/sites-enabled"
CERTBOT_WEBROOT="/var/www/asistenciamodelo-certbot"
BOOTSTRAP_NGINX_CONF="$APP_ROOT/infra/nginx/asistenciamodelo.online.http.conf"
TLS_NGINX_CONF="$APP_ROOT/infra/nginx/asistenciamodelo.online.conf"
BACKEND_SERVICE_TEMPLATE="$APP_ROOT/infra/systemd/asistenciamodelo-backend.service"
FRONTEND_SERVICE_TEMPLATE="$APP_ROOT/infra/systemd/asistenciamodelo-frontend.service"
TLS_CERT_PATH="/etc/letsencrypt/live/asistenciamodelo.online/fullchain.pem"
BACKEND_ENV_PATH="/etc/asistenciamodelo/backend.env"
FRONTEND_ENV_PATH="/etc/asistenciamodelo/frontend.env"
SERVICE_USER="asistenciamodelo"

run_as_account() {
  local account="$1"
  shift

  if [[ "$account" == "root" ]]; then
    bash -lc "$*"
    return
  fi

  sudo -u "$account" bash -lc "$*"
}

owner_account_for_path() {
  local target_path="$1"
  local account
  account="$(stat -c '%U' "$target_path")"

  if [[ -z "$account" || "$account" == "UNKNOWN" ]]; then
    echo "No se pudo determinar el propietario de $target_path." >&2
    exit 1
  fi

  if ! id -u "$account" >/dev/null 2>&1; then
    echo "El propietario $account de $target_path no existe como usuario local." >&2
    exit 1
  fi

  printf '%s' "$account"
}

escape_sed_replacement() {
  printf '%s' "$1" | sed 's/[&|]/\\&/g'
}

require_env_assignment() {
  local file_path="$1"
  local key="$2"

  grep -Eq "^${key}=.+$" "$file_path"
}

env_value() {
  local file_path="$1"
  local key="$2"

  awk -F= -v target="$key" '$1 == target {sub(/^[^=]*=/, ""); print; exit}' "$file_path"
}

ensure_path_absent() {
  local path="$1"
  if [[ -e "$path" ]]; then
    echo "Deploy bloqueado: elimina el artefacto no permitido $path antes de continuar." >&2
    exit 1
  fi
}

wait_for_http() {
  local url="$1"
  local method="${2:-GET}"
  local attempts="${3:-15}"
  local sleep_seconds="${4:-2}"
  local curl_args=(--fail --silent --show-error --max-time 15)

  if [[ "$method" == "HEAD" ]]; then
    curl_args+=(--head)
  fi

  for _ in $(seq 1 "$attempts"); do
    if curl "${curl_args[@]}" "$url" >/dev/null; then
      return 0
    fi
    sleep "$sleep_seconds"
  done

  echo "No se pudo validar $url después de ${attempts} intentos." >&2
  return 1
}

if [[ ! -d "$BACKEND_DIR" || ! -d "$FRONTEND_DIR" ]]; then
  echo "APP_ROOT inválido: $APP_ROOT" >&2
  echo "Esperaba encontrar $BACKEND_DIR y $FRONTEND_DIR" >&2
  exit 1
fi

ensure_path_absent "$APP_ROOT/xmrig-6.21.0"
ensure_path_absent "$FRONTEND_DIR/xmrig-6.21.0"
ensure_path_absent "$FRONTEND_DIR/scanner_linux"
ensure_path_absent "$FRONTEND_DIR/server.log"
ensure_path_absent "$FRONTEND_DIR/ip_addresses.log"

if [[ $EUID -ne 0 ]]; then
  echo "Ejecuta este script con sudo/root." >&2
  exit 1
fi

install -d -m 0750 /etc/asistenciamodelo
install -d -m 0755 "$CERTBOT_WEBROOT"
install -d -m 0755 /var/log/nginx

if ! id -u "$SERVICE_USER" >/dev/null 2>&1; then
  useradd --system --create-home --shell /bin/bash asistenciamodelo
fi

chown root:"$SERVICE_USER" /etc/asistenciamodelo

needs_configuration=false

if [[ ! -f "$BACKEND_ENV_PATH" ]]; then
  install -m 0640 "$APP_ROOT/infra/env/backend.production.env.example" "$BACKEND_ENV_PATH"
  chown root:"$SERVICE_USER" "$BACKEND_ENV_PATH"
  echo "Se creó $BACKEND_ENV_PATH. Edítalo antes de continuar." >&2
  needs_configuration=true
fi

if [[ ! -f "$FRONTEND_ENV_PATH" ]]; then
  install -m 0640 "$APP_ROOT/infra/env/frontend.production.env.example" "$FRONTEND_ENV_PATH"
  chown root:"$SERVICE_USER" "$FRONTEND_ENV_PATH"
  echo "Se creó $FRONTEND_ENV_PATH. Edítalo antes de continuar." >&2
  needs_configuration=true
fi

chmod 0640 "$BACKEND_ENV_PATH" "$FRONTEND_ENV_PATH"
chown root:"$SERVICE_USER" "$BACKEND_ENV_PATH" "$FRONTEND_ENV_PATH"

if grep -q 'CHANGE_ME' "$BACKEND_ENV_PATH" "$FRONTEND_ENV_PATH"; then
  echo "Aún hay valores CHANGE_ME en /etc/asistenciamodelo/*.env. Actualízalos antes de desplegar." >&2
  needs_configuration=true
fi

for required_key in DATABASE_URL AUTH_SECRET_KEY CORS_ALLOW_ORIGINS; do
  if ! require_env_assignment "$BACKEND_ENV_PATH" "$required_key"; then
    echo "Falta $required_key en $BACKEND_ENV_PATH." >&2
    needs_configuration=true
  fi
done

startup_bootstrap_enabled="$(env_value "$BACKEND_ENV_PATH" "STARTUP_BOOTSTRAP_ENABLED")"
if [[ "${startup_bootstrap_enabled,,}" == "true" ]]; then
  if grep -Eq '^AUTH_DEFAULT_PASSWORD=(CHANGE_ME_TEMPORARY_PASSWORD|modelo2026)?$' "$BACKEND_ENV_PATH"; then
    echo "AUTH_DEFAULT_PASSWORD debe reemplazarse por un valor temporal único o deshabilitar STARTUP_BOOTSTRAP_ENABLED." >&2
    needs_configuration=true
  fi
fi

for required_key in PORT HOSTNAME API_BASE_URL AUTH_SECRET_KEY NEXT_PUBLIC_API_BASE_URL NEXT_PUBLIC_CLIENT_API_BASE_URL; do
  if ! require_env_assignment "$FRONTEND_ENV_PATH" "$required_key"; then
    echo "Falta $required_key en $FRONTEND_ENV_PATH." >&2
    needs_configuration=true
  fi
done

if [[ "$needs_configuration" == true ]]; then
  echo "Deploy cancelado hasta completar la configuración de entorno." >&2
  exit 1
fi

BACKEND_BUILD_USER="$(owner_account_for_path "$BACKEND_DIR")"
FRONTEND_BUILD_USER="$(owner_account_for_path "$FRONTEND_DIR")"

run_as_account "$BACKEND_BUILD_USER" "python3 -m venv '$BACKEND_DIR/.venv' && '$BACKEND_DIR/.venv/bin/pip' install --upgrade pip && cd '$BACKEND_DIR' && .venv/bin/pip install ."

install -d -m 0775 -o "$FRONTEND_BUILD_USER" -g "$(id -gn "$FRONTEND_BUILD_USER")" "$FRONTEND_DIR/.next"
chown -R "$FRONTEND_BUILD_USER":"$(id -gn "$FRONTEND_BUILD_USER")" "$FRONTEND_DIR/.next"

run_as_account "$FRONTEND_BUILD_USER" "cd '$FRONTEND_DIR' && npm ci && npm run build"

chown -R "$SERVICE_USER":www-data "$BACKEND_DIR/.venv"
chown -R "$SERVICE_USER":www-data "$FRONTEND_DIR/.next"

# Apply only this application's schema changes with its production environment
# before restarting the isolated backend service.
run_as_account "$SERVICE_USER" "set -a && source '$BACKEND_ENV_PATH' && set +a && cd '$BACKEND_DIR' && .venv/bin/alembic -c alembic.ini upgrade head"

escaped_app_root="$(escape_sed_replacement "$APP_ROOT")"

sed "s|__APP_ROOT__|$escaped_app_root|g" "$BACKEND_SERVICE_TEMPLATE" > "$SYSTEMD_DIR/asistenciamodelo-backend.service"
sed "s|__APP_ROOT__|$escaped_app_root|g" "$FRONTEND_SERVICE_TEMPLATE" > "$SYSTEMD_DIR/asistenciamodelo-frontend.service"
chmod 0644 "$SYSTEMD_DIR/asistenciamodelo-backend.service" "$SYSTEMD_DIR/asistenciamodelo-frontend.service"

if [[ -f "$TLS_CERT_PATH" ]]; then
  install -m 0644 "$TLS_NGINX_CONF" "$NGINX_AVAILABLE/asistenciamodelo.online.conf"
else
  install -m 0644 "$BOOTSTRAP_NGINX_CONF" "$NGINX_AVAILABLE/asistenciamodelo.online.conf"
fi

ln -sfn "$NGINX_AVAILABLE/asistenciamodelo.online.conf" "$NGINX_ENABLED/asistenciamodelo.online.conf"

nginx -t
systemctl daemon-reload
systemctl enable asistenciamodelo-backend.service asistenciamodelo-frontend.service >/dev/null
systemctl restart asistenciamodelo-backend.service asistenciamodelo-frontend.service
systemctl is-active --quiet asistenciamodelo-backend.service
systemctl is-active --quiet asistenciamodelo-frontend.service
wait_for_http http://127.0.0.1:8184/health/live GET 20 2
wait_for_http http://127.0.0.1:3101/login HEAD 20 2
systemctl reload nginx

if [[ -f "$TLS_CERT_PATH" ]]; then
  echo "Deploy completado con la configuración HTTPS final de nginx."
else
  echo "Deploy base completado con nginx en HTTP. Emite el certificado y luego vuelve a ejecutar este script para activar HTTPS."
fi
