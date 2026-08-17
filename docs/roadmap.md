# Roadmap de implementación

1. **Autenticación y perfiles**
   - Magic link por correo institucional para colaboradores.
   - RBAC multinivel (empleado, director escuela, director campus, rector).
2. **APIs analíticas**
   - Endpoints para historial individual, ranking departamental y métricas globales.
   - Webhooks con dispositivos de registro para ingesta casi en tiempo real.
3. **Pipelines de datos**
   - Limpieza de `attendance_events` y cálculo de indicadores (lateness, streaks, risk score).
   - Publicación de vistas materializadas para dashboards.
4. **IA generativa**
   - Prompts parametrizados para coaching y briefs ejecutivos (Gemini 1.5 Pro).
   - Registro de prompts/respuestas en tabla `ai_insights` y evaluación de tono.
5. **Experiencia de usuario**
   - Portal de empleado con histórico, badges y recomendaciones.
   - Panel ejecutivo con ranking, alertas y exportaciones inteligentes.
6. **Observabilidad y seguridad**
   - Logs estructurados, trazas distribuidas y auditoría de acceso.
   - Gestión de secretos (GCP Secret Manager) y políticas de datos.
