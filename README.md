# Xorg Fonts

Xorg bitmap fonts traced to TTF format.

Source: https://xorg.freedesktop.org/releases/individual/font/
License: Various licenses, see individual font files for details.

Preview: https://blueset.github.io/xorg-fonts/

## Building

Install Java and the Python `tqdm` package, and set `BITSNPICAS` to the absolute
path of a [Bits’n’Picas](https://github.com/kreativekorp/bitsnpicas) JAR
(otherwise `bitsnpicas.jar` beside `build.py` is used).

Run `python build.py --convert` to rebuild the TTFs and `build_summary.json`.
Run `python build.py` to regenerate only the metadata; after changing source
metrics or grouping, rebuild the TTFs too.

Styles of the same bitmap strike share the maximum source ascent and maximum
source descent. Strikes are matched within each source folder by family,
foundry, nominal pixel/point size, resolution, width class, additional style,
spacing and character set; fixed-width fonts also retain their cell width.
Fonts without enough strike metadata are kept separate.

Only temporary BDF properties are normalized. Source bitmaps, glyph offsets,
advance widths and BDF files are not changed. Bits’n’Picas imports `FONT_ASCENT`
and `FONT_DESCENT` as both em and line metrics, and exports 100 font units per
bitmap pixel with `unitsPerEm = (ascent + descent) × 100`. Thus the shared
`size` in the summary renders one source pixel per CSS pixel at 1× on a
pixel-aligned, 100%-scaled display. Integer multiples retain that grid;
fractional display/preview scales or fractional text origins may antialias.

The preview groups by strike identity, not by the resulting em size: different
strikes can have the same ascent-plus-descent total. Hover over a size cell to
inspect its strike identity.

Run the regression tests with `python -m unittest discover -s tests`.
With `BITSNPICAS` set, this also checks the converter's actual TTF output.
