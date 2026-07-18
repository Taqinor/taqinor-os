"""Reset (wipe + re-seed) a single demo tenant — NTDMO6.

Deletes ONE demo company by ``--slug`` (via the ORM only — NEVER raw SQL) then
re-invokes ``seed_demo_company`` with the same slug, producing an identical
record count (the seed is deterministic, ``Faker.seed``/fixed RNG).

``company.delete()`` alone is NOT enough: many business models FK to
``Produit``/``Client`` (themselves ``CASCADE`` from ``Company``) with
``on_delete=PROTECT`` (``LigneDevis.produit``, ``Devis.client``,
``Facture.client``, ``MouvementStock.produit``…). Django's deletion collector
raises ``ProtectedError`` for those regardless of whether the referencing row
is ALSO being cascaded away in the same operation — PROTECT only cares that a
referencing row currently exists. ``_delete_cascading`` retries: on
``ProtectedError`` it deletes the exact blocking rows the exception reports
(``e.protected_objects`` — already scoped to the ids being deleted, so always
safe/company-local) and retries, recursing to handle chained PROTECT FKs
(e.g. a ``Facture`` protecting a ``Client`` while itself being protected by a
``Paiement``). Bounded depth guards against a genuine cycle.

Safety guards (to never wipe a real company by accident):
  * ``--slug`` is REQUIRED (no default) — the caller must name the tenant.
  * the slug MUST contain ``demo`` — otherwise the command refuses.

Run:
  python manage.py reset_demo_company --slug taqinor-demo-full
"""
from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.db.models import ProtectedError


def _delete_cascading(obj, max_depth=60):
    """Delete ``obj``, recursively clearing any PROTECT-blocking rows first.

    Never raw SQL — every deletion goes through the ORM's own ``.delete()``.
    ``ProtectedError.protected_objects`` is the queryset of rows actually
    blocking THIS deletion (already filtered to the ids being removed), so
    deleting them first is always scoped/safe, never a blanket company-wide
    wipe of the blocking model."""
    for _ in range(max_depth):
        try:
            obj.delete()
            return
        except ProtectedError as exc:
            for blocker in list(exc.protected_objects):
                _delete_cascading(blocker, max_depth=max_depth - 1)
    # Final attempt: surfaces a real (unresolvable/cyclic) PROTECT chain
    # instead of silently giving up.
    obj.delete()


class Command(BaseCommand):
    help = ('Wipe and re-seed a single demo company (by --slug). Refuses any '
            "slug that does not contain 'demo'.")

    def add_arguments(self, parser):
        # Pas de défaut : le slug DOIT être fourni explicitement (garde-fou).
        parser.add_argument(
            '--slug', required=True,
            help='Slug de la société démo à réinitialiser (doit contenir '
                 "'demo').")
        parser.add_argument(
            '--force', action='store_true',
            help='Transmis à seed_demo_company (re-seed hors DEBUG).')

    def handle(self, *args, **options):
        slug = options['slug']
        if 'demo' not in slug.lower():
            raise CommandError(
                f"Refus : le slug « {slug} » ne contient pas 'demo'. "
                "reset_demo_company ne réinitialise QUE des sociétés de "
                "démonstration (garde-fou anti-effacement d'une société réelle).")

        from authentication.models import Company, CustomUser

        company = Company.objects.filter(slug=slug).first()
        if company is not None:
            with transaction.atomic():
                # CustomUser.company est SET_NULL → supprimer explicitement les
                # comptes de la société démo (sinon ils seraient orphelinés).
                CustomUser.objects.filter(company=company).delete()
                # ORM only — jamais de SQL brut. `_delete_cascading` gère les
                # FK PROTECT (Produit/Client…) que le simple `company.delete()`
                # CASCADE ne peut pas traverser seul (voir docstring module).
                _delete_cascading(company)
            self.stdout.write(self.style.WARNING(
                f'Société démo "{slug}" vidée.'))
        else:
            self.stdout.write(self.style.WARNING(
                f'Aucune société "{slug}" existante — création directe.'))

        call_command('seed_demo_company', slug=slug,
                     force=options.get('force', False), verbosity=0)
        self.stdout.write(self.style.SUCCESS(
            f'Société démo "{slug}" réinitialisée (vidée puis re-peuplée).'))
