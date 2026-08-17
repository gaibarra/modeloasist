# Arquitectura inicial

## Objetivo
Analizar eventos de asistencia, detectar patrones y generar coaching personalizado con apoyo de
Vertex AI para empleados y directivos.

## Capas
1. **Experiencia (frontend)**: Next.js 15 (App Router) con componentes de dashboards, ranking y
   copiloto conversacional.
2. **API + IA (backend)**: FastAPI expone endpoints REST/GraphQL, integra SQLAlchemy y Vertex AI.
3. **Datos**: PostgreSQL existente (`attendance_events`, `employees`, `schedules`) más futuros
   modelos analíticos (materialized views, dbt/BigQuery).
4. **Observabilidad**: OpenTelemetry, métricas de puntualidad, auditoría de prompts/respuestas.

## Flujos claves
- **Empleado** inicia sesión con correo institucional, consulta historial y recibe mensajes
  motivacionales generados por IA basados en métricas recientes.
- **Director** consulta dashboards agregados y ranking, solicita reportes personalizados con
  explicaciones generadas por IA.

## Integración Vertex AI
- Modelo recomendado: Gemini 1.5 Pro vía `google-cloud-aiplatform`.
- Guardrails: prompt templating, moderación, logging de respuestas, almacenamiento en tabla
  `ai_insights`.

## Próximos entregables
- Esquemas para tablas derivadas (`ai_insights`, `attendance_compliance_fact`).
- Implementación de RBAC multi-nivel.
- Pipelines de sincronización (Airflow/Cloud Functions) para cargar datos históricos.
