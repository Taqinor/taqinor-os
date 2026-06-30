"""GED25 — Purge automatique de la corbeille échue (DRY-RUN par défaut).

Pour chaque société (ou une seule via ``--company``), liste — et SEULEMENT si
``--apply`` est posé, efface réellement — les documents DÉJÀ en corbeille (GED26)
dont le séjour dépasse le délai de grâce, en respectant les gardes légales
(GED23 write-once / GED24 legal hold : un document protégé est exclu).

Usage :

    python manage.py purger_corbeille [--company <slug-ou-id>]
                                      [--grace-days N] [--apply]

Conception :

  * DRY-RUN PAR DÉFAUT. Sans ``--apply``, RIEN n'est effacé : la commande
    compte/affiche seulement ce qui SERAIT purgé. L'effacement réel exige
    ``--apply`` explicite (opération destructive-mais-révertable au sens
    CLAUDE.md : les documents visés sont déjà en corbeille).

  * Multi-tenant. Chaque document est purgé bornée à SA société (jamais
    cross-société). ``--company`` limite à une seule société.

  * Délai de grâce surchargeable via ``--grace-days`` (défaut : réglage
    ``GED_PURGE_GRACE_DAYS``, lui-même 30 j).
"""
from django.core.management.base import BaseCommand, CommandError

from apps.ged import services


class Command(BaseCommand):
    help = (
        "Purge (DRY-RUN par défaut) les documents GED en corbeille échue, en "
        "respectant les gardes légales (GED23/GED24)."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--company', dest='company', default=None,
            help='Limite à une société (slug ou id).')
        parser.add_argument(
            '--grace-days', dest='grace_days', type=int, default=None,
            help='Délai de grâce (jours) en corbeille avant éligibilité.')
        parser.add_argument(
            '--apply', dest='apply', action='store_true', default=False,
            help='Efface RÉELLEMENT (sans ce drapeau : dry-run, rien effacé).')

    def handle(self, *args, **options):
        from authentication.models import Company

        apply = bool(options.get('apply'))
        grace_days = options.get('grace_days')

        companies = Company.objects.all()
        ident = options.get('company')
        if ident:
            if str(ident).isdigit():
                companies = companies.filter(pk=int(ident))
            else:
                companies = companies.filter(slug=ident)
            if not companies.exists():
                raise CommandError(f"Société introuvable : {ident}")

        mode = 'EFFACEMENT RÉEL' if apply else 'DRY-RUN (aucun effacement)'
        self.stdout.write(self.style.WARNING(f"Mode : {mode}"))
        total_purges = 0
        total_proteges = 0
        for company in companies:
            res = services.purger_corbeille_echue(
                company, grace_days=grace_days, apply=apply)
            if res['eligibles'] == 0:
                continue
            total_purges += res['purges']
            total_proteges += res['proteges']
            verbe = 'purgé(s)' if apply else 'purgeable(s)'
            self.stdout.write(
                f"  · {company.nom} — {res['eligibles']} éligible(s) : "
                f"{res['purges']} {verbe}, {res['proteges']} protégé(s) "
                f"(archive/legal hold)")

        if total_purges == 0 and total_proteges == 0:
            self.stdout.write(self.style.SUCCESS(
                "Aucun document en corbeille échue (rien à purger)."))
        elif apply:
            self.stdout.write(self.style.SUCCESS(
                f"\nTotal : {total_purges} document(s) purgé(s), "
                f"{total_proteges} protégé(s) conservé(s)."))
        else:
            self.stdout.write(self.style.SUCCESS(
                f"\nTotal : {total_purges} document(s) SERAIENT purgé(s), "
                f"{total_proteges} protégé(s) — DRY-RUN, rien n'a été effacé. "
                "Relancer avec --apply pour effacer réellement."))
