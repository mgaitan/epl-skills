# Criterios editoriales Scriptorium / EPL

## Alcance y lectura
- Referencia portable basada en los manuales I r3.1 y II r3.0, con reglas autocontenidas: no requiere los EPUB originales de la raíz ni una aplicación concreta. Taxonomía completa en [genres.json](../resources/genres.json); plantilla en [ePub Base r2.1](../resources/epub-base-epl-r2.1.epub).
- **REQ**: obligación/prohibición explícita del estándar editorial EPL descrito en esos manuales; no equivale a requisito universal del formato EPUB.
- **REC**: recomendación, opción o criterio de compatibilidad del manual. **AGENTE**: adaptación operativa propuesta aquí, no mandato textual del manual.
- Las citas `[I-…]` y `[II-…]` identifican al final la procedencia XHTML exacta, no lecturas necesarias para aplicar esta referencia. `[BASE]` identifica la plantilla incluida. Las fuentes pueden contener erratas; véanse las discrepancias.
- Fuera de alcance: expresiones regulares, catálogos de erratas de I §3.3.2, tutoriales de programas, código avanzado de III e imágenes/SVG de IV.

## 1. Estándar y plantilla
Fuentes: [I-01], [I-311], [I-312], [BASE].
- **REQ** del perfil EPL: usar el ePub Base común y respetar sus páginas normalizadas; priorizar limpieza y compatibilidad, no limitarse a convertir el formato.
- **AGENTE**: crear un EPUB no implica publicarlo ni obtener aprobación de EPL. Reservas, admisión de títulos y candidaturas son trámites del sitio [I-04], no requisitos del formato ni comprobaciones de derechos; no condicionan este flujo de creación.
- **REC**: trabajar sobre una copia de `../resources/epub-base-epl-r2.1.epub`, conservando intacta la plantilla incluida. El manual recomienda usar la última versión disponible; esta referencia se verifica contra r2.1.
- **REQ**: respetar la presentación de las páginas normalizadas; no modificar `epl.css`. Guardar el CSS en archivos de `Styles`, no dentro del XHTML.
- Plantilla: `Text` contiene `cubierta.xhtml`, `sinopsis.xhtml`, `titulo.xhtml`, `info.xhtml`, `TOC.xhtml`, `dedicatoria.xhtml`, `Section0001.xhtml`, `autor.xhtml`, `notas.xhtml`; no todos son obligatorios en todo libro.
- `Styles`: `epl.css`, `style.css`, `sgc-toc.css`; `Images`: cubierta, logo, exlibris y recursos que realmente se utilicen. Eliminar `autor.jpg`, `asterisco3.png`, `comilla1.png` y `fuente.png` si no se usan; el nombre de los asteriscos se ha comprobado en [BASE].

## 2. Identidad y metadatos
Fuentes: [I-312], [I-315].
- **REQ**: dar a cada libro nuevo un Book-Id UUID propio; no conservar el UUID de ceros de la plantilla. Hacer copia antes de intervenir en `content.opf`.
- **AGENTE**: conservar ese UUID al revisar el mismo libro; cambiarlo puede hacer que los lectores traten la revisión como otro libro y mantengan ambas copias.
- **REQ**: después de cambiar `content.opf` o añadir, modificar o borrar metadatos, regenerar la TOC para sincronizar también el identificador de `toc.ncx`. **REC**: repetir al finalizar.
- **REQ** mínimos: título, autor, idioma, fecha de publicación, descripción, género literario, `EPL_id`, revisión y traductor cuando corresponda. **REC**: completarlos al comienzo.
- **REQ**: mantener `ePubLibre` como editorial. El título debe usar mayúsculas normalizadas; no trasladar al texto bibliográfico la eliminación de tildes exigida al nombre del archivo.
- **REQ**: fecha de primera publicación de la obra en su idioma original, no fecha de traducción ni de la edición usada. La fecha de modificación es distinta; el manual indica que el editor la actualiza automáticamente.
- El manual permite completar día/mes desconocidos convencionalmente (muchos usan 1 de enero). **AGENTE**: si se adopta esa convención, registrar que es convencional, no presentarla como dato histórico verificado; no inventar el año.
- **REQ**: descripción = texto de la sinopsis, sin etiquetas. Reemplazar por comillas angulares las cursivas que allí hubiera, por ejemplo en títulos de obras.
- **REQ**: identificadores personalizados con esquema `EPL` (número de ficha) y `revision` (valor inicial `1.0`); no confundir estos identificadores con el UUID.
- **AGENTE**: si no hay ficha, dejar explícito que falta el EPL_id real; no asignar uno ficticio ni copiar el del manual o la plantilla.
- **REQ**: si pertenece a saga/serie, incluir nombre e índice de serie. El manual contempla `calibre:series` y `calibre:series_index` en `content.opf`.
- **REQ**: autor y campo «Ordenar como» (`opf:file-as`) completos, incluso con nombres simples. Seguir el catálogo BNE para nombres complejos y casos especiales.
- La ordenación habitual es `Apellido(s), Nombre(s)`; partículas como `de`, `de la`, `del`, `von` pasan al nombre. No descomponer automáticamente apellidos compuestos, nombres orientales o excepciones BNE.
- **REC** por compatibilidad: varios autores en una línea separados con `&`, tanto en visualización como en «Ordenar como»; no hay comportamiento universal entre lectores.
- **REQ**: añadir traductor y su «Ordenar como»; igual campo para cualquier otro colaborador incorporado. Para varios del mismo tipo, aplicar la separación con `&`.
- Otros colaboradores, como ilustradores, son **opcionales** en metadatos. Autor sin identidad declarada: `Anónimo`; traductor oficial cuya identidad no se consigue averiguar: `Desconocido` (no son equivalentes).
- **REQ** de catalogación EPL: tipo, género y entre uno y cinco subgéneros. En metadatos, solo género/subgéneros, separados por comas, nunca el tipo (`Ficción` o `No Ficción`).
- **REQ**: elegir términos de [genres.json](../resources/genres.json), extracción completa de [I-315], y respetar su grafía exacta, también en libros de otros idiomas (categorías en castellano). `tipos[].generos` y `tipos[].subgeneros` contienen las etiquetas en `nombre`; `descripcion` conserva explicaciones y excepciones, no etiquetas adicionales. No inventar variantes ni relaciones género/subgénero ausentes del recurso.

## 3. Páginas iniciales, créditos y opcionales
Fuente: [I-314].
- **REQ**: los cuatro primeros XHTML, en orden, son `cubierta.xhtml`, `sinopsis.xhtml`, `titulo.xhtml`, `info.xhtml`.
- **REQ**: al cambiar las dimensiones de `cover.jpg` respecto de 600 × 900, adaptar en `cubierta.xhtml` el `viewBox` y las dimensiones del SVG/imagen correspondientes.
- **REQ**: sinopsis igual a descripción de metadatos y texto de la ficha web; conservar su estructura `<div class="sinopsis"><p>…</p></div>`, sin suprimir las etiquetas de párrafo.
- **REQ** en `titulo.xhtml`: autor de la obra, título en el idioma del libro, subtítulo/serie si corresponde, revisión, editor/alias y fecha de edición o revisión. Quitar líneas opcionales no aplicables.
- **REQ** del perfil EPL: no añadir imágenes decorativas ni fuentes incrustadas a `titulo.xhtml`; conservar el logo EPL que ya trae la plantilla (`div.tlogo` con `../Images/EPL_logo.png`). La prohibición de imágenes de [I-314] no debe interpretarse como una orden de eliminar ese logo, verificado en [BASE]. **Opción**: portadilla adicional diseñada libremente, después de `info.xhtml`.
- **REQ** del perfil de revisión elegido: mantener coherentes revisión y fecha de `titulo.xhtml`. **REC**: registrar los cambios junto al entregable; actualizar una ficha web solo si se publica allí.
- **REQ** en `info.xhtml`: título original; autor y año de primera publicación original, concordantes con metadatos; traductor si es traducción; ilustrador si hay ilustraciones; créditos digitales y de cubierta aplicables.
- Si el libro está en su idioma original, eliminar la línea de traducción. Si la editorial no identifica al traductor y no se consigue averiguar, usar `Desconocido`.
- Cubierta conservada o con ajustes menores: mantener al diseñador original o no poner crédito de diseño; retoque significativo: «Retoque de portada», diseñador original y alias del retocador si lo desea; creación nueva: «Diseño de portada» y creador si lo desea.
- **REQ**: no confundir la versión del libro con la mención `ePub Base r…` de `info.xhtml`; esta identifica la plantilla y no se incrementa con las revisiones del aporte.
- **REQ**: obtener permiso antes de incluir nicks de colaboradores. La inclusión no es obligatoria por privacidad; puede usarse `Titivillus` como alias anónimo del editor.
- Si hay cesión, consultar al editor anterior si desea mantener el crédito; en su caso conservarlo con sus revisiones y añadir el nuevo editor con las suyas. Coeditores de una revisión figuran juntos.
- **REC**: contrastar datos faltantes con editorial, BNE, ISBN o WorldCat; no transformar una conjetura en crédito confirmado.
- `TOC.xhtml`: posición tras `info.xhtml` o al final. **REQ** si hay jerarquía `h3` o inferior; en EPUB3 es obligatorio en todos los libros según este manual. En los demás EPUB2, **opcional**.
- `dedicatoria.xhtml`: **opcional** solo si la obra original tiene dedicatoria; no inventar una del editor. Eliminarlo si no corresponde; usar el contenedor `dedicatoria` de la plantilla.
- `autor.xhtml`: **opcional**; respetar código de plantilla y empezar biografía con nombre del autor en mayúsculas. Ajustar el `title` del encabezado oculto a «Autor», «Autora» o «Autores». Si se omite, eliminar también `autor.jpg`.
- `notas.xhtml`: usar si hay notas; sustituir cualquier estructura previa por la probada del ePub Base. No conservar ejemplos de plantilla como contenido real.
- **REQ** en otros idiomas: traducir rótulos de cubierta, información, autor y notas con el listado consensuado EPL; no improvisarlo. Traducir nombres de archivos XHTML es **opcional**.

## 4. Portada y retrato
Fuentes: [I-313], [I-3131].
- **REQ**: portada JPEG llamada exactamente `cover.jpg`, en minúsculas, con identificación de imagen de portada en el paquete; no basta con que exista o se vea en `cubierta.xhtml`.
- **REQ**: proporción 2:3, de 600 × 900 a 1200 × 1800 px (ancho × alto). Las pruebas con imágenes mayores no anulan este rango editorial para la cubierta.
- **REQ** EPL: incorporar el logo oficial desde sus plantillas, con tamaño proporcional; retirar logos editoriales previos. Color y ubicación pueden adaptarse al diseño.
- **REC**: cubierta y otros archivos no superiores a 300 kB; equilibrar compresión/peso sin pérdida visible. No convertir esta recomendación en un límite universal del formato.
- **REC**: al recortar, preservar título, autor y elementos esenciales; usar una imagen de origen con resolución suficiente, no una ampliación pixelada.
- Retrato, si se incluye: **REQ** `autor.jpg`, JPEG. **REC** mínimo 270 × 360 px; el máximo escrito en [I-313] es ambiguo para una imagen vertical (véanse discrepancias).
- **REC** para la ficha web: versión separada de 400 × 600 px, preferiblemente desde el original editable; no sobrescribir con ella la cubierta del EPUB.

## 5. Contenido, jerarquía y estilos
Fuentes: [I-321], [I-322], [I-325].
- **REQ**: cada capítulo en archivo independiente. **REC** de compatibilidad: cada XHTML no debería superar 300 kB; dividir cuando sea necesario sin perder la estructura lógica.
- Para obras sin capítulos que excedan ese tamaño, el manual contempla una variante dividida como aporte principal compatible y otra alternativa; no entregar la menos compatible como única versión sin advertencia.
- **REQ**: ningún XHTML con `body` vacío o solo contenido oculto; puede cerrar el libro en algunos lectores.
- **REQ** en los archivos de contenido: primer enlace de estilos a `../Styles/epl.css`; segundo a `../Styles/style.css` o a la hoja necesaria para ese XHTML.
- **REC**: nombres internos reconocibles (`cap01.xhtml`, etc.). **REQ**: sin espacios, acentos ni caracteres extraños. No confundir esta regla con la pauta del nombre externo del EPUB.
- **REQ**: jerarquía consecutiva desde `h1`, sin saltos: partes/libros/secciones superiores en `h1`; subdivisiones en `h2`, `h3`…; si no hay partes, capítulos en `h1`.
- Cubierta, título, autor y notas llevan rango `h1`. Usar los encabezados al inicio de las divisiones de contenido, no seleccionar su nivel solo por el tamaño visual deseado.
- **REC**: usar `title` en el encabezado si el texto de la TOC debe diferir del visible, manteniendo su correlación. Un título multilínea puede combinar encabezado y párrafo de subtítulo.
- **Opción**: encabezado `class="oculto"` para incluir una división sin título visible. Si se requiere margen superior, aplicar `saltoinicio` al primer párrafo; no dejar una página solo con el encabezado oculto.
- **REQ**: CSS en hojas externas; prohibidos atributos `style`, bloques `<style>` y estilos autogenerados sin normalizar. Aplicar clases con `class`, preservando el significado del formato que sustituyen.
- **REQ**: `epl.css` intacto, incluso clases no usadas. Nuevas clases y ajustes en `style.css`; `sgc-toc.css` corresponde al índice HTML y puede personalizarse.
- **REC**: espaciamiento vertical en `em`, márgenes laterales en `%`; evitar medidas fijas que no se adapten a fuente y pantalla. Para cambio de escena, preferir `<hr/>` semántico.
- **REC**: si una combinación de propiedades se repite con significado propio (por ejemplo firmas de cartas), crear una clase común y mantenerla en un solo lugar.
- **REC** semántica/accesibilidad: `<cite>` para títulos de obras/publicaciones/artes; `<em>` para énfasis del autor; `<dfn>` para término definido; clase de cursiva para decoración.
- `<i>` para usos tipográficos como extranjerismos no asimilados, nombres científicos, notas musicales, nombres de vehículos, metalenguaje, neologismos, usos jergales/dialectales y apodos junto al nombre; respetar excepciones del manual (animales-personajes o clásicos en redonda).
- **REC**: indicar `xml:lang` en pasajes de otro idioma. [I-322] pide cursiva y nota aclaratoria para palabras que el original extranjero presentaba en español; no inferirlo sin cotejar ese original.
- **REQ**: pasar un corrector ortográfico a todo el texto. **REC**: diccionario adecuado al idioma, incluido el EPL si se dispone de él.

## 6. Notas: estructura y navegación bidireccional
Fuentes: [I-314], [I-323].
- **REQ**: conservar el sistema de notas del ePub Base: llamada enlazada, número en superíndice entre corchetes, destino con identificador y enlace de retorno a la llamada.
- Esquema mínimo (adaptar `cap01.xhtml` y el número de forma coherente):
```html
<a href="../Text/notas.xhtml#nt1" id="rf1"><sup>[1]</sup></a>
<div class="nota">
  <p id="nt1"><sup>[1]</sup> Texto de la nota. <a href="../Text/cap01.xhtml#rf1">&lt;&lt;</a></p>
</div>
```
- **REQ**: sincronizar número visible, `ntN`, `rfN`, rutas y destinos; reemplazar marcadores/ejemplos por texto real. El retorno debe apuntar al capítulo donde está la llamada, no al `Section0001.xhtml` de ejemplo.
- **REQ**: llamada pegada al término, antes de puntuación, comillas y paréntesis; también antes del cierre de interrogación/exclamación, salvo si la nota abarca toda la frase incluidos esos signos.
- **REC**: comprobar todas las notas en ambos sentidos. **AGENTE**: verificar además identificadores únicos en cada documento y destinos existentes después de dividir o renombrar archivos; no presumir que una herramienta actualiza los enlaces.
- **Opción**: repartir notas entre varios archivos según cantidad/extensión. No eliminar ni renumerar referencias sin actualizar su pareja y sus rutas.
- Si la llamada está en un encabezado, reducir su superíndice mediante clase externa (el manual ejemplifica `font-size:0.5em`) y usar `title` sin llamada para la TOC.
- **REQ** para notas añadidas por el editor digital: identificarlas como `(N. del E. D.)` o `(N. de la E. D.)`; si también es traductor, `(N. del T.)` o `(N. de la T.)`.

## 7. Tabla de contenidos
Fuentes: [I-311], [I-312], [I-314], [I-321], [I-324].
- **REQ**: generar la navegación a partir de los encabezados y su jerarquía; no modificar directamente `toc.ncx` para arreglar entradas (la siguiente generación perdería esos cambios).
- **REC**: revisar el árbol generado, sus etiquetas, destinos, orden y correlación con los títulos. Si necesita otra etiqueta, ajustar `title` en el encabezado, no el NCX a mano.
- **REC**: regenerar tras cambios significativos; es **REQ** tras cambios de metadatos/`content.opf`. Verificar también `TOC.xhtml`, cuando exista, para no dejar un índice HTML desactualizado.
- Para entradas sin encabezado visible, conservar un encabezado con `title` y/o `oculto`; para inicio mediante imagen, el manual muestra encabezado sin texto con `title`. **AGENTE**: serializar con apertura/cierre explícitos en HTML y mantener contenido visible real.
- Distinguir navegación del dispositivo (`toc.ncx` en el contexto EPUB2 del manual) e índice HTML (`TOC.xhtml`). No presentar el NCX por sí solo como solución completa de navegación EPUB3.

## 8. Perfiles de revisión y nombre del entregable
Fuentes: [I-335], [I-41], [I-312], [I-314].
- Estas son convenciones del **perfil editorial EPL**, no condiciones de validez del formato EPUB ni prueba de aprobación del sitio. Elegir el perfil antes de generar el archivo; no realizar trámites de publicación para crearlo.
- **Perfil final**: iniciar en `r1.0`, incrementar un decimal por revisión (`r1.9` → `r2.0`); un cambio radical permite saltar al entero siguiente. El esquema final EPL no usa más de un decimal.
- **Perfil borrador/candidatura**: `r0.1`, `r0.2`…; el manual permite continuar `r0.10`, `r0.11`… durante candidatura. No es un requisito general para borradores ni una autorización para ignorar fallos de formato, estructura o enlaces.
- **REQ** del perfil elegido: sincronizar revisión en nombre externo, `titulo.xhtml` y metadato `revision`, y actualizar fecha de título. Conservar UUID y versión del ePub Base. **REC**: dejar constancia local de los cambios; sincronizar la ficha web únicamente si existe una publicación.
- **Opción** del perfil EPL: sufijo `a`, como `r1.0a`, para una variante alternativa menos compatible; documentar sus diferencias y conservar una versión principal compatible. El sufijo no sustituye la validación.
- **REQ** si se solicita nombre externo EPL: `Apellido(s), Nombre(s) - [Serie/Colección Número] Título [EPL_ID] (r1.0 Editor).epub`; serie y alias se omiten cuando no correspondan/se prefiera anonimato. Sin EPL_id real, no inventarlo: usar un nombre de trabajo y declarar pendiente el nombre de publicación.
- Las reglas de nombre que siguen pertenecen a ese perfil, no restringen los nombres que admite el formato EPUB:
- **REQ**: mayúsculas normalizadas; sin tildes, eñes ni caracteres no latinos; signos admitidos `, . - _ ( ) &`, y corchetes solo para los campos previstos. No aplicar esta transliteración al contenido del libro.
- Dos autores: nombres completos invertidos unidos por `&`. Tres o más: `AA. VV.` en el nombre del archivo; no sustituir automáticamente los autores de metadatos por esa abreviatura.
- Colección de más de diez volúmenes: numeración con dos dígitos para los primeros (`01`, etc.); si se prevén más de cien, tres dígitos.
- Colecciones/subcolecciones extensas o de autores diferentes: `[Saga] [Serie Número] Apellido(s), Nombre(s) - Título [EPL_ID] (r1.0 Editor)`; sin subcolección, los ejemplos sitúan `[Colección Número]` delante del autor.
- Para distinguir ediciones: `(trad. Nombre Traductor)`, `(ilustrada)` o `(anotada)` después del título y antes de `[EPL_ID]`, cuando corresponda.
- Libros en otros idiomas: sufijo `[IDIOMA]` tras la revisión, usando ISO 639-1 de dos letras (ejemplos `[EN]`, `[DE]`); si la colección coincide con la castellana, distinguir también su nombre mediante idioma o denominación diferente.

## 9. Obtención y limpieza: PDF, OCR y otros orígenes
Fuentes: [II-11], [II-12], [II-13]; limpieza posterior [I-325], [II-202], [II-204], [II-206], [II-207].
- **REC**: disponer del original para cotejar integridad: el texto de la red puede estar alterado o tener capítulos/párrafos ausentes. Revisar especialmente saltos, cursivas, nombres propios y términos extranjeros.
- **AGENTE**: conservar fuente sin modificar y registrar procedencia, edición, orden de páginas y dudas. Para PDF, distinguir capa textual utilizable de páginas-imagen o texto defectuoso: extraer y cotejar la primera; usar OCR para las segundas. Esta selección no está especificada por el manual.
- El II documenta PDF como entrada al OCR, no un extractor de su capa de texto, ni procedimientos de columnas, tablas o fórmulas. **AGENTE**: no prometer conversión fiel de esos elementos sin revisión específica contra la página.
- **REC** si se digitaliza: comprobar estado del libro y equipos; evitar daño de encuadernación, sombras y pérdida de nitidez cerca del lomo o bordes. Para texto sin imágenes, 300 ppp, gris de 8 bits y JPEG se consideran suficientes. [II-11]
- **REC** preparación: imágenes numeradas y ordenadas; corregir orientación, separar dobles páginas, enderezar, delimitar contenido y ajustar márgenes. Revisar resultados automáticos página a página. [II-12]
- **AGENTE**: retirar del flujo de lectura cabeceras repetidas y números de página, sin confundirlos con títulos, notas o numeración significativa de la obra.
- **REC**: texto en blanco y negro; modo combinado si hay imágenes; tratar por separado texto e ilustraciones cuando requieran ajustes distintos. No aplicar limpieza de manchas tan agresiva que borre puntos, comas o trazos. [II-12]
- **REC**: ajustar grosor/deformación con revisión visual; no confiar ciegamente en el enderezado automático. La resolución recomendada por II varía entre 300 y 600 ppp (véanse discrepancias).
- **REC** OCR: configurar idioma(s), tipo de impresión, modo de reconocimiento y color adecuados a la fuente; cotejar caracteres inciertos con la imagen ampliada, no solo con el diccionario. [II-13]
- **AGENTE**: reconstruir párrafos y cortes de línea/guiones solo al verificar su continuidad; preservar diálogos, versos, listas, cursivas y cambios de escena. No deducir faltantes ni completar palabras ilegibles por plausibilidad: dejar una incidencia localizable.
- Exportaciones descritas: copia exacta conserva disposición; copia editable facilita cambios; texto con formato conserva fuentes/tamaños/párrafos pero no posiciones exactas; texto plano pierde formato. El modo con formato puede convertir texto vertical en horizontal. [II-13]
- **REC**: RTF permite una primera corrección de texto/estilos antes de convertir; EPUB/FB2 directo ahorra ese paso, pero no sustituye esa revisión. Ninguna salida automática exime de adaptar al ePub Base. [II-13], [I-325]
- **AGENTE**: en HTML, otros EPUB o documentos convertidos, inventariar estilos y recursos antes de limpiar. Sustituir código ajeno por estructura/clases EPL equivalentes, sin borrar a ciegas estilos que codifican cursivas, espaciados o énfasis. [I-321], [I-325]
- **REC**: examinar palabras sospechosas ordenadas y sus frecuencias; nombres válidos pueden faltar del diccionario y etiquetas dentro de una palabra pueden producir falsos positivos. No incorporar automáticamente sospechas al diccionario. [II-202]
- **REC**: auditar tamaños, dimensiones, hojas enlazadas, clases usadas sin definición, clases personales sin uso, enlaces sin destino y caracteres inesperados/confundibles. [II-204]
- **REQ**: retirar imágenes no usadas antes de publicar; **REC**: comprobar primero si el recurso estaba destinado a insertarse y se olvidó. La herramienta descrita en II solo detecta multimedia, no todos los tipos de archivo. [I-325], [II-206]
- **REQ**: borrar únicamente clases personales prescindibles de `style.css`; conservar siempre todas las de `epl.css`, aunque no se usen. [II-207]
- **REQ**: código nuevo o dudoso debe probarse en todos los lectores del banco de pruebas EPL. Validar sin errores no garantiza visualización compatible. [I-325]
- **AGENTE**: antes de entregar, comprobar integridad contra fuente, metadatos/páginas coherentes, notas ida/vuelta, navegación, recursos y CSS; informar qué validaciones y pruebas se ejecutaron realmente y cuáles quedan pendientes.

## 10. Discrepancias y límites que no deben ocultarse
- [I-322] y [I-325] escriben a veces `styles.css`; [I-311], [I-321] y [II-207] identifican `style.css`. Seguir el nombre real de la plantilla y sus enlaces; no crear una segunda hoja por esa errata.
- [II-204] dice que el número de hojas enlazadas «siempre tiene que ser uno», pero exige al menos `epl.css` y `style.css`; [I-321] prescribe ambos enlaces. No imponer una sola hoja.
- [II-12] primero prefiere 600 ppp para todas las hojas; después da como estándar 300 ppp y 600 con imágenes. Son recomendaciones contradictorias, no un umbral obligatorio único; decidir por legibilidad y errores observados.
- [I-313] recomienda retrato mínimo 270 ancho × 360 alto, pero escribe máximo «400 (de alto) × 600 (de ancho)». No invertir esas medidas silenciosamente ni reutilizarlas como límite de cubierta; confirmar si hace falta ese máximo.
- [I-41] prohíbe tildes pero incluye ejemplos acentuados; también mezcla posiciones de la colección. Priorizar la norma explícita y sus excepciones, y confirmar la convención de la colección si los ejemplos no la resuelven.
- [I-314] prohíbe imágenes en `titulo.xhtml`, pero [BASE] contiene su logo EPL; conservar ese elemento de plantilla y no añadir imágenes decorativas. [I-311] llama `asteriscos.png` al separador; el archivo real de [BASE] es `OEBPS/Images/asterisco3.png`.
- Los 300 kB se expresan como recomendación/límite de compatibilidad, no como restricción intrínseca EPUB; los manuales no precisan base decimal/binaria. No usar tamaños mayores probados en algunos lectores como garantía general.
- Versiones de plantilla, programas, traducciones de rótulos, taxonomía y normativa interna pueden cambiar. Esta referencia no verifica su vigencia web ni desarrolla los requisitos completos de EPUB3.

## Fuentes verificadas
Lectura con Python stdlib `zipfile` + `HTMLParser(convert_charrefs=True)`, sin parser XML: los XHTML usan entidades HTML. Las rutas siguientes son miembros de los EPUB fuente, conservadas como trazabilidad; no es necesario disponer de los manuales originales para usar esta referencia o la taxonomía local.

**I** — Proyecto Scriptorium, `Proyecto Scriptorium - [Manual para maquetar libros electronicos 01] Aprende a maquetar I Manual basico [2398] (r3.1).epub`.
- [I-01] §0.1, «El proyecto y su estándar de calidad»: `OEBPS/Text/0.1.xhtml`.
- [I-04] §0.4, «¿Qué puedo maquetar y qué no?»: `OEBPS/Text/0.4.Limitaciones.xhtml`.
- §3.1, apertura «PRIMEROS PASOS»: `OEBPS/Text/3.1.COMIENZA.xhtml`.
- [I-311] §3.1.1, «Plantilla base»: `OEBPS/Text/3.1.1.Plantilla.xhtml`.
- [I-312] §3.1.2, «El Book-Id y los metadatos»: `OEBPS/Text/3.1.2.Metadatos.xhtml`.
- [I-313] §3.1.3, «Añadir las imágenes de la portada y del autor»: `OEBPS/Text/3.1.3.Portada.xhtml`.
- [I-3131] §3.1.3.1, «Diseño básico de portadas»: `OEBPS/Text/3.1.3.1.Dis_bas_portadas.xhtml`.
- [I-314] §3.1.4, «Completar las páginas básicas»: `OEBPS/Text/3.1.4.Basico.xhtml`.
- [I-315] §3.1.5, «Guía para los distintos géneros y subgéneros»: `OEBPS/Text/3.1.5.Generos.xhtml`; extracción íntegra de taxonomía y reglas en [genres.json](../resources/genres.json).
- §3.2, apertura «MAQUETANDO EL CONTENIDO»: `OEBPS/Text/3.2.MAQUETACION.xhtml`.
- [I-321] §3.2.1, «Capítulos y el archivo Section0001.xhtml»: `OEBPS/Text/3.2.1.Capitulos.xhtml`.
- [I-322] §3.2.2, «Añadir y aplicar estilos CSS y etiquetas»: `OEBPS/Text/3.2.2.estilosCSS.xhtml`.
- [I-323] §3.2.3, «Añadir notas al ebook»: `OEBPS/Text/3.2.3.notas.xhtml`.
- [I-324] §3.2.4, «Tabla de contenido (TOC)»: `OEBPS/Text/3.2.4.TOC.xhtml`.
- [I-325] §3.2.5, «Código sucio y cómo limpiarlo»: `OEBPS/Text/3.2.5.sucio.xhtml`.
- [I-335] §3.3.5, «Números de revisión»: `OEBPS/Text/3.3.5.Revision.xhtml`.
- [I-41] §4.1, «Cómo nombrar los archivos»: `OEBPS/Text/4.1.NombrarArchivo.xhtml`.

**II** — Proyecto Scriptorium, `Proyecto Scriptorium - [Manual para maquetar libros electronicos 02] Aprende a maquetar II Herramientas utiles [46603] (r3.0).epub`.
- Apertura «PREVIO AL EPUB: OBTENIENDO EL CONTENIDO»: `OEBPS/Text/P1.OBTENCION.xhtml`.
- [II-11] §1.1, «Escaneado»: `OEBPS/Text/1.1.Escaneado.xhtml`.
- [II-12] §1.2, «Limpieza y preparación de las imágenes»: `OEBPS/Text/1.2.Limpieza.xhtml`.
- [II-13] §1.3, «Pasar las imágenes a texto: OCR»: `OEBPS/Text/1.3.OCR.xhtml`.
- [II-202] §2.02, «Revisión ortográfica»: `OEBPS/Text/2.02.Ortografia.xhtml`.
- [II-204] §2.04, «Informes»: `OEBPS/Text/2.04.Informes.xhtml`.
- [II-206] §2.06, «Borrar archivos no usados»: `OEBPS/Text/2.06.BorrarArchivos.xhtml`.
- [II-207] §2.07, «Borrar clases sin usar»: `OEBPS/Text/2.07.BorrarClases.xhtml`.
- Se comprobó el índice y se buscaron referencias a extracción/conversión/limpieza en el resto del II; §2.03 y §2.10 se leyeron completos, pero no aportan reglas de extracción adicionales. Se excluyen tutoriales, creación automatizada de notas, regex y catálogo ortotipográfico.

**[BASE]** — [ePub Base EPL r2.1 incluido](../resources/epub-base-epl-r2.1.epub), idéntico al original `Proyecto Scriptorium - ePub base ePL [2653] (r2.1).epub`. Comprobados `OEBPS/Text/titulo.xhtml` (logo `../Images/EPL_logo.png`) y `OEBPS/Images/asterisco3.png`.
