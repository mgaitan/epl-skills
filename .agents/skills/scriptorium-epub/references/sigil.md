# Reproducir en Sigil el flujo de un revisor

Usa este flujo si el revisor pide el índice HTML nativo de Sigil y su reparación/reformateo masivo. EPUBCheck y el auditor no ejecutan esas operaciones: pueden pasar aunque no se haya reproducido el flujo. Sigil es una herramienta opcional, no una dependencia del generador ni un requisito general para todos los EPUB.

## Secuencia manual

1. Conserva el EPUB original y abre **una copia** en Sigil. Anota la versión y, para diagnosticar un fallo, la huella del archivo recibido o enviado. Comprueba que el índice de navegación (NCX en EPUB2) ya tenga las entradas correctas.
2. En **Herramientas → Tabla de contenido → Crear tabla de contenido HTML**, genera `TOC.xhtml` a partir del índice de navegación ya cargado. Si Sigil pide reemplazar el existente, confirma. Guarda la copia. Esta acción no regenera el NCX desde los encabezados.
3. **Cierra y vuelve a abrir el mismo EPUB guardado**. Si necesitas identificar en qué paso ocurre un cambio, conserva también una copia de ese primer guardado.
4. Ejecuta **Reformatear HTML → Corregir y arreglar código → Todos los archivos HTML** (en inglés, *Mend and Prettify All HTML Files*). Guarda otra vez. Si hay un aviso, registra el texto y el archivo afectado; no des la operación por completada solo porque el EPUB abre.

## Listas opcionales (Sigil 2.8.6)

En **Edición → Preferencias → Aspecto**, activa **Mostrar el menú de automatización**. Configura dos listas mediante **Automatización**; si las preparas como archivos de texto, Sigil 2.8.6 lee `automate<NOMBRE>.txt` desde su directorio de preferencias. Para un perfil de prueba separado, inicia Sigil con `SIGIL_PREFS_DIR` apuntando a un directorio local existente. No modifiques el perfil habitual sin necesidad.

| Lista | Órdenes en líneas separadas |
| --- | --- |
| `automate01-Regenerar-TOC.txt` | `CreateHTMLTOC`, luego `Save` |
| `automate02-Corregir-y-reformatear.txt` | `MendPrettifyHTML`, luego `Save` |

Ejecuta la primera lista desde **Automatización → Ejecutar**, resuelve la confirmación de sobrescritura si aparece, cierra y reabre manualmente la copia y ejecuta la segunda lista. No uses `MendHTML` en lugar de `MendPrettifyHTML`: es otra operación. Esta automatización sigue usando la interfaz; no presupongas una CLI sin interfaz. Si no hay Sigil disponible, usa la [distribución oficial](https://github.com/Sigil-Ebook/Sigil/releases) o deja el paso pendiente.

## Después del último guardado

- Compara `TOC.xhtml` con el NCX y los encabezados: etiquetas, fragmentos, orden y jerarquía. Confirma que el texto, la estructura significativa y los enlaces de notas siguen intactos y que `info.xhtml` conserva la estructura del ePub Base. No supongas que todo cambio de Sigil es solo de indentación.
- Sigil 2.8.6 puede omitir `xml:lang` al crear `TOC.xhtml` y normalizar CRLF a LF en `epl.css` al guardar; ambos cambios se observaron en este flujo. Si hace falta, repón el idioma real en el elemento `html` del índice y restaura **los bytes exactos** de `epl.css` del ePub Base. Haz estos ajustes mínimos en una copia para entregar, después de guardar en Sigil, sin volver a ejecutar `navigation.py` ni reformatear el índice. No añadas `epl.css` al índice HTML nativo solo porque el resto de los XHTML lo enlaza: el `TOC.xhtml` de la base enlaza `sgc-toc.css`.
- Conserva el guardado de Sigil como evidencia, y ejecuta `epub.py check` y EPUBCheck sobre el EPUB final tras los ajustes. Registra su SHA-256 y declara por separado si se ejecutó el validador del revisor. No atribuyas el bloqueo original a un detalle de serialización sin reproducirlo.

Referencia de las órdenes: [código de Sigil 2.8.6](https://github.com/Sigil-Ebook/Sigil/blob/2.8.6/src/MainUI/MainWindow.cpp).
