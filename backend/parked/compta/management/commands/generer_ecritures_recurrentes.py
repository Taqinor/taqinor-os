"""XACC8 — Génère les écritures dues de tous les abonnements récurrents actifs.

Pour chaque société (ou une société ciblée par ``--company``), régénère les
écritures des ``AbonnementEcriture`` actifs dont l'échéance est atteinte
(loyer mensuel, abonnements trimestriels…), en BROUILLON, prêtes à valider.
IDEMPOTENT : rejouer la commande le même jour ne duplique jamais une écriture
déjà générée pour une période donnée (``services.generer_ecritures_
recurrentes``). Branchable Celery beat (appel direct de la fonction service
depuis une tâche périodique) — cette commande reste l'entrée manuelle/CLI.

Exemples ::

    python manage.py generer_ecritures_recurrentes --company acme
    python manage.py generer_ecritures_recurrentes --all
    python manage.py generer_ecritures_recurrentes --all --jusqua 2026-03-31
"""
from datetime import date

from django.core.management.base import BaseCommand, CommandError

from authentication.models import Company

from apps.compta import services


class Command(BaseCommand):
    help = ("Génère les écritures récurrentes dues (abonnements actifs), "
            "idempotent par période. Ne modifie rien tant qu'aucun "
            "abonnement n'est configuré.")

    def add_arguments(self, parser):
        parser.add_argument(
            '--company', dest='company',
            help="Slug de la société (obligatoire sauf avec --all).")
        parser.add_argument(
            '--all', dest='all', action='store_true',
            help="Traite toutes les sociétés.")
        parser.add_argument(
            '--jusqua', dest='jusqua',
            help="Date limite (YYYY-MM-DD) — défaut : aujourd'hui.")

    def handle(self, *args, **options):
        slug = options.get('company')
        do_all = options.get('all')
        jusqua_str = options.get('jusqua')

        if not slug and not do_all:
            raise CommandError("Précisez --company <slug> ou --all.")

        jusqua = None
        if jusqua_str:
            try:
                jusqua = date.fromisoformat(jusqua_str)
            except ValueError as exc:
                raise CommandError(
                    f"Date --jusqua invalide : {jusqua_str!r}") from exc

        if do_all:
            companies = list(Company.objects.order_by('slug'))
            if not companies:
                raise CommandError("Aucune société en base.")
        else:
            company = Company.objects.filter(slug=slug).first()
            if company is None:
                raise CommandError(f"Société inconnue : « {slug} ».")
            companies = [company]

        total_generees, total_ignorees = 0, 0
        for company in companies:
            resultat = services.generer_ecritures_recurrentes(
                company, jusqua=jusqua)
            total_generees += len(resultat['generees'])
            total_ignorees += len(resultat['ignorees'])
            for g in resultat['generees']:
                self.stdout.write(
                    f"  [{company.slug}] écriture #{g['ecriture_id']} "
                    f"générée (abonnement {g['abonnement_id']}, "
                    f"période {g['periode']})")
            for i in resultat['ignorees']:
                self.stdout.write(self.style.WARNING(
                    f"  [{company.slug}] abonnement {i['abonnement_id']} "
                    f"ignoré ({i['periode']}) : {i['raison']}"))

        self.stdout.write(self.style.SUCCESS(
            f"{total_generees} écriture(s) générée(s), "
            f"{total_ignorees} ignorée(s)."))
