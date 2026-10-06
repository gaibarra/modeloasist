# Escuela Modelo — Guía de apariencia y CSS reutilizable

Documento de transferencia visual · 22 de septiembre de 2026.

Esta guía documenta la apariencia implementada en la aplicación de asistencia de Escuela Modelo para reproducirla en otra aplicación institucional. Es una referencia del software actual, no un manual oficial de identidad corporativa.

## Archivos entregados

- [escuela-modelo.css](escuela-modelo.css): estilos completos en CSS estándar, sin dependencia de React, Next.js o Tailwind.
- [ejemplo.html](ejemplo.html): página de muestra; abrir directamente en un navegador.
- [Modelo.jpg](Modelo.jpg): copia del logotipo utilizado por la aplicación actual.

## Dirección visual

Interfaz clara y sobria, azul institucional como color principal, fondo gris azulado y superficies blancas. Los contenedores tienen bordes finos, esquinas redondeadas y sombras suaves. Los botones tienen forma de cápsula. Mantener espacios amplios, títulos oscuros y textos secundarios de menor contraste visual.

## Colores

Usar las variables CSS en lugar de repetir valores hexadecimales.

| Variable | Valor | Uso |
| --- | --- | --- |
| `--background` | `#f4f6f9` | Fondo general |
| `--foreground` | `#172033` | Texto principal |
| `--surface` | `#ffffff` | Tarjetas y controles |
| `--surface-muted` | `#edf2f7` | Bloques internos |
| `--surface-soft` | `#f8fafc` | Superficies secundarias |
| `--border` | `#d9e0ea` | Bordes habituales |
| `--border-strong` | `#bcc8d8` | Bordes destacados |
| `--brand` | `#15345d` | Acciones principales e identidad |
| `--brand-strong` | `#0f2747` | Títulos y hover principal |
| `--brand-soft` | `#40648f` | Subtítulos y foco |
| `--brand-tint` | `#e6edf7` | Insignias y fondos azules claros |
| `--muted` | `#5c687d` | Texto de apoyo |
| `--success` | `#1f6a52` | Éxito |
| `--warning` | `#a06217` | Advertencias |
| `--danger` | `#ab3f3f` | Errores |

## Tipografía

La aplicación original carga **Geist** y **Geist Mono** mediante `next/font/google`. El texto general usa Geist; la variable monoespaciada está disponible en el original. El paquete portable no incluye archivos de fuentes ni hace solicitudes externas: usará Geist si está instalada o configurada, y Arial/Helvetica como alternativas. Para igualar la tipografía exactamente, incorporar Geist en la aplicación destino y definir `--font-geist-sans` o una familia `Geist` mediante `@font-face`.

| Elemento | Tamaño | Peso y comportamiento |
| --- | --- | --- |
| Título principal | `clamp(2rem, 4vw, 3.25rem)` | 700; interlineado 1.08 |
| Descripción | `1rem` | Interlineado 1.7 |
| Etiqueta de sección | `0.72rem` | 700; mayúsculas; espaciado `0.18em` |
| Botón | `0.92rem` | 700 |
| Etiqueta de campo | `0.92rem` | 600 |
| Campo | `0.95rem` | Texto normal |
| Estado | `0.78rem` | 700 |
| Ayuda | `0.82rem` | Interlineado 1.6 |
| Valor de indicador | `1.5rem` / `1.875rem` | 600; mayor desde 640 px en el ejemplo |

## Estructura, espaciado y superficies

- `.page-shell`: altura mínima de pantalla, degradado radial azul tenue y degradado vertical claro; padding `2rem 1rem 2.5rem`.
- `.page-container`: ancho máximo de `72rem` (1152 px con raíz de 16 px), centrado y separación vertical de `1.5rem`.
- `.brand-panel`: cabecera institucional, degradado blanco, radio `1.75rem` (28 px).
- `.surface-card`: tarjeta blanca, radio `1.5rem` (24 px).
- `.surface-muted`: panel secundario, radio `1.25rem` (20 px).
- `.surface-subtle`: bloque interno, radio `1rem` (16 px).
- Sombra común: `0 16px 32px -24px rgba(15, 39, 71, 0.28)`.

Las superficies no incluyen padding por sí solas. Añadir `.em-panel` para 24 px, que pasan a 32 px desde 640 px, o `.em-kpi` para 20 px. `.em-stack` separa contenido 20 px y `.em-actions` distribuye acciones con 12 px y salto de línea.

La cabecera original pasa de columna a fila desde 1024 px. El login usa ancho máximo de 64rem y dos columnas `1.1fr 0.9fr` desde 1024 px. El ejemplo entregado es una composición genérica: sus indicadores pasan de una a tres columnas desde 640 px. Estas reglas pueden ajustarse al contenido del nuevo sistema conservando colores y componentes.

## Identidad

Mostrar el logotipo de `Modelo.jpg` en un contenedor circular de 64 × 64 px, con fondo blanco, borde tenue y padding de 6 px. El nombre “Escuela Modelo” usa mayúsculas visuales, tamaño de 12 px, peso 600 y espaciado `0.24em`. Debajo colocar el nombre de la aplicación con 18–20 px y peso 600; reemplazar “Asistencia institucional” por el nombre del nuevo servicio.

Mantener el recurso gráfico original y un texto alternativo descriptivo. La marca de agua `.logo-watermark` reproduce opacidad `0.035`; su contenedor debe tener posición relativa y recortar el desbordamiento.

## Componentes

| Componente | Clases | Uso |
| --- | --- | --- |
| Identificador institucional | `brand-badge` | Contexto breve, mayúsculas y fondo azul claro |
| Encabezado | `section-eyebrow`, `page-title`, `page-subtitle` | Jerarquía de textos |
| Acción principal | `primary-button` | Fondo azul y texto blanco |
| Acción secundaria | `secondary-button` | Fondo blanco y borde visible |
| Acción de seguridad | `security-button` | Fondo azul claro y borde tenue |
| Acción discreta | `ghost-button` | Fondo transparente |
| Formulario | `field-label`, `field-input`, `helper-text` | Etiqueta, control y ayuda |
| Estado | `status-pill` + `status-success/warning/danger/neutral` | Etiqueta con significado explícito |
| Aviso | `alert-info/success/warning/error` | Mensaje de información o resultado |

Los campos tienen radio de 16 px y padding `0.88rem 1rem`. El foco original cambia el borde y añade un halo azul de 4 px. Botones, campos y estados tienen transición de 180 ms.

El paquete portable añade foco visible en botones y enlaces, apariencia deshabilitada, borde de campo inválido y respeto de movimiento reducido. Son adaptaciones para reutilización, no reglas adicionales presentes en el CSS global original. Acompañar los estados con texto; asociar cada etiqueta mediante `for`/`id`. En errores de formulario usar `aria-invalid="true"` y conectar el mensaje con `aria-describedby`. Verificar teclado, contraste y zoom en la aplicación destino; esta extracción no constituye una auditoría de accesibilidad.

## Integración en otra aplicación

1. Copiar `escuela-modelo.css` y `Modelo.jpg` a los archivos estáticos del nuevo proyecto.
2. Cargar la hoja una vez, ajustando la ruta:

   ```html
   <link rel="stylesheet" href="/assets/escuela-modelo.css">
   ```

3. Usar la siguiente estructura y consultar `ejemplo.html` para formularios, indicadores y avisos:

   ```html
   <main class="page-shell">
     <div class="page-container">
       <header class="brand-panel em-panel em-stack">
         <div class="em-logo">
           <img class="em-logo-image" src="/assets/Modelo.jpg"
                width="64" height="64" alt="Logo de Escuela Modelo">
           <div>
             <p class="em-wordmark">Escuela Modelo</p>
             <p class="em-app-name">Nombre de la aplicación</p>
           </div>
         </div>
         <h1 class="page-title">Título de la pantalla</h1>
         <p class="page-subtitle">Descripción breve del servicio.</p>
       </header>
       <section class="surface-card em-panel em-stack">
         <h2 class="em-section-title">Contenido</h2>
         <a class="primary-button" href="/solicitudes">Ver solicitudes</a>
       </section>
     </div>
   </main>
   ```

4. En React usar `className` y `htmlFor`. En Next.js importar el CSS global desde el layout y servir el logotipo desde `public`.
5. Incorporar la fuente Geist si se requiere fidelidad tipográfica. Los iconos del proyecto original proceden de `lucide-react`; este paquete no incluye una biblioteca de iconos.
6. Comprobar la pantalla a 360, 640, 1024 y 1440 px, con textos largos, zoom de 200 %, navegación por teclado y estados de carga/error.

El CSS incluye variables en `:root` y un reset básico global que sustituye parte de la normalización de Tailwind. Si se integra en una aplicación con estilos existentes, revisar colisiones: las clases originales se conservan y el reset afecta elementos HTML generales. Para aislar un módulo, adaptar tanto los selectores de componentes como el reset a un contenedor propio y mover las variables de `:root` a ese contenedor.

No copiar las utilidades Tailwind de los componentes originales esperando que existan en este paquete. Las clases `em-*` son equivalentes de composición para el ejemplo. La hoja portable elimina `@import "tailwindcss"` y `@theme inline`; usar directamente variables como `var(--brand)` en CSS personalizado. Los controles del ejemplo son demostrativos; la navegación, validación y persistencia corresponden a la aplicación destino.

## Fuentes dentro del repositorio

- `frontend/src/app/globals.css`: paleta, superficies, botones, formularios, estados y avisos.
- `frontend/src/app/layout.tsx`: tipografía Geist.
- `frontend/src/components/institution-header.tsx`: cabecera y adaptación responsive.
- `frontend/src/components/school-logo.tsx`: identidad y logotipo.
- `frontend/src/components/kpi-card.tsx`: indicadores.
- `frontend/src/components/ranking-table.tsx`: filas en superficies secundarias.
- `frontend/src/app/login/page.tsx`: composición de acceso.

Los archivos entregados son una instantánea de estos estilos; no se sincronizan automáticamente con cambios futuros.
