# ePL Scriptorium Skill

Skill para agentes que preparan, maquetan y revisan libros **EPUB2 según el perfil Scriptorium / ePubLibre**, desde PDF, escaneos, DOCX, HTML, texto u otro EPUB.

Incluye el **ePub Base r2.1**, criterios operativos extraídos de los manuales I–IV, metadatos, notas bidireccionales, navegación, composición de portada y comprobaciones locales. No es una conversión de un clic: exige cotejar integridad, formato y datos contra la fuente.

## Instalar con npx

Desde el proyecto donde quieras trabajar:

```sh
npx skills add mgaitan/epl-scriptorium-skill --skill scriptorium-epub
```

El instalador permite elegir los agentes de destino. Para instalación global:

```sh
npx skills add mgaitan/epl-scriptorium-skill --skill scriptorium-epub -g
```

La CLI [`skills`](https://github.com/vercel-labs/skills) requiere Node.js/npm para **instalar**; no son dependencias de ejecución de esta skill. Si no usás npx, copiá el directorio completo [`.agents/skills/scriptorium-epub/`](.agents/skills/scriptorium-epub/) al directorio de skills compatible con tu agente, conservando sus recursos y scripts. La entrada es [`SKILL.md`](.agents/skills/scriptorium-epub/SKILL.md).

## Requisitos de ejecución

**Solo se presupone `uv`.** Gestiona el intérprete Python ≥3.12 y las dependencias declaradas en cada script mediante PEP 723; no hace falta instalar Python, pip o paquetes globalmente.

Si falta `uv`, el agente debe indicarlo e instalarlo en ámbito de usuario cuando las políticas del entorno lo permitan, siguiendo la [documentación oficial de Astral](https://docs.astral.sh/uv/getting-started/installation/index.md). En Linux/macOS, el comando oficial es:

```sh
curl -LsSf https://astral.sh/uv/install.sh | sh
```

Es un instalador remoto: revisar procedencia/script antes de ejecutarlo y solicitar aprobación si el entorno la exige. Hay alternativas oficiales para Windows y otros gestores. No se utiliza `sudo` ni se eluden restricciones de red.

- La primera ejecución puede descargar Python y paquetes; preparar las cachés antes si se necesita operar offline.
- Las portadas se procesan con **Pillow vía uv**. El símbolo ePL transparente ya está incluido: no se necesita PSD, Photocraft, GIMP, Photoshop ni ImageMagick.
- Para conversión, se recomiendan bibliotecas gestionadas por uv; no se presuponen Pandoc, Poppler, LibreOffice ni Tesseract.
- **Docker o Java/JAR son opcionales**, solo para ejecutar EPUBCheck. El auditor local no los necesita.

Ver [runtime y herramientas](.agents/skills/scriptorium-epub/references/runtime.md).

## Ejemplos de prompts

> Convertí `novela.pdf` a un EPUB2 con el estándar Scriptorium/ePL. Usá la plantilla incluida, preservá cursivas y notas, y cotejá la integridad. Como todavía no tengo ficha ePL, nombrá el borrador con `[dev]`. No subas el documento a servicios externos.

> Maquetá `ensayo.docx` según ePubLibre. Conservá imágenes, tablas y notas al pie; completá los metadatos solo con información verificable y preguntame por los datos imprescindibles que falten.

> Revisá `libro.epub` contra el perfil ePL sin modificar el original. Informá errores estructurales, alertas tipográficas y comprobaciones pendientes. Ejecutá EPUBCheck con Docker si está disponible.

> Prepará una portada ePL a partir de `portada-original.jpg`, en 600×900, sin recortar el título ni el autor. Añadí solo el símbolo ePL, con posición y color que contrasten, y mostrámela antes de incorporarla al EPUB.

> Buscá una cubierta para la edición con este ISBN en Open Library. Verificá edición, resolución y condiciones de reutilización antes de adaptarla; no elijas automáticamente la primera coincidencia.

> Corregí los enlaces de ida y vuelta de las notas y regenerá los índices de este proyecto ePL. Conservá el UUID del libro y volvé a comprobar el EPUB empaquetado.

## Qué incluye

| Componente | Función |
| --- | --- |
| `resources/epub-base-epl-r2.1.epub` | Plantilla original, inmutable. |
| `resources/epl-logo.png` | **Solo el símbolo** ePL, transparente, sin la leyenda «epubLibre». |
| `resources/genres.json` | Taxonomía de géneros/subgéneros extraída del manual. |
| `resources/manual-regex.json` | Alertas publicadas, con fuentes, intención y límites. |
| `scripts/epub.py` | Iniciar, empaquetar y auditar sin autocorrecciones. |
| `scripts/navigation.py` | Regenerar NCX e índice HTML desde los encabezados. |
| `scripts/cover.py` | Ajustar cubierta 2:3 y añadir el símbolo con contraste configurable. |

Las referencias detallan [metadatos y nombres](.agents/skills/scriptorium-epub/references/metadata.md), [reglas editoriales y notas](.agents/skills/scriptorium-epub/references/editorial.md), [código avanzado](.agents/skills/scriptorium-epub/references/advanced.md), [conversión](.agents/skills/scriptorium-epub/references/conversion.md), [portadas](.agents/skills/scriptorium-epub/references/covers.md) y [fuentes de cubiertas](.agents/skills/scriptorium-epub/references/cover-sources.md).

Los manuales completos y el PSD usado durante la preparación **no se versionan**. El bundle no depende de ellos para funcionar.

## Comandos de desarrollo

Estos ejemplos parten de un checkout; si la skill fue instalada en otro sitio, el agente resuelve la ruta desde su `SKILL.md`. Los destinos deben ser nuevos.

```sh
uv run --script .agents/skills/scriptorium-epub/scripts/epub.py init trabajo/libro
# Completar contenido, metadatos y recursos de la copia antes de continuar.
uv run --script .agents/skills/scriptorium-epub/scripts/navigation.py trabajo/libro
uv run --script .agents/skills/scriptorium-epub/scripts/epub.py pack trabajo/libro trabajo/libro.epub
uv run --script .agents/skills/scriptorium-epub/scripts/epub.py check trabajo/libro.epub --json
```

Cubierta, con Python y Pillow autogestionados y sin compilación local:

```sh
uv run --no-build -p 3.12 --script .agents/skills/scriptorium-epub/scripts/cover.py portada-original.jpg portada-epl.jpg --position bottom-right --logo-color auto
```

Se conserva toda la imagen por defecto; el recorte es optativo. El script no detecta texto ni elimina marcas previas. La revisión visual sigue siendo necesaria.

### EPUBCheck con Docker

```sh
uv run --script .agents/skills/scriptorium-epub/scripts/epub.py check trabajo/libro.epub --epubcheck-docker --json
```

Usa **EPUBCheck 5.4.0**, con la imagen de terceros `yamamotoatshoeisha/epubcheck:epub5.4.0_jdk27` **fijada por digest**, no `latest`. Se comprobó la versión y una validación real de la plantilla. Es más reciente que `kitforbes/epubcheck:5.1.0`; no es una imagen oficial W3C.

El contenedor no es interactivo, no tiene red y monta **solo el EPUB, de lectura**. El daemon puede descargar la imagen la primera vez. La imagen seleccionada es `linux/amd64`; no se asume compatibilidad nativa ARM ni se configura emulación. Se puede indicar otra imagen verificada o usar `--epubcheck` con un JAR local. Ver [EPUBCheck](.agents/skills/scriptorium-epub/references/epubcheck.md).

### Pruebas

```sh
uv run --isolated -p 3.15 --with=pytest --with=pillow pytest .agents/skills/scriptorium-epub/scripts -q
```

Tests como funciones pytest, sin `unittest`, con archivos temporales. CI ejecuta la suite en Python **3.12 y 3.15**. Los tests de Docker simulan el proceso y no requieren daemon ni red.

## Conversión de PDF y otros formatos

Se recomienda evaluar **[AnyDoc](https://github.com/firecrawl/anydoc)** como extractor local con su binding Python `firecrawl-anydoc`, instalado mediante uv. La [referencia de conversión](.agents/skills/scriptorium-epub/references/conversion.md) incluye recetas comprobadas para Markdown y assets, además de alternativas como pypdf, PyMuPDF y Mammoth.

- Markdown es un intermedio, **no un EPUB ePL terminado**; hay que conservar imágenes, énfasis, estructura y reconstruir notas.
- PDF escaneado requiere una estrategia OCR. AnyDoc local no lo resuelve por sí solo.
- El modo OCR alojado de AnyDoc puede enviar **el documento completo** a Firecrawl Parse. Nunca se activa automáticamente: requiere consentimiento explícito y evaluar privacidad, cuota y costos.
- Columnas, tablas, versos, fórmulas y texto incierto deben cotejarse con la fuente.

## Alcance y límites

- Nombre normal: `Apellido, Nombre - Titulo [EPL_ID] (r1.0).epub`. `[dev]` se admite como **convención local de borrador**, no como ID de ficha ni dato OPF.
- El `.ini` mencionado por los manuales es un catálogo de **búsquedas guardadas de Sigil**. El manual I §3.3.1 indica pedirlo al revisor de la candidatura junto con su guía; no se aportó y no se conoce aquí una descarga pública verificada.
- El auditor ejecuta 24 búsquedas literales del manual; dos patrones PCRE se informan como omitidos por incompatibilidad con `re`. No se presenta como reemplazo del `.ini` completo, ePLValidator ni EPUBCheck.
- Pasar comprobaciones no demuestra fidelidad del texto, permisos de distribución, compatibilidad con todos los lectores ni aprobación de ePubLibre.
- Esta skill no publica libros en el sitio ni sube originales a servicios automáticamente.

## Procedencia y recursos de terceros

Basada en los manuales Scriptorium I r3.1 y II–IV r3.0, y el ePub Base r2.1 aportados para este proyecto. Las huellas, citas y límites están en [fuentes](.agents/skills/scriptorium-epub/references/sources.md). No se afirma que representen la normativa web vigente.

La plantilla y la marca mantienen su procedencia ePL; este repositorio no pretende relicenciarlas ni implica afiliación o aprobación del proyecto. Verificar condiciones de reutilización de cada recurso y de los libros, traducciones, cubiertas y fuentes que se incorporen. Disponibilidad pública no equivale a dominio público.
