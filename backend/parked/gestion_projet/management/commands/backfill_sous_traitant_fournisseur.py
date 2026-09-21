"""ARC22 — Rattache les ``gestion_projet.SousTraitant`` EXISTANTS au master
sous-traitant unifié DC34 (``stock.Fournisseur`` type=service) par
correspondance nom/téléphone.

Régression constatée : le carnet ``gestion_projet`` (PROJ38) est un 3e
référentiel sous-traitant parallèle à ``stock.Fournisseur``/
``SousTraitantProfile`` (DC34). Ce backfill est PUREMENT ADDITIF et
IDEMPOTENT : il ne modifie/supprime AUCUNE ligne, ne fusionne rien, ne gèle
aucune colonne dupliquée (hors scope ARC22 — reste la propriété de DC34). Il
pose UNIQUEMENT le lien ``SousTraitant.fournisseur`` quand une correspondance
FIABLE existe déjà dans la même société, et laisse INCHANGÉES les lignes sans
correspondance (rapport des non-appariés en sortie).

Correspondance (dans l'ordre, la première qui matche gagne, scopée société) :
  1. nom EXACT (insensible à la casse) ET téléphone EXACT (si les deux sont
     renseignés des deux côtés) ;
  2. à défaut, nom EXACT (insensible à la casse) seul.
Un ``SousTraitant`` déjà lié (``fournisseur`` non NULL) est SAUTÉ (idempotent
— jamais réécrit).

Run :
    docker compose exec django_core python manage.py backfill_sous_traitant_fournisseur
    docker compose exec django_core python manage.py backfill_sous_traitant_fournisseur --company taqinor-demo
    docker compose exec django_core python manage.py backfill_sous_traitant_fournisseur --dry-run
"""
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = (
        "ARC22 — rattache les SousTraitant (gestion_projet) existants au "
        "master stock.Fournisseur (DC34) par correspondance nom/téléphone. "
        "Additif et idempotent : pose uniquement le lien fournisseur, ne "
        "modifie/fusionne rien d'autre."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--company', default=None,
            help="Slug d'une seule société à traiter (défaut : toutes).",
        )
        parser.add_argument(
            '--dry-run', action='store_true',
            help='Affiche le rapport sans écrire aucun lien.',
        )

    def handle(self, *args, **options):
        from authentication.models import Company
        from apps.gestion_projet.models import SousTraitant
        from apps.stock import selectors as stock_selectors

        slug = options.get('company')
        dry_run = options.get('dry_run')

        if slug:
            try:
                companies = [Company.objects.get(slug=slug)]
            except Company.DoesNotExist:
                raise CommandError(f"Company with slug '{slug}' not found.")
        else:
            companies = list(Company.objects.all())

        if not companies:
            self.stdout.write(self.style.WARNING(
                'Aucune société à traiter.'))
            return

        total_matched = 0
        total_unmatched = 0
        total_already = 0
        unmatched_report = []

        for company in companies:
            fournisseurs = list(stock_selectors.sous_traitants_qs(company))
            by_nom_tel = {}
            by_nom = {}
            for f in fournisseurs:
                nom_key = (f.nom or '').strip().lower()
                tel_key = (f.telephone or '').strip()
                if nom_key and tel_key:
                    by_nom_tel.setdefault((nom_key, tel_key), f)
                if nom_key:
                    by_nom.setdefault(nom_key, f)

            candidats = SousTraitant.objects.filter(
                company=company, fournisseur__isnull=True)
            for st in candidats:
                st_nom = (st.nom or '').strip().lower()
                st_tel = (st.telephone or '').strip()

                match = None
                if st_nom and st_tel:
                    match = by_nom_tel.get((st_nom, st_tel))
                if match is None and st_nom:
                    match = by_nom.get(st_nom)

                if match is not None:
                    total_matched += 1
                    if not dry_run:
                        st.fournisseur = match
                        st.save(update_fields=['fournisseur'])
                else:
                    total_unmatched += 1
                    unmatched_report.append(
                        f'  - [{company.slug}] SousTraitant#{st.pk} "{st.nom}"')

            total_already += SousTraitant.objects.filter(
                company=company, fournisseur__isnull=False).count()

        prefix = '[DRY-RUN] ' if dry_run else ''
        self.stdout.write(self.style.SUCCESS(
            f'{prefix}Backfill sous-traitant → fournisseur (ARC22) sur '
            f'{len(companies)} société(s) : {total_matched} apparié(s), '
            f'{total_unmatched} non-apparié(s), {total_already} déjà lié(s).'))
        if unmatched_report:
            self.stdout.write('Non-appariés (aucune correspondance fiable) :')
            for line in unmatched_report:
                self.stdout.write(line)
