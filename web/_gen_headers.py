from pathlib import Path

root = Path(__file__).resolve().parent.parent
web = root / "web"


def to_header(src_name: str, var_name: str, header_name: str, note: str) -> None:
    text = (web / src_name).read_text(encoding="utf-8")
    if ")rawliteral" in text:
        raise SystemExit(f"rawliteral conflict in {src_name}")
    guard = header_name.upper().replace(".", "_")
    body = "\n".join(
        [
            f"#ifndef {guard}",
            f"#define {guard}",
            "",
            f"// Auto-generated from web/{src_name} — {note}",
            f'const char {var_name}[] PROGMEM = R"rawliteral(',
            text.rstrip(),
            ')rawliteral";',
            "",
            "#endif",
            "",
        ]
    )
    (root / header_name).write_text(body, encoding="utf-8")
    print(f"Wrote {header_name} ({len(text)} chars)")


html_path = web / "index.html"
html = html_path.read_text(encoding="utf-8")
html = html.replace('href="style.css"', 'href="/style.css"')
html = html.replace('src="app.js"', 'src="/app.js"')
html_path.write_text(html, encoding="utf-8")

to_header("index.html", "HTML_CONTENT", "index_html.h", "text/html")
to_header("style.css", "STYLE_CSS_CONTENT", "style_css.h", "text/css")
to_header("app.js", "APP_JS_CONTENT", "app_js.h", "application/javascript")
