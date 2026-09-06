"""MRY17 — L'objectif de PREMIER CONTACT est dépassé : escalade immédiate.

La promesse tenue par Meryem est « rappelé en moins de cinq minutes ouvrées ».
Rien ne la surveillait : un lead arrivé pendant qu'elle est en rendez-vous
pouvait refroidir une demi-journée sans qu'aucune surface ne s'en aperçoive.
Cette commande tourne toutes les 5 minutes (Celery Beat
``crm.escalader_premier_contact``) et, pour chaque lead NEUF jamais touché
dont l'objectif est dépassé, notifie le responsable ET son supérieur.

Trois garde-fous qui font la différence entre une alerte utile et du bruit :

  * les minutes sont OUVRÉES (``crm.horaires.minutes_ouvrees_entre``) — un
    lead arrivé à 23 h n'est PAS en retard à 23 h 05, il l'est cinq minutes
    ouvrées après l'ouverture ;
  * l'escalade est idempotente PAR LEAD (marqueur en note chatter), sinon la
    même alerte partirait toutes les 5 minutes jusqu'au rappel ;
  * seuls les leads ``OS_NATIVE`` comptent — les 930 leads du miroir Odoo ne
    sont pas des demandes à rappeler.

    python manage.py escalader_premier_contact [--dry-run]
"""
import logging

from django.core.management.base import BaseCommand

logger = logging.getLogger(__name__)

#: Marqueur d'idempotence (même patron que ``ESCALATION_MARKER`` de
#: ``recycler_leads_non_travailles``) : recherché avant toute nouvelle alerte.
MARQUEUR = 'auto — objectif premier contact dépassé'


class Command(BaseCommand):
    help = ("MRY17 — Escalade les leads neufs jamais touchés au-delà de "
            "l'objectif de premier contact (minutes OUVRÉES).")

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run', action='store_true',
            help='Compte sans notifier ni écrire en base.')

    def handle(self, *args, **options):
        dry_run = options.get('dry_run', False)
        nb = escalader_premier_contact(dry_run=dry_run)
        prefixe = '[dry-run] ' if dry_run else ''
        self.stdout.write(self.style.SUCCESS(
            f'{prefixe}{nb} lead(s) escaladé(s).'))


def _objectif_minutes(company):
    """Objectif de la société (défaut 5). 0 = surveillance désactivée."""
    try:
        from apps.parametres.models import CompanyProfile
        profil = CompanyProfile.objects.filter(company=company).first()
        valeur = getattr(profil, 'premier_contact_objectif_min', None)
        return int(valeur) if valeur is not None else 5
    except Exception:  # noqa: BLE001 — défaut assumé
        return 5


def escalader_premier_contact(dry_run=False, now=None):
    """Cœur de la commande — appelable directement (tests, tâche Celery).

    Renvoie le nombre de leads escaladés sur CE passage."""
    from django.utils import timezone

    # SCA19 — jamais `Company.objects.all()` : un tenant suspendu ne
    # doit plus déclencher d'escalade chez personne.
    from authentication.selectors import active_companies

    # CLAUDE.md #2 — la clé d'étape vient de la SOURCE UNIQUE (STAGES.py à la
    # racine, chargée par `apps.crm.stages`), jamais d'une chaîne littérale.
    from apps.crm import horaires
    from apps.crm.stages import NEW
    from apps.crm.models import Lead, LeadActivity
    from apps.crm.services import lead_notification_recipients
    from apps.notifications.models import EventType
    from apps.notifications.services import notify_many

    maintenant = now or timezone.now()
    nb = 0

    for company in active_companies():
        objectif = _objectif_minutes(company)
        if not objectif:
            continue  # surveillance désactivée pour cette société
        candidats = Lead.objects.filter(
            company=company, source=Lead.Source.OS_NATIVE, stage=NEW,
            first_contacted_at__isnull=True, perdu=False, is_archived=False,
        ).select_related('owner')
        for lead in candidats:
            try:
                ecoulees = horaires.minutes_ouvrees_entre(
                    lead.date_creation, maintenant, company)
            except Exception:  # noqa: BLE001 — un lead en échec n'arrête rien
                logger.warning(
                    'escalader_premier_contact: calcul échoué (lead %s)',
                    lead.pk, exc_info=True)
                continue
            if ecoulees <= objectif:
                # Comprend le cas « lead de nuit » : hors fenêtre, zéro
                # minute ouvrée s'écoule — aucune escalade avant l'ouverture.
                continue
            if LeadActivity.objects.filter(
                    lead=lead, kind=LeadActivity.Kind.NOTE,
                    body__startswith=MARQUEUR).exists():
                continue
            nb += 1
            if dry_run:
                continue
            try:
                LeadActivity.objects.create(
                    company=company, lead=lead, user=None,
                    kind=LeadActivity.Kind.NOTE,
                    body=(f'{MARQUEUR} — {ecoulees} minute(s) ouvrée(s) '
                          f"écoulées depuis l'arrivée (objectif "
                          f'{objectif}).'))
                nom = (lead.nom or '').strip() or 'Nouveau prospect'
                notify_many(
                    lead_notification_recipients(lead),
                    EventType.PREMIER_CONTACT_DEPASSE,
                    title=f'{nom} attend depuis {ecoulees} min ouvrées',
                    body=("Ce lead n'a encore reçu aucune prise de contact. "
                          f"L'objectif de la société est de {objectif} "
                          'minute(s) ouvrée(s).'),
                    link=f'/crm/leads?lead={lead.pk}', company=company)
            except Exception:  # noqa: BLE001 — best-effort
                logger.warning(
                    'escalader_premier_contact: escalade échouée (lead %s)',
                    lead.pk, exc_info=True)
    return nb
