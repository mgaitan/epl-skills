# Conseguir una cubierta y comprobar su procedencia

Esta referencia complementa `covers.md`: primero seleccionar y descargar una imagen adecuada, después adaptarla con `scripts/cover.py`. No se incluyen descargas automáticas ni búsquedas masivas.

## Orden de selección

1. Preferir la cubierta de la **edición realmente usada**, aportada por el usuario o presente en la fuente con calidad suficiente.
2. Buscar por ISBN de esa edición, no solo título/autor. Verificar idioma, subtítulo, volumen, traductor y editorial. No tomar por verdadera una primera coincidencia de buscador.
3. Si no hay cubierta reutilizable adecuada, considerar una composición propia a partir de material con licencia compatible, identificándola como diseño nuevo, sin hacerla pasar por portada histórica.
4. Guardar original y procedencia en el informe externo: URL de página, URL de imagen, ISBN/OLID/edición, fecha de consulta, autor/diseñador y licencia/permiso conocido. No declarar que «está en internet» equivale a permiso de redistribución.

## Open Library (primera alternativa pública)

La [Covers API](https://openlibrary.org/dev/docs/api/covers) permite acceso puntual sin clave, por ISBN, OLID o Cover ID. Patrón:

```text
https://covers.openlibrary.org/b/isbn/{ISBN}-L.jpg?default=false
https://covers.openlibrary.org/b/olid/{EDITION_OLID}-L.jpg?default=false
https://covers.openlibrary.org/b/id/{COVER_ID}-L.jpg?default=false
```

- Sustituir los parámetros por identificadores verificados. `L` pide la variante grande, **no garantiza** 600×900 ni calidad suficiente.
- `?default=false` es importante: devuelve **404** en lugar de la imagen vacía predeterminada. Un HTTP 200 tampoco certifica que la imagen sea la cubierta correcta.
- Si solo se conoce título/autor, consultar la [Search API](https://openlibrary.org/dev/docs/api/search) (`https://openlibrary.org/search.json`) con parámetros codificados, límite pequeño y campos necesarios. `cover_i` identifica una imagen; los resultados por defecto son **obras**, no ediciones. Revisar una edición concreta antes de elegir cubierta.
- No asumir que `first_publish_year` de una coincidencia resuelve el año de la obra o de su traducción; contrastar los metadatos bibliográficos.
- La documentación de Covers prohíbe rastreo masivo. Indica 100 peticiones/IP por 5 minutos para identificadores distintos de Cover ID/OLID; tratar esos números como política consultada, no cuota contractual permanente. Respetar 403/429 y pausas, cachear sin insistir ni variar identificadores para eludir límites.
- Una API pública no concede por sí sola una licencia libre sobre el diseño de cubierta. Revisar derechos y créditos antes de incorporarlo a una distribución.

**No hace falta un script nuevo para una descarga puntual**: el agente puede usar su cliente HTTP con timeout, límites de tamaño y salida a un archivo nuevo. Validar Content-Type, firma/dimensiones de imagen y que no sea HTML, marcador vacío o miniatura; no sobrescribir el original. No enviar el PDF o texto del libro: la consulta transmite solo sus datos bibliográficos.

## Otras fuentes

| Fuente | Cuándo usarla | Precaución |
| --- | --- | --- |
| [Wikimedia Commons](https://commons.wikimedia.org/) | Portadas históricas, escaneos e ilustraciones con ficha de licencia explícita. También material para diseñar una cubierta propia. | Verificar autor, licencia, jurisdicción y atribución del **archivo concreto**; no confundir imágenes de Wikipedia local bajo fair use con Commons. |
| [Biblioteca Digital Hispánica / BNE](https://bdh.bne.es/) | Ediciones españolas digitalizadas e identificación bibliográfica; comprobar si hay cubierta o solo portada interior. | Consultar condiciones del objeto y calidad de la descarga; una portadilla no es necesariamente cubierta exterior. |
| [Gallica / BnF](https://gallica.bnf.fr/) | Ediciones históricas, especialmente francesas. | Condiciones del documento y de reutilización; distinguir cubierta, encuadernación y página de título. |
| [Internet Archive](https://archive.org/) | Escaneos de la edición buscada cuando su acceso/uso está permitido. | No eludir préstamos, acceso restringido ni controles; verificar páginas, resolución y derechos del ejemplar. |
| Editorial o sitio del autor | Cubierta actual de una edición exacta, prensa o material promocional. | Público/promocional no significa libre para redistribución; atender permiso y condiciones. |

No automatizar scraping de tiendas ni eludir restricciones. Otras APIs comerciales pueden exigir claves o imponer condiciones; no son necesarias para el flujo básico.

## Handoff a composición

Una vez seleccionada la imagen, usar `cover.py` con ajuste **contain** por defecto y revisar el resultado. El script coloca únicamente el logo EPL; no borra automáticamente logos previos ni detecta textos, títulos o personas. Ajustar posición/color sin tapar información. Para salida de 1200×1800, actualizar también SVG y `viewBox` de la cubierta en el EPUB.

Fuentes web consultadas: [Open Library Covers API](https://openlibrary.org/dev/docs/api/covers), [Search API](https://openlibrary.org/dev/docs/api/search) y [Commons: Reusing content](https://commons.wikimedia.org/wiki/Commons:Reusing_content_outside_Wikimedia). Las bibliotecas alternativas se recomiendan para evaluación por documento, no como APIs con licencia o disponibilidad garantizadas.
