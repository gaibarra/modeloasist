# Infraestructura

Plan inicial para desplegar la plataforma:

1. **Contenedores**: Build del backend y frontend mediante Dockerfiles individuales.
2. **Orquestación**: Kubernetes (GKE) con Helm Charts para staging/producción.
3. **CI/CD**: GitHub Actions para ejecutar pruebas, construir imágenes y publicar en Artifact
   Registry.
4. **Observabilidad**: OpenTelemetry + Grafana/Prometheus, Cloud Logging y alertas de
   cumplimiento.

Este espacio también alojará manifests de Terraform y definiciones de secretos.

## Activos listos para VPS
- `nginx`: `infra/nginx/asistenciamodelo.online.http.conf` y `infra/nginx/asistenciamodelo.online.conf`
- `systemd`: `infra/systemd/asistenciamodelo-backend.service` y `infra/systemd/asistenciamodelo-frontend.service`
- `env`: `infra/env/backend.production.env.example` y `infra/env/frontend.production.env.example`
- `deploy`: `infra/scripts/deploy_vps.sh`
- `auditoría`: `infra/scripts/vps_inventory_report.sh` y `infra/scripts/nginx_server_name_audit.sh`
- Guía operativa: `docs/deploy-vps-nginx-systemd-certbot.md`
- Playbook de cohabitación: `docs/vps-cohabitation-playbook.md`
- Inventario persistente del host: `docs/vps-service-inventory.md`
