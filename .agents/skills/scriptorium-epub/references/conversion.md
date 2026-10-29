# Conversión de fuentes: extracción local antes de maquetar

## Contrato y elección

- Único runtime/gestor supuesto: **uv**; Python **>=3.12**, obtenible con uv. No presuponer Python del sistema, Node/npm/npx, Cargo ni compilación de Rust.
- Conserva los originales sin modificar ni borrar. Trabaja en destinos nuevos, preferentemente fuera del proyecto; registra edición, SHA-256, herramienta/versión y correspondencia de páginas/pasajes.
- **AnyDoc es extracción, no maquetación ePL**. Su Markdown GFM es un intermedio revisable, no un EPUB ni XHTML listo para el ePub Base. No confundir ausencia de excepciones con fidelidad editorial.
- PDF textual: prueba primero capa de texto y orden de lectura. PDF escaneado/mixto: AnyDoc local **no hace OCR**; no encadenar automáticamente un servicio remoto.
- MOBI/AZW: AnyDoc no anuncia estos formatos. Si `ebook-convert` de Calibre ya está instalado, puede producir un EPUB intermedio para extraer estructura y recursos; no instales Calibre silenciosamente ni entregues esa conversión sin reconstruirla sobre ePub Base. Revisa créditos y páginas finales para corregir metadatos internos incompletos o erróneos.
- DOCX, DOC/RTF, ODT, HTML o EPUB de entrada: conservar estructura, énfasis y recursos verificables; no heredar sin revisión CSS, metadatos ni notas del origen. AnyDoc no anuncia HTML como formato de entrada.

## AnyDoc: binding Python y wheels

Consulta del **2026-10-29**: `firecrawl-anydoc==0.2.4`, importación `anydoc`; PyPI declara Python >=3.10, pero esta receta mantiene el mínimo de la skill en 3.12.
PyPI ofrece siete wheels **`cp310-abi3`**, no wheels específicas `cp312`/`cp315`: macOS x86_64/arm64, Linux manylinux y musllinux x86_64/aarch64, Windows amd64.
La ABI estable permite su selección en CPython 3.12 y 3.15 convencionales; se comprobó importación/conversión en ambos en Linux x86_64 glibc. No generalizar a PyPy, free-threaded, otras arquitecturas o cualquier libc.

```sh
uv run --help
uv pip install --help
uv run --no-project --no-config --no-build -p 3.12 --with firecrawl-anydoc==0.2.4 python -c 'import anydoc; from importlib.metadata import version; print(version("firecrawl-anydoc"))'
uv run --no-project --no-config --no-build -p 3.15 --with firecrawl-anydoc==0.2.4 python -c 'import anydoc; from importlib.metadata import version; print(version("firecrawl-anydoc"))'
```

Ayuda comprobada con **uv 0.13.4**: `uv run` admite `--no-build`, no `--only-binary`.
`uv pip install` sí admite **`--only-binary :all:`** (con dos puntos; `all` no es el selector global); `--no-build` es su alias.
Para un entorno explícito, sustituye `/ruta/temporal` por un directorio externo real y nuevo:

```sh
uv venv --no-config -p 3.12 /ruta/temporal/venv312
uv pip install --no-config --python /ruta/temporal/venv312/bin/python --only-binary :all: firecrawl-anydoc==0.2.4
```

La ruta `bin/python` es POSIX; en Windows usa la ruta real del intérprete del entorno.
Si no hay wheel compatible, **detener y elegir otra alternativa**, no quitar la restricción ni instalar un compilador por defecto.
uv puede reutilizar wheels cacheadas de compilaciones anteriores; aquí se contrastaron las wheels publicadas en PyPI. La primera ejecución puede descargar Python/paquetes: eso no autoriza subir documentos.
`--no-project --no-config` evita adoptar dependencias/configuración del checkout; uv utiliza sus cachés externas. No hace falta instalar globalmente ni crear scripts nuevos.

## Receta local: Markdown más assets, nunca solo texto si hay imágenes

Ejemplo POSIX desde el directorio de trabajo: sustituye `entrada.docx` por la fuente real (también PDF textual) y `extraccion-nueva` por un destino inexistente.
Se convierte sin `ocr="hosted"`; los errores se propagan y no activan red como fallback.

```sh
uv run --no-project --no-config --no-build -p 3.12 --with firecrawl-anydoc==0.2.4 python - entrada.docx extraccion-nueva <<'PY'
from hashlib import sha256
from importlib.metadata import version
from pathlib import Path
import json
import sys
import anydoc

source, out = map(Path, sys.argv[1:])
data = source.read_bytes()
fmt = anydoc.format_from_bytes(data)
markdown = anydoc.to_markdown(source)
model = None if fmt == "pdf" else anydoc.to_document(data)
out.mkdir(parents=True, exist_ok=False)
(out / "texto.md").write_text(markdown, encoding="utf-8")
records = []
if model is not None:
    assets = out / "assets"
    assets.mkdir()
    extensions = {"image/png": ".png", "image/jpeg": ".jpg",
                  "image/gif": ".gif", "image/svg+xml": ".svg"}
    for asset in model.assets:
        name = f"asset-{asset.id:04d}{extensions.get(asset.media_type, '.bin')}"
        target = assets / name
        target.write_bytes(asset.data)
        records.append({"id": asset.id, "media_type": asset.media_type,
                        "origin_part": asset.origin_part,
                        "file": target.relative_to(out).as_posix(),
                        "sha256": sha256(asset.data).hexdigest()})
report = {"source": str(source.resolve()), "sha256": sha256(data).hexdigest(),
          "anydoc": version("firecrawl-anydoc"), "format": fmt,
          "assets": records, "pdf_assets_pending": fmt == "pdf"}
(out / "extraccion.json").write_text(
    json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(out.resolve())
PY
```

- `to_markdown(Path(...))`, `to_markdown_bytes(data)` y `to_document(data)` fueron comprobados. El último devuelve objetos tipados con `blocks`, `notes` y `assets`, **no un dict**.
- Para imágenes incrustadas, el Markdown puede contener **solo el texto alternativo**; la imagen no queda preservada por guardar `.md`. `asset.data` conserva bytes, `media_type` su MIME, `origin_part` su procedencia e `id` su identidad.
- La receta conserva assets, pero no inserta imágenes automáticamente. Recorre los bloques/inlines del modelo, incluidas tablas/listas/notas: una imagen con `source.kind == "asset"` se relaciona por `source.asset_id` con ese registro. Conserva posición, alt y pie antes de construir XHTML.
- No deduzcas orden ni posición por el nombre del asset; puede haber reutilizaciones. Para `source.kind == "unavailable"`, registra la pérdida. Las URL externas no son recursos autocontenidos: no descargarlas sin revisar permisos/privacidad.
- Los assets también pueden ser objetos incrustados, no imágenes. No ejecutarlos ni incrustar `.bin` en el EPUB; verificar MIME real, formato permitido y necesidad editorial. No usar `origin_part` como ruta de salida.
- **PDF no tiene modelo `Document` en 0.2.4**: `to_document(pdf)` da `UnsupportedError`. El Markdown de PDF no garantiza extraer ilustraciones; inventaría imágenes y extráelas/renderízalas por separado, con procedencia y cotejo visual.
- `NeedsOcrError.pages` identifica páginas que necesitan OCR; detener, registrar y escoger estrategia. Registrar asimismo `EncryptedError`, `MalformedError`, `ResourceLimitError`, `MissingPartError`, `UnsupportedError` u `OSError`; no disfrazarlos de extracción vacía ni saltarse páginas.

## OCR alojado: exclusivamente con consentimiento explícito

AnyDoc local lee texto, **no reconoce escaneos**. Con `ocr="hosted"`, al necesitar OCR el binding puede enviar a Firecrawl Parse **EL DOCUMENTO ENTERO**, no únicamente `NeedsOcrError.pages`: el servicio no ofrece selección de páginas en esta vía.
Antes de activarlo, explicar destino, documento completo, confidencialidad/derechos, límites y posibles costos, y obtener autorización explícita para esa subida. No basta el pedido genérico «convertí este libro» ni que exista una key.
El README anuncia uso sin registro con límites; no prometer gratuidad o disponibilidad. Puede necesitar `api_key` o `FIRECRAWL_API_KEY` para mayores límites y consumir cuota/créditos. No guardar secretos en código, informes ni EPUB.
La llamada documentada es `anydoc.to_markdown(source, ocr="hosted")`; es **opcional y no fue ejecutada**. Revisar términos, tarifas y API de la versión instalada antes de usar parámetros adicionales. `HostedError` no autoriza reintentos/subidas automáticas.

## Alternativas locales, según el problema

No instalar todas: usa la mínima suficiente. Versiones siguientes comprobadas en CPython 3.12/Linux, no certificadas en 3.15 ni para todos los documentos.

**pypdf 6.21.4**: extracción textual PDF en Python puro, sin Poppler; no OCR, renderizado ni reconstrucción fiable de énfasis/columnas. Ejemplo que conserva límites de página por separado, sin escribir sobre fuentes:

```sh
uv run --no-project --no-config --no-build -p 3.12 --with pypdf==6.21.4 python -c 'from pathlib import Path; import sys; from pypdf import PdfReader; r=PdfReader(Path(sys.argv[1])); print("\n\f\n".join(p.extract_text() or "" for p in r.pages))' entrada.pdf
```

Una página vacía en la salida exige inspección, no omisión silenciosa. Para cotejos extensos guarda cada página y un mapa externo de procedencia.

**PyMuPDF 1.26.7**: renderizado local si existe wheel; tiene código nativo, no es Python puro. Ejemplo de primera página a 144 dpi en un directorio nuevo; no activa OCR:

```sh
uv run --no-project --no-config --no-build -p 3.12 --with pymupdf==1.26.7 python -c 'from pathlib import Path; import sys, pymupdf; out=Path(sys.argv[2]); out.mkdir(parents=True, exist_ok=False); doc=pymupdf.open(Path(sys.argv[1])); doc[0].get_pixmap(dpi=144).save(out / "pagina-001.png"); doc.close()' entrada.pdf render-nuevo
```

No usar la última versión sin revisar dependencias/licencia y wheels: esta prueba no obliga a actualizar. Renderizar crea una imagen de cotejo, **no texto OCR** ni necesariamente el recurso original de una figura.

**mammoth 1.13.0**: alternativa DOCX→HTML semántico; revisar estilos, imágenes y avisos. No produce XHTML ePL ni HTML seguro para servir directamente sin sanitización:

```sh
uv run --no-project --no-config --no-build -p 3.12 --with mammoth==1.13.0 python -c 'from pathlib import Path; import sys, mammoth; p=Path(sys.argv[1]); f=p.open("rb"); r=mammoth.convert_to_html(f); f.close(); print(r.value); print(r.messages, file=sys.stderr)' entrada.docx
```

**Docling/OCR local**: opción deliberada para escaneos/layout complejo, no default. Puede requerir modelos descargados, dependencias nativas, almacenamiento, RAM/CPU/GPU y configuración de idiomas; comprobar versiones, backend, wheel y red antes de instalar. No se probó aquí y no garantiza fidelidad.
Herramientas del sistema **solo si están disponibles**: comprobar `shutil.which(...)` antes de invocar. Nunca asumir `photocraft`, Pandoc, Poppler (`pdftotext`/`pdftoppm`), Tesseract, LibreOffice ni Java. Una wheel de PyMuPDF no implica disponer de Tesseract.

## Cotejo editorial y paso al ePub Base

1. **Integridad**: inventario de páginas/capítulos, inicios/finales y continuidad de todos ellos; cotejar faltantes, duplicados, caracteres/ligaduras, guiones, cabeceras y pies. Un hash prueba identidad del archivo, no calidad de extracción.
2. **Énfasis y estructura**: contrastar cursivas/negritas, superíndices, títulos, diálogos, versos, listas, separadores y enlaces. No convertir toda línea corta en encabezado ni reconstruir énfasis por conjetura.
3. **Columnas y lectura**: cotejar visualmente columnas, recuadros, pies y notas marginales; no confiar en el orden serializado ni reproducir columnas impresas que impidan reflujo.
4. **Tablas/fórmulas**: cotejar filas, celdas combinadas, encabezados, unidades, signos, índices y fracciones. Markdown/LaTeX o HTML emitido no son soporte matemático ePL terminado; decidir XHTML/SVG/imagen accesible según `advanced.md` y comprobar en lectores.
5. **Imágenes**: comparar cantidad, ubicación, alt/pies, resolución y recortes; mapear assets a `OEBPS/Images`, referencias XHTML y manifiesto OPF. No sustituir la ilustración por su alt ni borrar recursos sin investigar.
6. **Notas**: reconstruir el **grafo ePL**, no copiar `[^1]` como texto: llamada con `id="rf1"` y enlace a `notas.xhtml#nt1`, destino `id="nt1"` y retorno al capítulo `#rf1`. Mapear `note_ref.note_id` a `Document.notes` cuando exista; verificar números, llamadas repetidas y párrafos completos. Ver `SKILL.md` y `editorial.md`.
   - Al extraer MOBI con Calibre, inspecciona también superíndices Unicode (por ejemplo `¹`) en el cuerpo y marcadores de retorno como `[←1]` en las notas: el conversor puede conservarlos como texto plano y perder los hipervínculos. Vincula llamada y nota solo cuando el número y el contexto coincidan sin ambigüedad; si no, registra la incidencia y no adivines la ubicación.
7. Adaptar solo contenido cotejado a una **copia del ePub Base**: capítulos XHTML, jerarquía real, `epl.css` intacto, estilos propios en `style.css`, metadatos y navegación. Seguir `metadata.md`, `advanced.md` y `checks.md`; generar índices, empaquetar y auditar con los scripts existentes, más EPUBCheck si disponible.
8. Registrar externamente incertidumbres con página/pasaje, evidencia, decisión y pendiente: texto ilegible, nota sin destino, figura perdida o fórmula dudosa. No inventar soluciones, ocultar pérdidas ni introducir marcas de trabajo en el EPUB. Validación técnica no sustituye cotejo ni revisión visual.

## Comprobaciones y límites de esta receta

- Smoke en temporal externo `/tmp/epl-conversion-4uyno7rm`, sin documentos del usuario ni llamadas hosted: uv 0.13.4, AnyDoc 0.2.4, CPython **3.12.13 y 3.15.0**, Linux x86_64/glibc; selección/instalación sin compilación obligatoria.
- DOCX sintético con negrita, cursiva, nota y PNG: texto/énfasis/nota presentes, un asset con bytes idénticos y MIME/procedencia; PDF sintético textual: inicio/final presentes. PDF de solo imagen: `NeedsOcrError.pages == [1]` en ambos Python.
- El PDF textual de prueba salió con líneas marcadas como encabezados: evidencia de que la extracción necesita revisión. No se midió calidad sobre libros, columnas, tablas, fórmulas ni PDFs mixtos/encriptados; no extrapolar este smoke.
- También se comprobaron `uv pip install --only-binary :all:` en entorno 3.12, extracción pypdf, HTML/énfasis Mammoth y render PyMuPDF. No se probó OCR, lectores EPUB ni conformidad ePL mediante esta conversión.

## Fuentes consultadas

- [AnyDoc README](https://github.com/firecrawl/anydoc#readme): formatos, límites PDF/OCR y subida completa.
- [Binding Python](https://github.com/firecrawl/anydoc/blob/main/python/README.md) y stubs de la wheel 0.2.4: API/modelo/assets, PDF sin `Document`; `main` puede evolucionar respecto a esa release.
- [PyPI 0.2.4](https://pypi.org/project/firecrawl-anydoc/0.2.4/#files) y [metadatos JSON](https://pypi.org/pypi/firecrawl-anydoc/0.2.4/json): requisito Python y etiquetas de wheels; ayuda local de uv para flags. Sin usar benchmarks comerciales como garantía editorial.
