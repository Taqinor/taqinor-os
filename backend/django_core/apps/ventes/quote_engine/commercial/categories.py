# flake8: noqa
"""Rendu des catégories commerciales (QX46) — pictogramme + RENDU du contenu
servi par ``ci/categories.py`` (CIQ330).

CIQ330 — le CONTENU (libellé, accroche, titre conditionnel, lignes
trilingues tirées des réponses DÉCLARÉES) vit dans UNE table,
``quote_engine/ci/categories.py``, servie dans ``synthese_ci['categorie']``
au PDF et à /proposition. Ce module ne garde que le pictogramme et le HTML
du bloc de la page 2 : aucun texte client n'est écrit ici.
"""
from ..ci import categories as ci_categories

#: APDF15 (C-APDF-017) — pictogramme par catégorie : SVG EN LIGNE (trait,
#: couleur héritée ``currentColor``), plus JAMAIS un emoji. L'image ne porte
#: aucune police emoji (``fc-list :charset=1f3ea`` vide) : WeasyPrint imprimait
#: un carré vide devant le titre de la couverture. Aucun texte, aucun glyphe.
_SVG = ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" '
        'fill="none" stroke="currentColor" stroke-width="1.6" '
        'stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">'
        '{}</svg>')
ICONES = {
    "hotel": _SVG.format(
        '<path d="M3 18V7M3 14h18v4M21 18v-4a3 3 0 0 0-3-3h-8v3"/>'
        '<circle cx="7" cy="11" r="1.6"/>'),
    "restaurant": _SVG.format(
        '<path d="M7 3v18M5 3v5a2 2 0 0 0 4 0V3M17 3c-2 2-2 6 0 8v10"/>'),
    "commerce": _SVG.format(
        '<path d="M3 4h2l2.4 10.2a1 1 0 0 0 1 .8h8.8a1 1 0 0 0 1-.8L20 8H6.2"/>'
        '<circle cx="9" cy="19" r="1.5"/><circle cx="17" cy="19" r="1.5"/>'),
    "bureau": _SVG.format(
        '<path d="M5 21V4h10v17M15 9h4v12M3 21h18M8 8h1M11 8h1M8 12h1'
        'M11 12h1M8 16h1M11 16h1"/>'),
    "sante": _SVG.format(
        '<rect x="4" y="4" width="16" height="16" rx="3"/>'
        '<path d="M12 8v8M8 12h8"/>'),
    "ecole": _SVG.format(
        '<path d="M2 9l10-5 10 5-10 5z"/>'
        '<path d="M6 11v5c3 2 9 2 12 0v-5M22 9v6"/>'),
    "hammam": _SVG.format(
        '<path d="M8 4c-1 1.5 1 2.5 0 4M12 4c-1 1.5 1 2.5 0 4'
        'M16 4c-1 1.5 1 2.5 0 4"/>'
        '<path d="M4 12h16v2a6 6 0 0 1-6 6h-4a6 6 0 0 1-6-6z"/>'),
    "boulangerie": _SVG.format(
        '<path d="M5 18h14a2 2 0 0 0 2-2c0-5-4-9-9-9s-9 4-9 9a2 2 0 0 0 2 2z"/>'
        '<path d="M9 10l-1.5 4M13 9.5l-1 4.5M16.5 10.5l-1 3.5"/>'),
    "froid": _SVG.format(
        '<path d="M12 2v20M4.5 6.5l15 11M19.5 6.5l-15 11M9 4l3 2 3-2'
        'M9 20l3-2 3 2"/>'),
    "autre": _SVG.format(
        '<path d="M4 9l1.5-5h13L20 9M4 9h16M4 9a2.7 2.7 0 0 0 5.3 0 '
        '2.7 2.7 0 0 0 5.4 0 2.7 2.7 0 0 0 5.3 0M5 11v10h14V11M10 21v-5h4v5"/>'),
}

#: Les catégories connues (mêmes clés que la table CIQ330).
METADATA = {
    cle: {"label": meta["libelle"]["fr"], "icon": ICONES[cle],
          "accroche": meta["accroche"]["fr"]}
    for cle, meta in ci_categories.CATEGORIES.items()
}


def _categorie_par_defaut(category, etude, note_pointe=None, langue="fr",
                          synthese=None):
    """Contenu CIQ330 recalculé sur les seules réponses (sans synthèse) ;
    la note sur la pointe passée par l'appelant (CIQ307) sert au bloc
    générique. CIQ345 — ``synthese`` (la synthèse C&I servie, dont la note
    TRILINGUE sur la pointe) et ``langue`` : le bloc générique suit la
    langue du document (français inchangé)."""
    etude = dict(etude or {})
    etude["categorie_commerciale"] = category
    if not isinstance(synthese, dict) or not synthese.get("hypotheses"):
        synthese = ({"hypotheses": [{"cle": "pointe",
                                     "textes": {"fr": note_pointe}}]}
                    if note_pointe else None)
    donnees = {"etude": etude}
    if langue and langue != "fr":
        donnees["langue_sortie"] = langue
    return ci_categories.categorie_ci(donnees, synthese)


def meta(category, categorie=None):
    """``{label, icon, accroche}`` — lus sur ``synthese_ci['categorie']``
    quand elle est servie, sinon sur la table CIQ330 (français)."""
    if isinstance(categorie, dict) and categorie.get("cle"):
        cle = categorie["cle"]
        return {"label": categorie.get("libelle") or METADATA[cle]["label"],
                "icon": ICONES.get(cle, ICONES["autre"]),
                "accroche": categorie.get("accroche")
                or METADATA[cle]["accroche"]}
    return METADATA.get((category or "").strip().lower(), METADATA["autre"])


def category_block(category, etude, C, fmt, note_pointe=None, categorie=None,
                   langue="fr", synthese=None):
    """HTML du bloc de la page 2 — RENDU de ``synthese_ci['categorie']``
    (``categorie``), ou de la table CIQ330 sur les réponses ``etude`` quand
    la synthèse n'est pas fournie. Retourne une chaîne — jamais None.

    ``note_pointe`` : la note sur la pointe (table des mentions, CIQ305)
    imprimée par le bloc générique quand la synthèse n'est pas fournie."""
    if not isinstance(categorie, dict) or not categorie.get("bloc"):
        categorie = _categorie_par_defaut(
            category, etude, note_pointe, langue,
            synthese if langue and langue != "fr" else None)
    bloc = categorie.get("bloc") or {}
    lignes = "".join(
        f'<div class="c2b-li">{ci_categories.texte_ligne(li, langue)}</div>'
        for li in bloc.get("lignes") or [] if isinstance(li, dict))
    return (f'<div class="c2b"><div class="c2b-h">{bloc.get("titre") or ""}'
            f'</div><div class="c2b-body">{lignes}</div></div>')
