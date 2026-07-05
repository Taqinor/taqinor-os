"""ZRH2 — Acquisition mensuelle automatique des congés + report janvier.

Odoo « Accrual Time Off » : crédite ``SoldeConge.acquis`` du droit du mois pour
chaque employé actif (``rh.selectors.dossiers_actifs``), sans jamais dépasser
12 crédits/an (garde ``SoldeConge.mois_acquis``, idempotente). En janvier,
``--report`` bascule le ``disponible`` restant de N-1 dans ``report`` de N
(idempotent via ``SoldeConge.report_applique``, plafond optionnel via
``--plafond-report``).

Dry-run PAR DÉFAUT (n'écrit rien) : passer ``--apply`` pour committer. Aucune
dépendance Celery Beat obligatoire — lançable à la main ; Beat optionnel.
"""
from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.rh import selectors, services


class Command(BaseCommand):
    help = (
        'ZRH2 — crédite l’acquisition mensuelle de congés (et, en janvier, '
        'reporte le solde N-1) pour chaque employé actif. Dry-run par défaut.')

    def add_arguments(self, parser):
        today = timezone.localdate()
        parser.add_argument(
            '--annee', type=int, default=today.year,
            help='Année du crédit mensuel (défaut : année courante).')
        parser.add_argument(
            '--mois', type=int, default=today.month,
            help='Mois du crédit (1-12, défaut : mois courant).')
        parser.add_argument(
            '--apply', action='store_true',
            help='Committe réellement (sinon dry-run, rien n’est écrit).')
        parser.add_argument(
            '--report', action='store_true',
            help='Applique en plus le report janvier (annee-1 -> annee).')
        parser.add_argument(
            '--plafond-report', type=float, default=None,
            help='Plafond du report janvier (défaut : illimité).')
        parser.add_argument(
            '--company', type=int, default=None,
            help='Limiter à une société (ID). Défaut : toutes.')

    def handle(self, *args, **options):
        annee = options['annee']
        mois = options['mois']
        apply_ = options['apply']
        do_report = options['report']
        plafond = options['plafond_report']
        company_id = options['company']

        if not 1 <= mois <= 12:
            self.stderr.write(self.style.ERROR('Mois invalide (1-12).'))
            return

        from authentication.models import Company
        companies = Company.objects.all()
        if company_id is not None:
            companies = companies.filter(pk=company_id)

        total_credite = 0
        total_deja = 0
        total_reporte = 0
        total_report_deja = 0

        for company in companies:
            for dossier in selectors.dossiers_actifs(company):
                resultat = services.accruer_conges_mensuel(
                    dossier, annee=annee, mois=mois, apply=apply_)
                if resultat['deja_acquis']:
                    total_deja += 1
                else:
                    total_credite += 1

                if do_report:
                    resultat_report = services.reporter_solde_janvier(
                        dossier, annee_precedente=annee - 1,
                        annee_cible=annee, plafond=plafond, apply=apply_)
                    if resultat_report['deja_applique']:
                        total_report_deja += 1
                    else:
                        total_reporte += 1

        mode = 'APPLIQUÉ' if apply_ else 'DRY-RUN'
        self.stdout.write(self.style.SUCCESS(
            f'[{mode}] {annee}-{mois:02d} : {total_credite} crédité(s), '
            f'{total_deja} déjà acquis.'))
        if do_report:
            self.stdout.write(self.style.SUCCESS(
                f'[{mode}] Report janvier {annee - 1}->{annee} : '
                f'{total_reporte} reporté(s), '
                f'{total_report_deja} déjà appliqué(s).'))
