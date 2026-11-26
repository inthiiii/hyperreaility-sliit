"""RE:L!NK lockup: the original R symbol and the one-word wordmark."""
import base64
from functools import lru_cache
from pathlib import Path


@lru_cache(maxsize=1)
def mark_uri():
    data = (Path(__file__).with_name('assets') / 'relink-mark.png').read_bytes()
    return 'data:image/png;base64,' + base64.b64encode(data).decode()


WORDMARK = '<span class="relink-word">RE<i>:</i>L<i>!</i>NK</span>'


def brand_html(size='md', tagline=False):
    """size: 'md' (sidebar) or 'xl' (sign-in)."""
    tag = '<div class="relink-tagline">Restore connectivity. Coordinate recovery.</div>' if tagline else ''
    return (f'<div class="relink-lockup relink-lockup-{size}"><div class="relink-brand">'
            f'<img class="relink-mark" src="{mark_uri()}" alt="">{WORDMARK}</div>{tag}</div>')
