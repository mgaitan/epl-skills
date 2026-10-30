---
name: scriptorium-epub
description: "Usar para crear, maquetar, convertir, corregir o validar libros EPUB según Scriptorium/ePubLibre (ePL), incluido convertir un PDF, escaneo, DOCX, HTML, texto u otro EPUB al ePub Base. Activar ante pedidos de EPUB ePL, notas/índices/metadatos con ese estándar o comprobaciones tipográficas de sus manuales. No usar para EPUB genérico sin perfil ePL ni para subir libros a epublibre.org."
---

# Crear un EPUB Scriptorium / ePubLibre

Produce un libro **EPUB2 redistribuible y refluible**, adaptado al ePub Base incluido, no una conversión mecánica ni una reproducción de páginas de un PDF. Trabaja localmente; no necesita cuenta ePL ni programas gráficos.

## Entorno antes de empezar

Solo se presupone **uv**, no Python instalado ni aplicaciones gráficas. Comprueba `uv --version`; si falta, anuncia e instala en ámbito de usuario siguiendo `references/runtime.md` y la documentación oficial de Astral, con aprobación si el entorno la requiere. uv gestiona Python ≥3.12 y las dependencias PEP 723. No asumas Photocraft, GIMP, Pandoc, Poppler, Tesseract, Java ni Docker. Para gráficos usa Pillow vía uv y el símbolo ya incluido; no reextraigas el logo del PSD. Herramientas del sistema son opcionales, previa detección, nunca un requisito silencioso.

## Contrato y recursos

- Resuelve los caminos desde **el directorio de este `SKILL.md`**. El bundle completo es portable: no necesita los manuales originales ni archivos del repositorio de origen.
- Usa `resources/epub-base-epl-r2.1.epub` como plantilla inmutable. No la reconstruyas ni edites. La base determina la estructura real y prevalece sobre erratas de los manuales.
- Lee `references/editorial.md` antes de crear o revisar un libro y `references/metadata.md` para mapear datos al OPF y nombrar el entregable. Consulta `resources/genres.json` para catalogarlo, sin inventar etiquetas.
- Lee `references/advanced.md` solo para tablas, versos, imágenes, SVG, fuentes o estilos especiales.
- Para obtener una cubierta, consulta `references/cover-sources.md` (Open Library y alternativas, verificación de edición y permisos). Para adaptarla y colocar la marca transparente incluida, usa `scripts/cover.py` siguiendo `references/covers.md`.
- Lee `references/checks.md` antes de interpretar alertas. `resources/manual-regex.json` conserva los patrones publicados, sus fuentes y advertencias; no es el `.ini` oficial completo.
- `references/sources.md` documenta versiones, huellas, alcance y limitaciones de distribución. No afirmes que estos manuales son la normativa web vigente.
- No conviertas a EPUB3 sin que se pida explícitamente: el código incluido soporta EPUB2; para EPUB3 hace falta otra plantilla/perfil y navegación `nav` apropiada.

## 1. Relevar fuente y datos

1. Identifica archivo(s), idioma(s), edición, integridad, orden de capítulos, notas, imágenes y derechos/permisos comunicados. Conserva los originales sin modificar.
2. Obtén de la fuente título, autor y ordenación, título original, año de primera publicación original, traductor cuando corresponda, sinopsis, género/subgéneros, serie/volumen, cubierta y créditos reales. Diferencia esos datos del alias del editor digital y de la revisión del EPUB.
3. Busca primero en los archivos aportados. Pregunta solo por ambigüedades que impiden decidir; no adivines traductor, fechas, texto ilegible, EPL-ID ni permisos de colaboradores. Puedes preparar un borrador con incidencias **externas al EPUB**, sin rellenar hechos desconocidos con ficción.
4. Un EPUB local no requiere publicar en ePL. Si no hay ficha, deja pendiente el EPL-ID real y comunícalo; no uses un identificador ajeno para silenciar una alerta.

## 2. Extraer, cotejar y limpiar

Lee `references/conversion.md` para elegir bibliotecas gestionadas por uv. AnyDoc puede extraer PDF textual y documentos con su binding Python; Markdown es solo un intermedio y no conserva automáticamente los bytes/posición de imágenes. Guarda assets y coteja estructura y notas. Ante escaneos, no actives su OCR alojado automáticamente: puede subir el documento completo y requiere autorización explícita.

- **PDF textual**: comprueba la calidad y el orden de la capa de texto en páginas representativas. Extrae localmente con las herramientas disponibles; conserva correspondencia con páginas para cotejar. No asumas que el orden de extracción de columnas es el de lectura.
- **PDF escaneado / imágenes**: usa OCR del idioma correcto. Comprueba orientación, dobles páginas, notas y caracteres dudosos contra la imagen. No envíes el contenido a servicios externos sin autorización.
- **Solo si detectas OCR de baja calidad o se pide limpiar texto OCR**, consulta `references/ocr-cleanup.md`: guiones de corte, folios/cabeceras, segmentación y correcciones con cotejo. No la cargues como lectura inicial. La limpieza no autoriza modernizar, parafrasear, borrar variantes regionales/de época ni inventar texto ilegible.
- **MOBI/AZW**: si Calibre ya está disponible, puede servir para extraer a un EPUB intermedio; no uses ese EPUB como entregable sin adaptarlo a la base. Contrasta sus metadatos con los créditos impresos/digitales de la obra.
- **DOCX/RTF/ODT/HTML/EPUB**: importa texto, estructura, énfasis y recursos; trata su XHTML/CSS como material de entrada, no como maquetación ePL terminada. Texto plano exige reconstruir solo estructura verificable.
- Retira cabeceras/pies y paginación impresa repetidos sin borrar texto significativo. Une líneas y deshace guiones de fin de línea solo con evidencia; preserva párrafos, diálogos, versos, énfasis, listas, notas y cambios de escena.
- Coteja inicio/final y continuidad de todos los capítulos, pasajes ambiguos, llamadas de nota, ilustraciones y tablas. No sustituyas errores OCR con una reescritura plausible de la obra.
- Mantén un registro externo de incidencias con archivo, página/pasaje, problema y decisión; no incrustes marcas de trabajo ni informes en el libro entregable.

## 3. Iniciar y adaptar el ePub Base

Ejemplos desde la raíz de un checkout que contiene esta skill; si fue instalada en otro sitio, sustituye el prefijo por **su ruta real**. `trabajo/libro` debe ser un directorio nuevo. Todos los scripts tienen shebang `uv run --script` (PEP 723)

```sh
uv run --script .agents/skills/scriptorium-epub/scripts/epub.py init trabajo/libro
```

- `init` extrae una copia y genera un UUID nuevo sincronizado en OPF/NCX. El contenido de ejemplo **sigue siendo ejemplo**: completa/reemplaza todos los textos, imágenes y metadatos de prueba. En revisiones del mismo libro conserva su UUID.
- Mantén las primeras cuatro entradas del `spine`: `cubierta.xhtml`, `sinopsis.xhtml`, `titulo.xhtml`, `info.xhtml`. Adapta las páginas normalizadas y conserva el logo EPL ya incluido en la portadilla. No añadas fuentes/imágenes propias a esta página.
- No modifiques **ningún byte de `epl.css`**. Añade o modifica reglas en `style.css`; enlaza primero `epl.css` y luego las hojas necesarias. No dejes atributos `style` ni bloques CSS dentro del XHTML. Los estilos internos de SVG constituyen un caso separado.
- Pon cada capítulo en un XHTML; usa jerarquía global `h1`→`h2`→… sin saltos, no niveles elegidos por apariencia. Las partes pueden ser `h1` y sus capítulos `h2`. Conserva unidades lógicas al subdividir archivos grandes.
- Usa las clases de la base antes de crear otras. Marca cambios de escena con `hr`; no simules espacio con BR repetidos ni espacios/párrafos vacíos. Permite que el lector ajuste fuente y tamaño.
- Nombres internos sin espacios, tildes ni caracteres especiales; texto y metadatos conservan su ortografía. Usa UTF-8, namespace XHTML y `xml:lang`; prefiere caracteres Unicode o entidades numéricas para evitar depender de DTD remotas.
- Reemplaza `cover.jpg`: JPEG 2:3, 600×900 a 1200×1800; adapta `viewBox` y dimensiones de la imagen SVG. Identifícala en OPF mediante `meta name="cover"` apuntando al ID de manifiesto.
- Para componer la cubierta, ejecuta `uv run --script .agents/skills/scriptorium-epub/scripts/cover.py original.png trabajo/libro/OEBPS/Images/cover-nueva.jpg` y, tras revisarla, sustituye el ejemplo `cover.jpg` por el resultado. `cover.py` no sobrescribe archivos: no lo apuntes al `cover.jpg` ya extraído. Por defecto conserva toda la imagen, añade el logo sin fondo y elige blanco/negro por contraste local; posición y color se pueden cambiar. Revisa que no tape título/autor ni duplique una marca ya existente.
- Completa OPF, `titulo.xhtml`, `info.xhtml` y sinopsis coherentemente. Elimina traductor/serie/subtítulo si no aplican; no confíes en que conservar el ejemplo sea neutral. Catalogación: un género y 1–5 subgéneros del mismo tipo, sin incluir «Ficción/No Ficción» en `dc:subject`.
- Si no hay dedicatoria, biografía, notas o fuentes incrustadas, retira sus páginas/recursos opcionales y todas sus referencias en manifiesto, spine, guide, CSS e índices. Si quitas un recurso citado por una regla CSS, adapta o elimina esa regla personal.
- Preserva recursos normalizados, créditos pertinentes y versión de base `r2.1`; la revisión del libro empieza normalmente en `1.0` y es un dato distinto. No declares autorías, aprobación comunitaria ni derechos que no se comprobaron.

## 4. Notas y navegación

Usa el patrón ePL, no notas visualmente parecidas sin navegación:

```xhtml
<a href="../Text/notas.xhtml#nt1" id="rf1"><sup>[1]</sup></a>
```

```xhtml
<div class="nota">
  <p id="nt1"><sup>[1]</sup>Texto de la nota. <a href="../Text/cap01.xhtml#rf1">&lt;&lt;</a></p>
</div>
```

Sincroniza número, identificadores, archivo y retorno. Para notas de varios párrafos coloca el destino en un contenedor que incluya el enlace de retorno. Coteja colocación de llamadas y excepciones en `references/editorial.md`.

Después de completar el OPF y tras cambios de estructura/metadatos, regenera ambos índices:

```sh
uv run --script .agents/skills/scriptorium-epub/scripts/navigation.py trabajo/libro
```

`navigation.py` lee el `spine`, toma `title` del encabezado o su texto sin superíndices, agrega IDs estables si faltan, genera jerarquía NCX/índice HTML y sincroniza BookId y título. Valida antes de escribir, conserva el resto de los XHTML y es idempotente. No repara saltos de jerarquía: corrígelos en la fuente y repite. Genera siempre índice HTML, aun cuando sería opcional en algunos EPUB2. No edites los índices como fuente primaria: deriva sus entradas de los encabezados.

## 5. Empaquetar, comprobar y revisar

Nombra el entregable `Apellido, Nombre - Titulo [EPL_ID] (r1.0).epub`. Sin ficha se permite la **convención local** `[dev]` en el archivo, nunca como EPL-ID en OPF; no confundirla con norma de publicación ePL. Mantén tildes y nombres reales dentro del libro (`references/metadata.md`).

El destino EPUB debe ser nuevo y estar **fuera** del directorio que se empaqueta. Guarda también el informe externo fuera de ese directorio; `pack` empaqueta los archivos que encuentre allí y un informe suelto puede acabar dentro del EPUB:

```sh
uv run --script .agents/skills/scriptorium-epub/scripts/epub.py pack trabajo/libro trabajo/libro.epub
uv run --script .agents/skills/scriptorium-epub/scripts/epub.py check trabajo/libro.epub --json
```

- `pack` produce un ZIP reproducible con `mimetype` primero y sin comprimir. No valida el contenido ni lo declara terminado.
- `check` es de **solo lectura**. Informa errores, advertencias, localización/contexto de patrones y controles omitidos. Las muestras de texto tienen offsets sobre el cuerpo extraído, no líneas del XHTML; las muestras sobre fuente sí tienen línea. No aplica reemplazos del JSON.
- Salida de `check`: **0** sin errores detectados (puede haber alertas y controles pendientes), **1** con errores, o con alertas si usas `--strict`; fallos de uso de `init`/`pack` dan **2**. No equipares un código 0 con conformidad ePL.
- El auditor hace controles implementados del perfil, no todos los enumerados en las referencias: estructura ZIP/XML, manifiesto/spine, recursos y fragmentos, UUID/NCX, metadatos/taxonomía, secciones fijas, `epl.css` intacto, cubierta, notas y búsquedas locales. Valida formación XML, **no esquema XHTML/EPUB completo** ni sintaxis CSS completa.
- El auditor no contrasta semánticamente etiquetas, orden y cobertura de ambos índices contra todos los encabezados; genera los índices con `navigation.py` y revisa esa correspondencia. El informe identifica este control como pendiente.
- Ejecuta EPUBCheck además del auditor: **prioriza el JAR oficial si hay Java utilizable**, con `--epubcheck` y su ruta real. Lee `references/epubcheck.md` para obtener/verificar la distribución oficial 5.4.0 y conservar sus dependencias junto al JAR. **Si no hay Java utilizable**, usa `--epubcheck-docker` con cliente/daemon disponibles y autorizados: la imagen de terceros está fijada por digest para `linux/amd64`, monta solo el EPUB de lectura y no tiene red de contenedor; su descarga inicial sí necesita red. No instales Java o Docker privilegiados silenciosamente ni cambies de backend para ocultar errores de validación. Si no hay backend autorizado, informa «EPUBCheck pendiente», no «validado».
- Se ejecutan 24 búsquedas literales del manual. Dos regex PCRE no son compatibles con `re`; se informan explícitamente como omitidas. No ocultes esta cobertura parcial ni inventes el `.ini` oficial. Las heurísticas adicionales están etiquetadas como locales, no como regex oficiales.
- Revisa **cada alerta** contra el original antes de corregir. Puede haber comillas rectas legítimas, ordinales, semirrayas o asteriscos de la obra. Los 300 kB son un aviso conservador de compatibilidad; los manuales discrepan en alcance/unidad. No amputes contenido para pasar un check.
- Completa revisión ortográfica por idioma y cotejo de integridad. Prueba visualmente, al menos, fuente grande, pantalla estrecha, tablas/poemas, pies, SVG, notas ida/vuelta e índice. Solo afirma pruebas en lectores que realmente se hayan realizado.
- Repite generación de índices, empaquetado y comprobaciones después de corregir. No borres clases de `epl.css` aunque parezcan sin uso.

## Pruebas de la skill

Python mínimo **3.12**. Los tests son **funciones de pytest**, no `unittest`. Desde el checkout:

```sh
uv run --isolated -p 3.15 --with=pytest --with=pillow pytest .agents/skills/scriptorium-epub/scripts -q
```

Pillow solo se necesita para portadas; auditor/navegación usan stdlib. El script opcional `ocr_dehyphen.py` declara `dehyphen` vía PEP 723; sus tests simulan el modelo y no requieren esa biblioteca ni red. El shebang y PEP 723 declaran dependencias por script para ejecución normal con `uv run --script`.

## Entrega

Entrega el `.epub`, ubicación del proyecto editable e informe externo breve con fuente/edición, decisiones, revisión, errores/alertas revisados y pendientes explícitos (datos, EPL-ID, dos regex, EPUBCheck, ortografía o lectores no probados). No publiques ni subas a ePL automáticamente. «Compatible con el perfil documentado» no significa «aprobado por ePubLibre».
