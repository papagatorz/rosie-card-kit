#!/usr/bin/env python3
"""Fill a Rosie template.

usage:
  fill.py STYLE VALUES.json OUT_BASENAME [options]
  fill.py --template PATH.html VALUES.json OUT_BASENAME [options]

  STYLE            funny | heartfelt | kidfun | classic   (reads templates/STYLE.html + .txt)
  --template PATH  any HTML template file (relative or absolute). Its plain-text twin is
                   PATH with .txt, or pass --text-template PATH.txt.
  VALUES.json      {"RECIPIENT_NAME": "...", "HEADLINE": "...", ...}
  OUT_BASENAME     e.g. drafts/2026-11-02_Alex-Example  (writes .html and .txt)

options:
  --no-footer      drop the "made with Rosie" line
  --art IMAGE      local image (e.g. a 1280x720 GenerateImage PNG). It is resized to at most
                   --art-width px wide (default 960), saved as a JPEG under --art-max-kb
                   (default 300) as OUT.art.jpg, and embedded inline as cid:art.jpg.
                   Also writes OUT.eml (ready MIME: multipart/alternative of text/plain and
                   multipart/related[text/html + image/jpeg Content-ID <art.jpg>]) and
                   OUT.send.json (body / htmlBody / attachments fields for a mail API that
                   supports inline attachments, with the image as an inline attachment).
  --colors JSON|FILE  color overrides, e.g. --colors '{"COLOR_ACCENT":"#c0392b"}' or a .json
                   file. Slots: COLOR_BG (page), COLOR_CARD (card), COLOR_TEXT (verse),
                   COLOR_ACCENT (name), COLOR_BUTTON (reply button). Values must be #rgb or
                   #rrggbb. COLOR_* keys in VALUES.json work too; --colors wins.
                   Empty = the style's own palette.
                   Warns (does not fail) when a text color's WCAG contrast on its background
                   is below 4.5:1 (3:1 for the large name line).
  --style FILE|NAME  a style file (JSON) bundling colors, fonts, layout, wording and art; see
                   "Customize your card" in README.md. NAME means styles/NAME.json.
                   styles/default.json, if it exists, is applied to every card first
                   (skip it with --no-default-style).
  Individual style flags (each overrides the same key from the style files):
  --font NAME      all text; one of: classic-serif clean-sans elegant-serif friendly-sans
                   modern-sans rounded typewriter (or "style" for the template's own)
  --heading-font / --body-font / --signoff-font NAME   just that part
  --art-position top|side|bottom|none     --align center|left
  --corner-radius PX (0-40)   --border style|none|thin|medium|thick   --border-color #hex
  --badge TEXT | --no-badge   --emoji-top TEXT  --emoji-bottom TEXT  --no-emoji
  --name-suffix TEXT  --uppercase-headline | --no-uppercase-headline
  --greeting TEXT  --signoff TEXT  --button-text TEXT   ({name} and {sender} are filled in)
  --art-alt TEXT
  --from ADDR      sender address (required, or set the ROSIE_FROM environment variable).
                   Used for the From header and the Message-ID domain.
  --to ADDR --subject TEXT   headers for OUT.eml / OUT.send.json (optional)

ART_SRC may also be set in VALUES.json to a hosted https:// URL instead of using --art.
If ART_SRC is set, ART_ALT is required.

Never overwrites an existing file. Fails if a required slot is empty or any {{TOKEN}} or
marker is left unfilled.
"""
import argparse, base64, html, io, json, os, re, sys
from email.utils import parseaddr

TPL = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "templates")
STYLES = ["funny", "heartfelt", "kidfun", "classic"]
REQUIRED = ["PREHEADER", "RECIPIENT_NAME", "HEADLINE", "VERSE", "SIGNOFF", "REPLY_MAILTO", "SENDER_NAME"]
OPTIONAL = ["PS", "SIGNATURE_IMG_URL", "ENVELOPE_IMG_URL", "BADGE", "ART_SRC", "ART_ALT"]
URL_SLOTS = {"SIGNATURE_IMG_URL", "ENVELOPE_IMG_URL", "ART_SRC", "REPLY_MAILTO"}
ART_FILENAME = "art.jpg"            # inline image is referenced in the HTML as cid:FILENAME
ART_CID = "cid:" + ART_FILENAME
COLOR_SLOTS = ["COLOR_BG", "COLOR_CARD", "COLOR_TEXT", "COLOR_ACCENT", "COLOR_BUTTON"]
COLORS_RX = re.compile(r"<!--COLORS:(\{.*?\})-->\n?")
HEX_RX = re.compile(r"^#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6})$")
STYLE_RX = re.compile(r"<!--STYLE:(\{.*?\})-->\n?")
STYLE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "styles")
# internal switches set by fill.py (one art block per position, emoji strips)
SWITCHES = ["ART_TOP", "ART_SIDE", "ART_BOTTOM", "EMOJI_TOP", "EMOJI_BOTTOM", "EMOJI_TOP_TXT"]
STYLE_KEYS = {  # option: allowed JSON type(s); see "Customize your card" in README.md
    "base": str, "extends": str, "colors": dict,
    "font": str, "heading_font": str, "body_font": str, "signoff_font": str,
    "art_position": str, "align": str, "corner_radius": int, "border": str, "border_color": str,
    "badge": (bool, str), "footer": bool, "emoji": bool, "emoji_top": str, "emoji_bottom": str,
    "name_suffix": str, "uppercase_headline": bool,
    "greeting": str, "signoff": str, "button_text": str,
    "art": str, "art_alt": str, "art_source": str,
}
CHOICES = {"art_position": ["top", "side", "bottom", "none"], "align": ["center", "left"],
           "border": ["style", "none", "thin", "medium", "thick"],
           "art_source": ["own-photo", "own-art", "generated", "licensed"]}
TEXT_LIMITS = {"greeting": 60, "signoff": 80, "button_text": 40, "name_suffix": 12,
               "emoji_top": 60, "emoji_bottom": 60, "art_alt": 140, "badge": 60}
BORDER_PX = {"none": 0, "thin": 1, "medium": 2, "thick": 4}
SIDE_SCALE = 0.7   # headline/name size in the narrow column next to side art
SAFE_STACK_RX = re.compile(r"^[A-Za-z0-9 ,'\-]+$")


def find_style(spec, rel_to=None):
    """A style is a path to a JSON file, or a NAME meaning styles/NAME.json."""
    cands = [spec]
    if rel_to:
        cands.insert(0, os.path.join(rel_to, spec))
    if not spec.endswith(".json") and os.sep not in spec:
        cands.append(os.path.join(STYLE_DIR, spec + ".json"))
    for c in cands:
        if os.path.isfile(c):
            return os.path.abspath(c)
    sys.exit("style %r not found (a .json path, or a name in %s)" % (spec, os.path.normpath(STYLE_DIR)))


def load_style(spec, rel_to=None, depth=0):
    """Read a style file (following "extends"), validate it, and return the merged dict.
    Relative "art" paths are resolved against the file that names them."""
    if depth > 5:
        sys.exit("style files extend each other too deeply (loop?)")
    path = find_style(spec, rel_to)
    try:
        d = json.load(open(path, encoding="utf-8"))
    except ValueError as e:
        sys.exit("style file %s is not valid JSON: %s" % (path, e))
    if not isinstance(d, dict):
        sys.exit("style file %s must be a JSON object" % path)
    d = {k: v for k, v in d.items() if not k.startswith("_") and k not in ("notes", "rosie_style")}
    check_style(d, path)
    here = os.path.dirname(path)
    if d.get("art"):
        d["art"] = os.path.normpath(os.path.join(here, d["art"]))
    merged = {}
    if d.get("extends"):
        merged = load_style(d.pop("extends"), here, depth + 1)
    return merge_style(merged, d)


def merge_style(a, b):
    out = dict(a)
    for k, v in b.items():
        if k == "colors":
            out["colors"] = dict(out.get("colors", {}), **v)
        else:
            out[k] = v
    return out


def check_style(d, where):
    for k, v in d.items():
        if k not in STYLE_KEYS:
            sys.exit("unknown style option %r in %s (expected one of %s)" % (k, where, ", ".join(STYLE_KEYS)))
        t = STYLE_KEYS[k]
        if not isinstance(v, t) or (t is int and isinstance(v, bool)):
            sys.exit("style option %s in %s has the wrong type (%r)" % (k, where, v))
        if k in CHOICES and v not in CHOICES[k]:
            sys.exit("style option %s=%r in %s: pick one of %s" % (k, v, where, ", ".join(CHOICES[k])))
        if isinstance(v, str) and k in TEXT_LIMITS and len(v) > TEXT_LIMITS[k]:
            sys.exit("style option %s in %s is longer than %d characters" % (k, where, TEXT_LIMITS[k]))
        if k == "corner_radius" and not 0 <= v <= 40:
            sys.exit("corner_radius in %s must be 0-40 (pixels)" % where)
        if k == "border_color" and not HEX_RX.match(v):
            sys.exit("border_color %r in %s is not a hex color like #c0392b" % (v, where))
        if k.endswith("font") and v != "style":
            font_stack(v, where)
        if k == "colors":
            check_colors(v, where)
        if k == "base" and v not in STYLES:
            sys.exit("base %r in %s: pick one of %s" % (v, where, ", ".join(STYLES)))


def font_stack(v, where="--font"):
    """A menu name maps to its stack; a custom stack must use only email-safe fonts."""
    from safe_fonts import FONT_MENU, stack_problems
    if v in FONT_MENU:
        return FONT_MENU[v]
    if "," not in v:
        sys.exit("font %r in %s: pick one of %s, or give a full stack like \"Georgia,'Times New Roman',serif\""
                 % (v, where, ", ".join(FONT_MENU)))
    probs = stack_problems(v) if SAFE_STACK_RX.match(v) else ["unexpected characters"]
    if probs:
        sys.exit("font stack %r in %s is not email-safe: %s" % (v, where, "; ".join(probs)))
    return v


def resolve_style(tpl_text, st, vals):
    """Apply style options to the template's STYLE defaults. Returns (template text without the
    marker, raw S_* token values, text-slot defaults for vals)."""
    m = STYLE_RX.search(tpl_text)
    text = STYLE_RX.sub("", tpl_text)
    if not m:
        if st:
            print("warning: this template has no STYLE defaults; style options other than colors and wording are ignored", file=sys.stderr)
        return text, {}, {}
    d = json.loads(m.group(1))
    raw = {k: v for k, v in d.items() if k.startswith("S_")}
    for key, tok in (("heading_font", "S_FONT_HEAD"), ("body_font", "S_FONT_BODY"), ("signoff_font", "S_FONT_SIGN")):
        f = st.get(key, st.get("font", "style"))
        if f != "style":
            raw[tok] = font_stack(f, "style option " + key)
    if "corner_radius" in st:
        raw["S_RADIUS"] = "%dpx" % st["corner_radius"]
    bw = d["_BORDER_WIDTH"]
    if st.get("border", "style") != "style" or "border_color" in st:
        cur = re.match(r"(\d+)px solid (#[0-9a-fA-F]+)", d["S_BORDER"])
        bw = BORDER_PX.get(st.get("border", "style"), bw)
        color = st.get("border_color", cur.group(2) if cur else "#cccccc")
        raw["S_BORDER"] = "%dpx solid %s" % (bw, color) if bw else "none"
    raw["S_ART_W"] = str(480 - 2 * bw)
    raw["S_ART_W_INSET"] = str(480 - 2 * bw - 56)
    if st.get("align", "center") == "left":
        raw.update(S_ALIGN="left", S_SIGN_MARGIN="0", S_BADGE_ALIGN="",  # an align="left" table would float
                   S_HEAD_PAD="22px 36px 6px 36px", S_RULE_PAD="14px 36px 0 36px",  # line up with
                   S_BTN_PAD="12px 36px 26px 36px")                                 # the verse
    if "uppercase_headline" in st:
        raw["S_HEAD_TRANSFORM"] = "uppercase" if st["uppercase_headline"] else "none"
    if st.get("art_position") == "side" and str(vals.get("ART_SRC", "")).strip():
        for tok in ("S_HEAD_SIZE", "S_NAME_SIZE"):
            raw[tok] = "%dpx" % round(int(raw[tok].rstrip("px")) * SIDE_SCALE)
    if not d.get("_BADGE", True) and "badge" not in st:
        vals["BADGE"] = ""   # this style has no badge unless the style options turn it on
    tdef = {k: d[k] for k in ("EMOJI_TOP", "EMOJI_BOTTOM", "EMOJI_TOP_TXT", "NAME_SUFFIX", "NAME_SUFFIX_TXT")}
    if st.get("emoji") is False:
        tdef.update(EMOJI_TOP="", EMOJI_BOTTOM="", EMOJI_TOP_TXT="")
    if "emoji_top" in st:
        tdef["EMOJI_TOP"] = tdef["EMOJI_TOP_TXT"] = st["emoji_top"]
    if "emoji_bottom" in st:
        tdef["EMOJI_BOTTOM"] = st["emoji_bottom"]
    if "name_suffix" in st:
        tdef["NAME_SUFFIX"] = tdef["NAME_SUFFIX_TXT"] = st["name_suffix"]
    return text, raw, tdef


def fill_raw(text, raw):
    """Fill the validated {{S_*}} layout tokens without escaping (they hold CSS values)."""
    return re.sub(r"\{\{(S_[A-Z_]+)\}\}", lambda m: raw.get(m.group(1), m.group(0)), text)


def load_colors(arg):
    """--colors takes inline JSON or a path to a JSON file."""
    if not arg:
        return {}
    try:
        d = json.loads(open(arg).read()) if os.path.isfile(arg) else json.loads(arg)
    except (ValueError, OSError) as e:
        sys.exit("--colors is not valid JSON or a readable JSON file: %s" % e)
    if not isinstance(d, dict):
        sys.exit("--colors must be a JSON object")
    return d


def check_colors(d, where):
    for k, v in d.items():
        if k not in COLOR_SLOTS:
            sys.exit("unknown color slot %r in %s (expected %s)" % (k, where, ", ".join(COLOR_SLOTS)))
        if str(v).strip() and not HEX_RX.match(str(v).strip()):
            sys.exit("%s=%r in %s is not a hex color like #c0392b" % (k, v, where))


def luminance(hx):
    hx = hx.lstrip("#")
    if len(hx) == 3:
        hx = "".join(c * 2 for c in hx)
    def ch(c):
        c = int(c, 16) / 255
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
    r, g, b = (ch(hx[i:i + 2]) for i in (0, 2, 4))
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast(a, b):
    la, lb = sorted((luminance(a), luminance(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


def contrast_warnings(c, changed):
    pairs = [("verse text COLOR_TEXT", c["COLOR_TEXT"], "COLOR_CARD", c["COLOR_CARD"], 4.5),
             ("name COLOR_ACCENT", c["COLOR_ACCENT"], "COLOR_CARD", c["COLOR_CARD"], 3.0),
             ("button label", c.get("_BUTTON_TEXT"), "COLOR_BUTTON", c["COLOR_BUTTON"], 4.5),
             ("headline", c.get("_HEADLINE"), "COLOR_CARD", c["COLOR_CARD"], 3.0),
             ("sign-off", c.get("_SIGNOFF"), "COLOR_CARD", c["COLOR_CARD"], 4.5),
             ("P.S.", c.get("_PS"), "COLOR_CARD", c["COLOR_CARD"], 4.5),
             ("footer grey", "#8a8a8a", "COLOR_BG", c["COLOR_BG"], 3.0)]
    out = []
    fg_slot = {"verse text COLOR_TEXT": "COLOR_TEXT", "name COLOR_ACCENT": "COLOR_ACCENT"}
    for name, fg, bgname, bg, need in pairs:
        if fg_slot.get(name) not in changed and bgname not in changed:
            continue  # only report pairs the overrides touched
        if fg and bg:
            ratio = contrast(fg, bg)
            if ratio < need:
                out.append("low contrast: %s %s on %s %s is %.2f:1 (want >= %.1f:1)" % (name, fg, bgname, bg, ratio, need))
    for k in changed:
        if c[k].lower() in ("#000", "#000000", "#fff", "#ffffff"):
            out.append("%s is pure %s; dark-mode inversion handles off-black/off-white better" % (k, c[k]))
    return out


def resolve_colors(tpl_text, vals, overrides):
    """Return (template text without the COLORS marker, color values to fill)."""
    m = COLORS_RX.search(tpl_text)
    defaults = json.loads(m.group(1)) if m else {}
    text = COLORS_RX.sub("", tpl_text)
    from_vals = {k: vals[k] for k in COLOR_SLOTS if str(vals.get(k, "")).strip()}
    check_colors(from_vals, "VALUES.json")
    check_colors(overrides, "--colors")
    c = dict(defaults)
    c.update(from_vals)
    c.update({k: v for k, v in overrides.items() if str(v).strip()})
    c = {k: str(v).strip() for k, v in c.items()}
    return text, c


def blocks(text, vals, keep_footer):
    for key in OPTIONAL + SWITCHES:
        has = bool(str(vals.get(key, "")).strip())
        text = re.sub(r"<!--IF:%s-->\n?(.*?)<!--/IF:%s-->\n?" % (key, key),
                      (lambda m: m.group(1)) if has else "", text, flags=re.S)
        text = re.sub(r"<!--IFNOT:%s-->\n?(.*?)<!--/IFNOT:%s-->\n?" % (key, key),
                      "" if has else (lambda m: m.group(1)), text, flags=re.S)
    text = re.sub(r"<!--FOOTER-->\n?(.*?)<!--/FOOTER-->\n?",
                  (lambda m: m.group(1)) if keep_footer else "", text, flags=re.S)
    return text


def fill(text, vals, is_html):
    def rep(m):
        k = m.group(1)
        v = str(vals.get(k, ""))
        if not is_html:
            return v
        v = html.escape(v, quote=True)
        if k in URL_SLOTS:
            return v
        return v.replace("\n\n", "<br><br>").replace("\n", "<br>") if k == "VERSE" else v
    return re.sub(r"\{\{([A-Z_]+)\}\}", rep, text)


def compress_art(src, max_width=960, max_kb=300):
    """Resize to <= max_width px wide and save as a baseline JPEG under max_kb. Returns bytes."""
    try:
        from PIL import Image
    except ImportError:
        sys.exit("--art needs Pillow: pip install Pillow (or pip install -r requirements.txt)")
    im = Image.open(src)
    im = im.convert("RGBA") if im.mode in ("P", "LA") else im
    if im.mode == "RGBA":  # flatten transparency onto white
        bg = Image.new("RGB", im.size, (255, 255, 255)); bg.paste(im, mask=im.split()[-1]); im = bg
    im = im.convert("RGB")
    if im.width > max_width:
        im = im.resize((max_width, round(im.height * max_width / im.width)), Image.LANCZOS)
    for q in (85, 80, 75, 70, 65, 60, 55, 50, 45, 40):
        buf = io.BytesIO()
        im.save(buf, "JPEG", quality=q, optimize=True, progressive=False)
        if buf.tell() <= max_kb * 1024:
            return buf.getvalue(), im.size, q
    sys.exit("could not get art under %d KB even at quality 40" % max_kb)


def write_new(path, data):
    if os.path.exists(path):
        sys.exit("refusing to overwrite " + path)
    with open(path, "wb" if isinstance(data, bytes) else "w") as f:
        f.write(data)
    print("wrote", path, os.path.getsize(path), "bytes")


def style_from_flags(a):
    """The individual --flags, as style options (they override the style files)."""
    st = {}
    for flag, key in (("font", "font"), ("heading_font", "heading_font"), ("body_font", "body_font"),
                      ("signoff_font", "signoff_font"), ("art_position", "art_position"), ("align", "align"),
                      ("corner_radius", "corner_radius"), ("border", "border"), ("border_color", "border_color"),
                      ("emoji_top", "emoji_top"), ("emoji_bottom", "emoji_bottom"), ("name_suffix", "name_suffix"),
                      ("greeting", "greeting"), ("signoff", "signoff"), ("button_text", "button_text"),
                      ("art_alt", "art_alt"), ("uppercase_headline", "uppercase_headline")):
        v = getattr(a, flag)
        if v is not None:
            st[key] = v
    if a.badge is not None:
        st["badge"] = a.badge
    if a.no_badge:
        st["badge"] = False
    if a.no_emoji:
        st["emoji"] = False
    if a.no_footer:
        st["footer"] = False
    check_style(st, "the command line")
    return st


def apply_wording(vals, st):
    """greeting / signoff / button_text / badge from the style replace the values JSON's.
    {name} and {sender} are filled from RECIPIENT_NAME and SENDER_NAME."""
    def sub(t):
        return t.replace("{name}", str(vals.get("RECIPIENT_NAME", ""))).replace("{sender}", str(vals.get("SENDER_NAME", "")))
    for key, slot in (("greeting", "HEADLINE"), ("signoff", "SIGNOFF"), ("button_text", "BUTTON_TEXT"), ("art_alt", "ART_ALT")):
        if key in st:
            vals[slot] = sub(st[key])
    if st.get("badge") is False:
        vals["BADGE"] = ""
    elif isinstance(st.get("badge"), str):
        vals["BADGE"] = sub(st["badge"])
    if not str(vals.get("BUTTON_TEXT", "")).strip():
        vals["BUTTON_TEXT"] = "Write back to " + str(vals.get("SENDER_NAME", ""))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("args", nargs="+", help="[STYLE] VALUES.json OUT_BASENAME")
    ap.add_argument("--template"); ap.add_argument("--text-template")
    ap.add_argument("--no-footer", action="store_true")
    ap.add_argument("--art"); ap.add_argument("--art-width", type=int, default=960)
    ap.add_argument("--art-max-kb", type=int, default=300)
    ap.add_argument("--colors")
    ap.add_argument("--style"); ap.add_argument("--no-default-style", action="store_true")
    for f in ("font", "heading-font", "body-font", "signoff-font", "art-position", "align", "border",
              "border-color", "emoji-top", "emoji-bottom", "name-suffix", "greeting", "signoff",
              "button-text", "art-alt", "badge"):
        ap.add_argument("--" + f)
    ap.add_argument("--corner-radius", type=int)
    ap.add_argument("--no-badge", action="store_true"); ap.add_argument("--no-emoji", action="store_true")
    ap.add_argument("--uppercase-headline", dest="uppercase_headline", action="store_const", const=True)
    ap.add_argument("--no-uppercase-headline", dest="uppercase_headline", action="store_const", const=False)
    ap.add_argument("--to"); ap.add_argument("--subject")
    ap.add_argument("--from", dest="sender", default=os.environ.get("ROSIE_FROM"))
    a = ap.parse_args()
    a.sender = (a.sender or "").strip()
    if not a.sender:
        sys.exit("--from ADDR is required (or set the ROSIE_FROM environment variable)")
    if "@" not in parseaddr(a.sender)[1]:
        sys.exit("--from %r is not an email address" % a.sender)

    # Style options: styles/default.json, then --style FILE (and what it extends), then the flags.
    st = {}
    default_style = os.path.join(STYLE_DIR, "default.json")
    if not a.no_default_style and os.path.isfile(default_style):
        st = load_style(default_style)
        print("using default style", os.path.normpath(default_style))
    if a.style:
        st = merge_style(st, load_style(a.style))
    st = merge_style(st, style_from_flags(a))
    keep_footer = st.get("footer", True)

    if a.template:
        if len(a.args) != 2:
            sys.exit("with --template, pass VALUES.json OUT_BASENAME")
        values_path, out = a.args
        html_tpl = os.path.abspath(a.template)
        txt_tpl = os.path.abspath(a.text_template) if a.text_template else os.path.splitext(html_tpl)[0] + ".txt"
    else:
        if len(a.args) == 2 and st.get("base"):
            style = st["base"]; values_path, out = a.args
        elif len(a.args) == 3:
            style, values_path, out = a.args
        else:
            sys.exit("pass STYLE VALUES.json OUT_BASENAME (or --template PATH VALUES.json OUT_BASENAME, "
                     "or VALUES.json OUT_BASENAME with a style file that sets \"base\")")
        if style not in STYLES:
            sys.exit("unknown style %r (expected one of %s)" % (style, ", ".join(STYLES)))
        html_tpl = os.path.join(TPL, style + ".html"); txt_tpl = os.path.join(TPL, style + ".txt")
    for t in (html_tpl, txt_tpl):
        if not os.path.isfile(t):
            sys.exit("template not found: " + t)
    out = os.path.abspath(out)

    vals = json.load(open(values_path))
    apply_wording(vals, st)
    missing = [k for k in REQUIRED if not str(vals.get(k, "")).strip()]
    if missing:
        sys.exit("missing required slots: %s" % ", ".join(missing))
    if not vals["REPLY_MAILTO"].startswith("mailto:"):
        sys.exit("REPLY_MAILTO must be a mailto: link")
    art_file = a.art or st.get("art")
    position = st.get("art_position", "top")
    if position == "none":
        if art_file or str(vals.get("ART_SRC", "")).strip():
            print("note: art_position is none, so the card has no picture", file=sys.stderr)
        art_file = None; vals["ART_SRC"] = ""
    if art_file:
        if not os.path.isfile(art_file):
            sys.exit("art image not found: " + art_file)
        if str(vals.get("ART_SRC", "")).strip() and vals["ART_SRC"] != ART_CID:
            sys.exit("use either --art or a hosted ART_SRC in the values, not both")
        vals["ART_SRC"] = ART_CID
        if st.get("art") and not a.art:
            src = st.get("art_source")
            print("art from style file: %s%s" % (art_file, " (%s)" % src if src else ""))
        if st.get("art_source") == "generated":
            print("reminder: generated art must not show a real person's face or likeness", file=sys.stderr)
    a.art = art_file
    if position == "side" and a.art_width == 960:
        a.art_width = 300   # shown at 150 px; 300 px stays sharp on high-density screens
    art_src = str(vals.get("ART_SRC", "")).strip()
    if art_src:
        if not (art_src.startswith("https://") or art_src == ART_CID):
            sys.exit("ART_SRC must be a hosted https:// URL (or use --art for an inline cid image)")
        if art_src == ART_CID and not a.art:
            sys.exit("ART_SRC is %s but no --art image was given" % ART_CID)
        if not str(vals.get("ART_ALT", "")).strip():
            sys.exit("ART_ALT is required when ART_SRC is set (describe the picture in a few words)")
    for sw in ("ART_TOP", "ART_SIDE", "ART_BOTTOM"):
        vals[sw] = art_src if sw == "ART_" + position.upper() else ""

    # Check every destination first so nothing is half-written.
    dests = [out + ".html", out + ".txt"] + ([out + ".art.jpg", out + ".eml", out + ".send.json"] if a.art else [])
    for d in dests:
        if os.path.exists(d):
            sys.exit("refusing to overwrite " + d)

    style_colors = st.get("colors", {})
    overrides = dict(style_colors, **load_colors(a.colors))
    html_text, colors = resolve_colors(open(html_tpl).read(), vals, overrides)
    overridden = bool(overrides) or any(str(vals.get(k, "")).strip() for k in COLOR_SLOTS)
    if all(k in colors for k in COLOR_SLOTS) and overridden:
        changed = set(overrides) | {k for k in COLOR_SLOTS if str(vals.get(k, "")).strip()}
        for w in contrast_warnings(colors, changed):
            print("warning:", w, file=sys.stderr)
    elif overridden and not all(k in colors for k in COLOR_SLOTS):
        print("warning: this template has no COLORS defaults; color overrides only apply where it has {{COLOR_*}} tokens", file=sys.stderr)
    vals.update({k: v for k, v in colors.items() if k in COLOR_SLOTS})
    html_text, raw, tdef = resolve_style(html_text, st, vals)
    for k, v in tdef.items():
        vals[k] = v
    html_text = fill_raw(html_text, raw)

    rendered = {}
    for ext, tpl, is_html in ((".html", html_tpl, True), (".txt", txt_tpl, False)):
        text = blocks(html_text if is_html else open(tpl).read(), vals, keep_footer)
        text = fill(text, vals, is_html)
        if not is_html:
            text = re.sub(r"\n{3,}", "\n\n", text).strip() + "\n"
        left = re.findall(r"\{\{[A-Z_]+\}\}|<!--/?IF|<!--/?FOOTER|<!--COLORS|<!--STYLE", text)
        if left:
            sys.exit("unfilled tokens in %s: %s" % (out + ext, left))
        rendered[ext] = text
    for ext in (".html", ".txt"):
        write_new(out + ext, rendered[ext])

    if a.art:
        jpg, size, q = compress_art(a.art, a.art_width, a.art_max_kb)
        need = 300 if position == "side" else int(raw.get("S_ART_W", 480))
        if size[0] < need:
            print("warning: the picture is only %d px wide; it may look blurry (want >= %d px)" % (size[0], need), file=sys.stderr)
        write_new(out + ".art.jpg", jpg)
        print("  art %dx%d JPEG q=%d, %.0f KB" % (size[0], size[1], q, len(jpg) / 1024))
        write_new(out + ".eml", build_eml(rendered[".txt"], rendered[".html"], jpg, a))
        send = {"body": rendered[".txt"], "htmlBody": rendered[".html"],
                "attachments": [{"content": base64.b64encode(jpg).decode(), "filename": ART_FILENAME,
                                 "mimeType": "image/jpeg", "inline": True}]}
        if a.to: send["to"] = a.to
        if a.subject: send["subject"] = a.subject
        if a.sender: send["from"] = a.sender
        write_new(out + ".send.json", json.dumps(send, ensure_ascii=False, indent=1))


def sender_domain(sender):
    """Domain part of the --from address, used for the Message-ID."""
    return parseaddr(sender)[1].rsplit("@", 1)[-1].strip().lower()


def build_eml(text, html_body, jpg, a):
    from email.message import EmailMessage
    from email.utils import formatdate, make_msgid
    msg = EmailMessage()
    if a.sender: msg["From"] = a.sender
    if a.to: msg["To"] = a.to
    if a.subject: msg["Subject"] = a.subject
    msg["Date"] = formatdate(localtime=True)
    msg["Message-ID"] = make_msgid(domain=sender_domain(a.sender))
    msg.set_content(text)                                  # text/plain
    msg.add_alternative(html_body, subtype="html")         # text/html
    html_part = msg.get_payload()[1]
    html_part.add_related(jpg, maintype="image", subtype="jpeg", cid="<%s>" % ART_FILENAME,
                          disposition="inline", filename=ART_FILENAME)  # -> multipart/related
    return msg.as_bytes()


if __name__ == "__main__":
    main()
