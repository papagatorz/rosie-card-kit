#!/usr/bin/env python3
"""Email-safety lint for Rosie templates and filled cards.
usage: check_email_safety.py [--max-art-kb 300] FILE.html [...]   (exit 1 on any failure)
Fails on: <style>/<script>/<link>/<iframe>/<form>, on*= handlers, javascript: URLs, CSS
animation/transition/@keyframes/@import/@font-face, web-font hosts, tracking (1x1 pixels, utm_
params, redirect/click-tracking hosts), links/images that aren't https:/mailto:/cid:, any <img>
without alt text (or with empty alt), an <img> without a width attribute or wider than 600, art
not sized email-safely (full width: width:100%; max-width:480px; side: fixed px and
max-width:100%), fonts outside the email-safe list or a stack without a generic fallback, text
below 2.5:1 contrast on its background, an HTML body over 100 KB (Gmail clips at 102 KB), and an
inline art file (OUT.art.jpg next to a filled card) over --max-art-kb or wider than 960 px.
Warns (no failure) for text below 4.5:1 and for leftover {{TOKENS}} in a filled card."""
import os, re, sys
from html.parser import HTMLParser
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from safe_fonts import stack_problems

BAD = {
    "style block": r"<style\b", "script": r"<script\b|javascript:", "event handler": r"\son[a-z]+\s*=",
    "external css/link": r"<link\b", "iframe/form/object": r"<(iframe|form|object|embed)\b",
    "css animation": r"animation\s*:|@keyframes|transition\s*:", "css import": r"@import",
    "web font": r"@font-face|fonts\.googleapis|fonts\.gstatic|typekit|use\.fontawesome",
    "tracking param": r"[?&](utm_|mc_eid|mc_cid|fbclid|gclid)",
    "redirector/tracker": r"(click\.|track\.|/track/|/open\.gif|pixel\.|list-manage\.com|sendgrid\.net|mailchimp)",
    "1x1 pixel": r"<img\b[^>]*\b(width|height)=\"?1\"?[\s>/][^>]*>",
}
HEX = re.compile(r"^#([0-9a-fA-F]{3}|[0-9a-fA-F]{6})$")
FAIL_RATIO = 2.5   # below this text is hard to read for anyone; 2.5-4.5 is only a warning
VOID = {"img", "br", "meta", "hr", "input", "link"}


def lum(hx):
    hx = hx.lstrip("#")
    if len(hx) == 3: hx = "".join(c * 2 for c in hx)
    def ch(c):
        c = int(c, 16) / 255
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
    r, g, b = (ch(hx[i:i + 2]) for i in (0, 2, 4))
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def ratio(a, b):
    x, y = sorted((lum(a), lum(b)), reverse=True)
    return (x + 0.05) / (y + 0.05)


def css(style):
    return {k.strip().lower(): v.strip() for k, v in
            (d.split(":", 1) for d in (style or "").split(";") if ":" in d)}


class Contrast(HTMLParser):
    """Tracks the nearest solid background and checks each element that sets a text color."""
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.stack = [("#ffffff", None)]   # (background, text color) per open element
        self.fails, self.warns, self.seen = [], [], set()

    def handle_starttag(self, tag, attrs):
        a = dict(attrs); st = css(a.get("style"))
        bg = st.get("background-color") or a.get("bgcolor") or self.stack[-1][0]
        fg = st.get("color") or self.stack[-1][1]
        if "display" in st and st["display"] == "none":
            fg = None
        if tag != "img" and fg and HEX.match(fg) and HEX.match(bg) and (fg, bg) not in self.seen:
            self.seen.add((fg, bg))
            r = ratio(fg, bg)
            if r < FAIL_RATIO:
                self.fails.append("text %s on %s is %.2f:1 (nearly unreadable; needs >= %.1f:1)" % (fg, bg, r, FAIL_RATIO))
            elif r < 4.5:
                self.warns.append("text %s on %s is %.2f:1 (fine for large text only)" % (fg, bg, r))
        if tag not in VOID:
            self.stack.append((bg if HEX.match(bg or "") else self.stack[-1][0], fg))

    def handle_endtag(self, tag):
        if tag not in VOID and len(self.stack) > 1:
            self.stack.pop()


def check(path, max_art_kb=300):
    s = open(path, encoding="utf-8").read()
    errs = [name for name, rx in BAD.items() if re.search(rx, s, re.I)]
    warns = []
    is_template = "{{" in s and ("<!--IF:" in s or "<!--COLORS" in s)
    for m in re.finditer(r'\b(?:src|href)="([^"]*)"', s):
        u = m.group(1)
        if not re.match(r"(https://|mailto:|cid:|\{\{[A-Z_]+\}\}$)", u):
            errs.append("non-https link/src: " + u[:60])
    for img in re.findall(r"<img\b[^>]*>", s):
        alt = re.search(r'\balt="([^"]*)"', img)
        if not alt:
            errs.append("img without alt")
        elif not alt.group(1).strip():
            errs.append("img with empty alt text")
        w = re.search(r'\bwidth="(\d+|\{\{[A-Z_]+\}\})"', img)
        if not w:
            errs.append("img without a width attribute (Outlook needs one)")
        elif w.group(1).isdigit() and int(w.group(1)) > 600:
            errs.append("img width=%s is wider than 600" % w.group(1))
        if "{{ART_SRC}}" in img or "cid:art" in img:
            full = "width:100%" in img and "max-width:480px" in img
            side = re.search(r"width:(\d+)px", img) and "max-width:100%" in img
            if not (full or side):
                errs.append("art img must be width:100%; max-width:480px (or a fixed px width with max-width:100%)")
    for m in re.finditer(r"font-family:\s*([^;\"]+)", s):
        v = m.group(1).strip()
        if "{{" in v:
            continue
        for p in stack_problems(v.replace("&#39;", "'").replace("&#x27;", "'")):
            errs.append(p)
    if not is_template:   # templates hold {{COLOR_*}} tokens, so contrast is checked on filled cards
        c = Contrast()
        c.feed(s)
        errs += c.fails; warns += c.warns
    kb = len(s.encode("utf-8")) / 1024
    if kb > 100:
        errs.append("HTML is %.0f KB; Gmail clips messages over 102 KB" % kb)
    if not is_template:
        left = sorted(set(re.findall(r"\{\{[A-Z_]+\}\}", s)))
        if left:
            warns.append("unfilled tokens: " + ", ".join(left))
        if "cid:art.jpg" in s:
            art = os.path.splitext(path)[0] + ".art.jpg"
            if not os.path.isfile(art):
                warns.append("uses cid:art.jpg but no %s next to it" % os.path.basename(art))
            else:
                size = os.path.getsize(art) / 1024
                if size > max_art_kb:
                    errs.append("art %s is %.0f KB (limit %d KB)" % (os.path.basename(art), size, max_art_kb))
                try:
                    from PIL import Image
                    wpx = Image.open(art).width
                    if wpx > 960:
                        errs.append("art is %d px wide (limit 960)" % wpx)
                except ImportError:
                    pass
    # de-duplicate, keep order
    return list(dict.fromkeys(errs)), list(dict.fromkeys(warns))


def main(argv):
    max_kb = 300
    if "--max-art-kb" in argv:
        i = argv.index("--max-art-kb"); max_kb = int(argv[i + 1]); del argv[i:i + 2]
    bad = 0
    for p in argv:
        e, w = check(p, max_kb)
        print(("FAIL " if e else "ok   ") + p + (": " + "; ".join(e) if e else ""))
        for x in w:
            print("     warn: " + x)
        bad += bool(e)
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
