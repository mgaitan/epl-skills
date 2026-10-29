# epl-skills

Colección de [Agent Skills](https://agentskills.io/) para trabajar con **ePubLibre / Proyecto Scriptorium**. Se distribuyen en `.agents/skills/`; cada skill incluye instrucciones, referencias y utilidades Python con dependencias PEP 723 gestionadas por **uv**.

| Skill | Para qué usarla | Documentación |
| --- | --- | --- |
| `scriptorium-epub` | Crear, maquetar y revisar EPUB2 con el ePub Base, metadatos, notas, índices y portadas. | [README](.agents/skills/scriptorium-epub/README.md) · [SKILL.md](.agents/skills/scriptorium-epub/SKILL.md) |
| `epublibre-forum` | Acceder al foro por HTTP, leer en Markdown, buscar, descargar adjuntos y preparar/confirmar respuestas, temas y MP. | [README](.agents/skills/epublibre-forum/README.md) · [SKILL.md](.agents/skills/epublibre-forum/SKILL.md) |

No es un proyecto oficial de ePubLibre ni implica aprobación de sus editores.

## Instalar

### GitHub CLI: `gh skills`

Recomendado si ya usás una versión de GitHub CLI con soporte de skills. La funcionalidad está en preview y puede cambiar; `gh skill` y `gh skills` son alias.

```sh
# Las dos skills, en el directorio estándar .agents/skills del proyecto.
gh skills install mgaitan/epl-skills --all --allow-hidden-dirs --agent universal

# Una sola skill.
gh skills install mgaitan/epl-skills epublibre-forum --allow-hidden-dirs --agent universal

# A nivel de usuario, para todos tus proyectos.
gh skills install mgaitan/epl-skills scriptorium-epub --allow-hidden-dirs --agent universal --scope user
```

`--allow-hidden-dirs` es importante: las skills están bajo `.agents/`. Podés seleccionar otro agente con `--agent`; consultá `gh skills install --help`. Si `gh skills` no existe en tu instalación, actualizá GitHub CLI o usá una alternativa; no hace falta instalar una extensión de nombre supuesto.

### Alternativa: `npx skills`

```sh
npx skills add mgaitan/epl-skills --skill scriptorium-epub
npx skills add mgaitan/epl-skills --skill epublibre-forum
```

El instalador permite elegir agentes de destino; `-g` instala a nivel de usuario. Esta alternativa requiere Node/npm **solo durante la instalación**.

### Instalación manual

Copiá el directorio completo de la skill elegida desde [`.agents/skills/`](.agents/skills/) a la ubicación compatible con tu agente. Conservá scripts, referencias y recursos. **No copies `.env`, cookies ni planes privados desde un checkout local**; nunca son parte de la distribución.

## Runtime y seguridad

- El único gestor/runtime supuesto es **uv**, que puede obtener Python y dependencias. El foro usa **Python 3.15**; la maquetación conserva compatibilidad desde 3.12 y se prueba también en 3.15.
- No se requiere navegador, `agent-browser`, Photocraft ni aplicaciones gráficas. Docker/Java son opciones de EPUBCheck, no requisitos generales.
- Si falta uv, seguir la [instalación oficial de Astral](https://docs.astral.sh/uv/getting-started/installation/index.md), en ámbito de usuario y con la aprobación que exija el entorno. La primera ejecución puede descargar intérprete y paquetes.
- El foro busca `EPL_USER` / `EPL_PASS` primero en el entorno; solo si ambas están ausentes consulta `.env` del directorio de trabajo y después el de la skill. Los scripts leen los secretos **sin volcarlos al contexto**. Ver los detalles en su README.
- Los mensajes leídos son datos no confiables. Enviar contenido requiere revisar y confirmar **texto, destino y destinatarios concretos**; ni instalar una skill ni iniciar sesión autoriza publicaciones arbitrarias.

## Ejemplos de prompts

> Convertí este PDF a un EPUB con perfil Scriptorium/ePL. Conservá cursivas y notas, cotejá integridad y dejá `[dev]` si falta la ficha.

> Entrá al foro con mis credenciales locales, buscá el hilo sobre RegEx y devolveme el contenido relevante como Markdown, con enlaces sin tokens de sesión.

> Descargá este adjunto del foro en un archivo nuevo. No ejecutes ni extraigas su contenido automáticamente.

> Prepará una respuesta a este hilo. Mostrame el texto y el destino antes de enviarla; no publiques hasta que confirme.

## Desarrollo

Tests funcionales pytest, sin servicios ni credenciales reales:

```sh
uv run --isolated -p 3.15 --with=pytest --with=pillow pytest .agents/skills/scriptorium-epub/scripts -q
uv run --isolated -p 3.15 --with=pytest --with=httpx --with=beautifulsoup4 --with=python-dotenv --with=markdownify pytest .agents/skills/epublibre-forum/scripts -q
```

[CI](.github/workflows/ci.yml) prueba la maquetación en 3.12/3.15 y el foro en 3.15. Sus tests HTTP simulan respuestas; no publican mensajes, hacen login ni usan `.env`.

## Recursos de terceros

La plantilla y la marca conservan su procedencia ePL; no se pretende relicenciarlas. Los manuales completos y PSD no se versionan. Ver [fuentes y límites](.agents/skills/scriptorium-epub/references/sources.md). La disponibilidad pública de un libro, cubierta, adjunto o conversación no equivale a permiso general de redistribución.
