"""NTUX30 — digest hebdomadaire des favoris pointant vers une cible
définitivement supprimée (ex. purgée de la corbeille transverse, NTUX29).

Autodécouvert par `erp_agentique.celery` (`autodiscover_tasks()`), comme
`apps.trash.tasks`. Planifié chaque lundi 07h00 (Africa/Casablanca) dans
`erp_agentique/celery.py` `beat_schedule`. NE SUPPRIME JAMAIS rien : un favori
mort reste visible (l'écran l'affiche déjà en « favori mort » — cf.
`FavoriUtilisateurSerializer.get_libelle`), cette tâche se contente de
notifier son propriétaire pour qu'il fasse le ménage lui-même.

Portée volontairement LIMITÉE à `FavoriUtilisateur` (cible générique par
`content_type`+`object_id`, donc résoluble). `SavedView` (NTUX1) n'a PAS de
cible générique — juste un `ecran` (identifiant libre côté frontend, ex.
'crm.leads') — et aucun registre serveur des écrans valides n'existe encore
pour détecter une route retirée du router ; cette moitié reste hors périmètre
tant qu'un tel registre n'existe pas (documenté ici plutôt qu'un faux
positif/négatif inventé)."""
import logging

from celery import shared_task

logger = logging.getLogger(__name__)


def _favoris_obsoletes_par_proprietaire():
    """{(company_id, owner_id): nombre} de favoris dont la cible n'existe plus.

    Résout la cible par `content_type.model_class()` — jamais un import direct
    d'une app métier (frontière inter-apps, CLAUDE.md)."""
    from .models import FavoriUtilisateur

    par_owner = {}
    favoris = (FavoriUtilisateur.objects
               .select_related('content_type')
               .order_by('content_type_id', 'object_id'))
    # Regroupe par (content_type, {ids existants}) pour n'interroger chaque
    # modèle cible qu'UNE fois par lot plutôt qu'une requête par favori.
    par_content_type = {}
    for favori in favoris:
        par_content_type.setdefault(favori.content_type_id, []).append(favori)

    for content_type_id, lot in par_content_type.items():
        content_type = lot[0].content_type
        modele = content_type.model_class() if content_type_id else None
        if modele is None:
            continue
        manager = getattr(modele, 'all_objects', modele._default_manager)
        ids_demandes = {f.object_id for f in lot}
        ids_existants = set(
            manager.filter(pk__in=ids_demandes).values_list('pk', flat=True))
        for favori in lot:
            if favori.object_id not in ids_existants:
                cle = (favori.company_id, favori.owner_id)
                par_owner[cle] = par_owner.get(cle, 0) + 1
    return par_owner


@shared_task(name='uxviews.digest_favoris_obsoletes_hebdo')
def digest_favoris_obsoletes_hebdo():
    """NTUX30 — une notification par (société, propriétaire) ayant au moins un
    favori mort, jamais une par favori (pas de spam). Best-effort : une
    notification échouée pour un propriétaire ne bloque jamais les suivants."""
    from authentication.models import Company
    from django.contrib.auth import get_user_model

    from apps.notifications.models import EventType
    from apps.notifications.services import notify

    User = get_user_model()
    par_owner = _favoris_obsoletes_par_proprietaire()
    total_notifies = 0
    for (company_id, owner_id), nombre in sorted(par_owner.items()):
        try:
            company = Company.objects.filter(pk=company_id).first()
            owner = User.objects.filter(pk=owner_id).first()
            if company is None or owner is None:
                continue
            pluriel = 's' if nombre > 1 else ''
            notify(
                owner, EventType.UXVIEWS_FAVORIS_OBSOLETES,
                title=f'{nombre} favori{pluriel} pointe{"nt" if nombre > 1 else ""} vers des éléments supprimés',
                body=(
                    f'{nombre} de vos favoris pointe{"nt" if nombre > 1 else ""} '
                    'vers des éléments supprimés. Vous pouvez les retirer depuis '
                    'votre liste de favoris.'
                ),
                company=company,
            )
            total_notifies += 1
        except Exception:  # noqa: BLE001 — best-effort, ne casse jamais le beat
            logger.exception(
                'uxviews.digest_favoris_obsoletes_hebdo: échec notification '
                'société=%s owner=%s', company_id, owner_id)
    logger.info(
        'uxviews.digest_favoris_obsoletes_hebdo: %d propriétaire(s) notifié(s) '
        'sur %d avec des favoris obsolètes.', total_notifies, len(par_owner))
    return {'proprietaires_notifies': total_notifies}
