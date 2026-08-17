# Playbook de Cohabitación del VPS

Guía operativa para mantener varias aplicaciones en el mismo VPS con límites claros, inventario actualizado y cambios controlados.

## Objetivos
- Evitar conflictos entre aplicaciones por puertos, `nginx`, recursos o despliegues huérfanos.
- Mantener una línea base auditable de qué corre en el VPS y quién es responsable.
- Reducir el riesgo de suspensión del proveedor por procesos ajenos, picos de uso o configuraciones inconsistentes.

## Principios
- Cada aplicación usa solo puertos `127.0.0.1` exclusivos.
- Cada dominio tiene un único `server_name` canónico en `nginx`.
- Cada app tiene su propia unidad `systemd`, `.env`, logs y carpeta de trabajo.
- Ninguna app de producción corre con `npm run dev`, `uvicorn --reload` o comandos de desarrollo equivalentes.
- Cualquier artefacto no relacionado al producto se considera incidente operativo hasta demostrar lo contrario.

## Inventario mínimo por aplicación
Registrar y mantener actualizado:
- Nombre de la app.
- Responsable técnico.
- Ruta base en disco.
- Usuario del sistema.
- Puertos loopback.
- Dominio(s) y archivo(s) de `nginx`.
- Unidad(es) `systemd`.
- Método de despliegue y rollback.
- Health check y comando de verificación.

Referencia inicial del host actual: `docs/vps-service-inventory.md`.

## Rutina semanal
1. Ejecutar `infra/scripts/vps_inventory_report.sh --markdown`.
2. Ejecutar `infra/scripts/nginx_server_name_audit.sh`.
3. Revisar `systemctl --failed`.
4. Revisar ocupación de disco, memoria y crecimiento de logs.
5. Confirmar que no existan binarios, archives o logs ajenos al producto en rutas de despliegue.

## Checklist de alta de una app
- Reservar puertos `127.0.0.1` no usados.
- Crear usuario o contexto de ejecución definido.
- Crear archivo(s) `.env` fuera del repo si aplica.
- Crear unidad `systemd` con `WorkingDirectory`, límites y reinicio automático.
- Crear vhost exclusivo de `nginx` con `server_name` único.
- Validar `nginx -t` sin warnings nuevos.
- Registrar health check, rollback y responsable.
- Actualizar el inventario del host.

## Checklist de cambio
- Identificar impacto en puertos, `nginx`, certificados y recursos.
- Validar que no exista colisión con otra app.
- Ejecutar pruebas o build antes del despliegue.
- Confirmar que `systemd` y health checks queden en verde.
- Revisar `journalctl` y `nginx` después del cambio.
- Registrar fecha, cambio y responsable.

## Checklist de baja
- Deshabilitar y detener la unidad `systemd`.
- Retirar el vhost y validar `nginx -t`.
- Liberar puertos y certificados si ya no se usan.
- Archivar o eliminar artefactos y secretos de forma segura.
- Actualizar el inventario para evitar servicios huérfanos.

## Comandos de referencia
```bash
sudo bash infra/scripts/vps_inventory_report.sh --markdown
sudo bash infra/scripts/nginx_server_name_audit.sh --strict
sudo systemctl list-units --type=service --state=running
sudo systemctl --failed
sudo ss -ltnp
sudo nginx -t
sudo journalctl --disk-usage
```

## Estado actual a normalizar
En el VPS actual ya se confirmó que existen otras aplicaciones además de `modeloasist`, incluyendo servicios desde rutas como `/home/gaibarra/finiquitos/server`, `/home/gaibarra/uipcmodelo/server` y `/home/gaibarra/motel/frontend`. Antes de agregar más servicios, conviene consolidar sus responsables, puertos y vhosts.
