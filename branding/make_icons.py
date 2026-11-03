"""Draw every Grabzy.CC icon the build swaps in for Chromium's.

    python branding/make_icons.py

Needs Pillow. Writes branding/files/<path inside the Chromium tree>, which
brand.py copies over the originals. The mark is the website's: an ink tile, an
off-white G and the green live dot (branding/icon.svg, viewBox 0 0 512 512).
Run it again after changing the mark, and commit the output.
"""

import os
import shutil
import sys

from PIL import Image, ImageDraw, ImageFilter, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "files")

INK = (0x12, 0x15, 0x1E, 255)
PAPER = (0xEE, 0xF0, 0xF5, 255)
LIVE = (0x2E, 0xE8, 0x7A, 255)
MONO = (0x3C, 0x40, 0x43, 255)  # Chromium's own mono grey
TEXT_ON_LIGHT = (0x5F, 0x63, 0x68, 255)
SS = 8  # supersampling factor


def _mark(draw, s, ox, oy, stroke, dot):
    """The G and the dot, in 512-unit space scaled by s and moved to (ox, oy)."""
    def p(x, y):
        return ox + x * s, oy + y * s

    half = 32 * s
    outer = 140 * s + half
    cx, cy = p(256, 256)
    # Arc from the top right (-45 deg) the long way round to 3 o'clock.
    draw.arc((cx - outer, cy - outer, cx + outer, cy + outer), 0, 315, fill=stroke, width=round(64 * s))
    for x, y in ((355, 157), (322, 256)):  # round caps
        x, y = p(x, y)
        draw.ellipse((x - half, y - half, x + half, y + half), fill=stroke)
    draw.rectangle((*p(322, 224), *p(396, 288)), fill=stroke)  # the bar
    draw.rectangle((*p(396, 224), *p(428, 256)), fill=stroke)  # SVG's miter join with the arc
    if dot:
        x, y = p(236, 256)
        r = 34 * s
        draw.ellipse((x - r, y - r, x + r, y + r), fill=dot)


def tile(size, inset=0.0, radius=112 / 512, shadow=False):
    """The app icon: ink tile and mark, `inset` of the canvas left clear on each side."""
    big = size * SS
    im = Image.new("RGBA", (big, big), (0, 0, 0, 0))
    side = big * (1 - 2 * inset)
    o = big * inset
    if shadow:  # macOS keeps a soft drop shadow under the tile
        sh = Image.new("RGBA", (big, big), (0, 0, 0, 0))
        ImageDraw.Draw(sh).rounded_rectangle((o, o + side * 0.012, o + side, o + side * 1.012), radius=side * radius, fill=(0, 0, 0, 110))
        im = Image.alpha_composite(im, sh.filter(ImageFilter.GaussianBlur(side * 0.02)))
    d = ImageDraw.Draw(im)
    d.rounded_rectangle((o, o, o + side, o + side), radius=side * radius, fill=INK)
    _mark(d, side / 512, o, o, PAPER, LIVE)
    return im.resize((size, size), Image.LANCZOS)


def glyph(size, color, dot=None, pad=0.06):
    """The mark alone on transparency, cropped to its own box (viewBox 80 80 352 352)."""
    big = size * SS
    im = Image.new("RGBA", (big, big), (0, 0, 0, 0))
    inner = big * (1 - 2 * pad)
    s = inner / 352
    _mark(ImageDraw.Draw(im), s, big * pad - 80 * s, big * pad - 80 * s, color, dot or color)
    return im.resize((size, size), Image.LANCZOS)


def centered(size, scale):
    """The full icon at `scale` of a transparent canvas (Windows Start tiles)."""
    im = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    n = round(size * scale)
    im.alpha_composite(tile(n), ((size - n) // 2, (size - n) // 2))
    return im


def _font(px):
    for f in ("C:/Windows/Fonts/arial.ttf", "/System/Library/Fonts/Helvetica.ttc",
              "/Library/Fonts/Arial.ttf", "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
              "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"):
        if os.path.exists(f):
            return ImageFont.truetype(f, px)
    sys.exit("make_icons: no Arial, Helvetica, Liberation Sans or DejaVu Sans font found")


def lockup(w, h, text_color):
    """Icon plus 'Grabzy.CC', for the product_logo strips (171x32 and 342x64)."""
    W, H = w * SS, h * SS
    im = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    im.alpha_composite(_tile_big(H), (0, 0))
    font = _font(round(H * 0.62))
    d = ImageDraw.Draw(im)
    x = H + H * 0.3
    box = d.textbbox((0, 0), "Grabzy.CC", font=font)
    y = (H - (box[3] - box[1])) / 2 - box[1]
    d.text((x, y), "Grabzy.CC", font=font, fill=text_color, stroke_width=max(1, round(H * 0.012)), stroke_fill=text_color)
    if x + box[2] > W:
        sys.exit("make_icons: wordmark wider than %dx%d" % (w, h))
    return im.resize((w, h), Image.LANCZOS)


def _tile_big(n):
    big = Image.new("RGBA", (n, n), (0, 0, 0, 0))
    d = ImageDraw.Draw(big)
    d.rounded_rectangle((0, 0, n, n), radius=n * 112 / 512, fill=INK)
    _mark(d, n / 512, 0, 0, PAPER, LIVE)
    return big


def xpm(im, name):
    """A tiny XPM writer: one char per colour, alpha below half is transparent."""
    q = im.convert("RGBA")
    px = q.load()
    colors, rows = {}, []
    chars = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789#$%&*+-=@"
    pal = q.convert("RGB").quantize(len(chars) - 1)
    pp = pal.load()
    pr = pal.getpalette()
    for y in range(q.height):
        row = ""
        for x in range(q.width):
            if px[x, y][3] < 128:
                row += " "
                continue
            i = pp[x, y]
            colors[i] = chars[i]
            row += chars[i]
        rows.append(row)
    lines = ['"%d %d %d 1 ",' % (q.width, q.height, len(colors) + 1), '"  c None",']
    for i, c in sorted(colors.items()):
        lines.append('"%s c #%02X%02X%02X",' % (c, pr[i * 3], pr[i * 3 + 1], pr[i * 3 + 2]))
    lines += ['"%s",' % r for r in rows]
    lines[-1] = lines[-1].rstrip(",")
    return "/* XPM */\nstatic char *%s[] = {\n%s\n};\n" % (name, "\n".join(lines))


def main():
    shutil.rmtree(OUT, ignore_errors=True)

    def save(path, im):
        p = os.path.join(OUT, path)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        im.save(p, optimize=True)

    def icon(n):  # small sizes get a hair of margin, large ones a little more
        return tile(n, inset=0 if n <= 24 else 1 / 32)

    th = "chrome/app/theme/chromium/"
    for n in (16, 24, 48, 64, 128, 256):
        save(th + "product_logo_%d.png" % n, icon(n))
    save(th + "product_logo_22_mono.png", glyph(22, MONO))
    for n in (24, 48, 64, 128, 256):
        save(th + "linux/product_logo_%d.png" % n, icon(n))
    p = os.path.join(OUT, th + "linux/product_logo_32.xpm")
    open(p, "w", newline="\n").write(xpm(icon(32), "product_logo_32"))
    save(th + "win/tiles/Logo.png", centered(600, 0.56))
    save(th + "win/tiles/SmallLogo.png", centered(176, 0.56))

    for name in ("chromium.ico", "app_list.ico"):
        sizes = [icon(n) for n in (16, 32, 48, 256)]
        p = os.path.join(OUT, th + "win/" + name)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        sizes[-1].save(p, format="ICO", sizes=[(n, n) for n in (16, 32, 48, 256)], append_images=sizes[:-1])

    # macOS: Apple's grid puts an 824 tile on a 1024 canvas.
    def mac(n):
        return tile(n, inset=100 / 1024, radius=185 / 824, shadow=n >= 64)

    ai = th + "mac/Assets.xcassets/AppIcon.appiconset/"
    for n in (16, 32, 64, 128, 256, 512, 1024):
        save(ai + "appicon_%d.png" % n, mac(n))
    save(th + "mac/Assets.xcassets/Icon.iconset/icon_256x256.png", mac(256))
    save(th + "mac/Assets.xcassets/Icon.iconset/icon_256x256@2x.png", mac(512))
    big = mac(1024)
    p = os.path.join(OUT, th + "mac/app.icns")
    big.save(p, format="ICNS", append_images=[mac(n) for n in (16, 32, 64, 128, 256, 512)])

    shutil.copy(os.path.join(HERE, "icon.svg"), os.path.join(OUT, th + "product_logo.svg"))

    for scale, f in (("100", 1), ("200", 2)):
        d = "chrome/app/theme/default_%s_percent/chromium/" % scale
        save(d + "product_logo_16.png", icon(16 * f))
        save(d + "product_logo_32.png", icon(32 * f))
        if scale == "100":
            save(d + "linux/product_logo_16.png", icon(16))
            save(d + "linux/product_logo_32.png", icon(32))
        c = "components/resources/default_%s_percent/chromium/" % scale
        save(c + "favicon_product.png", icon(16 * f))
        save(c + "product_logo.png", lockup(171 * f, 32 * f, TEXT_ON_LIGHT))
        save(c + "product_logo_white.png", lockup(171 * f, 32 * f, PAPER))

    # A preview sheet for the README, not shipped into the build.
    sheet = Image.new("RGBA", (1280, 400), (0x0B, 0x0D, 0x14, 255))
    x = 64
    for n in (256, 128, 64, 48, 32, 16):
        sheet.alpha_composite(tile(n), (x, (400 - n) // 2))
        x += n + 48
    sheet.save(os.path.join(HERE, "preview.png"), optimize=True)
    count = sum(len(f) for _, _, f in os.walk(OUT))
    print("make_icons: wrote %d files to %s" % (count, os.path.relpath(OUT)))


if __name__ == "__main__":
    main()
