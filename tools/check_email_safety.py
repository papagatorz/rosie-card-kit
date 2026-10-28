#!/usr/bin/env python3
"""Email-safety lint for Rosie templates and filled cards.
usage: check_email_safety.py FILE.html [...]   (exit 1 on any failure)
Checks: no <style>/<script>/<link>/<iframe>/<form>, no on*= handlers, no javascript: URLs,
no CSS animation/transition/@keyframes/@import/@font-face, no web-font hosts, no tracking
(1x1 pixels, utm_ params, redirect/click-tracking hosts), only https:/mailto:/cid: links and
images, every <img> has alt, and the art image is width 100% / max-width 480px."""
import re, sys

BAD = {
    "style block": r"<style\b", "script": r"<script\b|javascript:", "event handler": r"\son[a-z]+\s*=",
    "external css/link": r"<link\b", "iframe/form/object": r"<(iframe|form|object|embed)\b",
    "css animation": r"animation\s*:|@keyframes|transition\s*:", "css import": r"@import",
    "web font": r"@font-face|fonts\.googleapis|fonts\.gstatic|typekit|use\.fontawesome",
    "tracking param": r"[?&](utm_|mc_eid|mc_cid|fbclid|gclid)",
    "redirector/tracker": r"(click\.|track\.|/track/|/open\.gif|pixel\.|list-manage\.com|sendgrid\.net|mailchimp)",
    "1x1 pixel": r"<img\b[^>]*\b(width|height)=\"?1\"?[\s>/][^>]*>",
}

def check(path):
    s = open(path, encoding="utf-8").read()
    errs = [name for name, rx in BAD.items() if re.search(rx, s, re.I)]
    for m in re.finditer(r'\b(?:src|href)="([^"]*)"', s):
        u = m.group(1)
        if not re.match(r"(https://|mailto:|cid:|\{\{[A-Z_]+\}\}$)", u):
            errs.append("non-https link/src: " + u[:60])
    for img in re.findall(r"<img\b[^>]*>", s):
        if "alt=" not in img: errs.append("img without alt")
        if "{{ART_SRC}}" in img or "cid:art" in img:
            if "width:100%" not in img or "max-width:480px" not in img:
                errs.append("art img must be width:100%; max-width:480px")
    return errs

bad = 0
for p in sys.argv[1:]:
    e = check(p)
    print(("FAIL " if e else "ok   ") + p + (": " + "; ".join(e) if e else ""))
    bad += bool(e)
sys.exit(1 if bad else 0)
