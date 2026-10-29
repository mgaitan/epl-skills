# Comprobaciones operativas de Scriptorium

## Fuentes y alcance

Manuales locales; los nombres siguientes identifican los EPUB en `epl/`:
- **I**: `Proyecto Scriptorium - [Manual para maquetar libros electronicos 01] Aprende a maquetar I Manual basico [2398] (r3.1).epub`.
- **II**: `Proyecto Scriptorium - [Manual para maquetar libros electronicos 02] Aprende a maquetar II Herramientas utiles [46603] (r3.0).epub`.
- SHA-256 I: `2e5b9ce44574bfbbce1cec3cdf727acc0a6cf0ec803e046ba3ff6fbec18fe838`.
- SHA-256 II: `6e3a41bb85a75ef9209fda2d3f4896f70fc98e1e97acd7be9c9706d7e0abad8c`.

Las citas de capítulos siguientes son miembros ZIP bajo `OEBPS/Text/`. Se inspeccionaron I `3.3.1.RegEx.xhtml`, `3.3.2*.xhtml`, `3.4*.xhtml` y `3.3.5.Revision.xhtml`; II se consultó para motor y recomendaciones prácticas. Lectura con `zipfile` y `HTMLParser` stdlib, sin GUI, ElementTree, lxml ni bs4.

**El `.ini` de búsquedas no está en ninguno de los dos EPUB.** Es un archivo de texto de **búsquedas guardadas de Sigil** con patrones y reemplazos para revisión, no un componente que requiera el EPUB generado. I `3.3.1.RegEx.xhtml` indica solicitarlo **al revisor de la candidatura**, junto con la guía explicativa del conjunto. No incluye una URL de descarga pública verificada: consultar a un revisor/editor del Proyecto Scriptorium o sus canales de maquetación. Si el usuario aporta una copia, registrar versión/procedencia y analizarla como datos, sin ejecutar sustituciones. No reconstruir grupos o reglas numeradas desde menciones o capturas. Este catálogo no equivale al conjunto completo.

## Uso del catálogo y omisiones con Python stdlib

La única lista de patrones está en [`../resources/manual-regex.json`](../resources/manual-regex.json): **26 entradas, todas `status=alerta`**. Conserva IDs y patrones de la transcripción; no incluye tutoriales, contraejemplos ni recetas de transformación de notas.

- **Solo alertar y revisar. Nunca autocorregir.** `replacement`, si existe, documenta la propuesta del manual; no autoriza ejecutarla. Fuente: I `3.3.1.RegEx.xhtml`.
- `source` identifica EPUB, miembro y tabla Buscar (`buscar`, ordinal) o pasaje de prosa (`location`). `description` y `caveat` contienen intención y límites por entrada; no se duplican aquí.
- Son **24 búsquedas literales y 2 regex originales PCRE/Sigil**. Para `kind=literal`, buscar literalmente o aplicar `re.escape(pattern)` antes de usar `re`; no compilar directamente cadenas como `...` o `*`.
- `stdlib_re_compatible` indica si la búsqueda, despachada según `kind`, compila en `re`. No certifica que una coincidencia sea errata ni que se esté buscando en el ámbito correcto.
- Si es `false`, **omitir explícitamente** y registrar ID y `stdlib_re_skip_reason`. No traducir el patrón, añadir dependencias ni informar «cero coincidencias» como si se hubiera ejecutado.
- `scope=text`: contenido textual, no atributos, cabeceras ni CSS. `scope=xhtml`: representación fuente; las entidades literales se buscan antes de decodificarlas. No hay regex CSS publicada que se haya convertido en alerta.
- Conservar localización y contexto del hallazgo. Etiquetas intercaladas fragmentan palabras; una búsqueda sobre texto extraído no conserva por sí sola posiciones en el fuente. Sigil busca en código, no en texto renderizado: II `2.05.Busquedas.xhtml`.
- Mantener separados «error estructural», «convención ePL», «posible errata» y «no comprobado». Una sección ilegible o una regla omitida no prueba conformidad.

### Alertas incompatibles con `re`

| ID conservado | Motivo / acción |
| --- | --- |
| `I-3-3.3.2.1.ErrataOrtotipograficas-04` | Lookbehind con alternativas de distinta longitud. Omitir en stdlib; requeriría otro motor para ejecutarse literalmente. |
| `I-3-3.3.2.2.ErroresTipograficos-01` | Mismo impedimento. Omitir en stdlib; requeriría otro motor para ejecutarse literalmente. |

Son ejemplos publicados en I para notas `N. de…` y extranjerismos, respectivamente. Se conservan como alertas revisables, no reglas infalibles: el primero tiene `N.` con punto sin escapar; el segundo no delimita palabras ni contempla mayúsculas. Ambos solo excluyen ciertas etiquetas inmediatamente anteriores, no cursiva efectiva por ancestros, atributos o CSS. Motor de origen: PCRE/Sigil, según II `2.05.Busquedas.xhtml` y `4.01.CrearRegex.xhtml`. Se verificó el rechazo por `re` (`look-behind requires fixed-width pattern`); no se repararon los originales.

## Límites editoriales de las alertas

| Grupo / fuente | Criterio operativo y falsos positivos |
| --- | --- |
| OCR y ortografía — I `3.3.2.1.ErrataOrtotipograficas.xhtml` | Revisar contexto y original. `muías` puede ser legítimo; diccionario del idioma y comparación de fuentes complementan las búsquedas. No confundir diferencias de edición/traducción con errores. |
| Puntos, comillas y apóstrofos — I `3.3.2.2.ErroresTipograficos.xhtml` | Tres puntos, comillas rectas y apóstrofos son candidatos. Minutos/segundos angulares son excepciones expresas. Elegir apertura/cierre según contexto. Las dos alertas sobre `'` distinguen comilla y apóstrofo: no contar ambas como dos errores independientes. |
| Grados y signo menos — misma fuente | `º` es válido como ordinal y `–` tiene usos correctos. Revisar solo su posible confusión con grados o resta/negativos. |
| Entidades — misma fuente | Preferencia editorial por símbolos, no error visual automático. No modificar ejemplos de código ni escapes necesarios; `&lt;`/`&gt;` no se sustituyen ciegamente. |
| Marcas pendientes — II `2.09.Fragmentos.xhtml` | Asteriscos y comentario de atención pueden indicar trabajo pendiente. Un asterisco puede ser legítimo; la cadena del comentario es un marcador literal, no la regex oficial 0.01. |
| Familias sin patrón publicado — I `3.3.2.1` y `3.3.2.2` citados | OCR, rayas, minúscula tras punto, romanos, siglas y cursiva requieren revisión; no inventar las regex oficiales ni presentar cobertura completa. Comparar énfasis, saltos de escena y estilos con la fuente. |

## Resumen de controles estructurales (sin regex inventadas)

Fuentes: I `3.3.2.3.ErroresMaquetacion.xhtml`, `3.3.2.4.ErroresEPL.xhtml` y `3.4.5.CodigosError.xhtml`. Son requisitos de análisis estructural o revisión; no se reproducen los mensajes del validador.

| Área | Qué comprobar | Límites y dependencias |
| --- | --- | --- |
| ZIP / contenedor | ZIP legible; `META-INF/container.xml`, rootfile y OPF existentes; `mimetype` único en raíz, primero, sin comprimir y contenido exacto `application/epub+zip`; datos extra y estructura ZIP. | Inspección binaria; si falla, declarar controles pendientes. No corregir ni borrar archivos. |
| XHTML / XML | Buena formación, cierres y anidación; raíz, versión/esquema, elementos/atributos obligatorios y permitidos; codificación declarada acorde a bytes; IDs válidos y únicos por documento. | `HTMLParser` es tolerante y no certifica validez XML. `re` tampoco sustituye validación de esquema. Un error puede estar antes de la línea reportada. |
| Recursos / manifiesto / spine | Archivos declarados y existentes, URI y tipo de medio, IDs e `idref` resolubles, entradas sin duplicación indebida, recursos alcanzables. | Resolver rutas y referencias desde XHTML, CSS y SVG antes de declarar desuso. Mismo ID en documentos diferentes no es duplicación local. |
| TOC / encabezados | Destinos y fragmentos existentes; título/BookId coherentes; jerarquía ePL desde h1, sin saltos; IDs para varios encabezados en una sección. | Navegación según versión EPUB. Si no puede comprobarse, informar cobertura incompleta, no fallo de toda la TOC. |
| Notas | Correspondencia `rfN`/`ntN`, número visible, enlace de ida, destino y retorno al archivo/fragmento correctos. | Grafo de enlaces, no solo parecido del código. Contemplar etiquetas intercaladas y notas con varios párrafos. |
| Metadatos | Presencia, valores, duplicación impropia y ausencia de datos residuales del Base; título, autor, traductor, roles y `file-as`; editorial ePL; idioma, género/subgénero; serie/volumen si proceden. | Comparar campos pertinentes entre OPF, título, info y TOC. Listas aprobadas de idiomas/géneros no se publican completas aquí; no inventarlas. Nombres y `file-as` pueden requerir revisión. |
| Identificadores / revisión / fechas | BookId no vacío, formato y distinto del Base; identificadores exigidos por versión; revisión, alias y fechas coherentes entre ubicaciones. | No confundir revisión del libro con revisión del Base en info. UUID distinto del Base no prueba que no se reutilizó el de otro libro. Ver excepciones abajo. |
| CSS / contenedores | Hoja protegida intacta y enlazada en orden; clases definidas/usadas; hojas sin uso; herencia, selectores y contenedores adecuados para texto. | Revisar hojas realmente enlazadas por sección. Clases en div no son desuso; spans/anclas aparentemente redundantes pueden tener uso. Conservar estilos del Base. |
| Fuentes | Archivo real de `@font-face`, uso de estilos/archivos, cobertura de glifos; fuentes aplicadas incrustadas salvo genéricas; icono de fuentes en info coherente; archivo Apple según Base. | Resolver dependencias y alcance de hojas. La lista completa de propiedades CSS desaconsejadas no se publica aquí. |
| Imágenes / portada | Recursos presentes, muestras del Base reemplazadas y logos protegidos; dimensiones SVG de cubierta acordes a imagen; conceptos y orden de secciones fijas. | Comparar con Base de la versión adecuada. Autor/notas pueden faltar; cuando existen, van al final en ese orden. No borrar recursos automáticamente. |
| Semántica / presentación | Idioma en html, title descriptivo, alt de imágenes de contenido; homogeneidad de estilos y fidelidad visual al original. | Decorativas pueden tener alt vacío y `role="none"`. Revisión editorial; no todo aviso es error normativo. |

## Contradicciones y reglas históricas que afectan decisiones

| Fuente en I | Precaución operativa |
| --- | --- |
| `3.3.2.2.ErroresTipograficos.xhtml`, tabla de entidades | Publica **`&ldaquo;` y `&rdaquo;`**, no nombres HTML estándar. El JSON conserva las erratas; no cambiarlas silenciosamente. |
| `3.3.2.1.ErrataOrtotipograficas.xhtml` frente a `3.3.2.2.ErroresTipograficos.xhtml` | Primero propone entidad `&nbsp;` → carácter **U+00A0**, después conservar código. No convertir a U+0020 ni denunciar una representación válida como fallo universal. |
| `3.3.2.4.ErroresEPL.xhtml` frente a `3.4.5.CodigosError.xhtml`, error 39 | El primero limita XHTML a 300 kb; el segundo habla de todo archivo interno, incluidas imágenes. No define KB/KiB. No imponer silenciosamente un umbral en bytes a todo recurso. El alternativo `a` no reemplaza la edición estándar. |
| `3.4.5.CodigosError.xhtml`, errores 40, 45 y 46 | Portada: 600×900 a 1200×1800, razón 2:3, para esta edición. En 45/46 se contradicen ancho/alto entre mensaje y explicación; 400 se dice recomendado. No invertir dimensiones ni universalizar límites. |
| `3.4.5.CodigosError.xhtml`, errores 14–16 y mensajes posteriores | Base 2.0 admite varias CSS: `epl.css` protegida, enlazada y primera; excepción de presencia para índice temático generado por Sigil. «Más de un CSS» es obsoleto. |
| `3.3.2.4.ErroresEPL.xhtml` frente a `3.4.5.CodigosError.xhtml`, estilos sin uso | Eliminación inicialmente opcional; después se pide quitar estilos personales y conservar los del Base. Tratar como limpieza revisable, no borrado automático. |
| `3.4.5.CodigosError.xhtml`, error 67 y mensajes posteriores | «ePL-ID solo en nombre, no interior» entra en conflicto con exigencia posterior de ePLID/revisión en metadatos para Base 2.0. Elegir por versión. |
| `3.3.5.Revision.xhtml`; `3.4.5.CodigosError.xhtml`, error 56 | Publicación: r1.0, un dígito tras punto, r1.9→r2.0; alternativo con `a`. Candidatura r0.10 y siguientes admite más dígitos: no error absoluto. Cambiar solo magnet no exige revisión. |
| `3.4.4.ePLValidator.xhtml`, fechas antiguas | Reconoce falso positivo con año de dos dígitos (`0060-01-01`); para a. C. propone año OPF sin signo y era en info. Conservar contexto de era; ausencia de detección no prueba ausencia de fecha. |
| `3.4.5.CodigosError.xhtml`, FlightCrew | La explicación dice erróneamente que NCX está prohibido en EPUB3; puede existir por compatibilidad. El mensaje sobre `linear` dice item, pero corresponde a itemref. |
| `3.4.4.ePLValidator.xhtml` frente a `3.4.5.CodigosError.xhtml` | La versión auto descrita solo existió hasta 1.18 según la segunda fuente; 1.19 ya no autocorrige. No recomendar reparación automática. |
| `3.4.3.epubsheck.xhtml`; `3.4.5.CodigosError.xhtml` | EPUBCheck 3.0.1, servicio IDPF de 10 Mb, prohibición de JPEG progresivo y div de un párrafo son históricos o marcados obsoletos. No son requisitos generales actuales. |
| `3.4.5.CodigosError.xhtml`, idioma y nombres | Preferir `es` a `es-es` es convención ePL citada, no invalidez universal de etiquetas de idioma. Normalización atípica de nombres y conceptos traducidos de distinta forma por Sigil pueden ser falsos positivos. |

Seleccionar reglas por versión EPUB y Base: «actual» en el manual significa Base 2.0 en su fecha, no la revisión más reciente del proyecto. FlightCrew, EPUBCheck y ePLValidator se presentan como complementarios, no equivalentes (I `3.4.1.Generalidades.xhtml`). Sin acceso a esos validadores, no afirmar sus resultados.

## Fidelidad y mantenimiento

- Patrones y reemplazos conservan sus literales originales. Las entidades de los XHTML del manual se decodificaron una sola vez para recuperar el código mostrado; no se normalizaron comillas, guiones ni espacios del patrón.
- La poda retiene únicamente las 26 alertas y sus IDs; no intenta completar cobertura con ejemplos didácticos ni reconstruir algoritmos de los diagnósticos.
- Verificar JSON, unicidad de IDs, `status=alerta`, campos de procedencia y compatibilidad `re` según `kind`. Registrar las dos omisiones explícitas; no ejecutar sustituciones sobre los EPUB.
