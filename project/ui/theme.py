"""RE:L!NK design tokens: one dark palette for CSS, diagrams, the map and charts.

Every colour the interface draws comes from here (or from .streamlit/config.toml,
which mirrors these values), so pages stay consistent and contrast can be tested.
"""
from __future__ import annotations

# Surfaces, from the page background up to raised cards.
BG = '#070B12'
SURFACE = '#0D141F'
SURFACE_2 = '#121B28'
RAISED = '#182334'
BORDER = '#22303F'
BORDER_STRONG = '#33465C'

# Text.
TEXT = '#EAF1F8'
TEXT_2 = '#B8C6D6'
MUTED = '#8D9EB3'

# Brand: RE:L!NK mint, plus status colours.
MINT = '#54D6BB'
MINT_BRIGHT = '#7BE8CF'
MINT_DEEP = '#1F8F78'
ON_MINT = '#03110D'
AMBER = '#F4C76B'
ORANGE = '#FF9F5A'
RED = '#FF7A85'
BLUE = '#7DB8F5'
VIOLET = '#B7A5E6'
SLATE = '#7A8CA3'

STATUS = {'ok': MINT, 'warn': AMBER, 'fault': RED, 'info': BLUE}
CHART = [MINT, AMBER, BLUE, ORANGE, VIOLET, RED, SLATE]

TOKENS = {
    'bg': BG, 'surface': SURFACE, 'surface-2': SURFACE_2, 'raised': RAISED, 'border': BORDER,
    'border-strong': BORDER_STRONG, 'text': TEXT, 'text-2': TEXT_2, 'muted': MUTED, 'mint': MINT,
    'mint-bright': MINT_BRIGHT, 'mint-deep': MINT_DEEP, 'on-mint': ON_MINT, 'amber': AMBER, 'orange': ORANGE,
    'red': RED, 'blue': BLUE, 'violet': VIOLET, 'slate': SLATE,
}

# Text/background pairs the interface actually uses; tests keep them at WCAG AA (4.5:1).
TEXT_PAIRS = [(fg, bg) for fg in (TEXT, TEXT_2, MUTED, MINT, AMBER, RED, BLUE) for bg in (BG, SURFACE, SURFACE_2, RAISED)]
TEXT_PAIRS.append((ON_MINT, MINT))


def rgb(hex_colour):
    h = hex_colour.lstrip('#')
    return [int(h[i:i + 2], 16) for i in (0, 2, 4)]


def contrast(fg, bg):
    def lum(c):
        def ch(v):
            v /= 255
            return v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4
        r, g, b = (ch(v) for v in rgb(c))
        return 0.2126 * r + 0.7152 * g + 0.0722 * b
    a, b = sorted((lum(fg), lum(bg)), reverse=True)
    return (a + 0.05) / (b + 0.05)


def css_vars():
    return ':root{' + ''.join(f'--rl-{k}:{v};' for k, v in TOKENS.items()) + '}'

# Logo colours, sampled from docs/assets/branding/relink-logo.png.
LOGO_CYAN = '#00C9FE'
LOGO_MINT = '#1AF4BA'
LOGO_TEAL = '#13E9D4'  # the ':' and '!' in the wordmark
TOKENS.update({'logo-cyan': LOGO_CYAN, 'logo-mint': LOGO_MINT, 'logo-teal': LOGO_TEAL})
