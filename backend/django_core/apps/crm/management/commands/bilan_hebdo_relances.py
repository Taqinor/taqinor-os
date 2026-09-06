"""MRY21 — Bilan hebdomadaire du moteur de relances, le lundi matin.

Sept chiffres, en français, envoyés à la direction : c'est le seul moment où
quelqu'un regarde le moteur DE HAUT plutôt que touche par touche. Sans lui,
une cadence qui dérape (personne ne décroche, les motifs de perte
disparaissent) resterait invisible jusqu'au trimestre.

Un chiffre indisponible s'affiche « — », JAMAIS 0 : « 0 % de leads joints »
et « aucun lead à mesurer cette semaine » ne veulent pas dire la même chose,
et confondre les deux ferait paniquer pour rien.

    python manage.py bilan_hebdo_relances [--jours 7] [--dry-run]
"""
import logging

from django.core.management.base import BaseCommand

logger = logging.getLogger(__name__)

#: Libellé FR de chaque chiffre du bilan, dans l'ordre de lecture.
LIGNES = [
    ('joints_sous_5j_pct', 'Leads joints sous 5 jours ouvrés', '%'),
    ('cadences_completes', 'Cadences de contact menées à leur terme', ''),
    ('cadences_arretees_joint', 'Cadences arrêtées « joint »', ''),
    ('perdus_avec_motif_pct', 'Leads perdus avec un motif', '%'),
    ('signatures', 'Signatures', ''),
    ('devis_envoyes', 'Devis envoyés', ''),
    ('tentatives_moy_avant_abandon',
     'Tentatives moyennes avant classement au froid', ''),
]


class Command(BaseCommand):
    help = ('MRY21 — Envoie à la direction le bilan hebdomadaire du moteur '
            'de relances (7 chiffres).')

    def add_arguments(self, parser):
        parser.add_argument('--jours', type=int, default=7,
                            help='Fenêtre du bilan (défaut 7).')
        parser.add_argument('--dry-run', action='store_true',
                            help='Affiche le bilan sans notifier.')

    def handle(self, *args, **options):
        jours = options.get('jours') or 7
        dry_run = options.get('dry_run', False)
        envoyes = bilan_hebdo_relances(jours=jours, dry_run=dry_run)
        prefixe = '[dry-run] ' if dry_run else ''
        self.stdout.write(self.style.SUCCESS(
            f'{prefixe}{envoyes} bilan(s) envoyé(s).'))


def formater_bilan(kpi):
    """Les sept lignes, en texte lisible. `None` → « — », jamais 0."""
    lignes = []
    for cle, libelle, unite in LIGNES:
        valeur = kpi.get(cle)
        affiche = '—' if valeur is None else f'{valeur}{unite}'
        lignes.append(f'{libelle} : {affiche}')
    return '\n'.join(lignes)


def bilan_hebdo_relances(*, jours=7, dry_run=False):
    """Cœur de la commande — appelable directement (tests, tâche Celery).

    Renvoie le nombre de sociétés pour lesquelles un bilan est parti."""
    # SCA19 — jamais `Company.objects.all()` : un tenant suspendu ne
    # reçoit plus de bilan.
    from authentication.selectors import active_companies

    from apps.crm.selectors import kpi_cadences
    from apps.crm.visites import utilisateurs_direction
    from apps.notifications.models import EventType
    from apps.notifications.services import notify_many

    envoyes = 0
    for company in active_companies():
        destinataires = utilisateurs_direction(company)
        if not destinataires:
            continue  # aucune direction résolvable — on ne fabrique personne
        try:
            kpi = kpi_cadences(company, jours=jours)
        except Exception:  # noqa: BLE001 — une société en échec n'arrête rien
            logger.warning(
                'bilan_hebdo_relances: KPI illisible (société %s)',
                company.pk, exc_info=True)
            continue
        envoyes += 1
        if dry_run:
            continue
        try:
            notify_many(
                destinataires, EventType.CRM_BILAN_HEBDO,
                title='Bilan relances de la semaine',
                body=formater_bilan(kpi), link='/crm/cockpit',
                company=company)
        except Exception:  # noqa: BLE001 — best-effort
            logger.warning(
                'bilan_hebdo_relances: envoi échoué (société %s)',
                company.pk, exc_info=True)
    return envoyes
