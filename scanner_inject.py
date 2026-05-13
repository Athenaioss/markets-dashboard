#!/usr/bin/env python3
"""
Injects live Market Pulse Scanner into index.html.
Simple marker-based replacement — no regex.
"""

from pathlib import Path

MARKER_START = '<!-- ⚡ SCANNER START -->'
MARKER_END = '<!-- ⚡ SCANNER END -->'

def inject(html_path="index.html"):
    """Generate scanner and inject between markers, or replace section."""
    from scanner_generator import main as gen_scanner
    scanner = gen_scanner()
    
    html = Path(html_path).read_text()
    
    # Strategy: find <section id="scanner"> up to its </section>
    # and replace everything between them
    start_tag = '<section id="scanner" class="scanner">'
    end_tag = '</section>'
    
    start_idx = html.find(start_tag)
    if start_idx == -1:
        print("⚠️ No scanner section found")
        return False
    
    # Find the matching </section> — scan for the one at the same depth
    # Simple approach: find </section> after start_tag, then verify
    end_search_start = start_idx + len(start_tag)
    depth = 1
    pos = end_search_start
    while depth > 0 and pos < len(html):
        next_open = html.find('<section', pos)
        next_close = html.find('</section>', pos)
        if next_close == -1:
            break
        if next_open != -1 and next_open < next_close:
            depth += 1
            pos = next_open + 8
        else:
            depth -= 1
            if depth == 0:
                end_idx = next_close + len('</section>')
                break
            pos = next_close + 10
    
    if depth != 0:
        print("⚠️ Could not find matching </section>")
        return False
    
    # Extract scanner inner content (between <section...> and </section>)
    import re
    inner = re.search(r'<section[^>]*>(.*)</section>\s*$', scanner, re.DOTALL)
    if not inner:
        print("⚠️ Could not extract scanner content")
        return False
    
    new_content = inner.group(1)
    new_html = html[:end_search_start] + new_content + html[end_idx - len('</section>'):]
    Path(html_path).write_text(new_html)
    
    print(f"✅ Scanner injected ({len(new_content)} bytes)")
    # Verify
    vfy = Path(html_path).read_text()
    print(f"  signal-rows: {vfy.count('signal-row')}")
    print(f"  asset-breakdown: {vfy.count('asset-breakdown')}")
    return True

if __name__ == "__main__":
    inject()
