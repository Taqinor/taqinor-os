"""QJR668 (décision fondateur 01/10/2026) — le bloc « Clauses particulières »
imprimé par TOUS les gabarits du devis (résidentiel, commercial, industriel,
legacy plein format et une page).

Source unique : ``data['clauses_cgv']`` posé par ``builder`` depuis le
snapshot ``Devis.clauses_appliquees`` (gelé à l'envoi, re-gelé à chaque
correction par ``domain/cycle_vie``). Le moteur ne fait que RENDRE : aucune
clause n'est choisie ni recalculée ici.

Les textes arrivent DÉJÀ échappés (``builder.echapper_textes_client`` pour
les gabarits maison, ``apply_quote_data`` pour le legacy) : rien n'est
ré-échappé. Sans clause → chaîne vide (document octet-identique).
"""

from . import i18n_labels

#: APDF9 — le titre vit dans ``i18n_labels`` (clé ``clauses_particulieres``) ;
#: ``TITRE`` en reste la forme française.
TITRE = i18n_labels.libelle("clauses_particulieres", "fr")


def bloc_clauses_html(clauses, *, couleur_titre="#0f2a44",
                      couleur_texte="#334155", taille_pt="7.5", langue=None):
    """HTML compact des clauses gelées, ou ``""`` quand il n'y en a pas.

    APDF9 — ``langue`` choisit le titre (``i18n_labels``) ; absente : le
    français d'hier, octet pour octet."""
    lignes = []
    for c in clauses or []:
        if not isinstance(c, dict):
            continue
        nom = str(c.get("nom") or "").strip()
        corps = str(c.get("corps_texte") or "").strip()
        if not nom and not corps:
            continue
        tete = f"<b>{nom}</b>" + (" &#8212; " if nom and corps else "")
        lignes.append(f'<div style="margin-top:2px;">{tete}{corps}</div>')
    if not lignes:
        return ""
    return (
        f'<div class="clauses-cgv" style="margin-top:8px;font-size:{taille_pt}pt;'
        f'line-height:1.35;color:{couleur_texte};">'
        f'<div style="font-weight:700;color:{couleur_titre};'
        'text-transform:uppercase;letter-spacing:.8px;">'
        f'{i18n_labels.libelle("clauses_particulieres", langue)}</div>'
        f'{"".join(lignes)}</div>')
