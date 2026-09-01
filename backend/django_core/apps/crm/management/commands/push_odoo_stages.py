"""ERP → Odoo sans IA : pousse les étapes des leads ERP vers le pipeline Odoo.

  python manage.py push_odoo_stages --company <slug-ou-id> [--apply]

Sens inverse de ``sync_odoo_leads``. Par défaut : À BLANC (affiche les
déplacements calculés, n'écrit rien) ; ``--apply`` écrit réellement.

Garde-fous :
  * écrit UNIQUEMENT ``stage_id`` sur ``crm.lead``, via l'API JSON-2
    (CLAUDE.md règle #1 — jamais de SQL) ; aucune création, suppression ni
    archivage côté Odoo ;
  * un lead Odoo ne bouge que si son étape actuelle, ramenée aux 6 étapes
    canoniques, DIFFÈRE de l'étape ERP — le détail fin des colonnes Odoo
    déjà cohérentes n'est jamais écrasé ;
  * ids d'étapes Odoo résolus à l'exécution par leur nom, jamais codés en dur.

Sans ODOO_SYNC_URL + ODOO_SYNC_API_KEY, ne fait RIEN (usage + sortie propre).
"""
from django.core.management.base import BaseCommand, CommandError

from apps.crm.odoo_sync import (
    OdooConfig, OdooSyncError, compute_push_moves, fetch_odoo_leads,
    push_stage_moves)


class Command(BaseCommand):
    help = ("ERP → Odoo : pousse les étapes des leads vers Odoo (JSON-2, "
            "stage_id uniquement). À blanc par défaut ; --apply pour écrire.")

    def add_arguments(self, parser):
        parser.add_argument(
            '--company', dest='company', default=None,
            help="Slug ou id de la société source (obligatoire).")
        parser.add_argument(
            '--apply', action='store_true',
            help="Écrit réellement dans Odoo (sinon : à blanc).")

    def _resolve_company(self, raw):
        from authentication.models import Company
        if raw is None:
            return None
        company = Company.objects.filter(slug=raw).first()
        if company is None and str(raw).isdigit():
            company = Company.objects.filter(pk=int(raw)).first()
        return company

    def handle(self, *args, **options):
        config = OdooConfig()
        if config.incomplete:
            self.stdout.write(self.style.WARNING(
                "Config Odoo absente — rien à pousser.\n"
                "Renseigner ODOO_SYNC_URL et ODOO_SYNC_API_KEY (clé créée "
                "dans Odoo : Préférences ▸ Sécurité du compte ▸ Nouvelle "
                "clé API), puis relancer."))
            return
        company = self._resolve_company(options.get('company'))
        if company is None:
            raise CommandError(
                "--company <slug-ou-id> est obligatoire et doit correspondre "
                "à une société existante.")

        try:
            odoo_leads, _tags = fetch_odoo_leads(config)
        except OdooSyncError as exc:
            raise CommandError(str(exc))
        self.stdout.write(f"{len(odoo_leads)} lead(s) lus dans Odoo.")

        moves, coherents, non_rapproches = compute_push_moves(
            company, odoo_leads)
        total = sum(len(ids) for ids in moves.values())
        for nom, ids in sorted(moves.items()):
            self.stdout.write(f"→ « {nom} » : {len(ids)} lead(s)")
        self.stdout.write(
            f"{coherents} cohérent(s), {non_rapproches} non rapproché(s), "
            f"{total} à déplacer.")

        if not options.get('apply'):
            self.stdout.write(self.style.WARNING(
                "À blanc — rien n'a été écrit dans Odoo. "
                "Relancer avec --apply pour appliquer."))
            return
        try:
            ecrits = push_stage_moves(config, moves)
        except OdooSyncError as exc:
            raise CommandError(str(exc))
        self.stdout.write(self.style.SUCCESS(
            f"{ecrits} lead(s) déplacé(s) dans Odoo."))
