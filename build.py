import subprocess
import glob
import os
from pathlib import Path
import json
from tqdm import tqdm

def build():
    summary = {}
    files = glob.glob("*/*.bdf")
    for file in tqdm(files):
        path = Path(file)
        folder = path.parent.name
        if folder not in summary:
            summary[folder] = {}
        name = path.stem
        if name not in summary[folder]:
            summary[folder][name] = {}
        font_size = 0
        family_name = ""
        weight_name = "Regular"
        slant = "R"
        charset_registry = ""
        with open(path, "r") as f:
            for line in f.readlines():
                if line.startswith("PIXEL_SIZE"):
                    font_size = int(line.split()[1])
                elif line.startswith("FAMILY_NAME"):
                    family_name = " ".join(line.split()[1:]).replace('"', '')
                elif line.startswith("WEIGHT_NAME"):
                    weight_name = " ".join(line.split()[1:]).replace('"', '')
                elif line.startswith("SLANT"):
                    slant = line.split()[1].replace('"', '')
                elif line.startswith("CHARSET_REGISTRY"):
                    charset_registry = " ".join(line.split()[1:]).replace('"', '')
        output_path = path.with_suffix(".ttf")

        cmd = [
            "-jar",
            os.environ.get("PITNPICAS", "pitnpicas.jar"),
            "convertbitmap",
            "-f", "ttf",
            "-o", str(output_path),
            "-s", f"(?<={family_name})",
            "-r", f" {font_size:0>2}",
            str(path)
        ]
        subprocess.run(["java"] + cmd, check=True)
        summary[folder][name]["size"] = font_size
        summary[folder][name]["family_name"] = family_name
        summary[folder][name]["weight_name"] = weight_name
        summary[folder][name]["slant"] = slant
        summary[folder][name]["charset_registry"] = charset_registry

        print(f"Built {output_path} ({family_name} {weight_name} {slant} {font_size})")

def build_json():
    summary = {}
    files = glob.glob("*/*.bdf")
    for file in tqdm(files):
        path = Path(file)
        folder = path.parent.name
        if folder not in summary:
            summary[folder] = {}
        name = path.stem
        if name not in summary[folder]:
            summary[folder][name] = {}
        font_size = 0
        family_name = ""
        weight_name = "Regular"
        slant = "R"
        charset_registry = ""
        with open(path, "r") as f:
            for line in f.readlines():
                if line.startswith("PIXEL_SIZE"):
                    font_size = int(line.split()[1])
                elif line.startswith("FAMILY_NAME"):
                    family_name = " ".join(line.split()[1:]).replace('"', '')
                elif line.startswith("WEIGHT_NAME"):
                    weight_name = " ".join(line.split()[1:]).replace('"', '')
                elif line.startswith("SLANT"):
                    slant = line.split()[1].replace('"', '')
                elif line.startswith("CHARSET_REGISTRY"):
                    charset_registry = " ".join(line.split()[1:]).replace('"', '')
        output_path = path.with_suffix(".ttf")

        summary[folder][name]["size"] = font_size
        summary[folder][name]["family_name"] = family_name
        summary[folder][name]["weight_name"] = weight_name
        summary[folder][name]["slant"] = slant
        summary[folder][name]["charset_registry"] = charset_registry

    with open("build_summary.json", "w") as f:
        json.dump(summary, f, indent=4)


if __name__ == "__main__":
    build_json()
