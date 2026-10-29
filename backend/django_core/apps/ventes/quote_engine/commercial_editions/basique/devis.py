# flake8: noqa
# D-ENF22 : exception de fichier entier signée — moteur de devis vendoré (règle #4 de CLAUDE.md), non réécrit pour le lint.
"""Édition Basique — PAGE 2 (variante « deux », tableau long) : bandeau
d'en-tête 10 mm puis la suite (échéancier, garanties, conditions, QR, bon
pour accord, bande légale)."""
from .. import commun, donnees
from .essentiel import suite


def build(ctx, m, j):
    d, p = m["d"], "ba"
    L = lambda cle, fr, **v: donnees.L(d, cle, fr, **v)
    entete = commun.bande_entete(ctx, j, p, L("bon_pour_accord", "Bon pour accord"),
                                 f'{L("ci_ref_devis", "Réf. devis")} {m["ref"]}')
    return f"""
<div class="ba-root" style="padding-top:22mm;">
  {entete}
  {suite(ctx, m, j)}
</div>"""
