"""Email-safe font menu shared by fill.py and check_email_safety.py.

Every stack lists only fonts that ship with Windows, macOS, iOS or Android (or system-font
keywords), includes a Windows font so Outlook for Windows gets a real face, and ends with a
generic family. No web fonts are loaded; nothing here needs @font-face or a
font host."""

SANS = "-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Helvetica,Arial,sans-serif"
SERIF = "Georgia,'Times New Roman',Times,serif"

FONT_MENU = {
    "classic-serif": SERIF,
    "clean-sans": SANS,
    "elegant-serif": "'Palatino Linotype',Palatino,'Book Antiqua',Georgia,serif",
    "friendly-sans": "Verdana,Geneva,Tahoma,sans-serif",
    "modern-sans": "'Trebuchet MS','Lucida Grande','Lucida Sans Unicode',Arial,sans-serif",
    "rounded": "'Arial Rounded MT Bold','Trebuchet MS',ui-rounded,'Helvetica Rounded',Verdana,sans-serif",
    "typewriter": "'Courier New',Courier,'American Typewriter',monospace",
}

GENERIC = {"serif", "sans-serif", "monospace", "cursive", "system-ui", "ui-rounded", "ui-serif",
           "ui-sans-serif", "ui-monospace", "-apple-system", "blinkmacsystemfont"}

# Fonts installed on common desktop/mobile systems (or system-font keywords). Anything else would
# only show for readers who happen to have it installed, so the lint rejects it.
SAFE_FONTS = GENERIC | {f.lower() for f in [
    "Segoe UI", "Roboto", "Helvetica", "Helvetica Neue", "Arial", "Georgia", "Times New Roman", "Times",
    "Palatino Linotype", "Palatino", "Book Antiqua", "Verdana", "Geneva", "Tahoma", "Trebuchet MS",
    "Lucida Grande", "Lucida Sans Unicode", "Arial Rounded MT Bold", "Helvetica Rounded",
    "Courier New", "Courier", "American Typewriter", "Garamond", "Baskerville", "Cambria", "Calibri",
    "Gill Sans", "Optima", "Futura", "Avenir", "Avenir Next", "Menlo", "Consolas", "Monaco",
]}


def parse_stack(stack):
    return [f.strip().strip("'\"").strip() for f in stack.split(",") if f.strip()]


def stack_problems(stack):
    """Return a list of reasons this font-family value is not email-safe (empty = fine)."""
    fams = parse_stack(stack)
    if not fams:
        return ["empty font-family"]
    out = ["font %r is not on the email-safe list" % f for f in fams if f.lower() not in SAFE_FONTS]
    if fams[-1].lower() not in {"serif", "sans-serif", "monospace", "cursive"}:
        out.append("font stack must end with a generic family (serif, sans-serif, monospace)")
    return out
