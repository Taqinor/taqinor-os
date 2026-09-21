"""NTFIN22 — Exécute les allocations récurrentes dues (déversements planifiés).

Pour chaque société (ou une société ciblée par ``--company``), exécute les
``AllocationRecurrente`` actives dont l'échéance est atteinte via le moteur
d'allocation NTFIN21, en avançant leur prochaine échéance. IDEMPOTENT : rejouer
la commande le même mois ne double jamais une allocation déjà exécutée pour une
période donnée (dédup par clé + compte source + période). Key-less (aucune clé
API requise).

Exemples ::

    python manage.py generer_allocations_dues --company acme
    python manage.py generer_allocations_dues --all
    python manage.py generer_allocations_dues --all --jusqua 2026-03-31
"""
from datetime import date

from django.core.management.base import BaseCommand, CommandError

from authentication.models import Company

from apps.compta import services


class Command(BaseCommand):
    help = ("Exécute les allocations récurrentes dues (NTFIN22), idempotent "
            "par période. Ne fait rien tant qu'aucune allocation récurrente "
            "n'est configurée.")

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
            resultat = services.generer_allocations_recurrentes(
                company, jusqua=jusqua)
            total_generees += len(resultat['generees'])
            total_ignorees += len(resultat['ignorees'])
            for g in resultat['generees']:
                self.stdout.write(
                    f"  [{company.slug}] run #{g['run_id']} "
                    f"(allocation {g['allocation_id']}, "
                    f"période {g['periode']})")
            for i in resultat['ignorees']:
                self.stdout.write(self.style.WARNING(
                    f"  [{company.slug}] allocation {i['allocation_id']} "
                    f"ignorée ({i['periode']}) : {i['raison']}"))

        self.stdout.write(self.style.SUCCESS(
            f"{total_generees} allocation(s) exécutée(s), "
            f"{total_ignorees} ignorée(s)."))
