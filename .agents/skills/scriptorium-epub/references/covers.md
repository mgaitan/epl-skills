# Adaptar una cubierta y colocar el símbolo ePL

Herramienta local: [`../scripts/cover.py`](../scripts/cover.py). No obtiene portadas ni modifica EPUB, metadatos o CSS. No sobrescribe archivos existentes. Usa Python ≥3.12 y Pillow ≥13,<14, instalados por uv. **No necesita Photocraft, PSD, GIMP, Photoshop, Poppler ni ImageMagick.** El símbolo transparente ya está incluido.

## Uso

Desde la raíz del checkout; ajustar el prefijo a la ubicación real de la skill:

```sh
uv run --no-build -p 3.12 --script .agents/skills/scriptorium-epub/scripts/cover.py original.png cover.jpg
uv run --no-build -p 3.12 --script .agents/skills/scriptorium-epub/scripts/cover.py original.png cover-grande.jpg --size 1200x1800 --position top-left --logo-color white --background '#202020' --logo-width 18% --margin 4%
```

Si falta uv, seguir `runtime.md`; uv puede descargar Python y dependencias. Las imágenes se procesan localmente y no se envían a servicios. `--no-build` evita asumir compiladores del sistema: si no hay wheel compatible, elegir una alternativa o informar el bloqueo.

- Destino nuevo `.jpg` o `.jpeg`; dentro del EPUB debe llamarse `cover.jpg`. El directorio de destino debe existir. Nunca se sobrescribe, ni siquiera con entrada/salida iguales, enlaces simbólicos o una creación concurrente del destino.
- `--size 600x900|1200x1800`: dos tamaños 2:3; por defecto 600×900.
- `--fit contain|crop`: **contain por defecto**, conserva toda la imagen y centra sobre fondo negro. `--background` admite un color opaco, p. ej. `white` o `#f0eee8`. **crop es optativo**, recorta por el centro y siempre genera advertencia; puede quitar títulos/autor.
- `--position bottom-right|bottom-left|top-right|top-left`: por defecto abajo a la derecha. No hay reconocimiento de texto ni elección automática del rincón.
- `--logo-width 18%`: ancho proporcional a la cubierta. `--margin 4%`: distancia al borde como porcentaje de cada eje, no porcentaje del logo. Se rechazan dimensiones/márgenes que no caben.
- `--logo-color auto|black|white`: por defecto `auto`. Compara contraste blanco/negro con la luminancia sRGB lineal local, ponderada por el alfa del símbolo. No garantiza contraste en cada píxel de fondos heterogéneos. Colores forzados con contraste medio <4,5:1 producen aviso; ese umbral es una heurística local, no una norma ePL.
- `--logo ruta.png`: recurso alternativo opcional, sujeto a revisión. El incluido se resuelve desde `cover.py`, no desde el directorio actual. Rechaza logos sin transparencia real o vacíos; recorta márgenes transparentes y conserva un píxel de borde. Recolorea RGB manteniendo el canal alfa.
- `--quality 92`: calidad fija por defecto, submuestreo 4:4:4, codificación optimizada **no progresiva**, RGB con perfil sRGB. No baja automáticamente la calidad para lograr un peso arbitrario.

Aplica orientación EXIF y retira esos metadatos del destino. Convierte ICC a sRGB mediante la biblioteca incluida en Pillow; un perfil inválido da error. Sin ICC asume sRGB en RGB/grises; CMYK sin ICC avisa de conversión aproximada. Rechaza fuentes de varias páginas/fotogramas.

Las ampliaciones generan aviso: no recuperan detalle. Un JPEG de más de **300000 bytes** avisa, no se recomprime automáticamente. El informe posterior detalla dimensiones, bytes, caja/posición, color, contraste y decisiones; advertencias por stderr. Errores devuelven 2; éxito con o sin avisos, 0.

**Revisión visual imprescindible:** título/autor, superposición del símbolo, fondos mixtos, marcas previas, color y calidad/peso. No identifica ni elimina logos editoriales. Con cubierta 1200×1800, ajustar por separado el `viewBox` y dimensiones de la imagen SVG en `cubierta.xhtml`. No modificar `epl.css`.

Si la cubierta de origen trae una marca editorial, no la tapes colocando encima el logo ePL. Retírala solo si puede restaurarse el fondo sin alterar título, autor u obra gráfica y si el uso de la cubierta lo permite; en fondos planos puede bastar una reparación local. Si no puede quitarse limpiamente, busca otra cubierta permitida o deja esa incidencia pendiente. Revisa la imagen final, no solo el informe de `cover.py`.

## Marca incluida y procedencia

`../resources/epl-logo.png` contiene **solo el símbolo ePL, sin la leyenda «epubLibre» y sin fondo**: RGBA **471×314**, 19872 bytes; bbox alfa `(1, 1, 470, 313)`, cuatro bordes transparentes.

SHA-256 del PNG:

```text
6b53c7186a726083572ebfc8ca1aefa8b46cde3a758996f3fdc8a679b9277e79
```

Procede del objeto vectorial incrustado en el PSD `EPL_logoBlancoNegro.psd` aportado al preparar la skill, SHA-256 `1c2df5873359215e8768c2aac785ffece45969b622d68da4aa9a356eea501a7d`. Ese objeto tenía símbolo **y** leyenda; no se añadió texto nuevo. Se separó el símbolo por la franja transparente entre ambas partes y se recortó al alfa, conservando un píxel de borde.

En la preparación original se utilizaron Photocraft para extraer el vector y un renderizador PDF para rasterizarlo. Son **antecedentes de procedencia, no dependencias del runtime**. El PSD y los temporales no se distribuyen ni se necesitan para generar cubiertas. No se modificó el EPUB base: su logo de portadilla se conserva según la plantilla y es un recurso distinto.

La procedencia no acredita por sí sola licencia ni aprobación ePL. No se impone que todas las variantes históricas de la marca sean iguales: esta selección usa el símbolo solo para las cubiertas generadas.

## Tests

```sh
uv run --isolated -p 3.15 --with=pytest --with=pillow pytest .agents/skills/scriptorium-epub/scripts/test_cover.py -q
```

Funciones pytest con `tmp_path`: alfa/bordes del recurso, recoloreado, contraste local, posiciones, contain/crop, avisos, orientación/perfiles, JPEG y protección de originales/destinos. La prueba de recursos usa el PNG incluido y no requiere el PSD ni aplicaciones externas.
