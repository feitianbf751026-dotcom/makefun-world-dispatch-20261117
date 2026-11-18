# SPDX-License-Identifier: MIT
"""Compose the 17 November edition from original illustrations and sourced copy."""

import argparse
import json
import math
import random
from functools import lru_cache
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent
ASSETS = ROOT / "assets"
SCALE = 2
PAPER = "#f5eee0"
INK = "#182b31"
MUTED = "#435457"
RULE = "#b8b5a6"
RED = "#9f3d34"
CREAM = "#f9eed7"
W = 1024
MAP_BOX = (49.1, 22.9, 58.3, 29.05)


@lru_cache
def font(face, size, weight):
    name = "Newsreader" if face == "serif" else "IBMPlexSans"
    result = ImageFont.truetype(ASSETS / f"{name}.ttf", size * SCALE)
    by_name = {b"Optical Size": min(72, max(10, size)), b"Weight": weight}
    result.set_variation_by_axes([
        by_name.get(axis["name"], axis["default"])
        for axis in result.get_variation_axes()
    ])
    return result


class Canvas:
    def __init__(self, width, height, background):
        self.image = Image.new("RGB", (width * SCALE, height * SCALE), background)
        self.pen = ImageDraw.Draw(self.image)

    @staticmethod
    def px(values):
        return tuple(round(v * SCALE) for v in values)

    def rect(self, box, fill, outline=None, width=1):
        self.pen.rectangle(self.px(box), fill, outline, width * SCALE)

    def ellipse(self, box, fill=None, outline=None, width=1):
        self.pen.ellipse(self.px(box), fill, outline, width * SCALE)

    def path(self, points, fill, width=1):
        self.pen.line([self.px(p) for p in points], fill, width * SCALE, joint="curve")

    def poly(self, points, fill):
        self.pen.polygon([self.px(p) for p in points], fill)

    def arc(self, box, start, end, fill, width=1):
        self.pen.arc(self.px(box), start, end, fill, width * SCALE)

    def paste(self, other, x, y):
        self.image.paste(other.image, self.px((x, y)))

    def text(self, x, y, message, size, *, face="sans", weight=450, fill=INK, anchor="lt"):
        self.pen.text(self.px((x, y)), message, font=font(face, size, weight), fill=fill, anchor=anchor)

    def lines(self, x, y, lines, size, step, **style):
        for index, line in enumerate(lines):
            self.text(x, y + index * step, line, size, **style)

    def check_width(self, lines, limit, size, face="sans", weight=450):
        for line in lines:
            length = self.pen.textlength(line, font=font(face, size, weight)) / SCALE
            if length > limit:
                raise ValueError(f"line width {length:.1f} > {limit}: {line}")


def clip_ring(points, bounds):
    """Sutherland–Hodgman clipping against the four sides of the map."""
    west, south, east, north = bounds
    for axis, side, keep_sign in ((0, west, 1), (0, east, -1), (1, south, 1), (1, north, -1)):
        if not points:
            break
        result = []
        previous = points[-1]
        for point in points:
            p_inside = (previous[axis] - side) * keep_sign >= 0
            c_inside = (point[axis] - side) * keep_sign >= 0
            if p_inside != c_inside:
                fraction = (side - previous[axis]) / (point[axis] - previous[axis])
                result.append(tuple(a + fraction * (b - a) for a, b in zip(previous, point)))
            if c_inside:
                result.append(point)
            previous = point
        points = result
    return points


def import_map(source):
    features = json.loads(source.read_text(encoding="utf-8"))["features"]
    clipped = []
    for feature in features:
        code = feature["properties"]["ADM0_A3"]
        if code not in {"IRN", "SAU", "BHR", "QAT", "ARE", "OMN"}:
            continue
        shape = feature["geometry"]
        polygons = shape["coordinates"] if shape["type"] == "MultiPolygon" else [shape["coordinates"]]
        for polygon in polygons:
            ring = clip_ring(polygon[0], MAP_BOX)
            compact = [(round(lon, 3), round(lat, 3)) for lon, lat in ring]
            if len(set(compact)) >= 3:
                clipped.append([code, compact])
    if {item[0] for item in clipped} != {"IRN", "SAU", "BHR", "QAT", "ARE", "OMN"}:
        raise ValueError("Natural Earth input is missing part of the map")
    (ASSETS / "gulf.json").write_text(json.dumps(clipped, separators=(",", ":")) + "\n", encoding="utf-8")


def gulf_map():
    width, height = 510, 272
    sea, land, edge = "#18343b", "#e5cc9c", "#f0ddb5"
    graphic = Canvas(width, height, sea)
    west, south, east, north = MAP_BOX

    def pos(lon, lat):
        return (lon - west) * width / (east - west), (north - lat) * height / (north - south)

    for lon in range(50, 59):
        x, _ = pos(lon, north)
        graphic.path([(x, 0), (x, height)], "#345057")
    for lat in range(23, 30):
        _, y = pos(west, lat)
        graphic.path([(0, y), (width, y)], "#345057")

    shape = json.loads((ASSETS / "gulf.json").read_text(encoding="utf-8"))
    for code, polygon in shape:
        points = [pos(lon, lat) for lon, lat in polygon]
        graphic.poly(points, land if code == "IRN" else "#c9b78e")
        graphic.path(points + [points[0]], edge)

    rng = random.Random(1702)
    for _ in range(8100):
        x, y = rng.randrange(width * SCALE), rng.randrange(height * SCALE)
        shade = graphic.image.getpixel((x, y))
        if shade in {(229, 204, 156), (201, 183, 142)}:
            graphic.pen.point((x, y), fill=tuple(value - 19 for value in shade))

    graphic.text(286, 35, "I R A N", 17, weight=650)
    graphic.text(26, 205, "SAUDI ARABIA", 15, weight=620)
    graphic.text(253, 225, "U.A.E.", 15, weight=620)
    graphic.text(413, 236, "OMAN", 15, weight=620)
    graphic.text(178, 162, "PERSIAN GULF", 14, weight=650, fill="#c6d9d5")
    graphic.lines(490, 171, ("STRAIT OF", "HORMUZ"), 13, 16, weight=630, fill="#e7dfca", anchor="rt")

    def marker(lon, lat, label, number, dx, dy):
        x, y = pos(lon, lat)
        line_x = x + dx
        line_y = y + dy
        graphic.path([(x, y), (line_x, y), (line_x, line_y)], "#e9ae7d", 2)
        graphic.ellipse((x-13, y-13, x+13, y+13), RED, CREAM, 2)
        graphic.text(x, y, number, 15, weight=700, fill=CREAM, anchor="mm")
        graphic.text(line_x + (5 if dx > 0 else -5), line_y - 6, label, 16,
                     weight=690, fill=CREAM, anchor="lt" if dx > 0 else "rt")

    marker(50.58, 26.14, "BAHRAIN", "1", 34, -32)
    marker(55.85, 26.76, "QESHM", "2", -33, 36)
    graphic.text(12, 12, "N ↑", 13, weight=680, fill=CREAM)
    return graphic


def summit_art():
    graphic = Canvas(300, 115, "#193d4d")
    graphic.ellipse((120, -65, 314, 128), "#df9169")
    graphic.ellipse((154, -42, 304, 109), "#f2b97e")
    columns = [(0, 79), (19, 71), (35, 78), (65, 54), (91, 73), (103, 62),
               (118, 73), (135, 51), (158, 77), (174, 68), (193, 84), (221, 61),
               (239, 72), (255, 54), (283, 77), (300, 78)]
    outline = []
    for (left, top), (right, _) in zip(columns, columns[1:]):
        outline.extend([(left, top), (right, top)])
    graphic.poly(outline + [(300, 115), (0, 115)], "#234452")
    for x in range(4, 300, 6):
        for y in (89, 96, 103):
            if (x * 7 + y * 13) % 11 < 5:
                graphic.rect((x, y, x+2, y+1), "#618086")
    # Four microphones reference the four delegations at the Quad meeting.
    for x, y in [(44, 59), (107, 48), (186, 45), (248, 56)]:
        tip = (x + (12 if x < 150 else -12), y - 9)
        graphic.path([(x, 102), (x, y), tip], CREAM, 2)
        graphic.ellipse((tip[0]-4, tip[1]-4, tip[0]+4, tip[1]+4), CREAM)
        graphic.path([(x-11, 103), (x+11, 103)], CREAM, 2)
    return graphic


def ebola_art():
    graphic = Canvas(300, 115, "#782d39")
    for i in range(8):
        graphic.arc((127 + i*10, -62 + i*10, 390-i*4, 187-i*4), 95, 259, "#ab5961")
    graphic.path([(151, 16), (151, 99)], "#c7827c")
    graphic.text(14, 23, "11,300+", 33, face="serif", weight=760, fill=CREAM)
    graphic.text(166, 23, "5,500+", 33, face="serif", weight=760, fill=CREAM)
    graphic.text(16, 70, "REPORTED CASES", 14, weight=650, fill=CREAM)
    graphic.text(168, 70, "DEATHS", 14, weight=650, fill=CREAM)
    return graphic


def climate_art():
    graphic = Canvas(300, 115, "#d7ca91")
    graphic.ellipse((176, -7, 286, 103), "#e7b35f")
    graphic.poly([(0, 94), (59, 89), (137, 99), (197, 82), (256, 84),
                  (300, 67), (300, 115), (0, 115)], "#8a9b79")
    graphic.poly([(0, 109), (77, 103), (122, 110), (229, 95), (300, 97),
                  (300, 115), (0, 115)], "#456a61")
    for x, y, size in [(223, 39, 28), (262, 55, 19)]:
        graphic.path([(x, y), (x-2, 99)], "#28484c", 3)
        for degrees in (30, 150, 270):
            angle = math.radians(degrees)
            tip = (x + size * math.cos(angle), y + size * math.sin(angle))
            graphic.path([(x, y), tip], "#28484c", 3)
        graphic.ellipse((x-3, y-3, x+3, y+3), CREAM)
    graphic.text(13, 21, "$200M", 46, face="serif", weight=730)
    graphic.text(16, 73, "APPROX. IN PLEDGES", 14, weight=700)
    return graphic


def compose():
    page = Canvas(W, W, PAPER)
    page.path([(42, 39), (982, 39)], RED, 3)
    page.text(43, 48, "THE WORLD IN ONE DAY", 16, weight=680, fill=RED)
    page.text(43, 74, "World Dispatch", 87, face="serif", weight=700)
    page.path([(783, 53), (783, 151)], RULE, 1)
    page.text(978, 56, "TUESDAY", 17, weight=680, fill=RED, anchor="rt")
    page.text(981, 83, "17 NOV", 46, face="serif", weight=730, anchor="rt")
    page.text(978, 137, "2026", 19, weight=650, anchor="rt")
    page.path([(42, 162), (982, 162)], INK, 2)

    page.text(43, 183, "WEST ASIA  /  SECURITY", 16, weight=700, fill=RED)
    page.lines(42, 218, ("U.S. and Iran", "trade strikes"), 63, 59, face="serif", weight=740)
    page.lines(44, 354, (
        "Iran hit a U.S. radar site in Bahrain.",
        "The U.S. struck a missile site on",
        "Iran’s Qeshm Island in response.",
    ), 22, 27, weight=480)
    page.text(45, 437, "SOURCE  AP / REUTERS", 14, weight=670, fill=MUTED)
    page.paste(gulf_map(), 472, 182)

    page.path([(42, 473), (982, 473)], INK, 2)
    cards = [
        (42, "MANILA  /  DIPLOMACY", ("Trump at ASEAN", "and Quad talks"),
         ("U.S.–Thai trade talks were", "largely complete, both said."),
         "AP / WHITE HOUSE", summit_art()),
        (362, "DR CONGO  /  HEALTH", ("WHO reviews", "Ebola emergency"),
         ("Cases and deaths more than", "doubled in three months."),
         "WHO", ebola_art()),
        (682, "ANTALYA  /  CLIMATE", ("Four pledge", "new COP31 funds"),
         ("Ministers also discussed", "faster emissions cuts by 2030."),
         "GEF / UNFCCC", climate_art()),
    ]
    for x, label, head, copy, source, illustration in cards:
        page.paste(illustration, x, 491)
        page.text(x, 619, label, 16, weight=690, fill=RED)
        page.check_width(head, 300, 35, "serif", 730)
        page.lines(x, 647, head, 35, 32, face="serif", weight=730)
        page.check_width(copy, 300, 19, "sans", 460)
        page.lines(x, 722, copy, 19, 24, weight=460)
        page.text(x, 774, f"SOURCE  {source}", 13, weight=680, fill=MUTED)
    for x in (352, 672):
        page.path([(x, 491), (x, 786)], RULE)

    page.rect((42, 805, 981, 974), "#eae3d3")
    page.path([(42, 805), (982, 805)], INK, 2)
    briefs = [
        (56, 821, "UKRAINE  /  AP", "Kerch Bridge hit again",
         "Kyiv said a road span collapsed after its strike."),
        (519, 821, "BUSINESS  /  NVIDIA", "Nvidia posts $115.8bn in sales",
         "Quarterly revenue more than doubled year on year."),
        (56, 900, "SPACE  /  NASA JPL", "A light for Voyager 1",
         "New York’s Empire State Building lit gold for the probe."),
        (519, 900, "SOUTH AMERICA  /  HOLY SEE", "Pope caps three-nation tour",
         "Leo XIV returned from Uruguay, Argentina and Peru."),
    ]
    page.path([(506, 816), (506, 961)], RULE)
    page.path([(56, 890), (966, 890)], RULE)
    for x, y, label, headline, body in briefs:
        page.text(x, y, label, 14, weight=680, fill=RED)
        page.check_width((headline,), 442, 27, "serif", 720)
        page.text(x, y + 20, headline, 27, face="serif", weight=720)
        page.check_width((body,), 442, 17, "sans", 470)
        page.text(x, y + 51, body, 17, weight=470)
    page.text(43, 990, "TUESDAY 17 NOVEMBER 2026", 14, weight=690, fill=MUTED)
    page.text(981, 990, "WORLD DISPATCH  /  FRONT PAGE", 14, weight=690, fill=MUTED, anchor="rt")
    return page.image.resize((W, W), Image.Resampling.LANCZOS)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "entry.png")
    parser.add_argument("--import-map", type=Path, help="Update the clipped map from Natural Earth GeoJSON")
    args = parser.parse_args()
    if args.import_map:
        import_map(args.import_map)
    image = compose()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    # Flat inks and reduced palette preserve small type and keep the PNG compact.
    image.quantize(colors=224, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.NONE).save(
        args.output, optimize=True, compress_level=9
    )
    if args.output.stat().st_size > 1_048_576:
        raise ValueError("PNG exceeds 1 MiB")


if __name__ == "__main__":
    main()
