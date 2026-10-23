"""Create a branded Selkies web root with the 7BZ streaming HUD."""
from importlib import resources
from pathlib import Path
import shutil


BENCH = Path("/tmp/kaggle-game-dev-bench")
WEB_ROOT = BENCH / "web-root"
ASSETS = BENCH / "web_client"
MARKER = "7BZ Dev Cloud Game HUD"


def _source_root() -> Path:
    import selkies
    direct = Path(selkies.__file__).resolve().parent / "selkies_web"
    if direct.is_dir():
        return direct
    package = resources.files("selkies.selkies_web")
    with resources.as_file(package) as extracted:
        if extracted.is_dir():
            temporary = BENCH / "selkies-web-source"
            shutil.copytree(extracted, temporary, dirs_exist_ok=True)
            return temporary
    raise RuntimeError("Selkies web assets were not found")


def install() -> Path:
    """Copy the installed client, add branded assets, and return its web root."""
    source = _source_root()
    shutil.copytree(source, WEB_ROOT, dirs_exist_ok=True)
    shutil.copy2(ASSETS / "hud.css", WEB_ROOT / "7bz-hud.css")
    shutil.copy2(ASSETS / "hud.js", WEB_ROOT / "7bz-hud.js")
    index = WEB_ROOT / "index.html"
    text = index.read_text(encoding="utf-8")
    if MARKER not in text:
        head = f'<!-- {MARKER} -->\n<link rel="stylesheet" href="7bz-hud.css">\n'
        script = '<script defer src="7bz-hud.js"></script>\n'
        text = text.replace("</head>", head + "</head>")
        text = text.replace("</body>", script + "</body>")
    text = text.replace("<title>Selkies</title>", "<title>7BZ Dev Cloud Game</title>")
    index.write_text(text, encoding="utf-8")
    return WEB_ROOT


if __name__ == "__main__":
    print(install())
