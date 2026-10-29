# EPUB ePL: código avanzado e imágenes

Fuentes: *Aprende a maquetar III: Código avanzado* [46604] y *IV: Imágenes y gráficos SVG* [46605], ambos r3.0, Proyecto Scriptorium.
Las citas `III/archivo.xhtml` y `IV/archivo.xhtml` designan capítulos internos bajo `OEBPS/Text/` del manual correspondiente; no requieren rutas locales.

## Alcance y fuerza de las indicaciones

- **[ePL]**: norma editorial del manual/base, no requisito universal de EPUB.
- **[Compatibilidad heredada]**: resultados de lectores/motores de aquella edición; no describen necesariamente versiones actuales.
- **[Recomendación]**: criterio práctico del manual, sujeto a contenido y pruebas.
- **[Ejemplo heredado]**: patrón opcional; cifras, nombres de clases y fuentes no son valores obligatorios.
- Los ejemplos siguientes conservan los patrones, con extractos o adaptaciones indicados. No reproducir erratas del original: `</br>`, comillas tipográficas en atributos, `text-alingn`, `text-size`, etiquetas incompletas.
- No tratar la apariencia en un editor ni la validación estructural como prueba suficiente de compatibilidad visual.

## XHTML/CSS y prácticas desaconsejadas

Fuentes: `III/2.01.CodigosUtiles.xhtml`, `III/2.02.Desaconsejado.xhtml`, `III/etiquetastexto.xhtml`, `III/etiquetascontenido.xhtml`, `III/Elementos-2.xhtml`, `III/Selectores-1.xhtml`.

- **[ePL]** Añadir estilos propios en `style.css`; no modificar `epl.css`. El capítulo dice inicialmente `styles.css`, pero sus ejemplos usan `style.css`: comprobar el nombre real en el EPUB.
- **[ePL]** No encadenar `<br />` ni usarlos como espaciadores; separar párrafos con CSS. Un salto dentro de un título sí está contemplado.
- **[Recomendación]** Separación entre párrafos en `em`; márgenes laterales respecto a pantalla en `%`.
- **[Recomendación]** Para líneas, usar `<hr />` con bordes CSS antes que párrafos/divs vacíos. Los vacíos aparecen en otros ejemplos como mecanismos específicos, no como espaciado general.
- **[Compatibilidad heredada]** Evitar `<pre>` salvo texto realmente preformateado sin mejor alternativa; no usarlo solo para conseguir monoespaciado.
- **[Compatibilidad heredada]** `<mark>` falla en Sony. No hacer que un enlace imprescindible dependa de pulsar una imagen: ofrecer enlace textual cercano, por ejemplo en el pie.
- **[Compatibilidad heredada]** Fondos con `background-image`/`background-repeat` pueden faltar o renderizar mal; preferir imágenes normales/flotantes. No hay solución probada para fondo detrás de texto.
- **[Compatibilidad heredada]** No depender de `font-variant:small-caps`: el manual propone `.versalita` del base o `<small>`; comprobar el texto en mayúsculas necesario para esa representación.
- **[Compatibilidad heredada]** No depender de pseudoelementos/selectores como `:first-letter`, `:first-line`, `:before`, `:after`, `:first-child`, `:nth-child`. El manual los agrupa imprecisamente; cuando se conoce el fragmento, marcarlo con clase/span explícito.
- **[Compatibilidad heredada]** También lista como ignorados `list-style-position`, `font-variant`, `!important`, `letter-spacing`, `text-transform`, `word-spacing`; no basar en ellos contenido o disposición indispensables.
- **[Compatibilidad heredada]** `max-height` porcentual es poco fiable si el contenedor no tiene altura fija; estudiar `height` o un máximo fijo en px. No garantizar ajuste vertical por un `max-height:100%` copiado de otro ejemplo.
- `vertical-align` no centra el contenido de un bloque: sirve para elementos en línea/inline-block y celdas. En texto inline ordinario, `width`/`height` no fijan caja; usar inline-block cuando sea necesario.
- **[Recomendación]** Verificar herencia y selectores en el resultado; no asumir que toda propiedad de un padre se transmite a sus hijos.

**[Ejemplos heredados, extractos]** Subtítulo, salto sobre contenido real y espacio inseparable (`III/2.01.CodigosUtiles.xhtml`):

```css
.subtit { text-align:center; text-indent:0; font-size:1.5em; }
.breakbefore { page-break-before:always; }
```
```xhtml
<h1 title="Título: Subtítulo">Título</h1>
<p class="subtit">Subtítulo</p>
<p class="breakbefore">Primer párrafo de la página siguiente.</p>
<p><span class="nosep">01-01-2000</span>; T.&#160;S. Eliot.</p>
```

El manual usa `title` para el texto que se lleva al TOC: no asumir que lo genera por sí solo. `.nosep` pertenece al base; `&#160;` representa el `&nbsp;` del ejemplo sin depender de una entidad HTML declarada.

## Listas, tablas y columnas

Fuentes: `III/3.01.Listas.xhtml`, `III/3.03.Tablas.xhtml`, `III/3.031.TabEjemplos.xhtml`, `III/Propiedades-1.xhtml`, `III/2.02.Desaconsejado.xhtml`.

- **[Compatibilidad heredada]** `ol start` y `li value` pueden ignorarse. Si importa continuar desde un número concreto, el manual recomienda numeración textual explícita, no confiar en esos atributos.
- **[Ejemplo heredado]** Lista con números propios: `.ul2 { list-style-type:none; }`, `.li2 { text-indent:-2em; margin-left:2em; }`; cada `li` incluye su número como texto.
- Las listas anidadas van dentro del `li` correspondiente, antes de cerrarlo. Un `li` puede contener varios párrafos; ajustar su sangría por clase si se necesita alinearlos.
- **[Compatibilidad heredada]** La variante con títulos intercalados (`li.sinnum`, inline-block) advierte de fallos con KindleGen; no asumir continuidad correcta por ocultar marcadores.
- **[Recomendación]** Para datos tabulados, usar tablas, no cajas CSS que simulen celdas. Las tablas para poesía/columnas son opciones heredadas de maquetación, no obligación general.
- Aplicar estilos concretos a `td`/`th`; el manual advierte que estilos sobre `tr` pueden no surtir efecto. Evitar reglas globales si hay tablas de distinto aspecto.
- Preferir CSS para bordes; `border-collapse:collapse` fusiona bordes compartidos. `border-spacing:0` por sí solo deja bordes dobles; con collapse, separar contenido mediante padding de celda.
- Al combinar con `rowspan`/`colspan`, omitir las celdas cubiertas; no generar celdas superpuestas.
- **[Recomendación]** Estilizar directamente la celda antes que añadir `p` que hereden estilos generales; para datos en líneas independientes, considerar filas nuevas antes que `<br />`.
- **[Compatibilidad heredada]** No depender de `caption-side`. El manual presenta `<th>` y `<td>` estilizado como equivalentes visuales, no como equivalentes semánticos: conservar encabezados reales.
- **[Recomendación]** Anchos en `em` para ajustarse al texto, `%` para ajustarse a pantalla; no fijar todas las columnas si no hace falta. Sumar anchos y padding: no exceder el 100%; propone ~95% como margen de seguridad, no cifra universal.
- **[Recomendación]** Dejar paginar tablas largas entre filas. `page-break-inside:avoid` solo para tablas pequeñas que quepan.
- **[Compatibilidad heredada]** Centrar mediante `display:inline-table` dentro de `.centrado`; restablecer alineación de celdas. Puede recortar por abajo si supera la página: reservarlo para pocas filas, no tablas largas.
- Una tabla flotante necesita `clear:both` en el contenido posterior cuando no deba fluir a su lado.
- **[Ejemplo heredado, no valor por defecto]** El manual propone 10–12 pt para tablas/pies muy ajustados. Bloquea el escalado del usuario: no aplicarlo indiscriminadamente. Su `text-size:12pt` es errata, no CSS utilizable.

**[Ejemplo heredado adaptado]** Tabla breve centrada; combina reglas del capítulo, con encabezados explícitos:

```css
.tabcentro { display:inline-table; border-collapse:collapse; }
.tabcentro th, .tabcentro td {
  vertical-align:top; text-align:left; padding-right:1em;
}
```
```xhtml
<div class="centrado">
  <table class="tabcentro">
    <caption>Datos</caption>
    <tr><th>Nombre</th><th>Valor</th></tr>
    <tr><td>Primero</td><td>Uno</td></tr>
  </table>
</div>
```

## Poesía y notas marginales

Fuente: `III/2.01.CodigosUtiles.xhtml`; alternativas en `III/3.031.TabEjemplos.xhtml`.

**[Ejemplo heredado, extracto]** Un párrafo por verso y sangría francesa; cursiva y medidas son opcionales según la obra:

```css
.verso { margin:2em 0 2em 5em; }
.verso p { text-align:left; line-height:1.2em; font-style:italic; text-indent:-2em; }
```
```xhtml
<div class="verso">
  <p>Este el primer verso</p>
  <p>este el segundo</p>
</div>
```

- **[Compatibilidad heredada]** Un poema entero en inline-block puede pasar íntegro a otra página o perder versos por abajo al aumentar fuente. No usar una caja indivisible para poemas largos.
- **[Ejemplo heredado]** Para centrar estrofas, el manual agrupa pocos versos por caja y fija un ancho común acorde al verso mayor (`6.5em` en su poema, no general), con `max-width:100%` y sangría negativa compensada. Advierte que cajas independientes sin ancho común centran de forma desigual.
- Numeración marginal: spans flotantes con margen negativo requieren reservar el mismo margen en el texto (ejemplo: `margin-right:-4em` en el número y `margin-right:4em` en párrafos); no dejar las cifras fuera de pantalla.
- **[Ejemplo heredado]** Notas a la izquierda: texto con `margin-left:30%`; nota con `margin-left:-42.86%` (30/70 × 100), `max-width:40%`. Recalcular al cambiar proporciones; son porcentajes del contenedor, no todos de pantalla.
- **[Compatibilidad heredada]** Para esas notas se cambia `max-width` a `width` bajo `@media amzn-kf8` por KindleGen. Es una excepción de conversión heredada, no CSS necesario para todo EPUB.

## Imágenes: página completa, flotación, escalado y pies

Fuentes: `III/4.02.Atodapagina.xhtml`, `III/4.03.ImgFlota.xhtml`, `III/4.04.Escalar_Img.xhtml`, `III/4.05.Pie.xhtml`, `III/4.06.ImgIrregular.xhtml`.

- **[ePL, uso del base]** `body.sinmargen` + `.cubierta` solo para imagen aislada en su propio XHTML. Entre texto, usar `.ilustra`; si hace falta `.sinmargen`, aplicarla a un contenedor, no al body de todo el capítulo.
- **[Compatibilidad heredada]** Flotar el contenedor funciona mejor con imágenes pequeñas; desde unos 400 px de ancho el manual detecta fallos. Si solo flota la imagen, poner la clase en `img`; si incluye pie, limitar también el `img` interior (`max-width:100%`, sujeto a pruebas de altura).
- **[Recomendación]** Para escalar con la fuente, preferir ancho `em` y máximo `%` en el contenedor, con `img { width:100%; }`; el escalado directo de `img` falló en iBooks/iPad.

**[Ejemplo heredado, extracto compartido con `IV/SVG02.InsercionSVG.xhtml`]** Ajustar `10em` al contenido; sirve para raster o SVG externo:

```css
.imagenesc { display:inline-block; margin:1em 0; text-indent:0; }
.imagenesc img { width:100%; }
.escalarsvg { width:10em; max-width:100%; }
```
```xhtml
<div class="centrado">
  <p class="imagenesc escalarsvg"><img alt="" src="../Images/Imagenes_eq.svg" /></p>
</div>
```

- **[Ejemplo heredado]** Símbolo en línea: contenedor inline-block de `.55em`, `max-width:100%`, `vertical-align:-.1em`, imagen interior al 100%. Son ajustes del símbolo mostrado, no métricas universales.
- Para mantener imagen y pie juntos, el manual los agrupa en inline-block; separación exterior con padding si margin falla. Si el conjunto supera la altura de página puede recortarse: comprobarlo con fuente grande.
- **[Ejemplo heredado]** Pie inferior: contenedor `width:60%; padding:1em 0`, imagen al 100%, pie `.75em`. Variante escalable: `width:20em; max-width:100%`. No imponer estas proporciones a todas las figuras.
- Pies laterales de varias líneas: imagen y texto inline-block con `vertical-align`; dejar holgura por el espacio entre cajas (~95% total propuesto). `float` no proporciona ese centrado vertical.
- **[Ejemplo heredado]** Para imagen casi a página completa y pie fijo: clase distinta de `.cubierta` sin su salto posterior; pie a 10 pt y reducir altura de imagen, aproximadamente 4–5% por línea (90% para dos). Es una heurística de lectores antiguos, no garantía ni plantilla universal.
- **[Compatibilidad heredada]** Contorno irregular: cajas flotantes auxiliares con `clear:left`, dimensiones proporcionales e imagen desbordando la primera caja; iBooks no siempre respeta tamaño. No usar a ciegas como patrón general.
- Para ese contorno, alturas porcentuales calculadas suponiendo pantalla 3:4 fallan con otra relación de aspecto. Las imágenes auxiliares invisibles preservan proporciones, pero pueden paginar aparte si son demasiado altas.
- **[Compatibilidad heredada]** ADE falla con contornos cuyo ancho aumenta hacia abajo (círculos, elipses, L). El manual desaconseja esta técnica en esos casos.

## Raster: formatos, tamaños y compresión

Fuentes: `IV/GIMPImagen.xhtml`, `IV/GIMPEjemplo.xhtml`, `IV/ProcesLotes.xhtml` (solo criterios de salida; no procedimientos gráficos).

- **[Recomendación]** Evitar recomprimir JPEG sucesivamente: tiene pérdidas y no admite transparencia. PNG comprime sin pérdidas y admite alfa; comprobar PNG indexado por cambios de color detectados en ADE. GIF limita a 256 colores; no depender de animación en EPUB.
- **[Recomendación heredada]** Exportar JPEG no progresivo. La calidad `0.75` es un ejemplo del procesador por lotes, no una escala comparable entre codificadores ni requisito de validación.
- **[Convención ePL heredada]** El ejemplo de portada usa 600×900 px como estándar editorial; no es dimensión universal de EPUB ni de todas las imágenes interiores. Los 200×300 px del mismo capítulo son para foto de autor **para la web**, no norma de imagen interior.
- Elegir tamaño por píxeles y uso previsto; cambiar solo ppp/ppi no añade detalle en pantalla. No ampliar una imagen pequeña esperando recuperar nitidez; conservar proporciones.
- Estos capítulos no establecen un único máximo de bytes/píxeles para todo raster. No extenderle automáticamente el límite de SVG.

## SVG y fuentes

Fuentes: `IV/SVG01.CreacionSVG.xhtml`, `IV/SVG02.InsercionSVG.xhtml`, `IV/SVG03.Adaptacion.xhtml`; `III/5.01.FuentesIntro.xhtml.xhtml`, `III/5.02.FuentesAnadir.xhtml`, `III/5.03.FuentesModificacion.xhtml`.

- **[Perfil heredado ePL/EPUB 2]** Generar SVG 1.1, UTF-8 y atributos de presentación; no confundir este perfil con una prohibición universal de SVG moderno. No basta cambiar `version` si el contenido no cumple ese perfil.
- **[Límite heredado ePL]** SVG individual no debe superar «300 Kb»; el manual atribuye al ePLValidator un error por encima. También cita 300 Kb por XHTML al hablar de SVG inline. No especifica base decimal/binaria: medir tamaño descomprimido y dejar margen, sin afirmar un umbral exacto en bytes.
- **[Recomendación heredada]** No superar un A4 y ajustar el lienzo al dibujo por fallos observados en lectores; no convertir A4 en un máximo de píxeles universal.
- **[Compatibilidad heredada]** Usar RGB, evitar degradados; convertir trazos discontinuos/flechas en geometría rellena si deben conservarse en lectores problemáticos. Transparencia uniforme solo con pruebas: el manual declara incertidumbre para algunos resultados.
- Preferir SVG externo mediante `img` y clases de imagen. **[Recomendación heredada]** SVG inline no recomendado mientras seguían las pruebas; aumenta XHTML y puede inflar la paginación ADE. La advertencia no prohíbe cualquier envoltorio SVG del base.
- Poco texto: curvas pueden ser adecuadas. Mucho texto: mantener texto y referenciar la fuente exacta incorporada al EPUB para conservar métricas; compartirla entre SVG reduce peso frente a incrustarla en cada gráfico. Valorar también el peso de la fuente.
- **[Ejemplo heredado, extracto de `IV/SVG03.Adaptacion.xhtml`]** Añadir dentro de `defs` del SVG y conservar el `font-family` correspondiente en sus textos:

```xml
<defs>
  <style type="text/css">
    @font-face { font-family:Baskerville; font-style:normal; font-weight:normal; src:url(../Fonts/Baskerville.ttf); }
  </style>
</defs>
```

- `font-face-src`/`font-face-uri` es otra solución SVG heredada del manual, no la única ni una exigencia. Las rutas se resuelven desde el propio SVG; extraído sin fuente puede descuadrarse.
- **[Compatibilidad heredada]** Sigil puede solapar texto SVG aunque el lector lo muestre bien. Texto rotado había funcionado en lectores de prueba, pero fallaba intermitentemente en Kobo: no darlo por resuelto.
- Limpiar datos de editor/metadatos problemáticos y IDs duplicados; no borrar IDs aún referenciados. Convertir texto fluido (`flowRoot`, `flowRegion`, `flowPara`) a texto normal/trazados: eliminarlo sin conversión podría perder contenido.
- **[Incertidumbre de fuente]** Un pasaje propone enlazar bitmaps y añadir sus archivos al EPUB; otro propone base64 dentro del SVG. No imponer una de las dos opciones como regla universal; verificar recursos, peso y lectores.
- **[ePL]** No imponer fuente incrustada a todo el cuerpo salvo necesidad de maquetación. El manual exige archivos probados/aprobados y distingue versiones del mismo nombre: no afirmar aprobación sin el archivo/listado correspondiente.
- Para familias normal/cursiva/negrita, declarar cada archivo con **igual** `font-family` y su `font-style`/`font-weight` real; así `<i>`/`<b>` seleccionan la variante. Respetar mayúsculas/minúsculas de rutas y extensiones.
- **[Convención de compatibilidad heredada]** Alias de familia sin espacios. No es una restricción general de CSS. Ejemplo de declaración: `@font-face { font-family:"times"; font-style:italic; font-weight:normal; src:url(../Fonts/timesi.ttf); }`.
- **[Compatibilidad heredada]** El base r2.0 incluye `com.apple.ibooks.display-options.xml` para fuentes en iBooks; conservar/comprobar el recurso del base, no asumir que una herramienta ausente lo reparará.
- **[Recomendación]** No recortar fuentes automáticamente sin revisar glifos: el manual detectó pérdidas con subconjuntos. Tras añadir texto, repetir cobertura; preservar espacio U+0020, inseparable U+00A0 y glifos/control básicos que enumera.
- Las afirmaciones sobre fallos de FontForge y superioridad de FontLab son históricas; no constituyen una selección obligatoria de herramientas actuales.

## Incertidumbres que el agente debe conservar

- `max-height:%` aparece en recetas pese a su advertencia de incompatibilidad; no prometer ajuste vertical automático.
- `IV/GIMPImagen.xhtml` menciona CMYK para vectoriales, pero `IV/SVG01.CreacionSVG.xhtml` exige RGB en la salida: seguir RGB en este perfil.
- No hay aquí una matriz vigente de lectores, fuentes aprobadas ni límites exactos en bytes. Contrastar el EPUB objetivo; validar y revisar visualmente tablas, poemas, pies y SVG con fuente grande antes de afirmar portabilidad.
