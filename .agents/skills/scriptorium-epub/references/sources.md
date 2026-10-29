# Fuentes, procedencia y alcance del bundle

## Ediciones usadas

Proyecto Scriptorium / ePubLibre; archivos aportados en este proyecto. Las referencias indican capítulos internos `OEBPS/Text/…` para trazabilidad; **no es necesario instalar los manuales originales junto con la skill**.

| Fuente | Revisión | EPL ID | SHA-256 del EPUB original |
| --- | --- | --- | --- |
| Aprende a maquetar I: Manual básico | r3.1 | 2398 | `2e5b9ce44574bfbbce1cec3cdf727acc0a6cf0ec803e046ba3ff6fbec18fe838` |
| Aprende a maquetar II: Herramientas útiles | r3.0 | 46603 | `6e3a41bb85a75ef9209fda2d3f4896f70fc98e1e97acd7be9c9706d7e0abad8c` |
| Aprende a maquetar III: Código avanzado | r3.0 | 46604 | `8e1dd17524d06d1a76d006eecb387d319a9ec1ac831410a236c8b707663de363` |
| Aprende a maquetar IV: Imágenes y gráficos SVG | r3.0 | 46605 | `49aa12577b335c03a15a51cecbb25df055e53e2740579bff4ca76195709c5c32` |
| ePub base ePL, plantilla incluida en `../resources/epub-base-epl-r2.1.epub` | r2.1 | 2653 | `bc2d570be7174f7dd8a6fadba58bf925570949f38decd913a286f2f1a3e38940` |

El EPUB base se conserva byte a byte. Su `OEBPS/Styles/epl.css` tiene SHA-256 `d8752523c52a22826433fe5ca7b5ad4969e473ca489efce23a0c1b38234ea532`.

El símbolo transparente `../resources/epl-logo.png`, **sin leyenda**, procede del vector interno del PSD `EPL_logoBlancoNegro.psd` aportado durante la preparación. `covers.md` documenta selección del símbolo, huellas y verificación de alfa. El runtime usa solo el PNG mediante Pillow/uv, no necesita PSD, Photocraft ni renderizadores externos. Los manuales completos y PSD fueron excluidos del repositorio; sus nombres y huellas se conservan únicamente como procedencia.

## Criterio de extracción

- Se conservan reglas editoriales y técnicas que necesita un agente para producir o revisar un EPUB: identidad, páginas normalizadas, estructura, estilos, notas, navegación, tipografía, recursos, compatibilidad y comprobaciones.
- Se excluyen tutoriales de interfaces, instalación de programas, publicación en la web, magnet-links y teoría de regex para principiantes.
- Las instrucciones de extracción/OCR y las heurísticas locales se identifican como adaptaciones operativas, no como algoritmos oficiales de ePL.
- No se reproducen los cuatro manuales dentro del bundle: referencias resumidas, catálogo de alertas, taxonomía y plantilla bastan para trabajar offline, salvo consultas bibliográficas y descarga opcional de cubiertas.
- No hay `.ini` oficial de búsquedas, ePLValidator, diccionario oficial completo, fuentes aprobadas ni matriz vigente de lectores dentro de los archivos recibidos. Los scripts no simulan esos recursos ni afirman su aprobación.
- Varias reglas y diagnósticos son históricos, contradictorios o específicos de lectores antiguos. Se documentan discrepancias y se usa la estructura de la plantilla real; no se atribuyen a EPUB universal ni a normativa web vigente.

## Reproducción técnica

El único gestor/runtime supuesto es uv; puede instalar Python ≥3.12 cuando haga falta. `runtime.md` indica cómo instalar uv si está ausente y cómo autogestionar bibliotecas sin asumir aplicaciones de sistema. `conversion.md` contiene recetas locales de extracción de PDF y documentos, y `epubcheck.md` los backends opcionales JAR/Docker. Los scripts usan Python ≥3.12, `pathlib.Path`, shebang `uv run --script` y metadatos PEP 723. Auditor, empaquetador y navegación usan stdlib; la composición de cubierta usa Pillow. La primera ejecución de `uv` puede descargar intérprete/dependencias: no envía el contenido de los libros. Para uso sin red, preparar antes el intérprete y su caché de dependencias.

Tests funcionales pytest desde un checkout, usando el intérprete pedido:

```sh
uv run --isolated -p 3.15 --with=pytest --with=pillow pytest .agents/skills/scriptorium-epub/scripts -q
```

`--with=pillow` es necesario al incluir los tests de portadas. Para solo auditor y navegación basta `--with=pytest`. Las pruebas crean publicaciones temporales; no validan derechos ni fidelidad editorial de un libro real.

El empaquetador no sobrescribe destinos, rechaza enlaces simbólicos y entradas inseguras y usa límites de seguridad de 32 MiB por miembro, 256 MiB total y 10000 entradas. Son límites operativos **locales**, no requisitos EPUB ni ePL. La navegación valida antes de escribir y reemplaza por archivo con rollback ante errores de E/S, no una transacción global resistente a cortes.

## Distribución y derechos

La estructura `.agents/skills/scriptorium-epub/` es portable y autocontenida, pero eso **no acredita licencia de redistribución** de recursos de terceros. En OPF y créditos de las fuentes inspeccionadas no se identificó una licencia explícita aplicable al bundle. No se añade una licencia global que pretenda relicenciar la plantilla, la marca ni los manuales. Antes de publicar el bundle, comprobar los permisos/condiciones de plantilla y logo y conservar su procedencia.

Tampoco se deducen permisos sobre libros, traducciones, cubiertas o fuentes por estar disponibles públicamente. La marca EPL no implica aprobación o afiliación de la skill. La procedencia web de cubiertas y sus condiciones se documentan por archivo, según `cover-sources.md`.
