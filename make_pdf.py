"""Convert EXE-USER-GUIDE.md to User Guide.pdf using PyMuPDF Story API."""
import os, sys
import markdown, fitz

GUIDE_MD = os.path.join(os.path.dirname(__file__), "EXE-USER-GUIDE.md")
OUT_PDF  = os.path.join(os.path.dirname(__file__),
                        "dist", "AQMD Rule Finder", "User Guide.pdf")

CSS = """
body {
    font-family: Arial, Helvetica, sans-serif;
    font-size: 11pt;
    line-height: 1.5;
    color: #222;
    margin: 0;
    padding: 0;
}
h1 {
    font-size: 20pt;
    color: #1a3a5c;
    border-bottom: 2px solid #1a3a5c;
    padding-bottom: 6pt;
    margin-top: 0;
}
h2 {
    font-size: 14pt;
    color: #1a3a5c;
    border-bottom: 1px solid #ccc;
    padding-bottom: 3pt;
    margin-top: 18pt;
}
h3 {
    font-size: 12pt;
    color: #2c5f8a;
    margin-top: 12pt;
}
h4 {
    font-size: 11pt;
    color: #2c5f8a;
    margin-top: 10pt;
}
p  { margin: 6pt 0; }
ul, ol { margin: 4pt 0 4pt 18pt; padding: 0; }
li { margin: 2pt 0; }
code {
    font-family: "Courier New", monospace;
    font-size: 9.5pt;
    background: #f4f4f4;
    padding: 1pt 3pt;
    border-radius: 2pt;
}
pre {
    font-family: "Courier New", monospace;
    font-size: 9pt;
    background: #f4f4f4;
    border: 1px solid #ddd;
    padding: 8pt;
    margin: 6pt 0;
    white-space: pre-wrap;
    border-radius: 3pt;
}
pre code { background: none; padding: 0; }
table {
    border-collapse: collapse;
    width: 100%;
    margin: 8pt 0;
    font-size: 10pt;
}
th {
    background: #1a3a5c;
    color: white;
    padding: 5pt 8pt;
    text-align: left;
}
td { padding: 4pt 8pt; border-bottom: 1px solid #ddd; }
tr:nth-child(even) td { background: #f8f8f8; }
blockquote {
    border-left: 3pt solid #2c5f8a;
    margin: 6pt 0 6pt 8pt;
    padding: 2pt 0 2pt 10pt;
    color: #444;
}
strong { color: #111; }
a { color: #2c5f8a; }
hr { border: none; border-top: 1px solid #ccc; margin: 12pt 0; }
"""

def make_pdf(out_path=None):
    if out_path is None:
        out_path = OUT_PDF
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(GUIDE_MD, encoding="utf-8") as f:
        md_text = f.read()
    html_body = markdown.markdown(md_text, extensions=["tables", "fenced_code"])
    full_html = f"<html><head><style>{CSS}</style></head><body>{html_body}</body></html>"
    PAGE_W, PAGE_H = fitz.paper_size("letter")
    MARGIN = 72
    story = fitz.Story(html=full_html)
    writer = fitz.DocumentWriter(out_path)
    more = True
    while more:
        device = writer.begin_page(fitz.Rect(0, 0, PAGE_W, PAGE_H))
        more, _ = story.place(fitz.Rect(MARGIN, MARGIN, PAGE_W - MARGIN, PAGE_H - MARGIN))
        story.draw(device)
        writer.end_page()
    writer.close()
    print(f"Saved: {out_path}")

if __name__ == "__main__":
    make_pdf()
