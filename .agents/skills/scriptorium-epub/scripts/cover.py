#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.12"
# dependencies = ["pillow>=13.0.0,<14"]
# ///
"""Adapta una cubierta ePL local y añade una marca transparente; no modifica EPUB/CSS."""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path

from PIL import Image, ImageCms, ImageColor, ImageOps

DEFAULT_LOGO = Path(__file__).resolve().parent.parent / "resources" / "epl-logo.png"
SIZES = {"600x900": (600, 900), "1200x1800": (1200, 1800)}
POSITIONS = ("bottom-right", "bottom-left", "top-right", "top-left")
TARGET_BYTES = 300_000
SRGB = ImageCms.ImageCmsProfile(ImageCms.createProfile("sRGB"))
LINEAR = tuple(
    v / 255 / 12.92 if v <= 10 else ((v / 255 + 0.055) / 1.055) ** 2.4
    for v in range(256)
)


class CoverError(ValueError):
    """Entrada u opciones que no pueden producir una cubierta segura."""


@dataclass(frozen=True)
class Report:
    output: Path
    source_size: tuple[int, int]
    size: tuple[int, int]
    fit: str
    background: tuple[int, int, int]
    position: str
    logo_box: tuple[int, int, int, int]
    color: str
    luminance: float
    contrast: float
    quality: int
    byte_count: int
    warnings: tuple[str, ...]


def background_rgb(value: str) -> tuple[int, int, int]:
    try:
        rgba = ImageColor.getcolor(value, "RGBA")
    except ValueError as exc:
        raise CoverError(f"Color de fondo inválido: {value}") from exc
    if rgba[3] != 255:
        raise CoverError("El fondo debe ser opaco: el destino es JPEG RGB.")
    return rgba[:3]


def read_source(path: Path, warnings: list[str]) -> Image.Image:
    with Image.open(path) as opened:
        if getattr(opened, "n_frames", 1) != 1:
            raise CoverError(
                "La fuente debe tener una sola imagen; selecciona antes la página/fotograma."
            )
        image = ImageOps.exif_transpose(opened)
        alpha = (
            image.convert("RGBA").getchannel("A")
            if "A" in image.getbands() or "transparency" in image.info
            else Image.new("L", image.size, 255)
        )
        profile = image.info.get("icc_profile")
        color = image if image.mode in ("RGB", "CMYK", "LAB") else image.convert("RGB")
        if profile:
            try:
                color = ImageCms.profileToProfile(
                    color,
                    ImageCms.ImageCmsProfile(BytesIO(profile)),
                    SRGB,
                    outputMode="RGB",
                )
            except (ImageCms.PyCMSError, OSError, ValueError) as exc:
                raise CoverError(
                    f"No se pudo convertir el perfil ICC a sRGB: {exc}"
                ) from exc
        else:
            if image.mode == "LAB":
                raise CoverError(
                    "Fuente LAB sin ICC: se necesita su perfil para convertir a sRGB."
                )
            if image.mode == "CMYK":
                warnings.append(
                    "Fuente CMYK sin ICC: conversión aproximada; revisar los colores."
                )
            color = color.convert("RGB")
        color.putalpha(alpha)
        return color


def read_logo(path: Path) -> Image.Image:
    with Image.open(path) as opened:
        if "A" not in opened.getbands() and "transparency" not in opened.info:
            raise CoverError(
                "El logo debe tener alfa real, no un fondo blanco/negro opaco."
            )
        logo = opened.convert("RGBA")
    alpha = logo.getchannel("A")
    minimum, maximum = alpha.getextrema()
    if minimum != 0 or maximum == 0:
        raise CoverError(
            "El logo necesita alfa real: píxeles transparentes y marca visible."
        )
    # Normaliza márgenes vacíos, dejando un píxel para el antialias al escalar.
    ink = logo.crop(alpha.getbbox())
    tight = Image.new("RGBA", (ink.width + 2, ink.height + 2))
    tight.paste(ink, (1, 1))
    return tight


def recolor_logo(logo: Image.Image, color: str) -> Image.Image:
    if color not in ("black", "white"):
        raise CoverError("El recoloreado requiere black o white.")
    result = Image.new("RGBA", logo.size, color)
    result.putalpha(logo.getchannel("A"))
    return result


def fit_cover(
    source: Image.Image,
    size: tuple[int, int],
    fit: str,
    background: tuple[int, int, int],
    warnings: list[str],
) -> Image.Image:
    ratios = (size[0] / source.width, size[1] / source.height)
    scale = min(ratios) if fit == "contain" else max(ratios)
    if scale > 1:
        warnings.append(
            f"Baja resolución: se amplía la fuente {source.width}×{source.height} "
            f"por {scale:.2f}; el remuestreo no recupera detalle ni inventa nitidez."
        )
    if fit == "crop":
        warnings.append(
            "Recorte central explícito (--fit crop): puede eliminar título/autor; revisar visualmente."
        )
        resized = ImageOps.fit(source, size, method=Image.Resampling.LANCZOS)
    else:
        resized = ImageOps.contain(source, size, method=Image.Resampling.LANCZOS)
    canvas = Image.new("RGBA", size, (*background, 255))
    canvas.alpha_composite(
        resized, ((size[0] - resized.width) // 2, (size[1] - resized.height) // 2)
    )
    return canvas.convert("RGB")


def logo_box(
    size: tuple[int, int],
    logo_size: tuple[int, int],
    position: str,
    margin: float,
) -> tuple[int, int, int, int]:
    mx, my = round(size[0] * margin), round(size[1] * margin)
    width, height = logo_size
    if width + 2 * mx > size[0] or height + 2 * my > size[1]:
        raise CoverError("El logo y sus márgenes no caben en la cubierta.")
    x = mx if position.endswith("left") else size[0] - mx - width
    y = my if position.startswith("top") else size[1] - my - height
    return x, y, x + width, y + height


def choose_color(
    region: Image.Image, alpha: Image.Image, requested: str
) -> tuple[str, float, float]:
    """Luminancia relativa sRGB, ponderada por los trazos (no por huecos del logo)."""
    weighted = total = 0.0
    for (r, g, b), weight in zip(
        region.convert("RGB").get_flattened_data(),
        alpha.get_flattened_data(),
        strict=True,
    ):
        weighted += (
            0.2126 * LINEAR[r] + 0.7152 * LINEAR[g] + 0.0722 * LINEAR[b]
        ) * weight
        total += weight
    if total == 0:
        raise CoverError("El logo no tiene trazos visibles al tamaño elegido.")
    luminance = weighted / total
    contrasts = {"black": (luminance + 0.05) / 0.05, "white": 1.05 / (luminance + 0.05)}
    color = (
        max(contrasts, key=lambda name: contrasts[name])
        if requested == "auto"
        else requested
    )
    return color, luminance, contrasts[color]


def build_cover(
    source: Path,
    output: Path,
    *,
    size: tuple[int, int] = (600, 900),
    fit: str = "contain",
    position: str = "bottom-right",
    logo_color: str = "auto",
    background: str = "black",
    logo_width: float = 0.18,
    margin: float = 0.04,
    logo_path: Path = DEFAULT_LOGO,
    quality: int = 92,
) -> Report:
    if source.resolve() == output.resolve():
        raise CoverError(
            "Entrada y salida deben ser distintas; no se sobrescribe el original."
        )
    if output.exists() or output.is_symlink():
        raise CoverError(f"La salida ya existe: {output}")
    if output.suffix.lower() not in (".jpg", ".jpeg"):
        raise CoverError(
            "La salida debe ser JPEG (.jpg o .jpeg); en el EPUB usa cover.jpg."
        )
    if size not in SIZES.values():
        raise CoverError("Tamaño permitido: 600x900 o 1200x1800 (2:3).")
    if fit not in ("contain", "crop") or position not in POSITIONS:
        raise CoverError("Ajuste o posición inválidos.")
    if logo_color not in ("auto", "black", "white"):
        raise CoverError("Color del logo inválido.")
    if not 0 < logo_width <= 1 or not 0 <= margin < 0.5:
        raise CoverError("Ancho del logo: (0%, 100%]; margen: [0%, 50%).")
    if not 1 <= quality <= 100:
        raise CoverError("La calidad JPEG debe estar entre 1 y 100.")
    warnings: list[str] = []
    rgb = background_rgb(background)
    image = read_source(source, warnings)
    canvas = fit_cover(image, size, fit, rgb, warnings)
    logo = read_logo(logo_path)
    width = max(1, round(size[0] * logo_width))
    height = max(1, round(width * logo.height / logo.width))
    box = logo_box(size, (width, height), position, margin)
    if width > logo.width or height > logo.height:
        warnings.append(
            "Se amplía el logo rasterizado; no se recupera detalle. Usar un recurso de mayor resolución."
        )
    logo = logo.resize((width, height), Image.Resampling.LANCZOS)
    color, luminance, contrast = choose_color(
        canvas.crop(box), logo.getchannel("A"), logo_color
    )
    if contrast < 4.5:
        warnings.append(
            f"Contraste medio bajo ({contrast:.2f}:1) con el color forzado; revisar."
        )
    logo = recolor_logo(logo, color)
    canvas.paste(logo, box[:2], logo.getchannel("A"))
    buffer = BytesIO()
    canvas.save(
        buffer,
        format="JPEG",
        quality=quality,
        subsampling=0,
        optimize=True,
        progressive=False,
        icc_profile=SRGB.tobytes(),
    )
    data = buffer.getvalue()
    if len(data) > TARGET_BYTES:
        warnings.append(
            f"JPEG de {len(data):,} bytes: supera el objetivo orientativo de 300 kB (300000 bytes). "
            "No se redujo automáticamente la calidad; decidir y repetir con otra salida/--quality."
        )
    # La creación exclusiva protege también frente a una salida creada durante el procesado.
    try:
        with output.open("xb") as stream:
            stream.write(data)
    except FileExistsError as exc:
        raise CoverError(f"La salida ya existe: {output}") from exc
    return Report(
        output,
        image.size,
        size,
        fit,
        rgb,
        position,
        box,
        color,
        luminance,
        contrast,
        quality,
        len(data),
        tuple(warnings),
    )


def percentage(value: str) -> float:
    try:
        if not value.endswith("%"):
            raise ValueError
        return float(value[:-1]) / 100
    except ValueError as exc:
        raise argparse.ArgumentTypeError(
            "Indica un porcentaje, por ejemplo 18%."
        ) from exc


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    result.add_argument("source", type=Path)
    result.add_argument("output", type=Path)
    result.add_argument("--size", choices=SIZES, default="600x900")
    result.add_argument(
        "--fit",
        choices=("contain", "crop"),
        default="contain",
        help="contain conserva toda la imagen; crop recorta el centro explícitamente",
    )
    result.add_argument("--position", choices=POSITIONS, default="bottom-right")
    result.add_argument(
        "--logo-color", choices=("auto", "black", "white"), default="auto"
    )
    result.add_argument(
        "--background", default="black", help="fondo opaco/padding (por defecto: black)"
    )
    result.add_argument(
        "--logo-width",
        type=percentage,
        default=0.18,
        help="porcentaje del ancho (18%%)",
    )
    result.add_argument(
        "--margin", type=percentage, default=0.04, help="porcentaje de cada eje (4%%)"
    )
    result.add_argument(
        "--logo",
        type=Path,
        default=DEFAULT_LOGO,
        help="PNG con alfa real; recurso portable por defecto",
    )
    result.add_argument(
        "--quality", type=int, default=92, help="calidad JPEG explícita, 1–100 (92)"
    )
    return result


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        report = build_cover(
            args.source,
            args.output,
            size=SIZES[args.size],
            fit=args.fit,
            position=args.position,
            logo_color=args.logo_color,
            background=args.background,
            logo_width=args.logo_width,
            margin=args.margin,
            logo_path=args.logo,
            quality=args.quality,
        )
    except (CoverError, OSError, Image.DecompressionBombError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    for warning in report.warnings:
        print(f"AVISO: {warning}", file=sys.stderr)
    x0, y0, x1, y1 = report.logo_box
    print(
        f"Salida: {report.output}\n"
        f"Fuente orientada: {report.source_size[0]}×{report.source_size[1]}; ajuste: {report.fit}; "
        f"fondo RGB: {report.background}\n"
        f"JPEG RGB sRGB, no progresivo: {report.size[0]}×{report.size[1]} (2:3); "
        f"calidad {report.quality}; {report.byte_count} bytes\n"
        f"Logo: {report.position}; {x1 - x0}×{y1 - y0}; caja {report.logo_box}; color {report.color}; "
        f"luminancia local {report.luminance:.3f}; contraste medio {report.contrast:.2f}:1\n"
        "Revisión visual pendiente: título/autor, superposición del logo y fondos heterogéneos. "
        "El informe no es una previsualización ni una aprobación ePL."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
