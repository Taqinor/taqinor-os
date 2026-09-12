"""ZSTK1 — Action planifiée : recompute réappro + alertes de rupture (cron).

Les sélecteurs de réappro existent (`produits_a_reapprovisionner` FG54,
`previsions_reappro` FG65, réappro multi-dépôts FG326) mais AUCUN cron ne les
faisait tourner — Odoo lance une action nocturne « reordering rules run ».
Aujourd'hui personne n'est notifié tant qu'un humain n'ouvre pas l'écran.

Autodécouvert par ``erp_agentique.celery`` (``autodiscover_tasks()``), comme
``apps.rh.tasks``/``apps.installations.tasks``. Boucle PAR société ACTIVE, au
sens de ``authentication.selectors.active_companies()`` (SCA19/AUD415) : un
tenant suspendu ou en fermeture n'est jamais balayé — la docstring l'affirmait
avant AUD415 alors que le code itérait ``Company.objects.all()``.
Jamais une company lue d'une requête ; une exception sur l'une n'empêche
jamais les suivantes (best-effort, journalisé). Aucun BCF n'est créé
automatiquement ici — SUGGESTION seulement (réutilise `produits_a_reapprovisionner`,
jamais de logique dupliquée).

Idempotence (« une seule notification par jour par société ») : avant
d'émettre, on vérifie qu'aucune ``Notification`` du même ``event_type``
portant le même ``link`` stable (encodant la société) n'a déjà été créée
AUJOURD'HUI (Africa/Casablanca).
"""
import logging

from celery import shared_task
from django.db.models import F
from django.utils import timezone

logger = logging.getLogger(__name__)


def _deja_notifie_aujourdhui(event_type, link):
    """Vrai si une notification portant CE lien a déjà été créée aujourd'hui
    (Africa/Casablanca) — quel que soit le destinataire (idempotence PAR
    société, pas par destinataire)."""
    from apps.notifications.models import Notification
    today = timezone.localdate()
    try:
        return Notification.objects.filter(
            event_type=event_type, link=link,
            created_at__date=today).exists()
    except Exception:  # pragma: no cover - défensif
        return False


def _recipients_reappro(company):
    """Responsables/admins actifs de la société (destinataires de l'alerte).
    À défaut (aucun rôle taggé), tous les utilisateurs actifs."""
    from django.contrib.auth import get_user_model
    User = get_user_model()
    qs = User.objects.filter(
        company=company, is_active=True,
        role_legacy__in=['responsable', 'admin'])
    if qs.exists():
        return list(qs)
    return list(User.objects.filter(company=company, is_active=True))


@shared_task(name='stock.recompute_reordering')
def recompute_reordering_task():
    """ZSTK1 — pour CHAQUE société, calcule les produits sous seuil effectif
    (réutilise `apps.stock.selectors.a_reapprovisionner`/
    `apps.stock.services.produits_a_reapprovisionner` — jamais de logique
    dupliquée) et notifie best-effort (« N références à réapprovisionner »).
    Idempotent : une seule notification par jour par société. Renvoie un dict
    {company_id: nb_produits_notifies} (0 = aucun produit sous seuil, ou déjà
    notifié aujourd'hui)."""
    from authentication.selectors import active_companies
    from apps.stock.services import produits_a_reapprovisionner
    from apps.notifications.services import notify_many
    from apps.notifications.models import EventType

    today = timezone.localdate()
    result = {}
    for company in active_companies():  # AUD415/SCA19 — pas les suspendus
        try:
            besoins = produits_a_reapprovisionner(company)
        except Exception:  # noqa: BLE001 — une société en échec n'arrête pas
            logger.warning(
                'stock.recompute_reordering: échec calcul société %s',
                company.id, exc_info=True)
            continue
        if not besoins:
            result[company.id] = 0
            continue
        link = f'stock-reappro-{company.id}-{today.isoformat()}'
        if _deja_notifie_aujourdhui(EventType.STOCK_LOW, link):
            result[company.id] = 0
            continue
        recipients = _recipients_reappro(company)
        noms = ', '.join(b['nom'] for b in besoins[:10])
        suffixe = '…' if len(besoins) > 10 else ''
        try:
            notify_many(
                recipients, EventType.STOCK_LOW,
                title=f'{len(besoins)} référence(s) à réapprovisionner',
                body=f'Sous le seuil effectif : {noms}{suffixe}.',
                link=link, company=company)
            result[company.id] = len(besoins)
        except Exception:  # noqa: BLE001 — best-effort, jamais bloquant
            logger.warning(
                'stock.recompute_reordering: notification échouée société %s',
                company.id, exc_info=True)
            result[company.id] = 0
    return result


@shared_task(name='stock.relancer_bcf_en_retard')
def relancer_bcf_en_retard_task():
    """ZPUR7 — pour CHAQUE société avec `AchatsParametres.relance_bcf_actif`
    (OFF par défaut = no-op), PROPOSE un brouillon de relance pré-rempli
    (réutilise l'infra WhatsApp/email QS3 — jamais un envoi automatique) pour
    chaque BCF ENVOYE en retard (réutilise `bcf_en_retard_list` XPUR7 — jamais
    de logique dupliquée) et incrémente `nb_relances` sur le BCF.

    NE RE-NOTIFIE JAMAIS l'alerte buyer de XPUR7 (`BCF_LATE`) : émet un
    événement DISTINCT (`BCF_RELANCE_PROPOSEE`). Idempotent : au plus une
    proposition par jour par BCF (le lien encode le BCF + la date). Best-
    effort : une société/un BCF en échec n'arrête jamais les suivants.
    Renvoie {company_id: nb_bcf_relances_proposees}."""
    from authentication.selectors import active_companies
    from .models import AchatsParametres
    from .services import bcf_en_retard_list
    from apps.ventes.services import bcf_share_url

    today = timezone.localdate()
    result = {}
    for company in active_companies():  # AUD415/SCA19 — pas les suspendus
        params = AchatsParametres.objects.filter(
            company=company, relance_bcf_actif=True).first()
        if params is None:
            result[company.id] = 0
            continue
        try:
            en_retard = bcf_en_retard_list(company)
        except Exception:  # noqa: BLE001 — défensif, société suivante
            logger.warning(
                'stock.relancer_bcf_en_retard: échec calcul société %s',
                company.id, exc_info=True)
            continue
        count = 0
        for bc in en_retard:
            link = f'stock-relance-bcf-{bc.id}-{today.isoformat()}'
            if _deja_notifie_aujourdhui('bcf_relance_proposee', link):
                continue
            try:
                from apps.notifications.services import notify_many
                from apps.notifications.models import EventType
                from django.contrib.auth import get_user_model
                User = get_user_model()
                recipients = list(User.objects.filter(
                    company=company, is_active=True,
                    role_legacy__in=['responsable', 'admin']))
                fournisseur_nom = (
                    bc.fournisseur.nom if bc.fournisseur_id else '')
                url, _token = bcf_share_url(bc)
                message = (
                    f'Bonjour {fournisseur_nom},\n\n'
                    f'Relance concernant notre bon de commande '
                    f'{bc.reference}, toujours en attente de livraison. '
                    f'Vous pouvez le consulter ici : {url}\n\n'
                    f'Merci de nous indiquer une date de livraison.')
                notify_many(
                    recipients, EventType.BCF_RELANCE_PROPOSEE,
                    title=f'Brouillon de relance proposé ({bc.reference})',
                    body=message, link=link, company=company)
                # AUD829 — F() atomic increment: a bare
                # `bc.nb_relances = (... or 0) + 1` then save() loses a
                # concurrent relance under two racing runs on the same BCF
                # (cross-app model — type(bc) avoids importing
                # apps.achats.models here, per the services.py boundary).
                type(bc).objects.filter(pk=bc.pk).update(
                    nb_relances=F('nb_relances') + 1)
                count += 1
            except Exception:  # noqa: BLE001 — best-effort, jamais bloquant
                logger.warning(
                    'stock.relancer_bcf_en_retard: échec pour BCF %s',
                    bc.pk, exc_info=True)
        result[company.id] = count
    return result


def _deja_notifie_aujourdhui_societe(event_type, company):
    """Vrai si une notification de CE type a déjà été créée AUJOURD'HUI pour
    CETTE société — utilisé quand la fonction notifiée (best-effort,
    existante, testée ailleurs) ne pose pas de ``link`` par notification
    (contrairement à `_deja_notifie_aujourdhui`, clé par lien stable)."""
    from apps.notifications.models import Notification
    today = timezone.localdate()
    try:
        return Notification.objects.filter(
            event_type=event_type, company=company,
            created_at__date=today).exists()
    except Exception:  # pragma: no cover - défensif
        return False


@shared_task(name='stock.notifier_documents_conformite_expirants')
def notifier_documents_conformite_expirants_task():
    """XPUR1 (AUDV04/DRAFT165-115) — pour CHAQUE société active, notifie les
    responsables/admins des documents de conformité fournisseur expirant
    sous 30 jours (réutilise `services.notify_expiring_conformite_documents`
    — jamais de logique dupliquée). ``notify_expiring_conformite_documents``
    existait déjà, testée, mais SANS AUCUN cron : cette tâche était le trou
    (le paramètre société `bloquer_paiement_conformite_expiree` bloque un
    paiement, mais rien n'alertait EN AMONT de l'échéance). Idempotent : au
    plus une notification-lot par jour par société. Renvoie
    {company_id: nb_documents_notifies}."""
    from authentication.selectors import active_companies
    from apps.notifications.models import EventType
    from .services import notify_expiring_conformite_documents

    result = {}
    for company in active_companies():  # AUD415/SCA19 — pas les suspendus
        if _deja_notifie_aujourdhui_societe(
                EventType.SUPPLIER_DOC_EXPIRING, company):
            result[company.id] = 0
            continue
        try:
            result[company.id] = notify_expiring_conformite_documents(
                company, jours=30)
        except Exception:  # noqa: BLE001 — une société en échec n'arrête
            logger.warning(
                'stock.notifier_documents_conformite_expirants: échec '
                'société %s', company.id, exc_info=True)
            result[company.id] = 0
    return result


@shared_task(name='stock.notifier_documents_fournisseur_expirants')
def notifier_documents_fournisseur_expirants_task():
    """NTP2P20 — pour CHAQUE société active, notifie les responsables/admins
    des pièces d'onboarding fournisseur (NTP2P7, ``DocumentFournisseur``)
    expirant sous 30 jours (réutilise
    ``services.notify_expiring_documents_fournisseur`` — jamais de logique
    dupliquée). Distinct de ``stock.notifier_documents_conformite_expirants``
    (XPUR1, ``DocumentConformiteFournisseur``, registre sans fichier).

    Idempotence PAR LIEN (``_deja_notifie_aujourdhui``, pas
    ``_deja_notifie_aujourdhui_societe``) : les deux sweeps partagent le même
    ``EventType.SUPPLIER_DOC_EXPIRING`` (sémantique identique) mais un lien
    DISTINCT — sinon celui qui tourne en premier « consommerait » le
    guard-par-société (sans lien) de l'autre pour le reste de la journée, un
    faux négatif qui ferait manquer des expirations sur une couche différente
    de documents. Renvoie {company_id: nb_documents_notifies}."""
    from authentication.selectors import active_companies
    from apps.notifications.models import EventType
    from .services import notify_expiring_documents_fournisseur

    today = timezone.localdate()
    result = {}
    for company in active_companies():  # AUD415/SCA19 — pas les suspendus
        link = (f'stock-doc-fournisseur-expirant-{company.id}-'
                f'{today.isoformat()}')
        if _deja_notifie_aujourdhui(EventType.SUPPLIER_DOC_EXPIRING, link):
            result[company.id] = 0
            continue
        try:
            result[company.id] = notify_expiring_documents_fournisseur(
                company, jours=30, link=link)
        except Exception:  # noqa: BLE001 — une société en échec n'arrête
            logger.warning(
                'stock.notifier_documents_fournisseur_expirants: échec '
                'société %s', company.id, exc_info=True)
            result[company.id] = 0
    return result


@shared_task(name='stock.notifier_bcf_en_retard_buyer')
def notifier_bcf_en_retard_buyer_task():
    """XPUR7 (AUDV04/DRAFT165-116) — pour CHAQUE société active, notifie les
    responsables/admins (l'ACHETEUR, pas le fournisseur — distinct de
    `stock.relancer_bcf_en_retard` qui propose une relance AU fournisseur)
    des BCF ENVOYE en retard (réutilise `services.notify_bcf_en_retard` —
    jamais de logique dupliquée). Cette fonction existait déjà, testée, mais
    n'avait AUCUN appelant ni cron : le buyer alert XPUR7 (`BCF_LATE`) ne
    partait donc jamais en pratique. Idempotent : au plus une notification-
    lot par jour par société. Renvoie {company_id: nb_bcf_notifies}."""
    from authentication.selectors import active_companies
    from apps.notifications.models import EventType
    from .services import notify_bcf_en_retard

    result = {}
    for company in active_companies():  # AUD415/SCA19 — pas les suspendus
        if _deja_notifie_aujourdhui_societe(EventType.BCF_LATE, company):
            result[company.id] = 0
            continue
        try:
            result[company.id] = notify_bcf_en_retard(company)
        except Exception:  # noqa: BLE001 — une société en échec n'arrête
            logger.warning(
                'stock.notifier_bcf_en_retard_buyer: échec société %s',
                company.id, exc_info=True)
            result[company.id] = 0
    return result


@shared_task(name='stock.recompute_scores_risque')
def recompute_scores_risque_task():
    """NTP2P34 — recalcule quotidiennement le score de risque (NTP2P8,
    ``selectors.score_risque_fournisseur``, calcul PUR sans appel externe)
    de tous les fournisseurs ACTIFS de chaque société active.

    ``score_risque_fournisseur`` ne met RIEN en cache (calcul à la volée à
    chaque appel de l'endpoint `fournisseurs/{id}/score-risque/`) — « invalide
    le cache éventuel du badge » est donc un no-op ici par construction (rien
    à invalider). Sans effet si le sélecteur NTP2P8 n'existe pas encore
    (garde d'existence, no-op silencieux). Best-effort : un fournisseur ou
    une société en échec n'arrête jamais les suivants. Renvoie
    ``{company_id: nb_fournisseurs_recalcules}`` pour observabilité/tests."""
    from authentication.selectors import active_companies
    from . import selectors as stock_selectors
    from .models import Fournisseur

    if not hasattr(stock_selectors, 'score_risque_fournisseur'):
        return {}

    result = {}
    for company in active_companies():  # AUD415/SCA19 — pas les suspendus
        count = 0
        fournisseur_ids = list(
            Fournisseur.objects.filter(
                company=company, is_archived=False
            ).values_list('id', flat=True))
        for fournisseur_id in fournisseur_ids:
            try:
                stock_selectors.score_risque_fournisseur(
                    company, fournisseur_id)
                count += 1
            except Exception:  # noqa: BLE001 — fournisseur suivant
                logger.warning(
                    'stock.recompute_scores_risque: échec fournisseur %s '
                    '(société %s)', fournisseur_id, company.id,
                    exc_info=True)
        result[company.id] = count
    return result


@shared_task(name='stock.alerter_surcapacite_zones')
def alerter_surcapacite_zones_task(seuil_pct=None):
    """NTWMS42 — alerte PASSIVE de sur-stockage par zone.

    Pour CHAQUE société, relève les zones dont le taux de remplissage franchit
    le seuil (défaut 95 %, cf. ``selectors_entrepot.SEUIL_SURCAPACITE_PCT``) et
    notifie best-effort le responsable d'entrepôt — sans qu'aucun utilisateur
    n'ait à lancer le simulateur NTWMS33. Idempotent : une seule notification
    par société et par jour (même garde ``link`` stable que ZSTK1/ZSTK2).

    Une zone sans capacité déclarée (aucune ``CategorieStockage`` posée sur ses
    casiers) n'est JAMAIS signalée : on ne devine pas un taux.

    Renvoie ``{company_id: nb_zones_alertees}``.
    """
    from authentication.selectors import active_companies
    from .selectors_entrepot import zones_en_surcapacite

    today = timezone.localdate()
    result = {}
    for company in active_companies():  # AUD415/SCA19 — pas les suspendus
        try:
            zones = zones_en_surcapacite(company, seuil_pct=seuil_pct)
        except Exception:  # noqa: BLE001 — société suivante, jamais bloquant
            logger.warning(
                'stock.alerter_surcapacite_zones: échec calcul société %s',
                company.id, exc_info=True)
            continue
        if not zones:
            result[company.id] = 0
            continue
        link = f'stock-surcapacite-{company.id}-{today.isoformat()}'
        if _deja_notifie_aujourdhui('stock_low', link):
            result[company.id] = 0
            continue
        try:
            from apps.notifications.models import EventType
            from apps.notifications.services import notify_many
            noms = ', '.join(
                f"{z['zone']} ({z['taux_pct']} %)" for z in zones[:10])
            suffixe = '…' if len(zones) > 10 else ''
            # `EventType` vit dans `apps.notifications`, hors périmètre de
            # cette lane : on EMPRUNTE la famille d'alerte stock existante
            # plutôt que d'écrire une valeur non déclarée dans le TextChoices
            # (le libellé de la notification, lui, est sans ambiguïté).
            notify_many(
                _recipients_reappro(company), EventType.STOCK_LOW,
                title=f'{len(zones)} zone(s) entrepôt en sur-capacité',
                body=f'Seuil de remplissage franchi : {noms}{suffixe}.',
                link=link, company=company)
            result[company.id] = len(zones)
        except Exception:  # noqa: BLE001 — best-effort, jamais bloquant
            logger.warning(
                'stock.alerter_surcapacite_zones: notification échouée '
                'société %s', company.id, exc_info=True)
            result[company.id] = 0
    return result


@shared_task(name='stock.expiration_alerts')
def expiration_alerts_task():
    """ZSTK2 — pour CHAQUE société, notifie (best-effort, une fois par jour)
    les produits/lots dont une réception a une date de péremption dans la
    fenêtre configurable `CompanyProfile.jours_alerte_peremption` (défaut 30).
    Réutilise `produits_expirant_bientot` (FG64) tel quel — jamais de logique
    d'expiry dupliquée. Renvoie {company_id: nb_produits_notifies}."""
    from authentication.selectors import active_companies
    from apps.parametres.models import CompanyProfile
    from .services import produits_expirant_bientot

    today = timezone.localdate()
    result = {}
    for company in active_companies():  # AUD415/SCA19 — pas les suspendus
        try:
            profile = CompanyProfile.get(company=company)
            jours = profile.jours_alerte_peremption or 30
            expirants = produits_expirant_bientot(company, jours=jours)
        except Exception:  # noqa: BLE001 — société suivante
            logger.warning(
                'stock.expiration_alerts: échec calcul société %s',
                company.id, exc_info=True)
            continue
        if not expirants:
            result[company.id] = 0
            continue
        link = f'stock-expiration-{company.id}-{today.isoformat()}'
        if _deja_notifie_aujourdhui('stock_expiration_soon', link):
            result[company.id] = 0
            continue
        try:
            from apps.notifications.services import notify_many
            from apps.notifications.models import EventType
            recipients = _recipients_reappro(company)
            noms = ', '.join(
                e['produit_nom'] for e in expirants[:10])
            suffixe = '…' if len(expirants) > 10 else ''
            notify_many(
                recipients, EventType.STOCK_EXPIRATION_SOON,
                title=f'{len(expirants)} lot(s) bientôt périmé(s)',
                body=f'Péremption proche : {noms}{suffixe}.',
                link=link, company=company)
            result[company.id] = len(expirants)
        except Exception:  # noqa: BLE001 — best-effort, jamais bloquant
            logger.warning(
                'stock.expiration_alerts: notification échouée société %s',
                company.id, exc_info=True)
            result[company.id] = 0
    return result


# ── AUD231 — deux jobs WMS écrits « pour Celery beat » mais planifiés NULLE
# PART. Leurs docstrings de commande annonçaient « Plannifiable par Celery beat
# comme les autres jobs du module » ; le grep sur `erp_agentique/` rendait
# ZÉRO. Les enveloppes ci-dessous appellent le SERVICE (jamais la commande, ni
# une logique dupliquée) et sont, elles, dans le `beat_schedule`.

@shared_task(name='stock.generer_comptages_tournants')
def generer_comptages_tournants_task():
    """NTWMS13 (AUD231) — génère les sessions d'inventaire de comptage tournant
    DUES, toutes sociétés. Idempotente : rejouée le même jour elle ne recrée
    rien (l'échéance du plan vient d'être repoussée). Renvoie le nombre de
    sessions créées."""
    from .services_wms import generer_comptages_tournants
    try:
        resultat = generer_comptages_tournants()
    except Exception:  # noqa: BLE001 — best-effort, jamais bloquant
        logger.warning('stock.generer_comptages_tournants: échec du balayage',
                       exc_info=True)
        return 0
    return len(resultat.get('sessions', []))


@shared_task(name='stock.liberer_vagues_planifiees')
def liberer_vagues_planifiees_task():
    """NTWMS12 (AUD231) — libère les vagues de prélèvement AUTO_HEURE /
    AUTO_SEUIL dont la condition est atteinte, toutes sociétés. Idempotente :
    une vague déjà lancée n'est jamais retouchée. Cadence courte assumée :
    l'heure de coupure est un réglage PAR SOCIÉTÉ, à la minute près. Renvoie le
    nombre de vagues libérées."""
    from .services_wms import liberer_vagues_planifiees
    try:
        resultat = liberer_vagues_planifiees()
    except Exception:  # noqa: BLE001 — best-effort, jamais bloquant
        logger.warning('stock.liberer_vagues_planifiees: échec du balayage',
                       exc_info=True)
        return 0
    return len(resultat.get('liberees', []))
