"""Lectures pures du moteur de territoires (NTCRM1). Aucune mutation ici."""
from core.rules import evaluate_condition_group

from .models import TerritoireRegle


def lead_criteres(lead_attrs):
    """Contexte plat de matching depuis des attributs de lead bruts.

    ``lead_attrs`` peut être un ``dict`` (chemin PRÉ-création — webhook/vue,
    le Lead n'existe pas encore) ou tout objet portant ces attributs (ex. une
    instance ``Lead`` déjà créée, en duck-typing — jamais d'import de
    ``apps.crm.models`` ici)."""
    def get(key):
        if isinstance(lead_attrs, dict):
            return lead_attrs.get(key)
        return getattr(lead_attrs, key, None)

    return {
        'ville': get('ville'),
        'type_installation': get('type_installation'),
        'montant_estime': get('montant_estime'),
        'canal': get('canal'),
    }


def match_territoire(company, criteres):
    """Premier territoire ACTIF dont une règle ACTIVE matche ``criteres``,
    parmi TOUTES les règles de la société triées par ordre de priorité
    croissant. Renvoie ``(territoire, regle)`` ou ``(None, None)`` si aucun
    match — l'appelant replie alors sur le round-robin XSAL11 existant."""
    criteres = criteres or {}
    regles = (
        TerritoireRegle.objects.filter(
            territoire__company=company, territoire__actif=True, actif=True,
        )
        .select_related('territoire')
        .order_by('ordre', 'id')
    )
    for regle in regles:
        if evaluate_condition_group(regle.condition, criteres):
            return regle.territoire, regle
    return None, None


def rapport_couverture(company, jours=30):
    """NTCRM25 — Leads récents de ``company`` qui n'ont matché AUCUNE règle de
    territoire ACTIVE (trou de couverture géo/segment), avec un compteur par
    région (``ville``) et par segment (``type_installation``). Lecture pure,
    aucune mutation (jamais de rotation déclenchée par un rapport)."""
    from apps.crm.selectors import leads_recents_pour_couverture

    non_couverts = []
    par_region = {}
    par_segment = {}
    for lead in leads_recents_pour_couverture(company, jours=jours):
        criteres = {
            'ville': lead['ville'],
            'type_installation': lead['type_installation'],
            'montant_estime': lead['montant_estime'],
            'canal': lead['canal'],
        }
        territoire, _regle = match_territoire(company, criteres)
        if territoire is not None:
            continue
        non_couverts.append({
            'lead_id': lead['id'],
            'nom': lead['nom'],
            'ville': lead['ville'],
            'type_installation': lead['type_installation'],
        })
        region_key = lead['ville'] or 'Ville inconnue'
        par_region[region_key] = par_region.get(region_key, 0) + 1
        segment_key = lead['type_installation'] or 'Segment inconnu'
        par_segment[segment_key] = par_segment.get(segment_key, 0) + 1
    return {
        'total_non_couverts': len(non_couverts),
        'leads': non_couverts,
        'par_region': par_region,
        'par_segment': par_segment,
    }


def previsualiser_territoire(territoire, criteres):
    """Aperçu SANS MUTATION : ``territoire`` matche-t-il ``criteres`` (une de
    ses règles actives) et, si oui, quel membre SERAIT choisi au prochain tour
    de rotation (le moins assigné, quota respecté au mieux) — sans rien
    persister. Sert à ``territoires/{id}/resoudre/`` (NTCRM1) et à l'aperçu de
    simulation de l'écran Paramètres (NTCRM3)."""
    regles = list(territoire.regles.filter(actif=True).order_by('ordre', 'id'))
    matched = any(evaluate_condition_group(r.condition, criteres) for r in regles)
    if not matched:
        return False, None
    membres = list(territoire.membres.filter(actif=True).order_by('id'))
    if not membres:
        return True, None
    membres.sort(key=lambda m: (m.nb_assignations, m.id))
    return True, membres[0]
