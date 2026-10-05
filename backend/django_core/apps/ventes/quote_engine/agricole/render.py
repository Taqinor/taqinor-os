"""AGR312 — point d'entrée HTML du paquet agricole, à la forme des autres
paquets du registre (``<paquet>.render.build_html``) : les gardes « document
rendu » (``tests/test_figures_parite.rendre_html``) le résolvent par ce nom.
Le gabarit vit dans :mod:`pages` ; ce module ne fait que le nommer."""
from .pages import build_html

__all__ = ["build_html"]
