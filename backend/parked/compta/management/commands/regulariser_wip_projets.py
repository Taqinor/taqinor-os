"""NTPRJ3 — Régularisations WIP/PCA déduites de l'avancement des projets.

Pour chaque projet encore en production d'une société (ou de toutes avec
``--all``), compare le revenu constaté à l'avancement au facturé cumulé
(``gestion_projet.selectors.avancement_vs_facture``) et poste la
régularisation de cut-off correspondante : ``WIP`` quand la production est en
avance sur la facturation, ``PCA`` quand la facturation est en avance sur la
production. Un écart nul ne crée aucune ligne.

IDEMPOTENT : une seule régularisation par projet ET par période — rejouer la
commande sur la même période ne double jamais l'écriture. Le verrouillage de
période est respecté (une période verrouillée fait échouer l'écriture, la
ligne n'est pas créée). Key-less (aucune clé API requise).

Lancée À LA MAIN à la clôture mensuelle — aucune planification automatique.

Exemples ::

    python manage.py regulariser_wip_projets --company acme --periode 2026-03
    python manage.py regulariser_wip_projets --all --periode 2026-03
    python manage.py regulariser_wip_projets --all --periode 2026-03 --dry-run
"""
from django.core.management.base import BaseCommand, CommandError

from authentication.models import Company

from apps.compta import services


class Command(BaseCommand):
    help = ("Poste les régularisations WIP/PCA déduites de l'avancement des "
            "projets pour une période (NTPRJ3), idempotent par "
            "projet + période.")

    def add_arguments(self, parser):
        parser.add_argument(
            '--company', dest='company',
            help="Slug de la société (obligatoire sauf avec --all).")
        parser.add_argument(
            '--all', dest='all', action='store_true',
            help='Traite toutes les sociétés.')
        parser.add_argument(
            '--periode', dest='periode', required=True,
            help='Période à régulariser, au format AAAA-MM (ex. 2026-03).')
        parser.add_argument(
            '--dry-run', dest='dry_run', action='store_true',
            help="N'écrit rien : affiche seulement ce qui serait régularisé.")

    def handle(self, *args, **options):
        from apps.gestion_projet import selectors as projet_selectors

        slug = options.get('company')
        do_all = options.get('all')
        periode = options.get('periode')
        dry_run = options.get('dry_run')

        if not slug and not do_all:
            raise CommandError('Précisez --company <slug> ou --all.')
        try:
            services._periode_projet(periode)
        except ValueError as exc:
            raise CommandError(str(exc)) from exc

        if do_all:
            companies = list(Company.objects.order_by('slug'))
            if not companies:
                raise CommandError('Aucune société en base.')
        else:
            company = Company.objects.filter(slug=slug).first()
            if company is None:
                raise CommandError(f'Société inconnue : « {slug} ».')
            companies = [company]

        total_creees, total_ignorees = 0, 0
        for company in companies:
            for projet in projet_selectors.projets_en_production(company):
                libelle = projet.code or projet.pk
                if dry_run:
                    # SIMULATION : lecture seule stricte — on ne passe même pas
                    # par le service (aucune ligne, aucune référence consommée).
                    avancement = projet_selectors.avancement_vs_facture(projet)
                    ecart = ((avancement.get('montant_avancement') or 0)
                             - (avancement.get('montant_facture') or 0))
                    if ecart == 0:
                        total_ignorees += 1
                        continue
                    total_creees += 1
                    nature = 'WIP' if ecart > 0 else 'PCA'
                    self.stdout.write(
                        f'  [{company.slug}] projet {libelle} → {nature} '
                        f'{abs(ecart)}')
                    continue
                try:
                    reg = services.generer_regularisation_wip_projet(
                        projet, periode)
                except Exception as exc:  # période verrouillée, compte absent…
                    total_ignorees += 1
                    self.stdout.write(self.style.WARNING(
                        f'  [{company.slug}] projet {libelle} ignoré : {exc}'))
                    continue
                if reg is None:
                    total_ignorees += 1
                    continue
                total_creees += 1
                self.stdout.write(
                    f'  [{company.slug}] {reg.reference} — '
                    f'{reg.get_nature_display()} {reg.montant} '
                    f'(projet {libelle})')

        if dry_run:
            self.stdout.write(self.style.SUCCESS(
                f'Simulation : {total_creees} régularisation(s) seraient '
                f'créée(s), {total_ignorees} projet(s) sans écart. '
                'Rien n’a été écrit.'))
            return
        self.stdout.write(self.style.SUCCESS(
            f'{total_creees} régularisation(s) créée(s), '
            f'{total_ignorees} projet(s) sans écart ou déjà régularisé(s).'))
