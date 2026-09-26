# Last Z State 798 Atlas

Static GitHub Pages atlas built from a complete 5,100-capture map sweep. Pan and zoom the stitched map, search the 2,854 outside-capital candidate headquarters or 827 candidates inside the capital's 100-tile radius, and open an original in-game screenshot crop for each HQ.

The published assets use compressed map tiles and per-HQ crops. The 5,100 full-resolution PNG captures and OCR cache remain in the user's local archive and are too large for GitHub Pages. [GitHub Pages limits](https://docs.github.com/en/pages/getting-started-with-github-pages/github-pages-limits) cap a published site at 1 GB.

City names, alliance tags, coordinates, and HQ levels are estimates from OCR and screenshot review. A follow-up badge audit recovered 154 capital HQs and 196 outside HQs omitted by the original dark-nameplate threshold; Samuelm and Imperial XXI were added from direct screenshot review. Four city nameplates outside the circle and some inside it remain unreadable. `[Helm]` members are excluded from the outside list and included in the capital list. The circle is centered at (500,500) with radius 100 tiles. Some capital HQ levels remain unreadable and are labeled as such.

The website is plain HTML/CSS/JavaScript. `build_assets.py`, `add_capital_assets.py`, `augment_missing_capital.py`, and `augment_missing_outside.py` record how its map tiles and photos were produced from the local capture archive.
