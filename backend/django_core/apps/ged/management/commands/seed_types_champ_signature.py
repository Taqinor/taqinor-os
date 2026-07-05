"""Seed the 5 base signature field types (ZGED4) per company.

Odoo Sign ships default field types (Signature/Initials/Date/Text/Checkbox).
Here they are seeded into the editable `TypeChampSignature` catalogue so they
stay available even if an admin edits/deletes a custom one — a `ChampSignature`
with no `type_champ_ref` still works via its legacy `type_champ` text field
(rétrocompatibilité, XGED3).

Idempotent and strictly additive — matched by the stable key
``(company, code)`` via ``get_or_create``: re-running creates nothing new and
never touches an already-edited row.

Run (inside the django_core container or with DB env vars set):
  python manage.py seed_types_champ_signature                     # all companies
  python manage.py seed_types_champ_signature --company taqinor-demo
"""
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.ged.models import TYPE_CHAMP_SIGNATURE_SEED_DE_BASE, TypeChampSignature


def seed_types_champ_signature_for_company(company):
    """Seed the 5 base field types for one company (idempotent, additive).

    Returns the number of NEW rows created. Existing rows (matched by
    ``(company, code)``) are left untouched."""
    created = 0
    for spec in TYPE_CHAMP_SIGNATURE_SEED_DE_BASE:
        _, is_new = TypeChampSignature.objects.get_or_create(
            company=company, code=spec['code'],
            defaults={
                'libelle': spec['libelle'],
                'mode_saisie': spec['mode_saisie'],
                'actif': True,
            },
        )
        if is_new:
            created += 1
    return created


class Command(BaseCommand):
    help = (
        "Seed the 5 base signature field types (signature/initiales/date/"
        "texte/case) per company or a single --company (idempotent, "
        "additive only)."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--company', default=None,
            help="Slug of a single company to seed (default: all companies).",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        from authentication.models import Company

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
                "No company to seed — nothing done."))
            return

        total_created = 0
        for company in companies:
            total_created += seed_types_champ_signature_for_company(company)

        self.stdout.write(self.style.SUCCESS(
            f"Types de champ de signature seeded for {len(companies)} "
            f"société(s): {total_created} type(s) created "
            "(existing rows left untouched)."))
