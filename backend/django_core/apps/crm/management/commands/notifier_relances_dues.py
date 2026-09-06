"""MRY17 — Digest 08:30 : « vous avez N relance(s) à faire aujourd'hui ».

Le panneau « Relances du jour » du Cockpit ne sert à rien si personne ne
l'ouvre. Cette commande, planifiée à 08:30 (Celery Beat
``crm.notifier_relances_dues``), envoie à CHAQUE commercial le compte de ses
touches dues — une seule fois par jour, quel que soit le nombre d'exécutions.

Idempotence par jour ET par destinataire : une ``Notification`` `relance_due`
déjà créée aujourd'hui pour cette personne bloque la suivante. Sans cela, un
beat rejoué (``acks_late`` : une tâche PEUT être relancée après un crash
worker) enverrait deux fois le même digest.

Best-effort par société et par destinataire : un échec n'interrompt jamais
les suivants.

    python manage.py notifier_relances_dues [--dry-run]
"""
import logging

from django.core.management.base import BaseCommand

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = ("MRY17 — Notifie chaque commercial du nombre de touches de "
            "relance dues aujourd'hui (idempotent par jour).")

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run', action='store_true',
            help='Compte sans notifier ni écrire en base.')

    def handle(self, *args, **options):
        dry_run = options.get('dry_run', False)
        envoyes, destinataires = notifier_relances_dues(dry_run=dry_run)
        prefixe = '[dry-run] ' if dry_run else ''
        self.stdout.write(self.style.SUCCESS(
            f'{prefixe}{envoyes} digest(s) envoyé(s) à '
            f'{destinataires} destinataire(s) éligible(s).'))


def notifier_relances_dues(dry_run=False, today=None):
    """Cœur de la commande — appelable directement (tests, tâche Celery).

    Renvoie ``(nb_digests, nb_destinataires_eligibles)``."""
    from django.contrib.auth import get_user_model
    from django.utils import timezone

    # SCA19 — un tenant SUSPENDU ou en fermeture ne doit plus être
    # balayé ni notifié : on itère la source unique des sociétés
    # opérationnelles, jamais `Company.objects.all()`.
    from authentication.selectors import active_companies

    from apps.crm.selectors import relance_etapes_dues
    from apps.notifications.models import EventType, Notification
    from apps.notifications.services import notify

    User = get_user_model()
    aujourdhui = today or timezone.localdate()
    nb_digests = 0
    nb_destinataires = 0

    for company in active_companies():
        # Les destinataires sont les OWNERS de leads, pas « tous les
        # utilisateurs » : un comptable n'a aucune relance à faire.
        proprietaires = User.objects.filter(
            company=company, is_active=True,
            leads_assignes__isnull=False).distinct()
        for owner in proprietaires:
            try:
                # `scope='all'` = dues aujourd'hui + en retard : c'est
                # exactement ce que le panneau affiche, jamais un compte qui
                # oublierait les touches en souffrance.
                dues = relance_etapes_dues(
                    company, owner, scope='all', owner=owner.pk,
                    today=aujourdhui)
                n = dues.count()
            except Exception:  # noqa: BLE001 — un owner en échec n'arrête rien
                logger.warning(
                    'notifier_relances_dues: comptage échoué pour %s',
                    owner.pk, exc_info=True)
                continue
            if not n:
                continue
            nb_destinataires += 1
            deja = Notification.objects.filter(
                recipient=owner, event_type=EventType.RELANCE_DUE,
                created_at__date=aujourdhui).exists()
            if deja:
                continue
            nb_digests += 1
            if dry_run:
                continue
            try:
                notify(
                    owner, EventType.RELANCE_DUE,
                    title=f"{n} relance(s) à faire aujourd'hui",
                    body=('Ouvrez le Cockpit CRM pour voir vos touches du '
                          'jour et celles en retard.'),
                    link='/crm/cockpit', company=company)
            except Exception:  # noqa: BLE001 — best-effort
                logger.warning(
                    'notifier_relances_dues: notification échouée pour %s',
                    owner.pk, exc_info=True)
    return nb_digests, nb_destinataires
