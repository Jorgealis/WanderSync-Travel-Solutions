"""Compila el Documento Técnico (tarea 7.5): Markdown + diagramas Mermaid → HTML → PDF.

    pip install markdown==3.7
    python scripts/build_technical_doc.py [--autores "Nombre 1 · Nombre 2"]

Une docs/arquitectura.md, docs/saga.md y docs/seguridad/README.md (y como anexo
docs/requerimientos.md) en docs/documento-tecnico.html, y lo imprime a
docs/documento-tecnico.pdf con Chrome o Edge en modo headless (los diagramas Mermaid se
renderizan en el navegador con mermaid.js).
"""

import argparse
import html
import re
import shutil
import subprocess
import sys
from datetime import date
from pathlib import Path

import markdown

ROOT = Path(__file__).resolve().parent.parent
DOCS = ROOT / "docs"
CHAPTERS = [
    ("arquitectura.md", "Arquitectura"),
    ("saga.md", "Patrón SAGA"),
    ("seguridad/README.md", "Seguridad por diseño"),
    ("requerimientos.md", "Anexo A — Trazabilidad de requerimientos"),
]
MERMAID = "https://cdn.jsdelivr.net/npm/mermaid@11.4.1/dist/mermaid.min.js"
BROWSERS = [
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    "google-chrome", "chromium", "chromium-browser", "msedge",
]

CSS = """
@page { size: A4; margin: 18mm 16mm; }
body { font-family: "Segoe UI", Roboto, Arial, sans-serif; font-size: 10.5pt; line-height: 1.45; color: #1f2933; }
h1 { font-size: 20pt; color: #0c4a6e; border-bottom: 2px solid #0c4a6e; padding-bottom: 4px; page-break-before: always; }
h2 { font-size: 14pt; color: #075985; margin-top: 1.4em; }
h3 { font-size: 12pt; color: #0369a1; }
table { border-collapse: collapse; width: 100%; margin: 0.8em 0; font-size: 9pt; page-break-inside: auto; }
tr { page-break-inside: avoid; }
th, td { border: 1px solid #cbd5e1; padding: 4px 6px; vertical-align: top; text-align: left; }
th { background: #e0f2fe; }
code { font-family: Consolas, "Courier New", monospace; font-size: 8.8pt; background: #f1f5f9; padding: 0 3px; border-radius: 3px; }
pre { background: #f1f5f9; padding: 8px; border-radius: 4px; overflow-wrap: anywhere; white-space: pre-wrap; font-size: 8.5pt; }
pre.mermaid { background: none; text-align: center; page-break-inside: avoid; }
blockquote { border-left: 3px solid #94a3b8; margin-left: 0; padding-left: 10px; color: #475569; }
a { color: #0369a1; text-decoration: none; }
.cover { height: 92vh; display: flex; flex-direction: column; justify-content: center; text-align: center; }
.cover h1 { border: none; page-break-before: avoid; font-size: 28pt; }
.cover .sub { font-size: 14pt; color: #475569; }
.toc { page-break-before: always; }
.toc li { margin: 4px 0; }
"""


def chapter_html(path: Path, title: str, number: int) -> str:
    text = path.read_text(encoding="utf-8")
    text = re.sub(r"^# .*$", f"# {number}. {title}", text, count=1, flags=re.MULTILINE)
    body = markdown.markdown(text, extensions=["tables", "fenced_code", "sane_lists"])
    # Bloques ```mermaid → <pre class="mermaid"> para mermaid.js.
    body = re.sub(r'<pre><code class="language-mermaid">(.*?)</code></pre>',
                  r'<pre class="mermaid">\1</pre>', body, flags=re.DOTALL)
    return f'<section id="cap{number}">{body}</section>'


def build_html(authors: str) -> str:
    chapters = [chapter_html(DOCS / file, title, i) for i, (file, title) in enumerate(CHAPTERS, 1)]
    toc = "".join(f'<li><a href="#cap{i}">{i}. {html.escape(t)}</a></li>' for i, (_f, t) in enumerate(CHAPTERS, 1))
    return f"""<!doctype html>
<html lang="es"><head><meta charset="utf-8"><title>WanderSync — Documento Técnico</title>
<style>{CSS}</style></head><body>
<div class="cover">
  <h1>WanderSync Travel Solutions</h1>
  <p class="sub">Plataforma de Empaquetamiento Turístico Dinámico</p>
  <p class="sub">Documento Técnico de Arquitectura</p>
  <p>Patrones Arquitectónicos Avanzados — Parcial 2 (Segundo Corte)</p>
  <p>{html.escape(authors)}</p>
  <p>{date.today().isoformat()} · https://github.com/Jorgealis/WanderSync-Travel-Solutions</p>
</div>
<div class="toc"><h2>Contenido</h2><ol style="list-style:none;padding-left:0">{toc}</ol></div>
{''.join(chapters)}
<script src="{MERMAID}"></script>
<script>
  mermaid.initialize({{ startOnLoad: false, theme: "neutral", securityLevel: "strict",
                       flowchart: {{ useMaxWidth: true }}, sequence: {{ useMaxWidth: true }} }});
  mermaid.run().then(() => {{ document.body.dataset.ready = "1"; }});
</script>
</body></html>"""


def find_browser() -> str:
    for candidate in BROWSERS:
        found = shutil.which(candidate) or (candidate if Path(candidate).exists() else None)
        if found:
            return found
    sys.exit("No se encontró Chrome/Edge/Chromium para imprimir el PDF")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--autores", default="Equipo WanderSync")
    args = parser.parse_args()
    html_path = DOCS / "documento-tecnico.html"
    pdf_path = DOCS / "documento-tecnico.pdf"
    html_path.write_text(build_html(args.autores), encoding="utf-8")
    subprocess.run([
        find_browser(), "--headless=new", "--disable-gpu", "--no-pdf-header-footer",
        "--run-all-compositor-stages-before-draw", "--virtual-time-budget=30000",
        f"--print-to-pdf={pdf_path}", html_path.as_uri(),
    ], check=True, capture_output=True)
    print(f"HTML: {html_path.relative_to(ROOT)}\nPDF:  {pdf_path.relative_to(ROOT)} ({pdf_path.stat().st_size // 1024} KiB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
