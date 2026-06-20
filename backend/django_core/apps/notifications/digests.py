"""N76 — Récapitulatifs (digests) quotidien & hebdomadaire par société.

Deux tâches Celery Beat construisent, POUR CHAQUE société, un résumé FR de l'état
opérationnel (chantiers à planifier, devis en attente d'acceptation, paiements en
retard, maintenances dues, SAV ouverts) et l'émettent via le moteur de
notifications unifié (`notify`) — in-app TOUJOURS, et email/WhatsApp best-effort
quand le canal est activé ET configuré (NO-OP silencieux sinon : comportement
actuel préservé).

Principes (règles fondatrices) :
  - MULTI-TENANT : chaque société est traitée isolément ; les requêtes sont
    bornées par `company`. Les destinataires sont les gérants/staff de CETTE
    société uniquement.
  - DÉFENSIF : chaque section est interrogée dans son propre try/except — un
    modèle absent ou en erreur n'empêche jamais les autres sections ni le digest.
  - IDEMPOTENT : produire un digest ne mute aucune donnée métier ; ré-exécuter la
    tâche ne fait que ré-émettre des notifications (jamais de double comptage).
  - NO-OP sûr : sans société ni destinataire, la tâche ne fait rien et ne lève
    jamais. Texte utilisateur en FRANÇAIS, code/identifiants en anglais.
"""
import logging

from celery import shared_task

from .models import EventType
from .services import notify

logger = logging.getLogger(__name__)


def _companies():
    """Toutes les sociétés actives (best-effort). Liste vide si erreur."""
    try:
        from authentication.models import Company
        return list(Company.objects.filter(actif=True))
    except Exception:  # pragma: no cover - défensif
        logger.warning('digest: chargement des sociétés impossible', exc_info=True)
        return []


def _recipients(company):
    """Gérants/staff destinataires du digest pour une société.

    Priorité aux comptes d'administration/responsables (ceux qui pilotent) ; à
    défaut, tous les utilisateurs actifs de la société. Toujours borné à la
    société (multi-tenant), jamais d'utilisateur d'une autre société."""
    try:
        from authentication.models import CustomUser
        base = CustomUser.objects.filter(company=company, is_active=True)
        managers = [u for u in base if _is_manager(u)]
        if managers:
            return managers
        return list(base)
    except Exception:  # pragma: no cover - défensif
        logger.warning('digest: chargement des destinataires impossible',
                       exc_info=True)
        return []


def _is_manager(user):
    """True pour un compte d'administration/responsable (best-effort)."""
    try:
        if getattr(user, 'is_admin_role', False):
            return True
        return getattr(user, 'role_tier', None) in ('admin', 'responsable')
    except Exception:  # pragma: no cover - défensif
        return False


# ── Sections du résumé (chacune défensive et bornée à la société) ────────────

def _count_chantiers_a_planifier(company):
    """Chantiers signés/à planifier mais pas encore planifiés."""
    from apps.installations.models import Installation
    statuts = [
        Installation.Statut.SIGNE,
        Installation.Statut.MATERIEL_COMMANDE,
        Installation.Statut.A_PLANIFIER,
    ]
    return Installation.objects.filter(
        company=company, statut__in=statuts).count()


def _count_devis_en_attente(company):
    """Devis envoyés en attente de réponse du client (ni acceptés ni refusés)."""
    from apps.ventes.models import Devis
    return Devis.objects.filter(
        company=company, statut=Devis.Statut.ENVOYE).count()


def _count_paiements_en_retard(company):
    """Factures en retard (échéance dépassée, non réglées)."""
    from apps.ventes.models import Facture
    return Facture.objects.filter(
        company=company, statut=Facture.Statut.EN_RETARD).count()


def _count_maintenances_dues(company):
    """Contrats de maintenance actifs dont une visite est due aujourd'hui."""
    from apps.sav.models import ContratMaintenance
    due = 0
    for contrat in ContratMaintenance.objects.filter(
            company=company, actif=True):
        try:
            if contrat.is_due():
                due += 1
        except Exception:  # pragma: no cover - défensif (date malformée)
            continue
    return due


def _count_sav_ouverts(company):
    """Tickets SAV encore ouverts (nouveau/planifié/en cours)."""
    from apps.sav.models import Ticket
    return Ticket.objects.filter(
        company=company, statut__in=Ticket.OPEN_STATUTS).count()


# Chaque section : (libellé FR, fonction de comptage). L'ordre est l'ordre
# d'affichage dans le corps du digest.
_SECTIONS = [
    ('Chantiers à planifier', _count_chantiers_a_planifier),
    ('Devis en attente d’acceptation', _count_devis_en_attente),
    ('Paiements en retard', _count_paiements_en_retard),
    ('Maintenances dues', _count_maintenances_dues),
    ('SAV ouverts', _count_sav_ouverts),
]


def build_summary(company):
    """Construit le résumé d'une société : liste de (libellé, compte).

    Chaque section est isolée : une erreur sur l'une (modèle absent, requête en
    échec) ne casse pas les autres — la section vaut alors 0. Renvoie toujours
    une ligne par section pour un corps de digest stable et lisible."""
    summary = []
    for label, fn in _SECTIONS:
        try:
            count = int(fn(company))
        except Exception:  # pragma: no cover - défensif par section
            logger.warning('digest: section %r en échec pour la société %s',
                           label, getattr(company, 'pk', None), exc_info=True)
            count = 0
        summary.append((label, count))
    return summary


def format_body(summary, periode):
    """Corps FR lisible du digest à partir du résumé (libellé : compte)."""
    lignes = [f'Récapitulatif {periode} de votre activité :', '']
    for label, count in summary:
        lignes.append(f'• {label} : {count}')
    return '\n'.join(lignes)


def _run_digest(periode_label, title):
    """Cœur commun : pour chaque société, construit le résumé et notifie ses
    gérants/staff. Renvoie le nombre de notifications émises. Best-effort par
    société : une société en erreur n'arrête pas les suivantes."""
    emitted = 0
    for company in _companies():
        try:
            recipients = _recipients(company)
            if not recipients:
                continue
            summary = build_summary(company)
            body = format_body(summary, periode_label)
            for user in recipients:
                if notify(user, EventType.DIGEST, title, body=body,
                          link='/', company=company) is not None:
                    emitted += 1
        except Exception:  # pragma: no cover - défensif par société
            logger.warning('digest: échec pour la société %s',
                           getattr(company, 'pk', None), exc_info=True)
            continue
    return emitted


@shared_task(name='notifications.daily_digest')
def daily_digest():
    """Récapitulatif QUOTIDIEN par société (planifié ~07:30 Casablanca)."""
    emitted = _run_digest('quotidien', 'Récapitulatif quotidien')
    logger.info('daily_digest: %s notification(s) émise(s)', emitted)
    return emitted


@shared_task(name='notifications.weekly_digest')
def weekly_digest():
    """Récapitulatif HEBDOMADAIRE par société (lundi ~07:30 Casablanca)."""
    emitted = _run_digest('hebdomadaire', 'Récapitulatif hebdomadaire')
    logger.info('weekly_digest: %s notification(s) émise(s)', emitted)
    return emitted
