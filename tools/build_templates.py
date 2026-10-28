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
   strip_bg=None, top="🌷", bottom=None, badge=False, badge_bg="#f3e1dc", badge_fg="#5a3e36",
   hfont=SERIF, hsize="30px", hweight="normal", hcolor="#5a3e36", htransform="none",
   nsize="34px", ncolor="#a4545b", nsuffix="",
   bfont=SERIF, bsize="18px", bcolor="#4a3f38", pscolor="#7a6a5f",
   scolor="#5a3e36", ssize="22px", sfont=SERIF, btn="#a4545b", btnfg="#ffffff"),
 "kidfun": dict(name="Kid/Fun", outer="#dff3fb", card="#fffef5", border="4px solid #ffb703", radius="28px",
   strip_bg="#fff3c4", strip_line="#ffd166", top="🎈🦕🎂🦖🎈", bottom="🎉🍰🦖🎁🎉",
   badge=False, badge_bg="#ffe066", badge_fg="#5c3c00", strip_size="34px",
   hfont=SANS, hsize="44px", hweight="900", hcolor="#d9480f", htransform="uppercase",
   nsize="54px", ncolor="#1864ab", nsuffix="! 🎉",
   bfont=SANS, bsize="21px", bcolor="#2b2b2b", pscolor="#5c5c5c",
   scolor="#d9480f", ssize="26px", sfont=SANS, btn="#1864ab", btnfg="#ffffff"),
 "classic": dict(name="Classic", outer="#f3efe4", card="#fffaf0", border="1px solid #1b2a4a", radius="4px",
   strip_bg=None, top="🎂 ✨ 🎉", bottom=None, badge=False, badge_bg="#efe3c8", badge_fg="#1b2a4a", rule="#b8975a",
   hfont=SERIF, hsize="32px", hweight="normal", hcolor="#1b2a4a", htransform="none",
   nsize="32px", ncolor="#1b2a4a", nsuffix="",
   bfont=SERIF, bsize="17px", bcolor="#2f3a4f", pscolor="#5b6475",
   scolor="#1b2a4a", ssize="21px", sfont=SERIF, btn="#1b2a4a", btnfg="#fffaf0"),
}

# Colors a user can override per card (fill.py --colors, COLOR_* keys in the values JSON, or a style file).
# The template carries {{COLOR_*}} tokens; the style's own palette is stored in a COLORS marker that
# fill.py reads for defaults and then removes, so a card with no overrides is unchanged.
COLOR_SLOTS = {"COLOR_BG": "outer", "COLOR_CARD": "card", "COLOR_TEXT": "bcolor",
               "COLOR_ACCENT": "ncolor", "COLOR_BUTTON": "btn"}

# Card customization (fill.py --style FILE and the individual flags). {{S_*}} tokens are filled raw
# by fill.py from a validated whitelist (fonts, sizes, radius, border, alignment), and the template's
# own values are stored in a STYLE marker, so a card with no style options is byte-for-byte unchanged.
# EMOJI_*, NAME_SUFFIX* and BUTTON_TEXT are ordinary (escaped) text slots whose defaults come from
# the same marker.
TXT_TOP = {"funny": "🎊🎈🤪🎈🎊", "heartfelt": "🌷", "kidfun": "🎈🦕🎂🦖🎈", "classic": "🎂 ✨ 🎉"}

def colors_marker(s):
    d = {slot: s[key] for slot, key in COLOR_SLOTS.items()}
    # fixed colors, listed only so fill.py can warn about contrast against an overridden card/button
    d.update({"_HEADLINE": s["hcolor"], "_SIGNOFF": s["scolor"], "_PS": s["pscolor"], "_BUTTON_TEXT": s["btnfg"]})
    return "<!--COLORS:" + json.dumps(d, separators=(",", ":")) + "-->\n"

def style_marker(k, s):
    bw = int(s["border"].split("px")[0])
    d = {"S_FONT_HEAD": s["hfont"], "S_FONT_BODY": s["bfont"], "S_FONT_SIGN": s["sfont"],
         "S_HEAD_SIZE": s["hsize"], "S_NAME_SIZE": s["nsize"], "S_HEAD_TRANSFORM": s["htransform"],
         "S_RADIUS": s["radius"], "S_BORDER": s["border"], "S_ART_W": str(480 - 2 * bw),
         "S_ALIGN": "center", "S_SIGN_MARGIN": "0 auto", "S_BADGE_ALIGN": ' align="center"',
         "S_HEAD_PAD": "22px 28px 6px 28px", "S_RULE_PAD": "14px 0 0 0", "S_BTN_PAD": "12px 24px 26px 24px",
         "EMOJI_TOP": s["top"] or "", "EMOJI_BOTTOM": s["bottom"] or "", "EMOJI_TOP_TXT": TXT_TOP[k],
         "NAME_SUFFIX": s["nsuffix"], "NAME_SUFFIX_TXT": "!" if k in ("funny", "kidfun") else "",
         "_BORDER_WIDTH": bw, "_BADGE": bool(s["badge"])}
    return "<!--STYLE:" + json.dumps(d, ensure_ascii=False, separators=(",", ":")) + "-->\n"

def html(k, s):
    marker = colors_marker(s) + style_marker(k, s)
    s = dict(s, **{key: "{{%s}}" % slot for slot, key in COLOR_SLOTS.items()})
    s = dict(s, hfont="{{S_FONT_HEAD}}", bfont="{{S_FONT_BODY}}", sfont="{{S_FONT_SIGN}}", hsize="{{S_HEAD_SIZE}}",
             nsize="{{S_NAME_SIZE}}", htransform="{{S_HEAD_TRANSFORM}}", radius="{{S_RADIUS}}")
    A = "{{S_ALIGN}}"
    strip_size = s.get("strip_size", "22px")
    def strip(slot, top=True):
        if s["strip_bg"]:
            r = s['radius']; rad = f"{r} {r} 0 0" if top else f"0 0 {r} {r}"
            line = f"border-{'bottom' if top else 'top'}:1px solid {s['strip_line']};border-radius:{rad};"
            row = (f'<tr><td align="center" bgcolor="{s["strip_bg"]}" style="background-color:{s["strip_bg"]};{line}'
                   f'padding:14px 10px;font-size:{strip_size};line-height:1.3;letter-spacing:4px;">{{{{{slot}}}}}</td></tr>\n')
        else:
            pad = "26px 10px 0 10px" if top else "0 10px 22px 10px"
            row = (f'<tr><td align="center" style="padding:{pad};font-size:{"30px" if k=="heartfelt" else "24px"};'
                   f'line-height:1.2;letter-spacing:6px;">{{{{{slot}}}}}</td></tr>\n')
        return f"<!--IF:{slot}-->\n{row}<!--/IF:{slot}-->\n"
    badge = (f'<!--IF:BADGE--><table role="presentation" cellpadding="0" cellspacing="0" border="0"{{{{S_BADGE_ALIGN}}}}><tr>'
             f'<td bgcolor="{s["badge_bg"]}" style="background-color:{s["badge_bg"]};color:{s["badge_fg"]};font-family:{SANS};'
             f'font-size:14px;font-weight:bold;padding:6px 14px;border-radius:30px;">{{{{BADGE}}}}</td></tr></table><!--/IF:BADGE-->\n')
    rule = ""
    if s.get("rule"):
        rule = (f'<tr><td align="{A}" style="padding:{{{{S_RULE_PAD}}}};"><table role="presentation" width="80" cellpadding="0" cellspacing="0" border="0">'
                f'<tr><td height="2" bgcolor="{s["rule"]}" style="background-color:{s["rule"]};font-size:0;line-height:0;">&nbsp;</td></tr></table></td></tr>\n')
    # Optional art. ART_TOP: full-width block above the headline (the HTML width attribute is the
    # card's inner width for Outlook; everyone else gets width:100%; max-width:480px).
    # ART_SIDE: a 150px picture left of the headline. ART_BOTTOM: inset picture above the sign-off.
    # fill.py sets exactly one of them from ART_SRC and the art_position option.
    art_pad = "0" if s["strip_bg"] else "18px 0 0 0"
    imgstyle = (f'height:auto;border:0;outline:none;text-decoration:none;font-family:{s["hfont"]};font-size:16px;line-height:1.4;'
                f'color:{s["hcolor"]};')
    art = (f'<!--IF:ART_TOP-->\n<tr><td align="center" style="padding:{art_pad};font-size:0;line-height:0;">'
           f'<img src="{{{{ART_SRC}}}}" width="{{{{S_ART_W}}}}" alt="{{{{ART_ALT}}}}" style="display:block;width:100%;max-width:480px;'
           f'{imgstyle}"></td></tr>\n<!--/IF:ART_TOP-->\n')
    side_open = (f'<!--IF:ART_SIDE-->\n<tr><td style="padding:22px 20px 6px 20px;"><table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0"><tr>\n'
                 f'<td width="150" valign="middle" style="width:150px;padding:0 14px 0 0;font-size:0;line-height:0;">'
                 f'<img src="{{{{ART_SRC}}}}" width="150" alt="{{{{ART_ALT}}}}" style="display:block;width:150px;max-width:100%;border-radius:8px;{imgstyle}"></td>\n'
                 f'<td align="{A}" valign="middle" style="font-family:{s["hfont"]};">\n<!--/IF:ART_SIDE-->\n'
                 f'<!--IFNOT:ART_SIDE--><tr><td align="{A}" style="padding:{{{{S_HEAD_PAD}}}};font-family:{s["hfont"]};">\n<!--/IFNOT:ART_SIDE-->')
    side_close = '<!--IF:ART_SIDE--></table></td></tr>\n<!--/IF:ART_SIDE-->\n'
    art_bottom = (f'<!--IF:ART_BOTTOM-->\n<tr><td align="center" style="padding:16px 28px 0 28px;font-size:0;line-height:0;">'
                  f'<img src="{{{{ART_SRC}}}}" width="{{{{S_ART_W_INSET}}}}" alt="{{{{ART_ALT}}}}" style="display:block;width:100%;max-width:480px;border-radius:8px;'
                  f'{imgstyle}"></td></tr>\n<!--/IF:ART_BOTTOM-->\n')
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
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" bgcolor="{s["card"]}" style="width:100%;background-color:{s["card"]};border:{{{{S_BORDER}}}};border-radius:{s["radius"]};{inner_border}">
{strip("EMOJI_TOP", True)}{art}{rule}{side_open}{badge}<div style="font-family:{s["hfont"]};font-size:{s["hsize"]};font-weight:{s["hweight"]};color:{s["hcolor"]};line-height:1.15;text-transform:{s["htransform"]};margin-top:14px;">{{{{HEADLINE}}}}</div>
<div style="font-family:{s["hfont"]};font-size:{s["nsize"]};font-weight:{"800" if s["hweight"]!="normal" else "normal"};color:{s["ncolor"]};line-height:1.15;margin-top:4px;{"font-style:italic;" if k in ("heartfelt","classic") else ""}">{{{{RECIPIENT_NAME}}}}{{{{NAME_SUFFIX}}}}</div>
</td></tr>
{side_close}{rule}<tr><td align="{A}" style="padding:20px 36px 8px 36px;font-family:{s["bfont"]};font-size:{s["bsize"]};line-height:1.6;color:{s["bcolor"]};">{{{{VERSE}}}}</td></tr>
<!--IF:PS-->
<tr><td align="{A}" style="padding:8px 36px 4px 36px;font-family:{s["bfont"]};font-size:14px;line-height:1.5;color:{s["pscolor"]};font-style:italic;">P.S. {{{{PS}}}}</td></tr>
<!--/IF:PS-->
{art_bottom}<tr><td align="{A}" style="padding:16px 36px 8px 36px;">
<!--IF:SIGNATURE_IMG_URL--><img src="{{{{SIGNATURE_IMG_URL}}}}" width="240" alt="{{{{SIGNOFF}}}}" style="display:block;margin:{{{{S_SIGN_MARGIN}}}};width:240px;max-width:100%;height:auto;border:0;font-family:{s["sfont"]};font-size:{s["ssize"]};color:{s["scolor"]};"><!--/IF:SIGNATURE_IMG_URL-->
<!--IFNOT:SIGNATURE_IMG_URL--><div style="font-family:{s["sfont"]};font-size:{s["ssize"]};font-weight:bold;color:{s["scolor"]};{"font-style:italic;font-weight:normal;" if k in ("heartfelt","classic") else ""}">{{{{SIGNOFF}}}}</div><!--/IFNOT:SIGNATURE_IMG_URL-->
</td></tr>
<tr><td align="{A}" style="padding:{{{{S_BTN_PAD}}}};">
<table role="presentation" cellpadding="0" cellspacing="0" border="0" align="{A}"><tr>
<td align="center" bgcolor="{s["btn"]}" style="background-color:{s["btn"]};border-radius:24px;padding:12px 26px;">
<a href="{{{{REPLY_MAILTO}}}}" style="font-family:{SANS};font-size:16px;font-weight:bold;line-height:1.2;color:{s["btnfg"]};text-decoration:none;display:inline-block;">&#9993;&#65039; {{{{BUTTON_TEXT}}}}</a>
</td></tr></table>
</td></tr>
{strip("EMOJI_BOTTOM", False)}</table>
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
    art = "<!--IF:ART_SRC-->\n(Picture: {{ART_ALT}})\n<!--/IF:ART_SRC-->\n"
    badge = "<!--IF:BADGE-->\n{{BADGE}}\n<!--/IF:BADGE-->\n"
    return f"""<!--IF:EMOJI_TOP_TXT-->
{{{{EMOJI_TOP_TXT}}}}
<!--/IF:EMOJI_TOP_TXT-->
{art}{badge}
{{{{HEADLINE}}}} {{{{RECIPIENT_NAME}}}}{{{{NAME_SUFFIX_TXT}}}}

{{{{VERSE}}}}

<!--IF:PS-->
P.S. {{{{PS}}}}

<!--/IF:PS-->
{{{{SIGNOFF}}}}

{{{{BUTTON_TEXT}}}}: {{{{REPLY_MAILTO}}}}

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
