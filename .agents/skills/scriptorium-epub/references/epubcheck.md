# EPUBCheck local: JAR o Docker opcional

`epub.py check` ejecuta el auditor ePL de solo lectura. **No requiere Docker ni
Java** salvo que se pida explícitamente EPUBCheck. El runtime habitual sigue
siendo `uv`; el auditor usa únicamente la biblioteca estándar de Python ≥3.12.
EPUBCheck comprueba el formato EPUB, no certifica el perfil editorial ePL,
derechos, integridad del texto ni presentación en lectores.

## Invocación

Desde la raíz del checkout; en una instalación portable, sustituir el prefijo
por la ubicación real de la skill. Colocar las opciones después del libro:

```sh
# Auditor local solamente: no consulta ni ejecuta Docker.
uv run --script .agents/skills/scriptorium-epub/scripts/epub.py check trabajo/libro.epub --json

# Docker con la imagen predeterminada fijada por digest.
uv run --script .agents/skills/scriptorium-epub/scripts/epub.py check trabajo/libro.epub --epubcheck-docker --json

# Imagen alternativa bajo responsabilidad de quien la selecciona.
uv run --script .agents/skills/scriptorium-epub/scripts/epub.py check trabajo/libro.epub --epubcheck-docker example.org/epubcheck:version --json

# Alternativa existente: Java y JAR local verificado; no descarga el JAR.
uv run --script .agents/skills/scriptorium-epub/scripts/epub.py check trabajo/libro.epub --epubcheck /ruta/epubcheck.jar --json
```

`--epubcheck-docker [IMAGE]` sin valor utiliza `DEFAULT_EPUBCHECK_IMAGE`.
`--epubcheck JAR` y `--epubcheck-docker` son mutuamente excluyentes: combinarlos
es un error de uso (código 2). No hay cambio automático de backend ni fallback
silencioso a una comprobación sin EPUBCheck.

## Versión, procedencia y arquitectura

La investigación aportada para esta integración identifica **EPUBCheck 5.4.0**,
publicado el **2026-09-15**, como la versión actual; la imagen kitforbes 5.1.0
(2023) no es el valor predeterminado. Referencias:

- Proyecto EPUBCheck: <https://github.com/w3c/epubcheck>.
- Release: <https://github.com/w3c/epubcheck/releases/tag/v5.4.0>.
- Fuente de la imagen de terceros:
  <https://github.com/shoeisha-books/docker_epubcheck>.
- Dockerfile consultado en `main`:
  <https://github.com/shoeisha-books/docker_epubcheck/blob/main/Dockerfile>.
- Registro: <https://hub.docker.com/r/yamamotoatshoeisha/epubcheck>.

Referencia predeterminada completa:

```text
yamamotoatshoeisha/epubcheck:epub5.4.0_jdk27@sha256:c69bb8ea600157e774b7682b15f9a3d49f7d6b45c187966ca95fa4d04c3dc503
```

Es una imagen **de terceros, no una imagen oficial de W3C/EPUBCheck**. El
Dockerfile investigado usa `openjdk:27-ea-jdk-slim`, sitúa el JAR en
`/app/target/epubcheck.jar`, declara `WORKDIR /data` y utiliza el entrypoint
`/app/entrypoint.sh` que pasa los argumentos al validador. El script aprovecha
ese contrato pasando solamente `/data/book.epub` a la imagen. Una imagen
alternativa debe aceptar el mismo argumento; no se reemplaza su entrypoint.
`main` es una fuente mutable, no una garantía de correspondencia reproducible
con todos los bytes del artefacto fijado.

El índice del digest indicado ofrece actualmente **solo `linux/amd64`**. El
script no añade `--platform`, no configura emulación y no cambia de imagen ni
actualiza el digest automáticamente. Ante una incompatibilidad de arquitectura,
revisar el error de Docker y elegir explícitamente una imagen compatible y
verificada o un JAR local; no asumir una ejecución nativa en ARM. La emulación
que ya tuviera configurada el entorno Docker es ajena al script.

El digest fija el contenido solicitado aunque cambie el tag, pero **no garantiza
licencia, seguridad, firma, procedencia del build ni ausencia de vulnerabilidades**.
Revisar también el runtime Java EA y las licencias del conjunto. Actualizar esta
selección exige revisar versión, fuente, arquitectura y nuevo digest; no usar
`latest` como sustitución silenciosa.

## Descarga y aislamiento

Se requiere un cliente y un daemon Docker accesibles, solo al optar por esta
modalidad. `docker run` puede descargar la imagen en el primer uso: el daemon
contactará el registro y sus servicios de distribución y consumirá red y disco.
`--network none` desactiva la red **del contenedor**, no la descarga del daemon.
El libro no se envía a un servicio de validación, pero se entrega a código de
terceros dentro del contenedor; el daemon/host Docker debe ser de confianza.
Con contextos remotos, la ruta del bind corresponde al host del daemon; el
script no copia archivos ni configura ese host.

La ejecución usa una lista de argumentos con `shell=False`, sin `-i` ni `-t`:

- `--rm`, `--network none`, `--read-only`.
- `--cap-drop ALL` y `--security-opt no-new-privileges`.
- Un `tmpfs` limitado a 64 MiB en `/tmp` para temporales de Java
  (`rw,nosuid,nodev`).
- **Un solo bind de archivo**, `book.resolve()` → `/data/book.epub`, de solo
  lectura. No monta el directorio padre, otros libros ni el socket Docker.
- `--mount` se construye con `csv.writer`: conserva espacios, comas y comillas
  del nombre del archivo. Dentro del contenedor se usa siempre el nombre fijo.
- El separador `--` precede la imagen; imagen y rutas nunca se interpretan como
  comandos de shell. Las referencias vacías o que comienzan por `-` se rechazan.

El límite es **300 segundos** para Docker, incluida una eventual descarga, y
120 segundos para Java/JAR. Un timeout es un fallo, nunca una validación
satisfactoria. Terminar el cliente por timeout no garantiza que el daemon haya
parado inmediatamente el contenedor; `--rm` lo elimina cuando este termine.
Si persiste una ejecución, inspeccionarla en el daemon antes de repetirla.

## Informe y códigos de salida

- `epubcheck` conserva `command`, `returncode`, `stdout`, `stderr` y `completed`
  cuando se intenta lanzar el proceso. `completed: true` significa que terminó,
  **no** que pasó la validación: también debe tener `returncode: 0`.
- Un ejecutable ausente, error de permisos o timeout produce `completed: false`
  y `error`; los timeouts conservan la salida parcial disponible. Fallos previos
  al lanzamiento, como JAR inexistente o imagen vacía, pueden no tener `command`
  ni `returncode`.
- Un código distinto de cero, incluidos los errores del daemon, del pull, de
  arquitectura o de validación, añade un hallazgo `error` con código `EPUBCHECK`.
  El contador de errores coincide con los hallazgos, para ambos backends.
- Solo una ejecución terminada con código **0** retira `EPUB_SCHEMA` de los
  controles pendientes. No elimina errores locales ni otros pendientes y
  `compliance_certified` permanece siempre en `false`.
- Si la entrada es ilegible/insegura y el auditor emite `ALL_CHECKS`, no se llama
  a ningún validador externo; `epubcheck` explica la omisión. El hallazgo `INPUT`
  ya hace fallar la comprobación, sin duplicarlo como fallo del validador.
- `check` devuelve 1 si hay errores, o también ante alertas con `--strict`;
  devuelve 0 en caso contrario. Un cero no es certificación editorial.

## Pruebas sin servicios externos

```sh
uv run --with=pytest pytest .agents/skills/scriptorium-epub/scripts/test_epubcheck.py -q
uv run --with=pytest --with=pillow pytest .agents/skills/scriptorium-epub/scripts -q
```

Las pruebas son funciones pytest y simulan `subprocess.run`: no instalan ni
invocan Java/Docker, no necesitan daemon y no hacen pulls. Comprueban comandos,
CSV del bind, selección de backend, errores y coherencia del informe. No
sustituyen una prueba real de la imagen y del daemon en la arquitectura destino.
