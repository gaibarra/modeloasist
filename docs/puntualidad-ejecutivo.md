# Informe ejecutivo: Parámetros para calcular la puntualidad

## 1. Objetivo del indicador
El porcentaje de puntualidad muestra qué proporción de los registros de entrada ocurren dentro del margen establecido de tolerancia (5 minutos). Sirve para comparar campus, departamentos y colaboradores con una métrica única y sencilla que refleje disciplina operativa.

## 2. Fuentes de información
- **Sistema de control de acceso**: provee eventos crudos de asistencia con fecha, hora y dispositivo.
- **Catálogo de empleados**: define campus y departamentos oficiales.
- **Horarios programados**: tabla de horarios formales; cuando no existe, se infiere automáticamente con el histórico de entradas.

Todos los datos residen en la base `asistencia`, y se procesan en lotes diarios mediante el servicio de analítica (FastAPI).

## 3. Ventana de análisis
- Para el tablero principal y el ranking general se usa una ventana móvil de **30 días**.
- Para el histórico semanal se consolidan semanas completas **de lunes a domingo**.
- Los cálculos pueden filtrarse por campus, departamento o colaborador sin alterar la lógica del indicador.

## 4. Clasificación de eventos
1. Se toma el **primer registro de cada colaborador por día** (entrada efectiva).
2. Se identifica el horario esperado para ese día:
   - Prioridad 1: horario oficial en el sistema académico.
   - Prioridad 2: horario inferido automáticamente a partir de sus últimas entradas (mediana de horarios).
3. Se compara la hora real contra la esperada. Si excede en más de **10 minutos** se clasifica como "tardanza"; en caso contrario es "puntual".

## 5. Cálculo del porcentaje
Para cada unidad de análisis (global, campus, departamento o persona):

```
Puntualidad (%) = (Entradas puntuales / (Entradas puntuales + Entradas tardías)) * 100
```

Solo se consideran días con al menos un registro válido. Si no hay datos en el periodo, el sistema reporta "Sin registros" en lugar de asumir 100 %.

## 6. Controles de calidad
- **Validación de campus**: únicamente Mérida, Montejo, Chetumal y Valladolid forman parte del indicador actual.
- **Depuración de duplicados**: se ignoran registros repetidos para el mismo colaborador y día.
- **Persistencia semanal**: los resultados consolidados se guardan en `attendance_weekly_metrics` para auditoría.

## 7. Interpretación para rectoría
- Valores **>85 %** sugieren procesos controlados; entre **70 %-85 %** requieren seguimiento; por debajo de **70 %** se catalogan como foco rojo.
- El ranking semanal compara campus en función del mismo porcentaje y muestra el avance respecto a la semana previa.
- El nuevo buscador de colaboradores permite consultar cualquier persona y filtrar por campus/departamento, asegurando transparencia del indicador.

## 8. Próximos pasos recomendados
1. Integrar notificaciones automáticas para campus con tres semanas consecutivas debajo de la meta.
2. Validar horarios oficiales cada semestre para reducir inferencias.
3. Incorporar justificaciones (permisos/guardias) para contextualizar la métrica en reportes a rectoría.
