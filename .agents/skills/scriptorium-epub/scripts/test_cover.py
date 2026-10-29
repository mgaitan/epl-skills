#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.12"
# dependencies = ["pillow>=13.0.0,<14", "pytest"]
# ///
"""uv run -p 3.15 --with=pytest --with=pillow pytest .agents/skills/scriptorium-epub/scripts/test_cover.py -q"""

import subprocess
import sys
from hashlib import sha256
from io import BytesIO
from pathlib import Path

import cover
import pytest
from PIL import Image, ImageCms, ImageDraw


@pytest.fixture
def source(tmp_path: Path) -> Path:
    path = tmp_path / "source.png"
    Image.new("RGB", (600, 900), "white").save(path)
    return path


@pytest.fixture
def logo(tmp_path: Path) -> Path:
    path = tmp_path / "logo.png"
    image = Image.new("RGBA", (100, 60))
    draw = ImageDraw.Draw(image)
    draw.rectangle((2, 2, 97, 20), fill=(90, 120, 140, 255))
    draw.rectangle((2, 21, 20, 57), fill=(20, 40, 80, 128))
    image.save(path)
    return path


def test_bundled_logo_is_only_tight_transparent_mark():
    with Image.open(cover.DEFAULT_LOGO) as image:
        assert image.format == "PNG"
        assert image.mode == "RGBA"
        assert image.size == (471, 314)
        alpha = image.getchannel("A")
        assert alpha.getextrema() == (0, 255)
        assert alpha.getbbox() == (1, 1, 470, 313)
        assert alpha.crop((0, 0, image.width, 1)).getbbox() is None
        assert (
            alpha.crop((0, image.height - 1, image.width, image.height)).getbbox()
            is None
        )
        assert alpha.crop((0, 0, 1, image.height)).getbbox() is None
        assert (
            alpha.crop((image.width - 1, 0, image.width, image.height)).getbbox()
            is None
        )
        values = alpha.get_flattened_data()
        assert sum(v == 0 for v in values) > len(values) * 0.4
        assert any(0 < v < 255 for v in values)


@pytest.mark.parametrize(
    "color, rgb", [("black", (0, 0, 0)), ("white", (255, 255, 255))]
)
def test_recolor_changes_only_rgb(logo: Path, color: str, rgb: tuple[int, int, int]):
    original = cover.read_logo(logo)
    alpha = original.getchannel("A").tobytes()
    result = cover.recolor_logo(original, color)
    assert result.getchannel("A").tobytes() == alpha
    assert set(result.convert("RGB").get_flattened_data()) == {rgb}
    assert original.getchannel("A").tobytes() == alpha


@pytest.mark.parametrize(
    "mode, color",
    [
        ("RGB", "white"),
        ("RGBA", (0, 0, 0, 255)),
        ("RGBA", (0, 0, 0, 0)),
        ("RGBA", (0, 0, 0, 128)),
    ],
)
def test_reject_fake_or_empty_alpha(tmp_path: Path, mode: str, color):
    path = tmp_path / "bad-logo.png"
    Image.new(mode, (40, 40), color).save(path)
    with pytest.raises(cover.CoverError, match="alfa real"):
        cover.read_logo(path)


def test_palette_transparency(tmp_path: Path):
    path = tmp_path / "palette.png"
    image = Image.new("P", (10, 10), 0)
    image.putpalette([0, 0, 0, 255, 255, 255] + [0] * 762)
    image.putpixel((5, 5), 1)
    image.save(path, transparency=0)
    assert cover.read_logo(path).getchannel("A").getextrema() == (0, 255)
    assert cover.read_source(path, []).getpixel((0, 0))[3] == 0


@pytest.mark.parametrize(
    "background, expected",
    [("black", "white"), ("white", "black"), ("#808080", "black")],
)
def test_auto_linear_luminance(background: str, expected: str):
    region = Image.new("RGB", (20, 20), background)
    chosen, luminance, contrast = cover.choose_color(
        region, Image.new("L", region.size, 255), "auto"
    )
    assert chosen == expected
    assert 0 <= luminance <= 1
    assert contrast >= 4.5
    if background == "#808080":
        assert luminance == pytest.approx(0.21586, abs=0.0001)


def test_auto_weights_only_visible_strokes():
    region = Image.new("RGB", (100, 10), "white")
    region.paste("black", (0, 0, 10, 10))
    alpha = Image.new("L", region.size, 0)
    alpha.paste(255, (0, 0, 10, 10))
    chosen, luminance, contrast = cover.choose_color(region, alpha, "auto")
    assert (chosen, luminance, contrast) == ("white", 0, 21)


@pytest.mark.parametrize("color", ["white", "black"])
def test_forced_color(color: str):
    assert (
        cover.choose_color(
            Image.new("RGB", (2, 2), color), Image.new("L", (2, 2), 255), color
        )[0]
        == color
    )


def test_empty_resized_alpha_rejected():
    with pytest.raises(cover.CoverError, match="trazos visibles"):
        cover.choose_color(Image.new("RGB", (2, 2)), Image.new("L", (2, 2)), "auto")


@pytest.mark.parametrize(
    "position, expected",
    [
        ("top-left", (24, 36, 132, 105)),
        ("top-right", (468, 36, 576, 105)),
        ("bottom-left", (24, 795, 132, 864)),
        ("bottom-right", (468, 795, 576, 864)),
    ],
)
def test_box_positions(position: str, expected: tuple[int, int, int, int]):
    assert cover.logo_box((600, 900), (108, 69), position, 0.04) == expected


def test_logo_must_fit():
    with pytest.raises(cover.CoverError, match="no caben"):
        cover.logo_box((600, 900), (600, 50), "bottom-right", 0.04)


def test_contain_preserves_edges_and_uses_padding():
    image = Image.new("RGBA", (100, 100), "white")
    image.paste("red", (0, 0, 100, 10))
    image.paste("blue", (0, 90, 100, 100))
    warnings = []
    result = cover.fit_cover(image, (600, 900), "contain", (12, 34, 56), warnings)
    assert result.getpixel((300, 0)) == (12, 34, 56)
    assert result.getpixel((300, 160)) == (255, 0, 0)
    assert result.getpixel((300, 740)) == (0, 0, 255)
    assert result.getpixel((300, 899)) == (12, 34, 56)
    assert any("Baja resolución" in w for w in warnings)
    assert not any("Recorte" in w for w in warnings)


def test_crop_is_explicit_and_warns():
    image = Image.new("RGBA", (900, 900), "white")
    image.paste("red", (0, 0, 100, 900))
    warnings = []
    result = cover.fit_cover(image, (600, 900), "crop", (0, 0, 0), warnings)
    assert result.getpixel((0, 450)) == (255, 255, 255)
    assert any("Recorte central explícito" in w for w in warnings)
    assert not any("Baja resolución" in w for w in warnings)


def test_source_alpha_composites_on_background():
    result = cover.fit_cover(
        Image.new("RGBA", (600, 900), (255, 0, 0, 128)),
        (600, 900),
        "contain",
        (0, 0, 255),
        [],
    )
    assert result.getpixel((0, 0)) == (128, 0, 127)


def test_exif_orientation_and_source_unchanged(tmp_path: Path):
    path = tmp_path / "rotated.jpg"
    exif = Image.Exif()
    exif[274] = 6
    Image.new("RGB", (900, 600), "red").save(path, exif=exif)
    before = path.read_bytes()
    oriented = cover.read_source(path, [])
    assert oriented.size == (600, 900)
    assert path.read_bytes() == before
    assert oriented.getexif().get(274) is None


def test_embedded_profile_preserves_alpha(tmp_path: Path):
    path = tmp_path / "profile.png"
    Image.new("RGBA", (10, 20), (20, 40, 60, 128)).save(
        path, icc_profile=cover.SRGB.tobytes()
    )
    result = cover.read_source(path, [])
    assert result.mode == "RGBA"
    assert result.getpixel((0, 0)) == (20, 40, 60, 128)


def test_lab_profile_converted(tmp_path: Path):
    path = tmp_path / "lab.tif"
    profile = ImageCms.ImageCmsProfile(ImageCms.createProfile("LAB"))
    Image.new("LAB", (10, 20), (128, 128, 128)).save(
        path, icc_profile=profile.tobytes()
    )
    assert cover.read_source(path, []).mode == "RGBA"


def test_cmyk_without_profile_warns(tmp_path: Path):
    path = tmp_path / "cmyk.jpg"
    Image.new("CMYK", (10, 20), (0, 255, 255, 0)).save(path)
    warnings = []
    assert cover.read_source(path, warnings).mode == "RGBA"
    assert any("CMYK sin ICC" in w for w in warnings)


def test_bad_profile_rejected(tmp_path: Path):
    path = tmp_path / "bad-icc.png"
    Image.new("RGB", (10, 20)).save(path, icc_profile=b"not a profile")
    with pytest.raises(cover.CoverError, match="perfil ICC"):
        cover.read_source(path, [])


def test_multiple_frames_rejected(tmp_path: Path):
    path = tmp_path / "animated.gif"
    Image.new("RGB", (20, 20), "red").save(
        path,
        save_all=True,
        append_images=[Image.new("RGB", (20, 20), "blue")],
        duration=100,
    )
    with pytest.raises(cover.CoverError, match="sola imagen"):
        cover.read_source(path, [])


@pytest.mark.parametrize("size", [(600, 900), (1200, 1800)])
def test_jpeg_format_size_metadata_and_source_intact(
    source: Path, tmp_path: Path, size
):
    output = tmp_path / "cover.jpg"
    before = sha256(source.read_bytes()).digest()
    report = cover.build_cover(source, output, size=size)
    assert report.size == size
    assert report.byte_count == output.stat().st_size
    assert report.color == "black"
    assert sha256(source.read_bytes()).digest() == before
    assert not any("Se amplía el logo" in w for w in report.warnings)
    with Image.open(output) as result:
        assert result.format == "JPEG"
        assert result.mode == "RGB"
        assert result.size == size
        assert not result.info.get("progressive")
        assert not result.getexif()
        assert "sRGB" in ImageCms.getProfileName(
            ImageCms.ImageCmsProfile(BytesIO(result.info["icc_profile"]))
        )


def test_existing_output_unchanged(source: Path, tmp_path: Path):
    output = tmp_path / "cover.jpg"
    output.write_bytes(b"KEEP")
    with pytest.raises(cover.CoverError, match="ya existe"):
        cover.build_cover(source, output)
    assert output.read_bytes() == b"KEEP"


def test_same_input_output_unchanged(source: Path):
    before = source.read_bytes()
    with pytest.raises(cover.CoverError, match="distintas"):
        cover.build_cover(source, source)
    assert source.read_bytes() == before


@pytest.mark.parametrize("dangling", [True, False])
def test_symlink_output_not_overwritten(source: Path, tmp_path: Path, dangling: bool):
    target = tmp_path / "absent" if dangling else source
    output = tmp_path / "link.jpg"
    output.symlink_to(target)
    with pytest.raises(cover.CoverError):
        cover.build_cover(source, output)
    assert output.is_symlink()
    if dangling:
        assert not target.exists()


def test_exclusive_output_handles_race(source: Path, tmp_path: Path, monkeypatch):
    output = tmp_path / "race.jpg"
    original = Path.open

    def racing_open(path, mode="r", *args, **kwargs):
        if path == output and mode == "xb":
            with original(path, "wb") as stream:
                stream.write(b"OTHER WRITER")
        return original(path, mode, *args, **kwargs)

    monkeypatch.setattr(Path, "open", racing_open)
    with pytest.raises(cover.CoverError, match="ya existe"):
        cover.build_cover(source, output)
    assert output.read_bytes() == b"OTHER WRITER"


@pytest.mark.parametrize(
    "kwargs",
    [
        {"size": (400, 600)},
        {"fit": "stretch"},
        {"position": "middle"},
        {"logo_color": "red"},
        {"logo_width": 0},
        {"logo_width": float("nan")},
        {"margin": -0.1},
        {"margin": 0.5},
        {"quality": 0},
        {"quality": 101},
        {"background": "no such color"},
        {"background": "#ffffff80"},
    ],
)
def test_invalid_options_leave_no_output(source: Path, tmp_path: Path, kwargs):
    output = tmp_path / "cover.jpg"
    with pytest.raises(cover.CoverError):
        cover.build_cover(source, output, **kwargs)
    assert not output.exists()


def test_wrong_extension_rejected(source: Path, tmp_path: Path):
    output = tmp_path / "cover.png"
    with pytest.raises(cover.CoverError, match="JPEG"):
        cover.build_cover(source, output)
    assert not output.exists()


def test_overweight_warns_without_quality_reduction(tmp_path: Path):
    source = tmp_path / "noise.png"
    Image.effect_noise((1200, 1800), 100).convert("RGB").save(source)
    output = tmp_path / "cover.jpg"
    report = cover.build_cover(source, output, size=(1200, 1800))
    assert report.byte_count > cover.TARGET_BYTES
    assert report.quality == 92
    assert any("No se redujo automáticamente" in w for w in report.warnings)


def test_low_contrast_forced_color_warns(source: Path, tmp_path: Path):
    report = cover.build_cover(source, tmp_path / "cover.jpg", logo_color="white")
    assert report.color == "white"
    assert any("Contraste medio bajo" in w for w in report.warnings)


def test_upscaled_logo_warns(source: Path, logo: Path, tmp_path: Path):
    report = cover.build_cover(
        source, tmp_path / "cover.jpg", logo_path=logo, logo_width=0.3
    )
    assert any("Se amplía el logo" in w for w in report.warnings)


def test_auto_uses_selected_corner(source: Path, tmp_path: Path):
    image = Image.new("RGB", (600, 900), "white")
    image.paste("black", (300, 450, 600, 900))
    image.save(source)
    right = cover.build_cover(source, tmp_path / "right.jpg")
    left = cover.build_cover(source, tmp_path / "left.jpg", position="bottom-left")
    assert right.color == "white"
    assert left.color == "black"


def test_cli_defaults_and_portability(
    source: Path, tmp_path: Path, monkeypatch, capsys
):
    monkeypatch.chdir(tmp_path)
    assert cover.main([str(source), "cover.jpg"]) == 0
    captured = capsys.readouterr()
    assert "600×900 (2:3)" in captured.out
    assert "bottom-right" in captured.out
    assert "color black" in captured.out
    assert "bytes" in captured.out
    assert "Revisión visual pendiente" in captured.out
    assert (tmp_path / "cover.jpg").exists()


def test_cli_all_options(source: Path, tmp_path: Path, capsys):
    output = tmp_path / "cover.jpeg"
    assert (
        cover.main(
            [
                str(source),
                str(output),
                "--size",
                "1200x1800",
                "--fit",
                "crop",
                "--position",
                "top-left",
                "--logo-color",
                "white",
                "--background",
                "#123456",
                "--logo-width",
                "15%",
                "--margin",
                "3%",
                "--quality",
                "90",
            ]
        )
        == 0
    )
    captured = capsys.readouterr()
    assert "top-left" in captured.out
    assert "Recorte central explícito" in captured.err


def test_cli_error_and_missing_source(tmp_path: Path, capsys):
    output = tmp_path / "cover.jpg"
    assert cover.main([str(tmp_path / "missing.png"), str(output)]) == 2
    assert "ERROR:" in capsys.readouterr().err
    assert not output.exists()


def test_cli_rejects_invalid_percentage(source: Path, tmp_path: Path):
    with pytest.raises(SystemExit) as exc:
        cover.main([str(source), str(tmp_path / "cover.jpg"), "--margin", "4"])
    assert exc.value.code == 2


def test_help_standalone_from_another_directory(tmp_path: Path):
    result = subprocess.run(
        [sys.executable, str(Path(cover.__file__).resolve()), "--help"],
        cwd=tmp_path,
        check=False,
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert result.returncode == 0
    assert "--logo-color" in result.stdout
    assert "--background" in result.stdout
