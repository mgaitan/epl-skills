# scriptorium-epub

Skill para crear, maquetar, convertir y revisar **EPUB2 con el perfil Scriptorium/ePubLibre**. Incluye ePub Base r2.1, referencias resumidas de los cuatro manuales y utilidades para índices, portadas, empaquetado y comprobaciones. No es una conversión de un clic ni acredita aprobación del sitio.

Entrada para el agente: [`SKILL.md`](.agents/skills/scriptorium-epub/SKILL.md).

## Instalar

```sh
gh skills install mgaitan/epl-skills scriptorium-epub --allow-hidden-dirs --agent universal
# Alternativa:
npx skills add mgaitan/epl-skills --skill scriptorium-epub
```

Con GitHub CLI, `--scope user` instala para todos los proyectos; con npx, `-g`. `gh skills` está en preview. Para instalar manualmente, copiá el directorio completo `.agents/skills/scriptorium-epub/` —incluidos `SKILL.md`, scripts, referencias y recursos— a la ubicación de skills compatible con tu agente.

## Requisitos

Solo **uv**; obtiene Python y las dependencias PEP 723. Compatibilidad Python ≥3.12, probado también en 3.15. No requiere GIMP, Photoshop, Photocraft, Calibre, Pandoc ni un Python preinstalado. Pillow procesa las portadas; el símbolo transparente ya está incluido.

Si falta uv, consultar [Astral](https://docs.astral.sh/uv/getting-started/installation/index.md) y [runtime](.agents/skills/scriptorium-epub/references/runtime.md). La instalación en ámbito de usuario puede necesitar red/aprobación; no usar sudo ni eludir políticas del host.

## Prompts

> Convertí `novela.pdf` a EPUB2 ePL con la plantilla incluida. Preservá cursivas y notas; no inventes texto ilegible ni datos bibliográficos. No subas el original a servicios externos.

> Maquetá `ensayo.docx` según Scriptorium, conservando ilustraciones, tablas y notas. Dejá el borrador como `[dev]` si todavía no hay ficha ePL.

> Revisá este EPUB sin modificar el original. Informá errores, alertas tipográficas y pendientes; ejecutá EPUBCheck si está disponible.

> Prepará la portada 600×900 sin recortar autor/título y añadí solo el símbolo ePL, en una posición y color que contrasten.

## Flujo técnico

Ejemplos desde la raíz de un checkout; si se instaló en otra ubicación, resolver el prefijo desde esta carpeta. Los destinos deben ser nuevos:

```sh
uv run -p 3.15 --script .agents/skills/scriptorium-epub/scripts/epub.py init trabajo/libro
# Reemplazar contenido/recursos de ejemplo y completar metadatos.
uv run -p 3.15 --script .agents/skills/scriptorium-epub/scripts/navigation.py trabajo/libro
uv run -p 3.15 --script .agents/skills/scriptorium-epub/scripts/epub.py pack trabajo/libro trabajo/libro.epub
uv run -p 3.15 --script .agents/skills/scriptorium-epub/scripts/epub.py check trabajo/libro.epub --json
```

`init` genera UUID nuevo; en revisiones del mismo libro, conservar el UUID. No modificar `epl.css`. El empaquetador no verifica que los ejemplos se hayan sustituido; el auditor no reescribe contenido ni aplica reemplazos globales.

Cubierta con Pillow autogestionado, sin compilación local:

```sh
uv run --no-build -p 3.15 --script .agents/skills/scriptorium-epub/scripts/cover.py original.jpg cover-nueva.jpg --position bottom-right --logo-color auto
```

Preserva toda la imagen por defecto; el recorte es optativo. El logo es **solo el símbolo**, sin leyenda y sin fondo. No detecta texto ni elimina marcas anteriores: revisar superposición, color, resolución y peso. Actualizar por separado el SVG/viewBox al cambiar dimensiones de la cubierta en el EPUB.

### EPUBCheck

```sh
uv run -p 3.15 --script .agents/skills/scriptorium-epub/scripts/epub.py check trabajo/libro.epub --epubcheck-docker --json
```

Opción Docker con EPUBCheck 5.4.0 en imagen de terceros fijada por digest, no `latest`. No es una imagen oficial W3C; está seleccionada para `linux/amd64`, sin emulación automática. Monta solo el EPUB de lectura y sin red del contenedor; el daemon puede descargar la imagen. También admite `--epubcheck` con Java/JAR local. Ver [protocolo y límites](.agents/skills/scriptorium-epub/references/epubcheck.md).

## Referencias

- [Reglas editoriales y notas bidireccionales](.agents/skills/scriptorium-epub/references/editorial.md).
- [Metadatos OPF y nombre de archivo](.agents/skills/scriptorium-epub/references/metadata.md).
- [Código avanzado, tablas, versos, imágenes, SVG y fuentes](.agents/skills/scriptorium-epub/references/advanced.md).
- [Conversión PDF/DOCX/etc., AnyDoc y alternativas vía uv](.agents/skills/scriptorium-epub/references/conversion.md).
- [Componer portadas](.agents/skills/scriptorium-epub/references/covers.md) y [encontrar cubiertas](.agents/skills/scriptorium-epub/references/cover-sources.md).
- [Comprobaciones y catálogo regex](.agents/skills/scriptorium-epub/references/checks.md).
- [Fuentes, versiones y derechos de recursos](.agents/skills/scriptorium-epub/references/sources.md).

Nombre externo: `Apellido, Nombre - Titulo [EPL_ID] (r1.0).epub`. `[dev]` es una convención local de borrador, no un ID de ficha ni dato para OPF. Conservar ortografía real dentro del libro.

## Límites

El `.ini` completo de búsquedas guardadas de Sigil no se recibió. El manual I §3.3.1 indica pedirlo al revisor con su guía; no se conoce aquí una descarga pública verificada. El auditor conserva 24 búsquedas literales y dos regex PCRE omitidas por incompatibilidad con `re`, además de checks propios identificados. No sustituye el `.ini`, ePLValidator, EPUBCheck ni cotejo editorial/visual.

AnyDoc es un extractor local, no maquetador ePL. Su OCR alojado puede enviar **el documento entero** y nunca se activa sin consentimiento. Columnas, fórmulas, imágenes y notas requieren revisión contra el original.

## Tests

```sh
uv run --isolated -p 3.15 --with=pytest --with=pillow pytest .agents/skills/scriptorium-epub/scripts -q
```

Pruebas funcionales con recursos del bundle y archivos temporales. No necesitan los manuales originales, PSD, Docker, Java ni cuentas ePL. Un resultado técnico satisfactorio no prueba derechos, fidelidad del texto ni compatibilidad de todos los lectores.
