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
    for key in OPTIONAL:
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


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("args", nargs="+", help="[STYLE] VALUES.json OUT_BASENAME")
    ap.add_argument("--template"); ap.add_argument("--text-template")
    ap.add_argument("--no-footer", action="store_true")
    ap.add_argument("--art"); ap.add_argument("--art-width", type=int, default=960)
    ap.add_argument("--art-max-kb", type=int, default=300)
    ap.add_argument("--colors")
    ap.add_argument("--to"); ap.add_argument("--subject")
    ap.add_argument("--from", dest="sender", default=os.environ.get("ROSIE_FROM"))
    a = ap.parse_args()
    a.sender = (a.sender or "").strip()
    if not a.sender:
        sys.exit("--from ADDR is required (or set the ROSIE_FROM environment variable)")
    if "@" not in parseaddr(a.sender)[1]:
        sys.exit("--from %r is not an email address" % a.sender)

    if a.template:
        if len(a.args) != 2:
            sys.exit("with --template, pass VALUES.json OUT_BASENAME")
        values_path, out = a.args
        html_tpl = os.path.abspath(a.template)
        txt_tpl = os.path.abspath(a.text_template) if a.text_template else os.path.splitext(html_tpl)[0] + ".txt"
    else:
        if len(a.args) != 3:
            sys.exit("pass STYLE VALUES.json OUT_BASENAME (or --template PATH VALUES.json OUT_BASENAME)")
        style, values_path, out = a.args
        if style not in STYLES:
            sys.exit("unknown style %r (expected one of %s)" % (style, ", ".join(STYLES)))
        html_tpl = os.path.join(TPL, style + ".html"); txt_tpl = os.path.join(TPL, style + ".txt")
    for t in (html_tpl, txt_tpl):
        if not os.path.isfile(t):
            sys.exit("template not found: " + t)
    out = os.path.abspath(out)

    vals = json.load(open(values_path))
    missing = [k for k in REQUIRED if not str(vals.get(k, "")).strip()]
    if missing:
        sys.exit("missing required slots: %s" % ", ".join(missing))
    if not vals["REPLY_MAILTO"].startswith("mailto:"):
        sys.exit("REPLY_MAILTO must be a mailto: link")
    if a.art:
        if str(vals.get("ART_SRC", "")).strip() and vals["ART_SRC"] != ART_CID:
            sys.exit("use either --art or a hosted ART_SRC in the values, not both")
        vals["ART_SRC"] = ART_CID
    art_src = str(vals.get("ART_SRC", "")).strip()
    if art_src:
        if not (art_src.startswith("https://") or art_src == ART_CID):
            sys.exit("ART_SRC must be a hosted https:// URL (or use --art for an inline cid image)")
        if art_src == ART_CID and not a.art:
            sys.exit("ART_SRC is %s but no --art image was given" % ART_CID)
        if not str(vals.get("ART_ALT", "")).strip():
            sys.exit("ART_ALT is required when ART_SRC is set (describe the picture in a few words)")

    # Check every destination first so nothing is half-written.
    dests = [out + ".html", out + ".txt"] + ([out + ".art.jpg", out + ".eml", out + ".send.json"] if a.art else [])
    for d in dests:
        if os.path.exists(d):
            sys.exit("refusing to overwrite " + d)

    overrides = load_colors(a.colors)
    html_text, colors = resolve_colors(open(html_tpl).read(), vals, overrides)
    overridden = bool(overrides) or any(str(vals.get(k, "")).strip() for k in COLOR_SLOTS)
    if all(k in colors for k in COLOR_SLOTS) and overridden:
        changed = set(overrides) | {k for k in COLOR_SLOTS if str(vals.get(k, "")).strip()}
        for w in contrast_warnings(colors, changed):
            print("warning:", w, file=sys.stderr)
    elif overridden and not all(k in colors for k in COLOR_SLOTS):
        print("warning: this template has no COLORS defaults; color overrides only apply where it has {{COLOR_*}} tokens", file=sys.stderr)
    vals.update({k: v for k, v in colors.items() if k in COLOR_SLOTS})

    rendered = {}
    for ext, tpl, is_html in ((".html", html_tpl, True), (".txt", txt_tpl, False)):
        text = blocks(html_text if is_html else open(tpl).read(), vals, not a.no_footer)
        text = fill(text, vals, is_html)
        if not is_html:
            text = re.sub(r"\n{3,}", "\n\n", text).strip() + "\n"
        left = re.findall(r"\{\{[A-Z_]+\}\}|<!--/?IF|<!--/?FOOTER|<!--COLORS", text)
        if left:
            sys.exit("unfilled tokens in %s: %s" % (out + ext, left))
        rendered[ext] = text
    for ext in (".html", ".txt"):
        write_new(out + ext, rendered[ext])

    if a.art:
        jpg, size, q = compress_art(a.art, a.art_width, a.art_max_kb)
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
