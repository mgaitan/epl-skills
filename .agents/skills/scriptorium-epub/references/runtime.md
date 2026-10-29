# Runtime portable y herramientas autogestionadas

## Único requisito de ejecución: uv

No presuponer Python del sistema, entornos virtuales, aplicaciones gráficas, Node,
Pandoc, Calibre, LibreOffice, Photocraft, Poppler, Tesseract, Java ni Docker.
La instalación por `npx skills` usa Node/npm **solo como instalador**; el runtime
habitual de la skill usa `uv` y Python ≥3.12, que uv descarga si hace falta.

1. Comprueba `uv --version` con la herramienta de terminal del agente.
2. Si falta, anuncia la instalación y usa las instrucciones oficiales de
   [Astral](https://docs.astral.sh/uv/getting-started/installation/index.md).
   Instala en ámbito de usuario, sin `sudo`, si las políticas del entorno permiten
   descargar y ejecutar el instalador. Si requiere aprobación, solicítala; si no
   se permite red o instalación, explica el bloqueo, no simules haber ejecutado
   scripts ni asumas un Python incompatible.
3. El instalador es código remoto: verifica el dominio oficial y, cuando sea
   posible, descarga e inspecciona el script antes de ejecutarlo. No copies
   instaladores de blogs o mirrors desconocidos.

Comando oficial Linux/macOS, si hay `curl` y shell POSIX:

```sh
curl -LsSf https://astral.sh/uv/install.sh | sh
```

Alternativa oficial con `wget`:

```sh
wget -qO- https://astral.sh/uv/install.sh | sh
```

En Windows, con PowerShell disponible:

```powershell
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

El instalador puede modificar perfiles de shell/PATH. Comprueba su salida y vuelve
a ejecutar `uv --version`; si la sesión no recoge el PATH, invoca el binario por
la ruta real que informó, sin inventar un directorio. No hace falta instalar
Python manualmente, pip global ni entornos en el proyecto. Si el usuario fijó
`UV_PYTHON_DOWNLOADS=never` u otra política de red, no la eludas.

## Ejecución y descarga de dependencias

Los scripts tienen shebang `uv run --script` y dependencias PEP 723:

- `epub.py` y `navigation.py`: stdlib.
- `cover.py`: Pillow, instalado aisladamente por uv.
- Tests: pytest, más Pillow para las portadas.

Para elegir un intérprete con wheels ampliamente disponibles, añade `-p 3.12`;
no hace falta usar Python 3.15 para operar la skill aunque CI pruebe esa versión.
Al instalar bibliotecas nativas opcionales, usa `--no-build` para no depender de
compiladores o cabeceras del sistema. Ejemplo desde el checkout:

```sh
uv run --no-build -p 3.12 --script .agents/skills/scriptorium-epub/scripts/cover.py original.png cover.jpg
```

Si no existe wheel compatible, no instales un toolchain sin avisar: selecciona
otra biblioteca/versión compatible o informa la limitación. La primera ejecución
puede descargar Python y paquetes; los archivos del libro se procesan localmente.
No equivale a autorizar una API de OCR remota. Para uso offline, prepara antes
intérprete y cachés; no prometas funcionar sin red en un host recién instalado.

## Gráficos, PDF y validación externa

- **Portadas y ajustes raster:** `cover.py`/Pillow vía uv. El símbolo ePL
  transparente ya está incluido: no extraerlo de nuevo, no buscar el PSD ni
  requerir Photocraft. Una herramienta usada al preparar un recurso no es una
  dependencia del usuario final.
- **Renderizar PDF para cotejar:** PyMuPDF vía uv con wheel compatible, según
  `conversion.md`. No asumir `pdftoppm` ni ImageMagick.
- **Entrada PSD u otro formato gráfico futuro:** evaluar lectores de Python
  gestionados por uv, por ejemplo `psd-tools`, y comprobar compatibilidad/fidelidad
  antes de elegirlos. No instalar aplicaciones de escritorio como requisito.
- **OCR:** elegir deliberadamente backend local/modelos y sus recursos; no
  afirmar que instalar una biblioteca instala Tesseract o resuelve todo escaneo.
- **EPUBCheck:** Docker o Java/JAR son opciones detectadas, no requisitos
  generales. Ver `epubcheck.md`; no instalar Docker/daemon, Java global ni pedir
  privilegios de administrador silenciosamente. Si no están disponibles y no se
  autoriza instalarlos, informar EPUBCheck pendiente.

Solo usa herramientas de sistema adicionales tras comprobar su disponibilidad.
Para scripts nuevos, conserva Python ≥3.12, PEP 723 y `pathlib.Path` para todas
las rutas, sin `os.path`; evita añadir dependencias si la stdlib ya resuelve el
problema.
