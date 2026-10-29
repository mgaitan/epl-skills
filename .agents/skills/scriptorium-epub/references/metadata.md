# Metadatos, identidad y nombre de archivo

Aplicar junto con `editorial.md` §§2, 3 y 8. Perfil: ePub Base r2.1 / EPUB2; no extrapolar sintaxis OPF2 a EPUB3.

## Dónde va cada dato

`content.opf` usa namespaces `http://www.idpf.org/2007/opf` y `dc=http://purl.org/dc/elements/1.1/`; los atributos `opf:*` pertenecen al namespace OPF. XML siempre escapa `&` como `&amp;`.

| Dato | Campo OPF2 | Coherencia / criterio |
| --- | --- | --- |
| Título | `dc:title` | Título en el idioma del libro, concordante con `.ttitulo` en `titulo.xhtml` y `docTitle` NCX. Conservar tildes. |
| Autor | `dc:creator`, `opf:role="aut"`, `opf:file-as` | Nombre bibliográfico; ordenación `Apellido(s), Nombre(s)` salvo excepciones verificadas. No usar el orden invertido como visualización automáticamente. Concordar con `.tautor`. |
| Idioma | `dc:language` | Etiqueta del contenido, normalmente `es`; `xml:lang` en XHTML y pasajes de otro idioma. No copiar el idioma del catálogo si corresponde a otra traducción. |
| Traductor | `dc:contributor`, `opf:role="trl"`, `opf:file-as` | Solo si es traducción; cotejar crédito. `Desconocido` solo cuando la traducción existe pero no se identifica a su traductor, no como sustituto de investigar. |
| Sinopsis | `dc:description` | Texto sin etiquetas, concordante con `sinopsis.xhtml`. Los títulos en cursiva se convierten en comillas angulares según el manual. No generar una sinopsis engañosa de texto no leído. |
| Género/subgéneros | `dc:subject` | Un género + 1–5 subgéneros de `../resources/genres.json`, separados por comas. No incluir el tipo Ficción/No Ficción. |
| Editorial digital | `dc:publisher` | `ePubLibre` según este perfil; no confundir con la editorial de la edición impresa. No implica aprobación del sitio. |
| Publicación original | `dc:date opf:event="publication"` | Primera publicación de la obra en idioma original, no traducción ni edición escaneada. Año verificado; mes/día convencional solo si se documenta como tal. |
| Revisión digital | `dc:date opf:event="modification"` | Fecha de modificación del EPUB, no la de la obra original. Mantener la fecha de firma en `titulo.xhtml` actualizada. |
| Identidad del libro | `dc:identifier id="BookId" opf:scheme="UUID"` | `urn:uuid:` + UUID propio. `package@unique-identifier="BookId"`; mismo valor en NCX `dtb:uid`. Conservar al revisar el mismo libro. |
| Ficha ePL | `dc:identifier opf:scheme="EPL"` | ID numérico real de la ficha. No ISBN, no UUID, no `[dev]`, no número inventado. Si falta, omitir campo en borrador y registrar pendiente. |
| Revisión del libro | `dc:identifier opf:scheme="revision"` | `1.0` en OPF, `r1.0` en archivo, `ePub r1.0` en portadilla. No cambiar el `ePub base r2.1` de créditos. |
| Serie / volumen | `meta name="calibre:series" content="…"`, `meta name="calibre:series_index" content="…"` | Solo si corresponde; ambos coherentes con portadilla. Retirar los valores `Serie`/`1` de muestra si no aplica. |
| Imagen de portada | `meta name="cover" content="…"` | `content` es **ID del item del manifest**, no una ruta; el item debe apuntar a `Images/cover.jpg` con tipo `image/jpeg`. |

Los créditos de título original, ilustración, cubierta, edición digital y versión del base van además en `info.xhtml`. No confundas datos de colaboradores reales con alias de la plantilla. Otras contribuciones OPF son opcionales según el manual; si se incluyen, completa su ordenación.

## Nombre de archivo

**Sin serie ni alias del editor**, la forma de los manuales es:

```text
Apellido, Nombre - Titulo [EPL_ID] (r1.0).epub
```

El ejemplo de la captura del usuario tiene la estructura:

```text
Proust, Marcel - El escandalo Lemoine [85598] (r1.0).epub
```

Esto ilustra el formato; no verifica el ID, la revisión o los datos bibliográficos de ese libro.

**Convención local de desarrollo de esta skill**, aceptada para trabajar sin ficha:

```text
Apellido, Nombre - Titulo [dev] (r1.0).epub
```

- `[dev]` significa **borrador local**, no campo normalizado ni ID de ePL. No se copia a `dc:identifier opf:scheme="EPL"`.
- No exige marcar el título interno como «dev» ni inventar datos pendientes. El auditor avisará que falta EPL-ID; conservar ese aviso pendiente, no «arreglarlo» con ceros.
- Antes de una entrega destinada al catálogo, sustituir `[dev]` por el ID real y sincronizar OPF. Preparar localmente no implica subir ni publicar.
- En el **nombre externo**, transliterar tildes y `ñ` según la pauta del manual; conservar ortografía real dentro del EPUB. No renombrar al usuario ni eliminar tildes del texto.
- Si hay serie/colección, varios autores, idioma distinto o ediciones anotadas/ilustradas, aplicar variantes de `editorial.md` §8. El alias del editor tras revisión es opcional.
- `r0.x` es el perfil de candidatura descrito en los manuales, no sinónimo obligatorio de `[dev]`. No afirmar estado de candidatura sin intervención del sitio.

## Antes de cerrar

1. Contrastar fuente original, ISBN/edición y traductor; separar datos de obra y edición. Los catálogos son evidencia auxiliar, no autoridad infalible.
2. Retirar metadatos de muestra no pertinentes, incluyendo la versión histórica de Sigil si no describe el proceso real.
3. Sincronizar OPF, páginas fijas, revisión y fechas; regenerar los índices con `navigation.py`.
4. Ejecutar auditor y EPUBCheck cuando esté disponible. La comprobación sintáctica no verifica que un nombre, fecha, sinopsis o traductor sean verdaderos.

Procedencia: manual I r3.1, `OEBPS/Text/3.1.2.Metadatos.xhtml`, `3.1.4.Basico.xhtml`, `3.1.5.Generos.xhtml`, `3.3.5.Revision.xhtml`, `4.1.NombrarArchivo.xhtml`, y plantilla base r2.1. `[dev]` es una convención **local**, no se atribuye al manual.
