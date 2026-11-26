"""D-ACAL-167 (fondateur 26/11/2026, « nouveaux rendus seulement ») — le court
bloc « Bases du calcul » de la page « Rentabilité sur N ans » du document
industriel (constat T4-U2-020).

Le tableau complet des hypothèses de la page (``finance._hypotheses`` ou, à
deux options, ``finance_deux._bases``) est CÉDABLE (``data-graphique=
"hypotheses"``) : sur une page dense le rendu adaptatif le retire, et la page
n'imprimait plus ni l'horizon, ni l'indexation, ni la dégradation, ni la base
de production, ni le tarif qui a servi au « prix moyen de votre kWh évité ».
Quand il a cédé, ce module imprime à sa place UNE ligne compacte, dans la
classe du pied de page (``i2-foot`` : aucune CSS neuve), construite par LE
même constructeur que le tableau de la page 3 commerciale
(``finance.rangees_hypotheses`` : une source, aucune valeur écrite ici, une
valeur absente est omise).

Jamais une 5ᵉ page : la ligne est elle-même cédable (``data-graphique=
"bases_courtes"``, dernière étape de ``commercial.equip.ORDRE_CEDABLES``) ;
si la page déborde encore, le rendu adaptatif la retire SEULE et le document
redevient exactement celui d'hier. Au dernier
recours du rendu adaptatif (conditions tronquées, ``_cgv_max``) elle n'est pas
posée : ce chemin reste octet pour octet celui d'avant.

Nouveaux rendus seulement : drapeau ``phrases_pdf_2611`` (posé par le builder
via ``regles_calcul.drapeaux_pdf_2611``) ; sans lui, rien ne change.
"""
from __future__ import annotations

from ..ci.graphiques import cede

#: Nom cédable de la ligne (``ci.graphiques.cede``).
NOM = "bases_courtes"
#: Les hypothèses du flux servi gardées par la ligne courte.
CLES_FLUX = ("horizon_ans", "indexation_pct", "degradation_pct")
_PIED = '<div class="i2-foot">'


def _dict(valeur):
    return valeur if isinstance(valeur, dict) else {}


def _synthese_courte(d, argent):
    """La synthèse réduite aux seules bases de la ligne : horizon, indexation,
    dégradation (flux principal servi), tarif retenu, base de production."""
    from . import finance as F
    argent = _dict(argent)
    cle, flux = F.flux_principal(argent)
    court = dict(argent, remplacements=[], batterie_duree=None, hypotheses=[
        h for h in argent.get("hypotheses") or []
        if isinstance(h, dict) and h.get("cle") == "tarif"])
    if cle:
        court[cle] = dict(flux, hypotheses=[
            h for h in flux.get("hypotheses") or []
            if isinstance(h, dict) and h.get("cle") in CLES_FLUX])
    synthese = _dict(d.get("ind_synthese"))
    production = _dict(_dict(synthese.get("estimation")).get("production"))
    return dict(synthese, argent=court, estimation={"production": production})


def bloc(d, argent, fmt, fmt_mad, L):
    """La ligne « Bases du calcul : … » quand le tableau complet a cédé, ou ''."""
    if (not d.get("phrases_pdf_2611") or not cede(d, "hypotheses")
            or cede(d, NOM) or "_cgv_max" in d):
        return ""
    from . import finance as F
    items = [f"{libelle}&#160;: {valeur}" if libelle and valeur
             else (libelle or valeur)
             for libelle, valeur in F.rangees_hypotheses(
                 d, _synthese_courte(d, argent), fmt, fmt_mad, L, compact=True)]
    items = [i for i in items if i]
    if not items:
        return ""
    return (f'<div class="i2-foot" data-graphique="{NOM}">'
            f'<b>{L("ci_bases_calcul", F.TITRE_HYPOTHESES)}</b>&#160;: '
            + " · ".join(items) + "</div>")


def avec_bases(d, corps, argent, fmt, fmt_mad, L):
    """``corps`` avec la ligne courte juste avant son pied (à défaut, à la
    fin) ; ``corps`` tel quel quand elle n'est pas posée."""
    court = bloc(d, argent, fmt, fmt_mad, L)
    if not court:
        return corps
    i = corps.rfind(_PIED)
    return corps + court if i < 0 else corps[:i] + court + corps[i:]


def annoncees(corps):
    """Des bases du calcul (tableau complet ou ligne courte) sont-elles
    imprimées dans ``corps`` ? (l'annonce « bases du calcul ci-dessous »)"""
    return ('data-graphique="hypotheses"' in corps
            or f'data-graphique="{NOM}"' in corps)
