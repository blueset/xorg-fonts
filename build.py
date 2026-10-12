import argparse
import json
import os
import re
import shutil
import subprocess
import tempfile
from collections import defaultdict
from pathlib import Path

from tqdm import tqdm


ROOT = Path(__file__).resolve().parent
STRIKE_PROPERTIES = (
    "FOUNDRY", "FAMILY_NAME", "PIXEL_SIZE", "POINT_SIZE",
    "RESOLUTION_X", "RESOLUTION_Y", "SETWIDTH_NAME", "ADD_STYLE_NAME",
    "SPACING", "CHARSET_REGISTRY", "CHARSET_ENCODING",
)


def read_properties(path):
    properties = {}
    with path.open() as source:
        for line in source:
            parts = line.split(None, 1)
            if not parts:
                continue
            if parts[0] == "CHARS":
                break
            if len(parts) == 2:
                properties[parts[0]] = parts[1].strip().strip('"')
    return properties


def strike_key(path, properties):
    if not properties.get("FAMILY_NAME") or not int(properties.get("PIXEL_SIZE", 0)):
        return (path.parent.name, path.stem)
    key = (path.parent.name,) + tuple(
        properties.get(name, "").casefold() if name == "FOUNDRY"
        else properties.get(name, "")
        for name in STRIKE_PROPERTIES
    )
    # Fixed-width strikes of equal height can have different cell widths.
    if properties.get("SPACING") in ("C", "M"):
        key += (properties.get("AVERAGE_WIDTH", ""),)
    return key


def load_fonts(root=ROOT):
    groups = defaultdict(list)
    for path in sorted(root.glob("*/*.bdf")):
        properties = read_properties(path)
        groups[strike_key(path, properties)].append((path, properties))

    fonts = {}
    for key, members in groups.items():
        ascent = max(int(p.get("FONT_ASCENT", 0)) for _, p in members)
        descent = max(int(p.get("FONT_DESCENT", 0)) for _, p in members)
        if ascent + descent == 0:
            ascent = max(int(p.get("PIXEL_SIZE", 0)) for _, p in members)
        for path, properties in members:
            fonts[path] = {
                "size": ascent + descent,
                "family_name": properties.get("FAMILY_NAME", ""),
                "weight_name": properties.get("WEIGHT_NAME", "Regular"),
                "slant": properties.get("SLANT", "R"),
                "charset_registry": properties.get("CHARSET_REGISTRY", ""),
                "pixel_size": int(properties.get("PIXEL_SIZE", 0)),
                "ascent": ascent,
                "descent": descent,
                "strike": json.dumps(key, separators=(",", ":")),
            }
    return fonts


def normalized_bdf(path, ascent, descent):
    text = path.read_text()
    header, glyphs = re.split(
        r"(?=^CHARS[ \t]+\d+[ \t]*$)", text, maxsplit=1, flags=re.MULTILINE,
    )
    metrics = {"FONT_ASCENT": ascent, "FONT_DESCENT": descent}
    block = re.search(
        r"^STARTPROPERTIES[ \t]+\d+\n(.*?)^ENDPROPERTIES[ \t]*$",
        header, re.MULTILINE | re.DOTALL,
    )
    if block:
        properties = block.group(1).splitlines()
        for name, value in metrics.items():
            for index, line in enumerate(properties):
                if line.split(None, 1)[:1] == [name]:
                    properties[index] = f"{name} {value}"
                    break
            else:
                properties.append(f"{name} {value}")
        replacement = (
            f"STARTPROPERTIES {len(properties)}\n"
            + "\n".join(properties) + "\nENDPROPERTIES"
        )
        header = header[:block.start()] + replacement + header[block.end():]
    else:
        header += (
            f"STARTPROPERTIES 2\nFONT_ASCENT {ascent}\n"
            f"FONT_DESCENT {descent}\nENDPROPERTIES\n"
        )
    # BBX, DWIDTH and BITMAP remain unchanged, including baseline offsets.
    return header + glyphs


def build(fonts=None):
    if fonts is None:
        fonts = load_fonts()
    jar = str(Path(os.environ.get("BITSNPICAS", ROOT / "bitsnpicas.jar")).resolve())
    with tempfile.TemporaryDirectory(prefix="xorg-fonts-") as temporary:
        for path, font in tqdm(fonts.items()):
            source = Path(temporary) / path.name
            source.write_text(normalized_bdf(path, font["ascent"], font["descent"]))
            output_path = path.with_suffix(".ttf")
            converted = source.with_suffix(".ttf")
            cmd = [
                "java", "-jar", jar, "convertbitmap",
                "-f", "ttf", "-o", str(converted),
                "-w", "100", "-h", "100", "-T",
                "-s", f"(?<={re.escape(font['family_name'])})",
                "-r", f" {font['size']:0>2}",
                str(source),
            ]
            subprocess.run(cmd, check=True)
            # The converter creates numbered siblings instead of overwriting.
            shutil.move(str(converted), str(output_path))
            print(f"Built {output_path} ({font['family_name']} {font['size']})")


def build_json(fonts=None, root=ROOT):
    if fonts is None:
        fonts = load_fonts(root)
    summary = {}
    for path, font in sorted(fonts.items()):
        summary.setdefault(path.parent.name, {})[path.stem] = font
    with (root / "build_summary.json").open("w") as output:
        json.dump(summary, output, indent=4)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--convert", action="store_true", help="Rebuild TTFs as well as metadata")
    args = parser.parse_args()
    fonts = load_fonts()
    if args.convert:
        build(fonts)
    build_json(fonts)
