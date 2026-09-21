"""Clôture (suspension) automatique des contrats impayés — ZCTR2.

Odoo a le cron « Sale Subscription: subscriptions expiration » qui clôt les
abonnements impayés passé le délai du plan. Ici, pour chaque société,
suspend (JAMAIS résilie) les ``Contrat`` ACTIFS rattachés à un
``PlanRecurrent`` dont ``delai_cloture_auto_jours`` est dépassé par une
facture de cycle impayée (lue via ``apps.ventes.selectors`` — jamais un
import direct de ``apps.ventes.models``).

Un contrat SANS ``plan_recurrent`` rattaché, ou dont
``delai_cloture_auto_jours`` est NULL, n'est jamais concerné (comportement
neutre par défaut — ``PlanRecurrent`` est optionnel, ZCTR1).

Idempotent : un contrat déjà ``suspendu`` n'est jamais re-suspendu ; ré-
exécuter la commande le même jour ne produit aucune double suspension ni
double notification (``services.suspendre_contrat_si_impaye`` court-circuite
dès l'entrée si le statut n'est plus ``actif``).

Multi-société : boucle explicitement par société (jamais de lecture de
company du corps de requête) ; une exception sur un contrat n'empêche jamais
le traitement des suivants (best-effort par contrat, cf. ``services``).

Branchable au Celery beat existant (``erp_agentique/celery.py``) au même
patron que les autres tâches quotidiennes de l'app (``scheduled.py``).

Run (inside the django_core container or with DB env vars set):
  python manage.py cloturer_contrats_impayes                     # toutes sociétés
  python manage.py cloturer_contrats_impayes --company taqinor-demo
  python manage.py cloturer_contrats_impayes --dry-run
"""
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from apps.contrats.services import cloturer_contrats_impayes


class Command(BaseCommand):
    help = (
        'Suspend automatiquement les contrats ACTIFS dont une facture de '
        "cycle est impayée depuis plus que le délai de clôture auto de leur "
        'PlanRecurrent (ZCTR2). Ne résilie jamais — suspension seulement.'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--company', default=None,
            help='Slug de société à traiter (défaut : toutes les sociétés).',
        )
        parser.add_argument(
            '--dry-run', action='store_true',
            help=(
                "Calcule et journalise (stdout) sans écrire (ne suspend "
                "rien, n'envoie aucune notification)."),
        )

    def handle(self, *args, **options):
        from authentication.models import Company

        slug = options.get('company')
        dry_run = options['dry_run']
        today = timezone.localdate()

        if slug:
            try:
                companies = [Company.objects.get(slug=slug)]
            except Company.DoesNotExist:
                raise CommandError(f"Company with slug '{slug}' not found.")
        else:
            companies = list(Company.objects.all())

        if not companies:
            self.stdout.write(self.style.WARNING(
                'Aucune société à traiter — rien fait.'))
            return

        total_suspendus = 0
        for company in companies:
            if dry_run:
                from apps.contrats.models import Contrat
                from apps.contrats.services import _jours_impaye_contrat

                candidats = Contrat.objects.filter(
                    company=company, statut=Contrat.Statut.ACTIF,
                    plan_recurrent__isnull=False,
                    plan_recurrent__delai_cloture_auto_jours__isnull=False,
                ).select_related('plan_recurrent')
                a_suspendre = [
                    c for c in candidats
                    if _jours_impaye_contrat(c) >
                    c.plan_recurrent.delai_cloture_auto_jours
                ]
                self.stdout.write(
                    f'{company} : {len(a_suspendre)} contrat(s) seraient '
                    f'suspendu(s) (dry-run, aucune écriture).')
                continue

            suspendus = cloturer_contrats_impayes(company, today=today)
            total_suspendus += len(suspendus)
            if suspendus:
                self.stdout.write(
                    f'{company} : {len(suspendus)} contrat(s) suspendu(s) '
                    f'(impayé) — #{[c.id for c in suspendus]}.')

        if dry_run:
            return

        self.stdout.write(self.style.SUCCESS(
            f'{total_suspendus} contrat(s) suspendu(s) au total (impayé).'))
