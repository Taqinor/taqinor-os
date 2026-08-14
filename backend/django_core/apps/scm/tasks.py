"""Tâches planifiées (Celery beat) de planification supply chain
(NTSCM21/NTSCM22).

Autodécouvertes par ``erp_agentique.celery`` (``autodiscover_tasks()``, comme
``apps.stock.tasks``/``apps.rh.tasks``) ; leur cadence est déclarée dans
``erp_agentique/celery.py`` (``beat_schedule``), introspectable via
``core.jobs`` (FG368, ``/api/django/core/jobs/``). Chaque tâche boucle PAR
société (jamais une company lue d'une requête) et reste best-effort : une
exception sur une société/un produit n'empêche jamais les suivants — même
patron que ``apps/stock/tasks.py`` (ZSTK1)."""
import logging

from celery import shared_task
from django.utils import timezone

logger = logging.getLogger(__name__)


@shared_task(name='scm.generer_previsions_mensuelles')
def generer_previsions_mensuelles_task(horizon_mois=None):
    """NTSCM21 — pour CHAQUE société, (re)génère les prévisions de demande
    (NTSCM2, ``services.generer_previsions``) de TOUS les produits actifs sur
    ``horizon_mois`` mois — NTSCM33 : ``None`` (défaut) retombe sur
    ``ParametresSCM.horizon_prevision_mois_defaut`` DE CHAQUE société (plus un
    seul horizon global pour toutes). Best-effort par société ET par produit
    (une erreur sur l'un n'interrompt jamais les autres, journalisée).

    Notifie (``notifications.notify_many``, réutilisé — jamais un nouveau
    canal) les rôles Administrateur/Directeur (``resolve_recipients``, repli
    historique) d'un résumé : nombre de prévisions mises à jour + nombre
    d'écarts >30% détectés vs la valeur PRÉCÉDEMMENT enregistrée pour le même
    (produit, période) — comparée AVANT écrasement par le recalcul.

    Renvoie ``[{'company_id', 'nb_maj', 'nb_ecarts'}, ...]``."""
    from authentication.models import Company
    from django.apps import apps as django_apps

    from apps.notifications.models import EventType
    from apps.notifications.services import notify_many, resolve_recipients

    from . import services
    from .models import PrevisionDemande

    Produit = django_apps.get_model('stock', 'Produit')

    resume_global = []
    for company in Company.objects.all():
        nb_maj = 0
        nb_ecarts = 0
        horizon_effectif = horizon_mois
        if horizon_effectif is None:
            from . import selectors
            horizon_effectif = selectors.parametres(company).horizon_prevision_mois_defaut
        produits = Produit.objects.filter(company=company, is_archived=False)
        for produit in produits:
            try:
                avant = dict(
                    PrevisionDemande.objects
                    .filter(company=company, produit=produit)
                    .values_list('periode', 'quantite_prevue'))
                previsions = services.generer_previsions(
                    produit, horizon_effectif, company)
            except Exception:  # noqa: BLE001 — best-effort par produit
                logger.warning(
                    'scm.generer_previsions_mensuelles: échec produit %s '
                    '(société %s)', produit.id, company.id, exc_info=True)
                continue

            nb_maj += len(previsions)
            for prevision in previsions:
                ancienne = avant.get(prevision.periode)
                if ancienne and ancienne > 0:
                    ecart_pct = (
                        abs(prevision.quantite_prevue - ancienne) / ancienne * 100)
                    if ecart_pct > 30:
                        nb_ecarts += 1

        if nb_maj:
            titre = f'{nb_maj} prévision(s) de demande mise(s) à jour'
            corps = (
                f'{nb_maj} prévisions mises à jour, {nb_ecarts} écart(s) '
                '>30% détecté(s) vs la valeur précédente.')
            try:
                notify_many(
                    resolve_recipients(company, EventType.SCM_PREVISIONS_GENEREES),
                    EventType.SCM_PREVISIONS_GENEREES, titre, body=corps,
                    company=company)
            except Exception:  # noqa: BLE001 — notification best-effort
                logger.warning(
                    'scm.generer_previsions_mensuelles: notification échouée '
                    '(société %s)', company.id, exc_info=True)

        resume_global.append({
            'company_id': company.id, 'nb_maj': nb_maj, 'nb_ecarts': nb_ecarts,
        })

    return resume_global


@shared_task(name='scm.ouvrir_cycle_sop_mensuel')
def ouvrir_cycle_sop_mensuel_task(*, today=None):
    """NTSCM22 — crée le ``CyclePlanificationSOP`` du mois SUIVANT (statut
    brouillon) pour CHAQUE société ayant activé l'opt-in
    (``ParametresSCM.sop_actif`` — défaut DÉSACTIVÉ, voir
    ``models.ParametresSCM`` pour l'adaptation de périmètre NTSCM22 :
    n'affecte AUCUNE société tant que non activée explicitement).

    Idempotent : ``CyclePlanificationSOP`` porte une contrainte unique
    ``(company, periode)`` — un doublon (deux déclenchements le même mois)
    est absorbé proprement (vérifié AVANT insertion, capturé en secours si
    la course gagne quand même). Notifie l'animateur désigné
    (``ParametresSCM.animateur_sop``) quand renseigné, best-effort.

    Renvoie la liste des id de cycles créés."""
    from django.core.exceptions import ValidationError
    from django.db import IntegrityError

    from apps.notifications.models import EventType
    from apps.notifications.services import notify

    from .models import CyclePlanificationSOP, ParametresSCM

    today = today or timezone.localdate()
    idx_suivant = today.year * 12 + (today.month - 1) + 1
    annee, mois0 = divmod(idx_suivant, 12)
    periode_cible = f'{annee:04d}-{mois0 + 1:02d}'

    crees = []
    parametres_actifs = (
        ParametresSCM.objects.filter(sop_actif=True)
        .select_related('company', 'animateur_sop'))
    for parametres in parametres_actifs:
        company = parametres.company
        if CyclePlanificationSOP.objects.filter(
                company=company, periode=periode_cible).exists():
            continue
        try:
            cycle = CyclePlanificationSOP.objects.create(
                company=company, periode=periode_cible,
                anime_par=parametres.animateur_sop)
        except (IntegrityError, ValidationError):  # pragma: no cover - course concurrente
            continue

        crees.append(cycle)
        if parametres.animateur_sop_id:
            try:
                notify(
                    parametres.animateur_sop, EventType.SCM_CYCLE_SOP_OUVERT,
                    f'Cycle S&OP {periode_cible} ouvert',
                    body=(
                        f'Le cycle S&OP {periode_cible} a été créé '
                        'automatiquement (brouillon) — à animer.'),
                    company=company)
            except Exception:  # noqa: BLE001 — notification best-effort
                logger.warning(
                    'scm.ouvrir_cycle_sop_mensuel: notification échouée '
                    '(société %s)', company.id, exc_info=True)

    return [cycle.id for cycle in crees]
