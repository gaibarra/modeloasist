#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Uso: vps_inventory_report.sh [--markdown]

Genera un inventario de solo lectura del VPS para convivencia ordenada de varias apps.
Requiere herramientas estándar de Linux; para incluir configuración completa de nginx,
conviene ejecutarlo con permisos suficientes.
EOF
}

format="text"
if [[ "${1:-}" == "--markdown" ]]; then
  format="markdown"
elif [[ "${1:-}" == "-h" || "${1:-}" == "--help" ]]; then
  usage
  exit 0
elif [[ $# -gt 0 ]]; then
  usage >&2
  exit 1
fi

section() {
  local title="$1"
  if [[ "$format" == "markdown" ]]; then
    printf '\n## %s\n' "$title"
  else
    printf '\n[%s]\n' "$title"
  fi
}

item() {
  local label="$1"
  local value="$2"
  if [[ "$format" == "markdown" ]]; then
    printf -- '- **%s**: %s\n' "$label" "$value"
  else
    printf -- '- %s: %s\n' "$label" "$value"
  fi
}

command_exists() {
  command -v "$1" >/dev/null 2>&1
}

capture() {
  local command_text="$1"
  if output=$(eval "$command_text" 2>/dev/null); then
    printf '%s' "$output"
  else
    return 1
  fi
}

render_block() {
  local content="$1"
  if [[ -z "$content" ]]; then
    item "Estado" "Sin datos"
    return
  fi
  if [[ "$format" == "markdown" ]]; then
    printf '```text\n%s\n```\n' "$content"
  else
    printf '%s\n' "$content"
  fi
}

hostname_value=$(hostname 2>/dev/null || echo desconocido)
date_value=$(date -Iseconds 2>/dev/null || echo desconocido)
kernel_value=$(uname -sr 2>/dev/null || echo desconocido)

section "Resumen"
item "Host" "$hostname_value"
item "Fecha" "$date_value"
item "Kernel" "$kernel_value"

section "Recursos"
render_block "$(
  {
    echo '# uptime'
    uptime
    echo
    echo '# memoria'
    free -h
    echo
    echo '# disco'
    df -h /
  } 2>/dev/null
)"

section "Servicios systemd"
if command_exists systemctl; then
  render_block "$(systemctl list-units --type=service --state=running --no-pager --plain 2>/dev/null | sed '/^$/d')"
else
  item "Estado" "systemctl no disponible"
fi

section "Puertos escuchando"
if command_exists ss; then
  render_block "$(ss -ltnp 2>/dev/null)"
else
  item "Estado" "ss no disponible"
fi

section "Sitios nginx habilitados"
if [[ -d /etc/nginx/sites-enabled ]]; then
  render_block "$(find /etc/nginx/sites-enabled -maxdepth 1 -type l -o -type f 2>/dev/null | sort)"
else
  item "Estado" "No existe /etc/nginx/sites-enabled"
fi

section "Server names detectados"
if command_exists nginx; then
  server_names="$(nginx -T 2>/dev/null | awk '
    $1 == "server_name" {
      for (field_idx = 2; field_idx <= NF; field_idx++) {
        field_value = $field_idx
        gsub(/;/, "", field_value)
        if (field_value != "_") {
          print field_value
        }
      }
    }
  ' | sort -u)"
  render_block "$server_names"
else
  item "Estado" "nginx no disponible"
fi

section "Servicios de aplicación sugeridos"
render_block "$(
  if command_exists systemctl; then
    systemctl list-units --type=service --all --no-pager --plain 2>/dev/null \
      | grep -Ei 'node|next|gunicorn|uvicorn|docker|container|pm2|asistencia|modelo|frontend|backend' || true
  fi
)"
