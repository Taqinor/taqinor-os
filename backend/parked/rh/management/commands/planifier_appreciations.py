"""ZRH8 — Planifie les évaluations d'appréciation dues (jalons d'ancienneté).

Pour chaque société (ou une seule via ``--company``), parcourt les
``PlanAppreciation`` actifs et, pour chaque ``DossierEmploye`` actif dont
l'ancienneté franchit un jalon (``mois_apres_embauche``) sans qu'une
évaluation « planifiée » existe déjà pour ce jalon, crée une
``EvaluationEmploye`` (campagne cible du plan, ou campagne annuelle par
défaut) — évaluateur = manager si identifiable.

Dry-run PAR DÉFAUT (n'écrit rien) : passer ``--apply`` pour committer.
Idempotent : un jalon donné ne génère jamais deux évaluations (marque stable
``[ZRH8:jalon=<n>]`` dans ``synthese``) ; un employé sous le jalon ne génère
rien.

Run (inside the django_core container or with DB env vars set):
  python manage.py planifier_appreciations                    # dry-run, toutes sociétés
  python manage.py planifier_appreciations --apply             # committe réellement
  python manage.py planifier_appreciations --company <slug>    # une seule société
"""
from django.core.management.base import BaseCommand, CommandError

from apps.rh import services


class Command(BaseCommand):
    help = (
        "ZRH8 — planifie les évaluations d'appréciation dues (jalons "
        "d'ancienneté franchis) pour chaque employé actif. Dry-run par "
        "défaut ; --apply pour committer.")

    def add_arguments(self, parser):
        parser.add_argument(
            '--apply', action='store_true',
            help='Committe réellement (sinon dry-run, rien n’est écrit).')
        parser.add_argument(
            '--company', default=None,
            help='Slug d’une seule société à traiter (défaut : toutes).')

    def handle(self, *args, **options):
        from authentication.models import Company

        apply_ = options['apply']
        slug = options.get('company')

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

        mode = 'APPLIQUÉ' if apply_ else 'DRY-RUN'
        total_a_creer = 0
        total_deja = 0

        for company in companies:
            resultat = services.planifier_appreciations_pour_societe(
                company, apply=apply_)
            total_a_creer += resultat['nb_a_creer']
            total_deja += resultat['nb_deja']
            self.stdout.write(
                f'[{mode}] {company.nom} : {resultat["nb_a_creer"]} '
                f'planifiée(s), {resultat["nb_deja"]} déjà existante(s).')

        self.stdout.write(self.style.SUCCESS(
            f'[{mode}] Total : {total_a_creer} planifiée(s), '
            f'{total_deja} déjà existante(s) sur {len(companies)} '
            'société(s).'))
