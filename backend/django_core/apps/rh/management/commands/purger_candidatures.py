"""XRH24 — Rétention & anonymisation des candidats rejetés (loi 09-08).

DRY-RUN PAR DÉFAUT. Pour chaque société (ou une seule via ``--company``),
liste — et SEULEMENT si ``--apply`` est posé, anonymise réellement — les
candidatures REJETÉES hors vivier dont le séjour dépasse la rétention société
(``ReglageRH.retention_candidatures_mois``, défaut 24 mois).

Usage :

    python manage.py purger_candidatures [--company <slug-ou-id>]
                                         [--retention-mois N] [--apply]

Conception (miroir GED25 ``purger_corbeille``) :

  * DRY-RUN PAR DÉFAUT. Sans ``--apply``, RIEN n'est modifié : la commande
    compte/affiche seulement ce qui SERAIT anonymisé.
  * Multi-tenant. Chaque candidature est purgée bornée à SA société.
  * Ne touche JAMAIS un candidat EMBAUCHÉ ni au VIVIER actif (filtré côté
    service : ``apps.rh.services.candidatures_purgeables``).
  * La ligne survit — anonymisation, jamais suppression : les comptages/
    statistiques (XRH22) restent corrects.
"""
from django.core.management.base import BaseCommand, CommandError

from apps.rh import services


class Command(BaseCommand):
    help = (
        "Anonymise (DRY-RUN par défaut) les candidatures rejetées hors "
        "vivier au-delà de la rétention société (loi 09-08)."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--company', dest='company', default=None,
            help='Limite à une société (slug ou id).')
        parser.add_argument(
            '--retention-mois', dest='retention_mois', type=int, default=None,
            help='Rétention en mois (défaut : réglage société, 24 sinon).')
        parser.add_argument(
            '--apply', dest='apply', action='store_true', default=False,
            help='Anonymise RÉELLEMENT (sans ce drapeau : dry-run).')

    def handle(self, *args, **options):
        from authentication.models import Company

        apply = bool(options.get('apply'))
        retention_mois = options.get('retention_mois')

        companies = Company.objects.all()
        ident = options.get('company')
        if ident:
            if str(ident).isdigit():
                companies = companies.filter(pk=int(ident))
            else:
                companies = companies.filter(slug=ident)
            if not companies.exists():
                raise CommandError(f"Société introuvable : {ident}")

        mode = 'ANONYMISATION RÉELLE' if apply else 'DRY-RUN (rien modifié)'
        self.stdout.write(self.style.WARNING(f"Mode : {mode}"))

        total_eligibles = 0
        total_anonymisees = 0
        for company in companies:
            res = services.purger_candidatures(
                company, retention_mois=retention_mois, apply=apply)
            if res['eligibles'] == 0:
                continue
            total_eligibles += res['eligibles']
            total_anonymisees += res['anonymisees']
            verbe = 'anonymisée(s)' if apply else 'à anonymiser'
            self.stdout.write(
                f"  · {company.nom} — {res['eligibles']} {verbe}")

        if total_eligibles == 0:
            self.stdout.write(self.style.SUCCESS(
                'Aucune candidature éligible (rien à anonymiser).'))
        elif apply:
            self.stdout.write(self.style.SUCCESS(
                f"\nTotal : {total_anonymisees} candidature(s) anonymisée(s)."))
        else:
            self.stdout.write(self.style.SUCCESS(
                f"\nTotal : {total_eligibles} candidature(s) SERAIENT "
                "anonymisées — DRY-RUN, rien n'a été modifié. Relancer avec "
                "--apply pour anonymiser réellement."))
