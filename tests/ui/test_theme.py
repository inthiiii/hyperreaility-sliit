"""RE:L!NK dark theme: readable contrast and one palette across config, CSS and diagrams."""
import re
import tomllib
from pathlib import Path

from project.ui import theme

ROOT = Path(__file__).resolve().parents[2]
UI = ROOT / 'project' / 'ui'


def test_every_text_colour_meets_wcag_aa_on_every_surface():
    low = [(fg, bg, round(theme.contrast(fg, bg), 2)) for fg, bg in theme.TEXT_PAIRS if theme.contrast(fg, bg) < 4.5]
    assert not low


def test_streamlit_config_mirrors_the_theme_tokens():
    config = tomllib.loads((ROOT / '.streamlit' / 'config.toml').read_text())['theme']
    assert config['base'] == 'dark'
    assert config['primaryColor'].upper() == theme.MINT
    assert config['backgroundColor'].upper() == theme.BG
    assert config['textColor'].upper() == theme.TEXT
    assert [c.upper() for c in config['chartCategoricalColors']] == theme.CHART


def test_stylesheet_uses_tokens_that_exist():
    css = (UI / 'styles.css').read_text()
    used = set(re.findall(r'var\(--rl-([a-z0-9-]+)\)', css))
    assert used and used <= set(theme.TOKENS)
    assert theme.css_vars().startswith(':root{--rl-bg:')


def test_panel_text_colours_in_page_code_are_readable():
    # CSS text colours embedded in the agent-flow and map panels, which sit on SURFACE.
    found = []
    for path in ('agent_flow.py', 'map_page.py'):
        found += re.findall(r'(?<![-\w])color:\s*(#[0-9A-Fa-f]{6})', (UI / path).read_text())
    assert found
    low = {c for c in found if theme.contrast(c, theme.SURFACE) < 4.5}
    assert not low
