# Rosie card kit (beta)

> **BETA.** This kit works and is in daily use, but it is still evolving. Feedback, bug reports and ideas are welcome on X: [@papagatorz](https://x.com/papagatorz).

Rosie is a Grok Bot that designs greeting cards where **the email itself is the card**. There's no "click here to view your e-card" link and no card website. The birthday (or thank-you, or just-because) card arrives as an email body that looks like a card, with a plain-text twin for mail apps that don't show HTML.

This repo is the card kit Rosie uses: four email-safe HTML templates, plus small Python tools to fill them, lint them and render previews. You can use it on its own with any mail sender that accepts HTML and plain-text parts.

## The four styles

Each preview below is filled with the example values in [`previews/example-values.json`](previews/example-values.json) ("Alex", from "Sam"). The left image has no art; the right image has the example art.

| Style | Templates | Look |
|---|---|---|
| Funny | `templates/funny.html`, `funny.txt` | Off-white card with a thin tan border, emoji strips at the top and bottom, a tan badge, a big navy uppercase headline, and the name in green. Loud and playful. |
| Heartfelt | `templates/heartfelt.html`, `heartfelt.txt` | Soft cream card, serif lettering, one 🌷 accent, rose-colored name. Warm, no jokes. |
| Kid/Fun | `templates/kidfun.html`, `kidfun.txt` | Bright yellow border, big emoji strips (🎈🦕🎂🦖), very large friendly type. |
| Classic | `templates/classic.html`, `classic.txt` | Cream card, navy lettering and border, gold rules, a modest 🎂 ✨ 🎉 header. A good default. |

### Funny

<img src="previews/funny.png" width="300" alt="Funny style card preview"> <img src="previews/funny-art.png" width="300" alt="Funny style card with art">

### Heartfelt

<img src="previews/heartfelt.png" width="300" alt="Heartfelt style card preview"> <img src="previews/heartfelt-art.png" width="300" alt="Heartfelt style card with art">

### Kid/Fun

<img src="previews/kidfun.png" width="300" alt="Kid/Fun style card preview"> <img src="previews/kidfun-art.png" width="300" alt="Kid/Fun style card with art">

### Classic

<img src="previews/classic.png" width="300" alt="Classic style card preview"> <img src="previews/classic-art.png" width="300" alt="Classic style card with art">

Every style also has `-dark.png` and `-art-dark.png` previews in [`previews/`](previews/). They simulate a mail app that force-inverts colors in dark mode. Emoji look odd in that simulation only; real mail apps don't invert emoji.

## Quick start

Requires Python 3.8+.

```bash
pip install -r requirements.txt                  # Pillow (for --art) and playwright (for previews)
python3 -m playwright install chromium           # only needed for preview.py

# Fill the Classic template with the example values and the example art:
python3 tools/fill.py classic previews/example-values.json out/alex-classic \
  --from you@example.com --to alex@example.com --subject "Happy birthday, Alex" \
  --art previews/example-art-1280x720.png

# Render a PNG preview (add --dark to simulate forced dark mode):
python3 tools/preview.py out/alex-classic.html out/alex-classic.png

# Lint templates or filled cards for email safety:
python3 tools/check_email_safety.py templates/*.html out/alex-classic.html
```

(`fill.py` doesn't create folders, so run `mkdir -p out` first.)

## Slots

Each slot is a `{{TOKEN}}` in both the `.html` and the `.txt` file. Values come from a JSON file (see [`previews/example-values.json`](previews/example-values.json)).

| Slot | Required | Notes |
|---|---|---|
| `{{PREHEADER}}` | yes | Inbox preview text, hidden in the body. Keep it to about 40–90 characters. |
| `{{RECIPIENT_NAME}}` | yes | First name (or nickname) only. |
| `{{HEADLINE}}` | yes | For example `Happy birthday,`. The name is printed on the next line. Funny and Kid/Fun print the headline in uppercase; the name is printed as written in every style. |
| `{{VERSE}}` | yes | 2–4 short sentences, as plain text. A blank line becomes `<br><br>`. The text is HTML-escaped. |
| `{{PS}}` | optional | Text after `P.S.`. Don't include "P.S." yourself. If it's empty, the row is removed. |
| `{{SIGNOFF}}` | yes | For example `Love, Sam 🎉` or `With love, Sam`. |
| `{{SIGNATURE_IMG_URL}}` | optional | A hosted `https://` PNG of the sign-off in a handwriting-style font. Its alt text is `{{SIGNOFF}}`. When it's set, it replaces the text sign-off. |
| `{{ENVELOPE_IMG_URL}}` | optional | A "closed envelope" header image above the card that the reader scrolls past, with a "scroll down to open ↓" hint. If it's an animated GIF, frame 1 must be a finished design, because Outlook shows only frame 1. If it's empty, the block is removed. |
| `{{REPLY_MAILTO}}` | yes | A `mailto:` link for the **Write back to `{{SENDER_NAME}}`** button, for example `mailto:sam@example.com?subject=Re%3A%20your%20card`. |
| `{{SENDER_NAME}}` | yes | For example `Sam`. It's used on the button. |
| `{{ART_SRC}}` | optional | The card's picture: a full-width image above the headline. Either `cid:art.jpg` (set for you by `fill.py --art`) or a hosted `https://` URL. If it's empty, the block is removed. See [Art](#art). |
| `{{ART_ALT}}` | required when `ART_SRC` is set | A few words describing the picture, for example `Balloons and a birthday cake`. It's the image's alt text, and the `.txt` gets a `(Picture: …)` line. |
| `{{BADGE}}` | optional, **Funny only** | The tan badge text, for example `🚨 ALERT: BIRTHDAY IN PROGRESS 🚨`. If it's empty, the badge is removed. |
| `{{COLOR_BG}}`, `{{COLOR_CARD}}`, `{{COLOR_TEXT}}`, `{{COLOR_ACCENT}}`, `{{COLOR_BUTTON}}` | optional | Color overrides; empty means the style's own palette. See [Custom colors](#custom-colors). |

### Markers

- `<!--IF:SLOT--> … <!--/IF:SLOT-->`: the block is kept only when that slot has a value.
- `<!--IFNOT:SLOT--> … <!--/IFNOT:SLOT-->`: the block is kept only when that slot is empty.
- `<!--COLORS:{…}-->`: the style's default palette as JSON (plus the fixed headline, sign-off, P.S. and button-label colors used for contrast checks). `fill.py` reads it for the `COLOR_*` defaults and removes it.
- `<!--FOOTER--> … <!--/FOOTER-->`: the small grey line "made with Rosie · digitalswamp.io". Pass `--no-footer` to drop it.

`tools/fill.py` resolves every marker. A filled file contains no markers and no `{{…}}`.

## Custom colors

Five colors can be overridden per card. Anything left empty keeps the style's palette, so a card with no overrides is byte-for-byte the same as the stock template.

| Slot | Colors | Funny | Heartfelt | Kid/Fun | Classic |
|---|---|---|---|---|---|
| `COLOR_BG` | page background around the card | `#f4f1ea` | `#efe6dc` | `#dff3fb` | `#f3efe4` |
| `COLOR_CARD` | card background | `#fffdf8` | `#fbf6ee` | `#fffef5` | `#fffaf0` |
| `COLOR_TEXT` | verse text | `#333333` | `#4a3f38` | `#2b2b2b` | `#2f3a4f` |
| `COLOR_ACCENT` | the recipient's name | `#2e6b3f` | `#a4545b` | `#1864ab` | `#1b2a4a` |
| `COLOR_BUTTON` | "Write back" button | `#2e6b3f` | `#a4545b` | `#1864ab` | `#1b2a4a` |

Borders, emoji strips, badge, rules, headline, sign-off and P.S. keep the style's colors.

- **How to pass them:** `--colors '{"COLOR_ACCENT":"#c0392b"}'` or `--colors file.json`. `COLOR_*` keys inside the values JSON work too; `--colors` wins.
- **Validation:** only the five slot names are accepted, and each value must be `#rgb` or `#rrggbb`. Anything else stops `fill.py`.
- **Contrast warning:** when overrides are given, `fill.py` prints a `warning:` (it still writes the card) for any touched pair below WCAG 4.5:1: verse on card, button label on button, sign-off and P.S. on card. The large name and headline lines use 3:1, as does the footer grey on the page background. It also warns about pure `#000000`/`#ffffff`, which behave badly under dark-mode inversion. Take the warning seriously and pick a darker or lighter shade rather than sending a hard-to-read card.
- **Example:** [`previews/example-colors.json`](previews/example-colors.json) (red accent and button, pale blue page) rendered on the Classic style:

<img src="previews/classic-override.png" width="300" alt="Classic card with custom red accent and pale blue page">

## Art

Each template has an optional art block right above the headline: a full-width image (`width:100%; max-width:480px`, with an HTML `width` set to the card's inner width for Outlook). It's removed when `ART_SRC` is empty, so cards without art are unchanged.

### Inline CID attachment (default)

`fill.py --art IMAGE` embeds the picture as an **inline CID attachment** named `art.jpg`, and the HTML references it as `<img src="cid:art.jpg">`. This needs no image hosting and shows even when the reader's mail app blocks remote images.

`fill.py ... --art picture.png` resizes the image to at most 960 px wide (`--art-width`), saves a JPEG at the highest quality that fits under 300 KB (`--art-max-kb`; quality steps down from 85 to 40), and writes:

- `OUT.html` / `OUT.txt`, with `ART_SRC` set to `cid:art.jpg`
- `OUT.art.jpg`: the compressed image (a 1280×720 PNG becomes 960×540; compare [`previews/example-art-1280x720.png`](previews/example-art-1280x720.png) and [`previews/example-art-960.jpg`](previews/example-art-960.jpg))
- `OUT.eml`: a complete MIME message: `multipart/alternative` → `text/plain` + `multipart/related` → (`text/html`, `image/jpeg` with `Content-ID: <art.jpg>`, inline). Open it in a mail app or send it through anything that accepts raw MIME.
- `OUT.send.json`: `to`, `subject`, `from`, `body` (text), `htmlBody`, and `attachments: [{content (base64), filename: "art.jpg", mimeType: "image/jpeg", inline: true}]`, for mail APIs that take inline attachments.

If you send it yourself, don't rename the attachment: the `cid:art.jpg` in the HTML must match the filename/Content-ID `art.jpg`.

### Hosted image (alternative)

Put a hosted `https://` URL in `ART_SRC` in the values JSON and leave out `--art`. It only shows when the reader's mail app loads remote images. Use a static host that serves the image file directly; avoid share links that redirect to a sign-in page, and never use a host that adds tracking or redirects.

Make your own art at any size (a 16:9 image such as 1280×720 works well). Please don't use real people's faces or likenesses.

## Running the tools

### `tools/fill.py`

```
python3 tools/fill.py STYLE VALUES.json OUT_BASENAME --from ADDR [options]
python3 tools/fill.py --template PATH.html VALUES.json OUT_BASENAME --from ADDR [options]
```

- `STYLE` is `funny`, `heartfelt`, `kidfun` or `classic` (reads `templates/STYLE.html` and `.txt`). Or pass any template with `--template PATH.html` (its text twin is the same path ending `.txt`, or pass `--text-template`).
- `--from ADDR` is **required**, or set the `ROSIE_FROM` environment variable. It's used for the `From` header and for the `Message-ID` domain in the `.eml`.
- `--to ADDR`, `--subject TEXT`: optional headers for `OUT.eml` / `OUT.send.json`.
- `--no-footer`: drop the "made with Rosie" line.
- `--colors JSON|FILE`: color overrides (see above).
- `--art IMAGE [--art-width 960] [--art-max-kb 300]`: inline art (needs Pillow).

It writes `OUT.html` and `OUT.txt` (plus `.art.jpg`, `.eml` and `.send.json` with `--art`). It refuses to overwrite any existing file, fails on an empty required slot, and fails on any unfilled slot or marker.

### `tools/preview.py`

```
python3 tools/preview.py IN.html OUT.png [--dark] [--art FILE]
```

Renders a filled card to a PNG at 600 px wide (2× scale) with headless Chromium. It needs `playwright` and a browser (`python3 -m playwright install chromium`). To use an installed Chrome or Chromium instead, set `ROSIE_CHROME=/path/to/chrome`. If the card uses `cid:art.jpg`, the sibling `IN.art.jpg` written by `fill.py --art` is shown in its place (or pass `--art FILE`). `--dark` simulates a mail app that force-inverts colors.

### `tools/check_email_safety.py`

```
python3 tools/check_email_safety.py FILE.html [...]
```

Lints templates or filled cards and exits 1 on any failure: style blocks, scripts, event handlers, CSS animation, web fonts, tracking params, redirectors, 1×1 pixels, non-https links or images, images without alt, and art that isn't `width:100%; max-width:480px`.

### `tools/build_templates.py`

Regenerates the four templates in `templates/` from their palettes. You only need it if you change a style.

## Email-safety rules these templates follow

- **Full head:** `lang="en"`, `meta charset="utf-8"`, viewport, and `x-apple-disable-message-reformatting`.
- **Dark mode meta:** `color-scheme` and `supported-color-schemes` set to `light dark`. Every text color sits on its own solid `bgcolor`, with no pure black or white, so mid-tone accents stay readable when a client inverts colors. The footer grey `#8a8a8a` reads on both.
- **Hidden preheader** div (`display:none; mso-hide:all`).
- **Tables for layout:** an outer table at 100% width, then an inner table at `width:100%; max-width:480px`.
- **MSO wrapper:** Outlook gets a conditional `<!--[if mso]>` `<table width="480">` wrapper, since it ignores `max-width`.
- **Inline CSS only**, with no `<style>` block and no external CSS. Fonts are system stacks only (sans: `-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial`; serif: `Georgia, 'Times New Roman'`). No web fonts.
- **No JavaScript** and no CSS animation. Decoration is emoji; the only content images are the optional art, signature and envelope images.
- **No tracking:** no tracking pixels, open or click tracking, or link redirectors.

## How Rosie uses it

Rosie (the Grok Bot) follows a simple loop with its owner: **draft** a card with `fill.py` and show the preview PNG plus the plain-text version, **test-send** it to the owner's own address to check it in real mail apps, wait until the **owner approves**, then **send** it once, on the day. Rosie never sends a card without approval and never posts anywhere.

## Files

```
templates/   funny, heartfelt, kidfun, classic (.html + .txt)
tools/       fill.py, preview.py, check_email_safety.py, build_templates.py
previews/    example renders (plain, -art, -dark, -art-dark, classic-override),
             example-values.json, example-colors.json, example art (PNG + compressed JPEG)
```

## License

MIT. See [LICENSE](LICENSE).
