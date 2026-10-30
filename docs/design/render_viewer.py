"""Embed the checked-in D2 SVGs in the architecture skill's offline viewer.

Run from any directory. No dependency beyond Python's standard library.
The copied template is retained locally; diagram edits belong in the D2 files.
"""

from pathlib import Path
import re


ROOT = Path(__file__).resolve().parent


def svg(name: str) -> str:
    content = (ROOT / "diagrams" / f"{name}.svg").read_text()
    content = re.sub(r"<\?xml[^>]*\?>\s*", "", content)
    # D2 embeds its own styles/fonts and no external diagram assets.
    return content


def main() -> None:
    template = (ROOT / "viewer-template.html").read_text()
    architecture = svg("architecture")
    publication = svg("publication")
    template = template.replace("[ARCHITECTURE_SVG]", architecture)
    template = template.replace("[PUBLICATION_SVG]", publication)
    (ROOT / "architecture.html").write_text(template)
    print("Generated docs/design/architecture.html from D2 SVGs")


if __name__ == "__main__":
    main()
