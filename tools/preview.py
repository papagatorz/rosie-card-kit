"""Render a filled card HTML to PNG with headless Chrome.
usage: python3 preview.py IN.html OUT.png [--dark] [--art FILE]
Needs playwright and a Chromium: pip install playwright && python3 -m playwright install chromium.
Set ROSIE_CHROME=/path/to/chrome to use an installed Chrome/Chromium instead of the bundled one.
Paths may be relative (to the current directory) or absolute.
--dark simulates forced color inversion.
If the card uses inline art (src="cid:art.jpg"), the sibling IN-basename.art.jpg written by
fill.py --art is shown in its place (pass --art FILE to use a different image)."""
import os, re, sys, tempfile
from pathlib import Path
from playwright.sync_api import sync_playwright

argv = sys.argv[1:]
art = None
if "--art" in argv:
    i = argv.index("--art"); art = os.path.abspath(argv[i + 1]); del argv[i:i + 2]
pos = [x for x in argv if not x.startswith("--")]
if len(pos) != 2:
    sys.exit(__doc__)
src, dst = (os.path.abspath(os.path.expanduser(p)) for p in pos)
if not os.path.isfile(src):
    sys.exit("not found: " + src)

page_path = src
html_text = open(src, encoding="utf-8").read()
if re.search(r'src="cid:', html_text):
    if art is None:
        art = os.path.splitext(src)[0] + ".art.jpg"
    if not os.path.isfile(art):
        sys.exit("card uses a cid: image but no art file found at " + art + " (pass --art FILE)")
    tmp = tempfile.NamedTemporaryFile("w", suffix=".html", delete=False, encoding="utf-8")
    tmp.write(re.sub(r'src="cid:[^"]+"', 'src="%s"' % Path(art).as_uri(), html_text)); tmp.close()
    page_path = tmp.name

with sync_playwright() as p:
    chrome = os.environ.get("ROSIE_CHROME")  # optional: path to a system Chrome/Chromium
    b = p.chromium.launch(executable_path=chrome or None, args=["--no-sandbox"])
    pg = b.new_page(viewport={"width": 600, "height": 300}, device_scale_factor=2,
                    color_scheme="light")
    pg.goto(Path(page_path).as_uri())
    pg.wait_for_load_state("load")
    if "--dark" in sys.argv:  # simulate a client that force-inverts colors (e.g. Gmail app dark mode)
        pg.add_style_tag(content="html{filter:invert(1) hue-rotate(180deg)} img{filter:invert(1) hue-rotate(180deg)}")
    pg.screenshot(path=dst, full_page=True)
    b.close()
if page_path != src:
    os.unlink(page_path)
print("wrote", dst)
