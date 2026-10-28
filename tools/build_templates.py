"""Generates the four Rosie card templates (HTML + TXT). Re-run only to rebuild templates."""
import json, os
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "templates")
SANS = "-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Helvetica,Arial,sans-serif"
SERIF = "Georgia,'Times New Roman',Times,serif"

STYLES = {
 "funny": dict(name="Funny", outer="#f4f1ea", card="#fffdf8", border="2px solid #d9cfbf", radius="20px",
   strip_bg="#faf7f2", strip_line="#e5dccd", top="🎊🎈🤪🎈🎊🎈🤪🎈🎊", bottom="🎁🍕🎂🎸🎁🍦🎂🎁",
   badge=True, badge_bg="#f3e3b5", badge_fg="#4a3b20",
   hfont=SANS, hsize="38px", hweight="800", hcolor="#1f3a5f", htransform="uppercase",
   nsize="44px", ncolor="#2e6b3f", nsuffix="! 🥳",
   bfont=SANS, bsize="17px", bcolor="#333333", pscolor="#6b6256",
   scolor="#1f3a5f", ssize="22px", sfont=SANS, btn="#2e6b3f", btnfg="#ffffff"),
 "heartfelt": dict(name="Heartfelt", outer="#efe6dc", card="#fbf6ee", border="1px solid #e6d6c3", radius="14px",
   strip_bg=None, top="🌷", bottom=None, badge=False,
   hfont=SERIF, hsize="30px", hweight="normal", hcolor="#5a3e36", htransform="none",
   nsize="34px", ncolor="#a4545b", nsuffix="",
   bfont=SERIF, bsize="18px", bcolor="#4a3f38", pscolor="#7a6a5f",
   scolor="#5a3e36", ssize="22px", sfont=SERIF, btn="#a4545b", btnfg="#ffffff"),
 "kidfun": dict(name="Kid/Fun", outer="#dff3fb", card="#fffef5", border="4px solid #ffb703", radius="28px",
   strip_bg="#fff3c4", strip_line="#ffd166", top="🎈🦕🎂🦖🎈", bottom="🎉🍰🦖🎁🎉",
   badge=False, strip_size="34px",
   hfont=SANS, hsize="44px", hweight="900", hcolor="#d9480f", htransform="uppercase",
   nsize="54px", ncolor="#1864ab", nsuffix="! 🎉",
   bfont=SANS, bsize="21px", bcolor="#2b2b2b", pscolor="#5c5c5c",
   scolor="#d9480f", ssize="26px", sfont=SANS, btn="#1864ab", btnfg="#ffffff"),
 "classic": dict(name="Classic", outer="#f3efe4", card="#fffaf0", border="1px solid #1b2a4a", radius="4px",
   strip_bg=None, top="🎂 ✨ 🎉", bottom=None, badge=False, rule="#b8975a",
   hfont=SERIF, hsize="32px", hweight="normal", hcolor="#1b2a4a", htransform="none",
   nsize="32px", ncolor="#1b2a4a", nsuffix="",
   bfont=SERIF, bsize="17px", bcolor="#2f3a4f", pscolor="#5b6475",
   scolor="#1b2a4a", ssize="21px", sfont=SERIF, btn="#1b2a4a", btnfg="#fffaf0"),
}

# Colors a user can override per card (fill.py --colors, or COLOR_* keys in the values JSON).
# The template carries {{COLOR_*}} tokens; the style's own palette is stored in a COLORS marker that
# fill.py reads for defaults and then removes, so a card with no overrides is unchanged.
COLOR_SLOTS = {"COLOR_BG": "outer", "COLOR_CARD": "card", "COLOR_TEXT": "bcolor",
               "COLOR_ACCENT": "ncolor", "COLOR_BUTTON": "btn"}

def colors_marker(s):
    d = {slot: s[key] for slot, key in COLOR_SLOTS.items()}
    # fixed colors, listed only so fill.py can warn about contrast against an overridden card/button
    d.update({"_HEADLINE": s["hcolor"], "_SIGNOFF": s["scolor"], "_PS": s["pscolor"], "_BUTTON_TEXT": s["btnfg"]})
    return "<!--COLORS:" + json.dumps(d, separators=(",", ":")) + "-->\n"

def html(k, s):
    marker = colors_marker(s)
    s = dict(s, **{key: "{{%s}}" % slot for slot, key in COLOR_SLOTS.items()})
    strip_size = s.get("strip_size", "22px")
    def strip(txt, top=True):
        if not txt: return ""
        if s["strip_bg"]:
            r = s['radius']; rad = f"{r} {r} 0 0" if top else f"0 0 {r} {r}"
            line = f"border-{'bottom' if top else 'top'}:1px solid {s['strip_line']};border-radius:{rad};"
            return (f'<tr><td align="center" bgcolor="{s["strip_bg"]}" style="background-color:{s["strip_bg"]};{line}'
                    f'padding:14px 10px;font-size:{strip_size};line-height:1.3;letter-spacing:4px;">{txt}</td></tr>\n')
        return (f'<tr><td align="center" style="padding:26px 10px 0 10px;font-size:{"30px" if k=="heartfelt" else "24px"};'
                f'line-height:1.2;letter-spacing:6px;">{txt}</td></tr>\n')
    badge = ""
    if s["badge"]:
        badge = (f'<!--IF:BADGE--><table role="presentation" cellpadding="0" cellspacing="0" border="0" align="center"><tr>'
                 f'<td bgcolor="{s["badge_bg"]}" style="background-color:{s["badge_bg"]};color:{s["badge_fg"]};font-family:{SANS};'
                 f'font-size:14px;font-weight:bold;padding:6px 14px;border-radius:30px;">{{{{BADGE}}}}</td></tr></table><!--/IF:BADGE-->\n')
    rule = ""
    if s.get("rule"):
        rule = (f'<tr><td align="center" style="padding:14px 0 0 0;"><table role="presentation" width="80" cellpadding="0" cellspacing="0" border="0">'
                f'<tr><td height="2" bgcolor="{s["rule"]}" style="background-color:{s["rule"]};font-size:0;line-height:0;">&nbsp;</td></tr></table></td></tr>\n')
    # Optional full-width art block above the headline (hidden when ART_SRC is empty).
    # The HTML width attribute is the card's inner width (480 minus both borders) for Outlook;
    # everyone else gets width:100%; max-width:480px.
    bw = int(s["border"].split("px")[0])
    art_w = 480 - 2 * bw
    art_pad = "0" if s["strip_bg"] else "18px 0 0 0"
    art = (f'<!--IF:ART_SRC-->\n<tr><td align="center" style="padding:{art_pad};font-size:0;line-height:0;">'
           f'<img src="{{{{ART_SRC}}}}" width="{art_w}" alt="{{{{ART_ALT}}}}" style="display:block;width:100%;max-width:480px;'
           f'height:auto;border:0;outline:none;text-decoration:none;font-family:{s["hfont"]};font-size:16px;line-height:1.4;'
           f'color:{s["hcolor"]};"></td></tr>\n<!--/IF:ART_SRC-->\n')
    inner_border = ""
    if k == "classic":
        inner_border = "outline:none;"
    return f'''<!DOCTYPE html>
<html lang="en" dir="ltr" xmlns="http://www.w3.org/1999/xhtml" xmlns:v="urn:schemas-microsoft-com:vml" xmlns:o="urn:schemas-microsoft-com:office:office">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta http-equiv="X-UA-Compatible" content="IE=edge">
<meta name="x-apple-disable-message-reformatting">
<meta name="format-detection" content="telephone=no, date=no, address=no, email=no, url=no">
<meta name="color-scheme" content="light dark">
<meta name="supported-color-schemes" content="light dark">
<title>{{{{HEADLINE}}}} {{{{RECIPIENT_NAME}}}}</title>
<!--[if mso]><xml><o:OfficeDocumentSettings><o:AllowPNG/><o:PixelsPerInch>96</o:PixelsPerInch></o:OfficeDocumentSettings></xml><![endif]-->
</head>
<!-- Rosie card template: {s["name"]}. Slots are {{{{TOKENS}}}}. IF blocks and FOOTER markers are handled by tools/fill.py. -->
{marker}<body style="margin:0;padding:0;width:100%;background-color:{s["outer"]};color-scheme:light dark;" bgcolor="{s["outer"]}">
<div style="display:none;font-size:1px;line-height:1px;max-height:0;max-width:0;opacity:0;overflow:hidden;mso-hide:all;">{{{{PREHEADER}}}}&#8199;&#847;&#8199;&#847;&#8199;&#847;&#8199;&#847;&#8199;&#847;&#8199;&#847;&#8199;&#847;&#8199;&#847;&nbsp;</div>
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" bgcolor="{s["outer"]}" style="width:100%;background-color:{s["outer"]};">
<tr><td align="center" style="padding:24px 12px;">
<!--[if mso]><table role="presentation" width="480" align="center" cellpadding="0" cellspacing="0" border="0"><tr><td width="480"><![endif]-->
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="width:100%;max-width:480px;margin:0 auto;">
<!--IF:ENVELOPE_IMG_URL-->
<tr><td align="center" style="padding:0 0 8px 0;"><img src="{{{{ENVELOPE_IMG_URL}}}}" width="480" alt="A closed envelope for {{{{RECIPIENT_NAME}}}}" style="display:block;width:100%;max-width:480px;height:auto;border:0;outline:none;text-decoration:none;font-family:{SANS};font-size:16px;color:{s["hcolor"]};"></td></tr>
<tr><td align="center" style="padding:0 0 20px 0;font-family:{SANS};font-size:13px;color:#7a7a7a;">scroll down to open &#8595;</td></tr>
<!--/IF:ENVELOPE_IMG_URL-->
<tr><td>
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" bgcolor="{s["card"]}" style="width:100%;background-color:{s["card"]};border:{s["border"]};border-radius:{s["radius"]};{inner_border}">
{strip(s["top"], True)}{art}{rule}<tr><td align="center" style="padding:22px 28px 6px 28px;font-family:{s["hfont"]};">
{badge}<div style="font-family:{s["hfont"]};font-size:{s["hsize"]};font-weight:{s["hweight"]};color:{s["hcolor"]};line-height:1.15;text-transform:{s["htransform"]};margin-top:14px;">{{{{HEADLINE}}}}</div>
<div style="font-family:{s["hfont"]};font-size:{s["nsize"]};font-weight:{"800" if s["hweight"]!="normal" else "normal"};color:{s["ncolor"]};line-height:1.15;margin-top:4px;{"font-style:italic;" if k in ("heartfelt","classic") else ""}">{{{{RECIPIENT_NAME}}}}{s["nsuffix"]}</div>
</td></tr>
{rule}<tr><td align="center" style="padding:20px 36px 8px 36px;font-family:{s["bfont"]};font-size:{s["bsize"]};line-height:1.6;color:{s["bcolor"]};">{{{{VERSE}}}}</td></tr>
<!--IF:PS-->
<tr><td align="center" style="padding:8px 36px 4px 36px;font-family:{s["bfont"]};font-size:14px;line-height:1.5;color:{s["pscolor"]};font-style:italic;">P.S. {{{{PS}}}}</td></tr>
<!--/IF:PS-->
<tr><td align="center" style="padding:16px 36px 8px 36px;">
<!--IF:SIGNATURE_IMG_URL--><img src="{{{{SIGNATURE_IMG_URL}}}}" width="240" alt="{{{{SIGNOFF}}}}" style="display:block;margin:0 auto;width:240px;max-width:100%;height:auto;border:0;font-family:{s["sfont"]};font-size:{s["ssize"]};color:{s["scolor"]};"><!--/IF:SIGNATURE_IMG_URL-->
<!--IFNOT:SIGNATURE_IMG_URL--><div style="font-family:{s["sfont"]};font-size:{s["ssize"]};font-weight:bold;color:{s["scolor"]};{"font-style:italic;font-weight:normal;" if k in ("heartfelt","classic") else ""}">{{{{SIGNOFF}}}}</div><!--/IFNOT:SIGNATURE_IMG_URL-->
</td></tr>
<tr><td align="center" style="padding:12px 24px 26px 24px;">
<table role="presentation" cellpadding="0" cellspacing="0" border="0" align="center"><tr>
<td align="center" bgcolor="{s["btn"]}" style="background-color:{s["btn"]};border-radius:24px;padding:12px 26px;">
<a href="{{{{REPLY_MAILTO}}}}" style="font-family:{SANS};font-size:16px;font-weight:bold;line-height:1.2;color:{s["btnfg"]};text-decoration:none;display:inline-block;">&#9993;&#65039; Write back to {{{{SENDER_NAME}}}}</a>
</td></tr></table>
</td></tr>
{strip(s["bottom"], False)}</table>
</td></tr>
<!--FOOTER-->
<tr><td align="center" style="padding:14px 8px 0 8px;font-family:{SANS};font-size:11px;line-height:1.4;color:#8a8a8a;"><a href="https://digitalswamp.io" style="color:#8a8a8a;text-decoration:none;">made with Rosie &middot; digitalswamp.io</a></td></tr>
<!--/FOOTER-->
</table>
<!--[if mso]></td></tr></table><![endif]-->
</td></tr></table>
</body>
</html>
'''

def txt(k, s):
    top = {"funny":"🎊🎈🤪🎈🎊","heartfelt":"🌷","kidfun":"🎈🦕🎂🦖🎈","classic":"🎂 ✨ 🎉"}[k]
    head = "{{HEADLINE}} {{RECIPIENT_NAME}}" + ("!" if k in ("funny","kidfun") else "")
    badge = "<!--IF:BADGE-->\n{{BADGE}}\n<!--/IF:BADGE-->\n" if s["badge"] else ""
    art = "<!--IF:ART_SRC-->\n(Picture: {{ART_ALT}})\n<!--/IF:ART_SRC-->\n"
    return f"""{top}
{art}{badge}
{head}

{{{{VERSE}}}}

<!--IF:PS-->
P.S. {{{{PS}}}}

<!--/IF:PS-->
{{{{SIGNOFF}}}}

Write back to {{{{SENDER_NAME}}}}: {{{{REPLY_MAILTO}}}}

<!--FOOTER-->
--
made with Rosie · digitalswamp.io
https://digitalswamp.io
<!--/FOOTER-->
"""

for k, s in STYLES.items():
    open(os.path.join(OUT, k + ".html"), "w").write(html(k, s))
    open(os.path.join(OUT, k + ".txt"), "w").write(txt(k, s))
    print(k, os.path.getsize(os.path.join(OUT, k + ".html")), "bytes")
