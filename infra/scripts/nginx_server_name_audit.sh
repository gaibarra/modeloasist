#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Uso: nginx_server_name_audit.sh [--strict]

Analiza `nginx -T` y reporta `server_name` duplicados.
- Sin flags: siempre sale con código 0, útil para revisión manual.
- `--strict`: sale con código 1 si encuentra duplicados.
EOF
}

strict=false
if [[ "${1:-}" == "--strict" ]]; then
  strict=true
elif [[ "${1:-}" == "-h" || "${1:-}" == "--help" ]]; then
  usage
  exit 0
elif [[ $# -gt 0 ]]; then
  usage >&2
  exit 1
fi

if ! command -v nginx >/dev/null 2>&1; then
  echo "nginx no está disponible en este host" >&2
  exit 2
fi

config_dump=$(nginx -T 2>/dev/null)
if [[ -z "$config_dump" ]]; then
  echo "No fue posible leer la configuración efectiva de nginx" >&2
  exit 2
fi

duplicates=$(printf '%s\n' "$config_dump" | awk '
  /^# configuration file / {
    current_file = $4
    sub(/:$/, "", current_file)
    next
  }
  $1 == "server_name" {
    for (field_idx = 2; field_idx <= NF; field_idx++) {
      field_value = $field_idx
      gsub(/;/, "", field_value)
      if (field_value != "_" && field_value != "" && current_file != "") {
        key = field_value SUBSEP current_file
        if (!(key in seen)) {
          seen[key] = 1
          counts[field_value]++
          files[field_value] = files[field_value] current_file "\n"
        }
      }
    }
  }
  END {
    for (name in counts) {
      if (counts[name] > 1) {
        printf "%s|%d|%s\n", name, counts[name], files[name]
      }
    }
  }
' | sort)

if [[ -z "$duplicates" ]]; then
  echo "Sin duplicados de server_name detectados."
  exit 0
fi

echo "Duplicados detectados:"
while IFS='|' read -r name count file_list; do
  [[ -z "$name" ]] && continue
  printf -- '- %s (%s apariciones)\n' "$name" "$count"
  while read -r file_path; do
    [[ -z "$file_path" ]] && continue
    printf '  - %s\n' "$file_path"
  done <<< "$file_list"
done <<< "$duplicates"

if [[ "$strict" == true ]]; then
  exit 1
fi
