"""AGR305 — garanties par composant d'un devis de POMPAGE, dérivées des
lignes du devis (pompe, variateur, panneaux) — jamais les garanties
résidentielles.

POURQUOI. ``generate_devis_premium._garanties_du_devis`` ne connaît que
l'onduleur, les panneaux et la batterie, et ``residential/theme.warranties_for``
retombe ENTIÈREMENT sur la constante résidentielle ``theme.WARRANTIES``
(onduleur 10 ans, installation 2 ans…) faute de lignes. Un agriculteur ne doit
lire ni la garantie d'un onduleur qu'il n'achète pas, ni une durée qu'aucune
fiche ne porte.

LA RÈGLE.
  * La durée vient UNIQUEMENT des champs STRUCTURÉS de la fiche de la ligne
    (``garantie_mois`` / ``garantie_production_mois``, posés par
    ``builder._line_to_item``). Le texte libre ``garantie`` (« 24 »,
    « constructeur 2 ans ») n'est JAMAIS interprété en mois ou en ans, et
    aucune durée de vie ne remplace une garantie.
  * Le composant est identifié par le ``role_pompage`` de l'item (contrat stock
    ``produit_pompage.json``, AGR7, copié par le builder — AGR304). Repli : les
    classifieurs PARTAGÉS existants seulement — ``core.product_roles``
    (``role_devis == 'panneau'``) et ``solar_design.is_panel`` pour les
    panneaux. Il n'existe aucun classifieur partagé de pompe ni de variateur :
    sans ``role_pompage``, ces deux composants ne sont pas devinés (jamais un
    nouveau mot-clé ad hoc).
  * Un composant présent SANS durée structurée est OMIS, avec le motif
    « garantie non renseignée ». La garantie de pose / main-d'œuvre est OMISE
    tant que le fondateur ne l'a pas décidée pour le pompage (tâche manuelle
    AGRM22).
  * Une composition vide rend une liste vide — jamais le repli résidentiel.

Fonction PURE : aucun accès base, aucun réseau.
"""
from __future__ import annotations

#: Ordre d'affichage et libellés client (le nombre est ajouté à la fin).
COMPOSANTS = (
    ("pompe", "garantie_mois", "Garantie constructeur de la pompe"),
    ("variateur", "garantie_mois", "Garantie constructeur du variateur"),
    ("panneaux", "garantie_mois", "Garantie produit des panneaux"),
    ("performance_panneaux", "garantie_production_mois",
     "Garantie de production des panneaux"),
)

#: ``role_pompage`` (contrat AGR7) → composant de garantie.
ROLE_VERS_COMPOSANT = {
    "pompe": "pompe",
    "variateur_pompage": "variateur",
}

MOTIF_NON_RENSEIGNEE = "garantie non renseignée"
MOTIF_POSE_NON_DECIDEE = (
    "garantie de pose du pompage non décidée par le fondateur (AGRM22) : omise")


def _mois(v):
    """Durée structurée en mois (entier > 0), sinon None — jamais un texte lu."""
    if v is None or isinstance(v, bool) or isinstance(v, str):
        return None
    try:
        n = int(v)
    except (TypeError, ValueError):
        return None
    return n if n > 0 and n == v else None


def _duree_texte(mois):
    if mois % 12 == 0:
        ans = mois // 12
        return f"{ans} an" if ans == 1 else f"{ans} ans"
    return f"{mois} mois"


def _est_panneau(it):
    if it.get("role_devis") == "panneau":
        return True
    try:
        from apps.ventes.solar_classification import is_panel
    except Exception:  # noqa: BLE001 — jamais casser un rendu
        return False
    return is_panel(it.get("designation", "") or "",
                    it.get("_produit_nom", "") or "")


def _composant_de(it):
    role = it.get("role_pompage")
    if role in ROLE_VERS_COMPOSANT:
        return ROLE_VERS_COMPOSANT[role]
    if role in (None, "") and _est_panneau(it):
        return "panneaux"
    return None


def garanties_pompage_et_omissions(items):
    """``(garanties, omissions)`` — ``garanties`` : liste de
    ``{composant, mois, libelle}`` ; ``omissions`` : ``{bloc, motif}`` des
    composants présents sans durée structurée (et de la pose)."""
    lignes = [it for it in (items or []) if isinstance(it, dict)]
    if not lignes:
        return [], []
    par_composant = {}
    for it in lignes:
        composant = _composant_de(it)
        if composant is None:
            continue
        par_composant.setdefault(composant, []).append(it)
        if composant == "panneaux":
            par_composant.setdefault("performance_panneaux", []).append(it)

    garanties, omissions = [], []
    for composant, champ, libelle in COMPOSANTS:
        porteurs = par_composant.get(composant)
        if not porteurs:
            continue
        mois = next((m for m in (_mois(it.get(champ)) for it in porteurs)
                     if m is not None), None)
        if mois is None:
            # La performance des panneaux n'est pas une pièce : son absence ne
            # mérite pas de motif quand la garantie produit est déjà omise.
            if composant != "performance_panneaux":
                omissions.append({"bloc": f"garanties.{composant}",
                                  "motif": MOTIF_NON_RENSEIGNEE})
            continue
        garanties.append({"composant": composant, "mois": mois,
                          "libelle": f"{libelle} : {_duree_texte(mois)}"})
    omissions.append({"bloc": "garanties.installation",
                      "motif": MOTIF_POSE_NON_DECIDEE})
    return garanties, omissions


def garanties_pompage(items):
    """La liste des garanties par composant (voir le module)."""
    return garanties_pompage_et_omissions(items)[0]
