"""XGED6 — Vérification périodique d'intégrité des archives légales (GED23,
loi 43-20).

Pour chaque société (ou une seule via ``--company``), re-télécharge le
contenu de chaque archivage légal, recompare son hash SHA-256 à celui figé au
dépôt, et journalise le résultat (`ControleIntegrite`). Notifie les admins
(best-effort) en cas d'écart. Ne modifie JAMAIS `ArchivageLegal` lui-même
(write-once GED23 intact) — purement un CONTRÔLE, jamais une correction.

Usage :

    python manage.py verifier_archives [--company <slug-ou-id>]
"""
from django.core.management.base import BaseCommand, CommandError

from apps.ged import services


class Command(BaseCommand):
    help = (
        "Re-vérifie l'intégrité des archives légales GED23 (hash constaté vs "
        "hash au dépôt) et journalise chaque contrôle."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--company', dest='company', default=None,
            help='Limite à une société (slug ou id).')

    def handle(self, *args, **options):
        from authentication.models import Company

        companies = Company.objects.all()
        ident = options.get('company')
        if ident:
            if str(ident).isdigit():
                companies = companies.filter(pk=int(ident))
            else:
                companies = companies.filter(slug=ident)
            if not companies.exists():
                raise CommandError(f"Société introuvable : {ident}")

        total = {'total': 0, 'ok': 0, 'altere': 0, 'indisponible': 0}
        for company in companies:
            res = services.verifier_integrite_archives(company)
            if res['total'] == 0:
                continue
            for key in total:
                total[key] += res[key]
            self.stdout.write(
                f"  · {company.nom} — {res['total']} archivage(s) : "
                f"{res['ok']} intègre(s), {res['altere']} altéré(s), "
                f"{res['indisponible']} indisponible(s)")

        if total['total'] == 0:
            self.stdout.write(self.style.SUCCESS(
                "Aucun archivage légal à contrôler."))
        elif total['altere']:
            self.stdout.write(self.style.ERROR(
                f"\nTotal : {total['altere']} archivage(s) ALTÉRÉ(S) détecté(s) "
                f"sur {total['total']} contrôlé(s) — admins notifiés."))
        else:
            self.stdout.write(self.style.SUCCESS(
                f"\nTotal : {total['total']} archivage(s) contrôlé(s), tous "
                "intègres (ou indisponibles au moment du contrôle)."))
