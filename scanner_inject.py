#!/usr/bin/env python3
"""
Inject Hawkeye scanner into index.html with run_id validation and atomic write.
"""

from __future__ import annotations

from pathlib import Path
from datetime import datetime
import re


def atomic_write(path: Path, content: str) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(content)
    tmp.replace(path)



def _sync_hero_asset_count(html: str, scanner: str) -> str:
    m = re.search(r'<div class="scanner-score"><div class="num">(\d+)</div>', scanner)
    if not m:
        return html
    total = m.group(1)
    html = re.sub(r'data-target="\d+">\d+</span> assets', f'data-target="{total}">{total}</span> assets', html, count=1)
    return html

def inject(html_path="index.html", run_id: str | None = None):
    from scanner_generator import main as gen_scanner

    run_id = run_id or datetime.now().astimezone().strftime("%Y%m%d-%H%M%S")
    scanner = gen_scanner(run_id=run_id)
    if f'data-run-id="{run_id}"' not in scanner:
        raise RuntimeError(f"scanner run_id mismatch before injection: {run_id}")

    path = Path(html_path)
    html = path.read_text()
    start_tag = '<section id="scanner" class="scanner">'
    start_idx = html.find(start_tag)
    if start_idx == -1:
        # Current artifact can already contain an augmented class; fall back to id match.
        m = re.search(r'<section\s+id="scanner"[^>]*>', html)
        if not m:
            raise RuntimeError("No scanner section found")
        start_idx = m.start()
        end_search_start = m.end()
    else:
        end_search_start = start_idx + len(start_tag)

    depth = 1
    pos = end_search_start
    end_idx = None
    while depth > 0 and pos < len(html):
        next_open = html.find('<section', pos)
        next_close = html.find('</section>', pos)
        if next_close == -1:
            break
        if next_open != -1 and next_open < next_close:
            depth += 1
            pos = next_open + len('<section')
        else:
            depth -= 1
            if depth == 0:
                end_idx = next_close + len('</section>')
                break
            pos = next_close + len('</section>')
    if depth != 0 or end_idx is None:
        raise RuntimeError("Could not find matching scanner </section>")

    inner = re.search(r'<section[^>]*>(.*)</section>\s*$', scanner, re.DOTALL)
    if not inner:
        raise RuntimeError("Could not extract scanner content")
    new_content = inner.group(1)
    new_html = html[:end_search_start] + new_content + html[end_idx - len('</section>'):]
    if f'data-run-id="{run_id}"' not in scanner:
        raise RuntimeError(f"run_id validation failed after injection: {run_id}")
    new_html = _sync_hero_asset_count(new_html, scanner)
    atomic_write(path, new_html)
    print(f"✅ Scanner injected ({len(new_content)} bytes)")
    return True


if __name__ == "__main__":
    inject()
