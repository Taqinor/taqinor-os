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

#: Pictogramme par catégorie (emoji rendu par WeasyPrint via Noto).
ICONES = {
    "hotel": "🏨", "restaurant": "🍽️", "commerce": "🛒", "bureau": "🏢",
    "sante": "🏥", "ecole": "🎓", "hammam": "🧖", "boulangerie": "🥖",
    "froid": "❄️", "autre": "🏪",
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
