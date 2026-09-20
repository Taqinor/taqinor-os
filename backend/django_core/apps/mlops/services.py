"""Services (ÉCRITURE) du module « mlops » (Groupe NTAI, P3)."""
from __future__ import annotations

from django.db import transaction

# Borne défensive sur le nombre de leads matérialisés par appel (une société
# avec un très gros historique ne bloque jamais indéfiniment le job Beat).
LIMITE_FEATURES = 5000


def activer_version(company, modele_id):
    """NTAI27 — Active UNE version d'un scorer pour une société ; désactive
    toutes les AUTRES versions du MÊME scorer (au plus une active à la fois —
    la contrainte base ``uniq_mlops_modele_actif`` le garantit, ceci en fait
    une opération atomique et sans erreur d'intégrité).

    Renvoie l'instance activée, ou ``None`` si ``modele_id`` n'appartient pas
    à ``company`` (jamais une activation cross-tenant)."""
    from .models import ModeleML

    with transaction.atomic():
        cible = (ModeleML.objects.select_for_update()
                 .filter(company=company, pk=modele_id).first())
        if cible is None:
            return None
        (ModeleML.objects.filter(company=company, nom=cible.nom, actif=True)
         .exclude(pk=cible.pk).update(actif=False))
        if not cible.actif:
            cible.actif = True
            cible.save(update_fields=['actif', 'updated_at'])
    return cible


def _anciennete_jours_approx(mois_creation, *, aujourdhui=None):
    """NTAI30 — Ancienneté APPROXIMATIVE d'un lead, dérivée de son MOIS de
    création (seule granularité temporelle exposée par le dataset BI
    ``crm_leads``) — jamais un jour exact inventé. ``None`` sans
    ``mois_creation``, jamais négatif (borné à 0)."""
    if mois_creation is None:
        return None
    from django.utils import timezone

    today = aujourdhui or timezone.localdate()
    mois_date = (mois_creation.date()
                 if hasattr(mois_creation, 'date') else mois_creation)
    return max((today - mois_date).days, 0)


def recompute_features(company, *, user=None, limite=LIMITE_FEATURES):
    """NTAI30 — Matérialise le ``FeatureVector`` de chaque LEAD de la société,
    depuis le dataset BI ``crm_leads`` (``core.data_explorer``, déjà scopé
    société ; jamais un import direct de ``crm.models``) : canal, priorité,
    perdu, signé, et une ancienneté APPROXIMATIVE (mois de création → jours).

    ``nb_relances``/``retard_moyen`` (mentionnés par la tâche NTAI30) NE SONT
    PAS matérialisés ici : aucun sélecteur en masse (par lead, à faible coût)
    n'est accessible depuis ce module aujourd'hui — à ajouter dans un passage
    ultérieur plutôt que d'inventer une valeur.

    Best-effort : conçu pour un déclenchement Celery (voir ``tasks.py``),
    idempotent (upsert par (société, lead)). Renvoie le nombre de vecteurs
    créés/mis à jour.
    """
    from core import data_explorer

    from .models import FeatureVector

    try:
        lignes = data_explorer.run_query(
            'crm_leads', company, user,
            {'select': ['id', 'canal', 'priorite', 'perdu_bool',
                        'signe_num', 'mois_creation'],
             'limit': limite})
    except data_explorer.DatasetInconnu:
        return 0

    compte = 0
    for ligne in lignes:
        lead_id = ligne.get('id')
        if lead_id is None:
            continue
        features = {
            'canal': ligne.get('canal'),
            'priorite': ligne.get('priorite'),
            'perdu': bool(ligne.get('perdu_bool')),
            'signe': bool(ligne.get('signe_num')),
            'anciennete_jours_approx': _anciennete_jours_approx(
                ligne.get('mois_creation')),
        }
        FeatureVector.objects.update_or_create(
            company=company, content_type='crm.lead', object_id=lead_id,
            defaults={'features_json': features})
        compte += 1
    return compte
