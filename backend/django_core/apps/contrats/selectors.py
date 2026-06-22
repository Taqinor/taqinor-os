"""Sélecteurs LECTURE SEULE de la Gestion des contrats.

Point d'entrée cross-app : enrichissent les liens d'un contrat
(``ContratLien``) en appelant le sélecteur de l'app CIBLE quand elle en expose
un — jamais en important ses ``models``/``views`` (voir CLAUDE.md, frontière
cross-app). Tous les imports cross-app sont fonction-locaux pour éviter les
cycles. Quand une app cible n'a pas de sélecteur exploitable, on DÉGRADE
proprement : on renvoie le ``libelle`` mis en cache et les ids stockés, sans
rien importer.
"""
from .models import ContratLien


def liens_for_contrat(contrat):
    """Liens d'un contrat (QuerySet scopé société, ordonné par id).

    Lecture seule. La société est portée par le contrat : on filtre aussi sur
    ``contrat.company`` par sécurité même si le FK ``contrat`` la garantit déjà.
    """
    return ContratLien.objects.filter(
        contrat=contrat, company=contrat.company).order_by('id')


def _label_devis(company, cible_id):
    """Libellé enrichi d'un devis via ``ventes.selectors`` (ou None).

    Import fonction-local : on ne touche JAMAIS ``ventes.models`` directement.
    Renvoie le ``label`` de la fiche-carte du devis, ou None si l'app ne peut
    pas l'enrichir (devis absent / hors société / sélecteur indisponible).
    """
    try:
        from apps.ventes import selectors as ventes_selectors
    except Exception:  # pragma: no cover - défensif (app absente)
        return None
    try:
        card = ventes_selectors.devis_card(cible_id, company)
    except Exception:  # pragma: no cover - défensif (cible introuvable)
        return None
    if not card:
        return None
    return card.get('label') or None


def _label_lead(company, cible_id):
    """Libellé enrichi d'un lead via ``crm.selectors`` (ou None).

    Import fonction-local : on ne touche JAMAIS ``crm.models`` directement.
    """
    try:
        from apps.crm import selectors as crm_selectors
    except Exception:  # pragma: no cover - défensif (app absente)
        return None
    try:
        card = crm_selectors.lead_card(cible_id, company)
    except Exception:  # pragma: no cover - défensif (cible introuvable)
        return None
    if not card:
        return None
    return card.get('label') or None


def _label_installation(company, cible_id):
    """Libellé enrichi d'un chantier via ``installations.selectors`` (ou None).

    Import fonction-local : on ne touche JAMAIS ``installations.models``
    directement.
    """
    try:
        from apps.installations import selectors as inst_selectors
    except Exception:  # pragma: no cover - défensif (app absente)
        return None
    try:
        card = inst_selectors.chantier_card(cible_id, company)
    except Exception:  # pragma: no cover - défensif (cible introuvable)
        return None
    if not card:
        return None
    return card.get('label') or None


# Enrichisseurs par type de cible. Une entrée n'existe QUE si l'app cible expose
# un sélecteur de lecture exploitable : `maintenance` → sav n'a pas de
# selectors.py aujourd'hui → ce type dégrade au libellé stocké, sans aucun
# import.
_ENRICHERS = {
    ContratLien.TypeCible.DEVIS: _label_devis,
    ContratLien.TypeCible.LEAD: _label_lead,
    ContratLien.TypeCible.INSTALLATION: _label_installation,
}


def liens_enrichis(contrat):
    """Liste de dicts {id, type_cible, cible_id, libelle, source} d'un contrat.

    Pour chaque lien : si l'app cible expose un enrichisseur, on s'en sert pour
    récupérer un libellé frais (``source='live'``) ; sinon — ou si
    l'enrichissement renvoie vide — on retombe sur le ``libelle`` stocké
    (``source='stored'``). Aucune exception ne remonte : un enrichisseur qui
    échoue dégrade au libellé stocké.
    """
    out = []
    for lien in liens_for_contrat(contrat):
        libelle = lien.libelle
        source = 'stored'
        enricher = _ENRICHERS.get(lien.type_cible)
        if enricher is not None:
            try:
                fresh = enricher(lien.company, lien.cible_id)
            except Exception:  # pragma: no cover - défensif
                fresh = None
            if fresh:
                libelle = fresh
                source = 'live'
        out.append({
            'id': lien.id,
            'type_cible': lien.type_cible,
            'cible_id': lien.cible_id,
            'libelle': libelle,
            'source': source,
        })
    return out
