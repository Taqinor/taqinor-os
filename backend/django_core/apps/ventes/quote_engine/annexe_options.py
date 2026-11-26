"""D-ACAL-166 (fondateur, 26/11/2026) — l'annexe technique PV46 d'un devis à
deux options : UNE PAGE PAR OPTION.

Le builder (``artefacts_rendu._annexes_par_option``) ne sert ``annexes_options``
— ``[{option, electrical_design, sld_svg}]``, une entrée par option dont la
conception est RANGÉE (D-ACAL-158, jamais un calcul à la lecture, D-ACAL-140) —
que pour un devis qui porte les deux conceptions rangées et dont l'annexe est
demandée. Sans cette clé (tout devis envoyé avant, tout devis à une option),
l'annexe est la page unique d'hier, octet pour octet : ``page_annexe_technique``
est appelée exactement comme avant. Chaque page imprime le schéma, la
nomenclature et les repères « chaînes / régime » de SON option, et son titre dit
l'option (« Sans batterie », ou le libellé de l'option 2 servi par le builder,
traduits comme partout dans le PDF). Le moteur ne fait que RENDRE (règle #4) :
aucun montant n'entre ici.
"""


def nombre_pages_annexe(options) -> int:
    """Pages de l'annexe quand elle est rendue : une par option rangée sur un
    devis à deux options, sinon la page unique d'aujourd'hui."""
    options = list(options or [])
    return len(options) if len(options) >= 2 else 1


def _titre(g, option) -> str:
    """« — <nom de l'option> » dans la langue du document."""
    libelle = "Sans batterie" if option == "sans_batterie" else g.LIBELLE_AVEC
    return " — " + g._esc(g.i18n_labels.nom_option(libelle, g.LANGUE_SORTIE))


def pages_annexe_technique(g) -> str:
    """Le HTML de l'annexe du document chargé dans le moteur ``g`` (le module
    ``generate_devis_premium``, lu à l'appel)."""
    options = list(g.ANNEXES_OPTIONS or [])
    if nombre_pages_annexe(options) == 1:
        return g.page_annexe_technique()
    return "".join(
        g.page_annexe_technique(o.get("electrical_design") or {}, o.get("sld_svg") or "",
                                _titre(g, o.get("option")))
        for o in options)
