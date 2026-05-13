#!/usr/bin/env python3
"""
Injects live Momentum Scanner data into index.html.
Run after scanner_generator.py to wire real data.
"""

import re
from pathlib import Path

def inject_scanner(index_path="index.html", scanner_fragment_path=None):
    """Replace the <section id="scanner"> block in index.html with live data."""
    index = Path(index_path)
    html = index.read_text()
    
    if scanner_fragment_path and Path(scanner_fragment_path).exists():
        # Use generated fragment
        fragment = Path(scanner_fragment_path).read_text()
        # Find and replace the scanner section
        pattern = r'<!-- ⚡ Momentum Scanner.*?</section>'
        repl = re.sub(r'<!-- ⚡ Momentum Scanner.*?</section>', 
                      fragment.replace('\\', '\\\\'), html, count=1, flags=re.DOTALL)
        if repl != html:
            index.write_text(repl)
            print(f"✅ Scanner injected from {scanner_fragment_path}")
            return True
    
    # If no fragment, generate inline
    from scanner_generator import main as gen_scanner
    scanner_html = gen_scanner()
    
    # Find the scanner section and replace its board/content
    # Strategy: replace everything between <section id="scanner"> and its closing </section>
    pattern = r'(<section id="scanner" class="scanner">).*?(</section>)'
    if re.search(pattern, html, re.DOTALL):
        # extract the scanner block we want to inject (body only, no section wrapper)
        inner = re.search(r'<div class="scanner-head">.*</div>\s*</section>', scanner_html, re.DOTALL)
        if inner:
            new_html = re.sub(pattern, inner.group(0), html, count=1, flags=re.DOTALL)
            index.write_text(new_html)
            print(f"✅ Scanner live data injected into {index_path}")
            return True
    
    print("⚠️ Could not inject scanner — no matching section found")
    return False

if __name__ == "__main__":
    import sys
    frag = sys.argv[1] if len(sys.argv) > 1 else None
    inject_scanner(scanner_fragment_path=frag)
