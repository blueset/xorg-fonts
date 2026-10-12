import contextlib
import io
import json
import os
import shutil
import struct
import subprocess
import tempfile
import unittest
from pathlib import Path

import build


def ttf_tables(path):
    data = path.read_bytes()
    tables = {}
    for index in range(struct.unpack_from(">H", data, 4)[0]):
        tag, _, offset, length = struct.unpack_from(">4sIII", data, 12 + 16 * index)
        tables[tag.decode()] = data[offset:offset + length]
    return tables


class FontBuildTests(unittest.TestCase):
    def test_courier_styles_share_metrics_without_mixing_strikes(self):
        fonts = build.load_fonts()
        folder = build.ROOT / "font-adobe-100dpi-1.0.4"
        styles = [fonts[folder / f"cour{style}10.bdf"] for style in ("R", "O", "B", "BO")]
        self.assertEqual({f["size"] for f in styles}, {15})
        self.assertEqual({(f["ascent"], f["descent"]) for f in styles}, {(11, 4)})
        self.assertEqual(len({f["strike"] for f in styles}), 1)
        other = fonts[folder / "courR12.bdf"]
        self.assertEqual(other["size"], 15)
        self.assertNotEqual(styles[0]["strike"], other["strike"])
        self.assertNotEqual(
            styles[0]["strike"],
            fonts[build.ROOT / "font-adobe-75dpi-1.0.4/courR10.bdf"]["strike"],
        )

    def test_non_style_attributes_and_fixed_widths_separate_strikes(self):
        path = Path("source/font.bdf")
        properties = {
            "FAMILY_NAME": "Example", "PIXEL_SIZE": "14", "SPACING": "P",
            "AVERAGE_WIDTH": "70",
        }
        key = build.strike_key(path, properties)
        for name in build.STRIKE_PROPERTIES:
            with self.subTest(name=name):
                changed = dict(properties, **{name: "15" if name == "PIXEL_SIZE" else "Other"})
                self.assertNotEqual(key, build.strike_key(path, changed))
        for name in ("WEIGHT_NAME", "SLANT", "AVERAGE_WIDTH"):
            self.assertEqual(key, build.strike_key(path, dict(properties, **{name: "Other"})))
        properties["SPACING"] = "C"
        self.assertNotEqual(
            build.strike_key(path, properties),
            build.strike_key(path, dict(properties, AVERAGE_WIDTH="80")),
        )
        fonts = build.load_fonts()
        folder = build.ROOT / "font-misc-misc-1.1.3"
        self.assertNotEqual(fonts[folder / "7x13.bdf"]["strike"], fonts[folder / "8x13.bdf"]["strike"])

    def test_incomplete_metadata_is_isolated(self):
        for properties in ({}, {"FAMILY_NAME": "Example"}, {"PIXEL_SIZE": "14"}):
            self.assertNotEqual(
                build.strike_key(Path("source/a.bdf"), properties),
                build.strike_key(Path("source/b.bdf"), properties),
            )

    def test_normalization_preserves_glyphs_and_source(self):
        for path in build.ROOT.glob("*/*.bdf"):
            with self.subTest(path=path):
                before = path.read_text()
                normalized = build.normalized_bdf(path, 30, 10)
                self.assertEqual(before[before.index("\nCHARS "):], normalized[normalized.index("\nCHARS "):])
                self.assertIn("\nFONT_ASCENT 30\n", normalized)
                self.assertIn("\nFONT_DESCENT 10\n", normalized)
                self.assertEqual(path.read_text(), before)

    def test_missing_metrics_and_zero_metrics(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            folder = root / "source"
            folder.mkdir()
            path = folder / "font.bdf"
            path.write_text(
                'STARTFONT 2.1\nSTARTPROPERTIES 2\n'
                'FAMILY_NAME "Example"\nPIXEL_SIZE 14\nENDPROPERTIES\nCHARS 0\nENDFONT\n'
            )
            font = build.load_fonts(root)[path]
            self.assertEqual((font["ascent"], font["descent"], font["size"]), (14, 0, 14))
            normalized = build.normalized_bdf(path, 14, 0)
            self.assertIn("STARTPROPERTIES 4\n", normalized)
            self.assertIn("ENDPROPERTIES\nCHARS 0\n", normalized)
            path.write_text("STARTFONT 2.1\nCHARS 0\nENDFONT\n")
            normalized = build.normalized_bdf(path, 0, 0)
            self.assertIn("STARTPROPERTIES 2\nFONT_ASCENT 0\nFONT_DESCENT 0\nENDPROPERTIES\n", normalized)
            self.assertEqual(build.load_fonts(root)[path]["size"], 0)

    def test_maximum_ascent_and_descent_are_independent(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            folder = root / "source"
            folder.mkdir()
            for name, ascent, descent in (("regular", 11, 3), ("bold", 10, 5)):
                (folder / f"{name}.bdf").write_text(
                    'STARTFONT 2.1\nSTARTPROPERTIES 4\nFAMILY_NAME "Example"\n'
                    f'PIXEL_SIZE 14\nFONT_ASCENT {ascent}\nFONT_DESCENT {descent}\n'
                    'ENDPROPERTIES\nCHARS 0\nENDFONT\n'
                )
            fonts = build.load_fonts(root)
            self.assertEqual({(f["ascent"], f["descent"], f["size"]) for f in fonts.values()}, {(11, 5, 16)})
            build.build_json(fonts, root)
            summary = json.loads((root / "build_summary.json").read_text())
            self.assertEqual(summary["source"]["regular"], fonts[folder / "regular.bdf"])

    def test_published_metrics_match_every_ttf(self):
        fonts = build.load_fonts()
        summary = json.loads((build.ROOT / "build_summary.json").read_text())
        for path, font in fonts.items():
            with self.subTest(path=path):
                self.assertEqual(summary[path.parent.name][path.stem], font)
                tables = ttf_tables(path.with_suffix(".ttf"))
                self.assertEqual(struct.unpack_from(">H", tables["head"], 18)[0], font["size"] * 100)
                expected = (font["ascent"] * 100, -font["descent"] * 100, 0)
                self.assertEqual(struct.unpack_from(">hhh", tables["hhea"], 4), expected)
                self.assertEqual(struct.unpack_from(">hhh", tables["OS/2"], 68), expected)
                self.assertEqual(
                    struct.unpack_from(">HH", tables["OS/2"], 74),
                    (font["ascent"] * 100, font["descent"] * 100),
                )

    @unittest.skipUnless(os.environ.get("BITSNPICAS"), "Set BITSNPICAS for converter integration")
    def test_converter_preserves_outlines_offsets_and_advances(self):
        jar = str(Path(os.environ["BITSNPICAS"]).resolve())
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            folder = root / "source"
            folder.mkdir()
            for style in ("R", "O", "B", "BO"):
                source = build.ROOT / f"font-adobe-100dpi-1.0.4/cour{style}10.bdf"
                shutil.copyfile(source, folder / source.name)
            fonts = build.load_fonts(root)
            with contextlib.redirect_stdout(io.StringIO()):
                build.build(fonts)
            for path, font in fonts.items():
                with self.subTest(path=path):
                    original = root / f"original-{path.stem}.ttf"
                    subprocess.run(
                        ["java", "-jar", jar, "convertbitmap", "-f", "ttf",
                         "-o", str(original), "-w", "100", "-h", "100", "-T", str(path)],
                        check=True, capture_output=True,
                    )
                    before = ttf_tables(original)
                    after = ttf_tables(path.with_suffix(".ttf"))
                    for tag in ("glyf", "loca", "hmtx", "cmap"):
                        self.assertEqual(before[tag], after[tag], tag)
                    self.assertEqual(struct.unpack_from(">H", after["head"], 18)[0], 1500)
                    self.assertEqual(struct.unpack_from(">hhh", after["hhea"], 4), (1100, -400, 0))


if __name__ == "__main__":
    unittest.main()
