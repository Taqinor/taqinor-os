"""Seed standard defect codes (CodeDefaut) for the solar QHSE Pareto (XQHS4).

Creates a sensible referential of defect codes — one per common solar-install
failure family (produit / pose DC / pose AC / structure / document /
fournisseur) — for every company (or a single ``--company`` slug).

Idempotent and strictly additive, modelled on ``seed_itp_solaire``:
  * each code is matched by the stable key ``(company, code)`` via
    ``get_or_create`` — re-running creates nothing new;
  * a code already present (even with edited fields) is left untouched.

Run (inside the django_core container or with DB env vars set):
  python manage.py seed_codes_defaut_solaire            # all companies
  python manage.py seed_codes_defaut_solaire --company taqinor-demo
"""
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction


# (code, libelle, famille) — famille mirrors CodeDefaut.Famille.choices values.
CODES_DEFAUT = [
    ('PRD-CASSE', 'Panneau/onduleur cassé ou endommagé au transport', 'produit'),
    ('PRD-NONCONF', "Référence livrée non conforme à la commande", 'produit'),
    ('PRD-DEFAUT', 'Défaut de fabrication constaté', 'produit'),
    ('DC-SERRAGE', 'Couple de serrage DC non conforme', 'pose_dc'),
    ('DC-POLARITE', 'Erreur de polarité / câblage DC', 'pose_dc'),
    ('DC-ETANCHE', "Défaut d'étanchéité des connecteurs DC", 'pose_dc'),
    ('AC-PROTECTION', 'Calibre de protection AC non conforme', 'pose_ac'),
    ('AC-TERRE', 'Continuité de terre / liaison équipotentielle défaillante',
     'pose_ac'),
    ('AC-CABLAGE', 'Erreur de câblage AC', 'pose_ac'),
    ('STR-FIXATION', 'Fixation de structure non conforme', 'structure'),
    ('STR-ALIGNEMENT', 'Défaut d\'alignement / calepinage', 'structure'),
    ('STR-CORROSION', 'Corrosion ou défaut de traitement de la structure',
     'structure'),
    ('DOC-MANQUANT', "Document manquant (note de calcul, PV, garantie…)",
     'document'),
    ('DOC-INCOMPLET', 'Dossier de réception incomplet', 'document'),
    ('FRS-RETARD', 'Retard de livraison fournisseur', 'fournisseur'),
    ('FRS-QUALITE', 'Non-conformité qualité imputable au fournisseur',
     'fournisseur'),
    ('AUTRE', 'Autre défaut (non classé)', 'autre'),
]


class Command(BaseCommand):
    help = (
        "Seed standard defect codes (CodeDefaut) for the solar QHSE Pareto "
        "(XQHS4). Idempotent and additive — safe to re-run."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--company', dest='company', default=None,
            help='Company slug to seed. Omit to seed all companies.')

    @transaction.atomic
    def handle(self, *args, **options):
        from authentication.models import Company
        from apps.qhse.models import CodeDefaut

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

        codes_created = 0
        for company in companies:
            for code, libelle, famille in CODES_DEFAUT:
                _, is_new = CodeDefaut.objects.get_or_create(
                    company=company,
                    code=code,
                    defaults={
                        'libelle': libelle,
                        'famille': famille,
                        'actif': True,
                    },
                )
                if is_new:
                    codes_created += 1

        self.stdout.write(self.style.SUCCESS(
            f"Codes de défaut seedés pour {len(companies)} société(s) : "
            f"{codes_created} code(s) créé(s) (existants laissés intacts)."))
