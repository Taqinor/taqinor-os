"""HOLIDAY-PAYS (complément NTI18N13) — Commande de seed des jours fériés
fixes ivoiriens.

Usage :
    python manage.py seed_holidays_ci
    python manage.py seed_holidays_ci --company-id 3   # une société précise

Idempotente + additive : ne crée une ligne que si elle n'existe pas déjà
(basé sur la contrainte unique company + date + nom). Ne modifie jamais
les lignes existantes.

Fêtes MOBILES (islamiques : Aïd el-Fitr, Aïd el-Adha, Maouloud ;
chrétiennes calées sur Pâques : Lundi de Pâques, Ascension, Lundi de
Pentecôte) : DÉLIBÉRÉMENT EXCLUES du seed automatique — même politique que
``seed_ma_holidays`` — et doivent être saisies manuellement via l'API ou
l'admin.
"""
import datetime
import logging

from django.core.management.base import BaseCommand

logger = logging.getLogger(__name__)

# 6 jours fériés FIXES ivoiriens (mois, jour, libellé).
CI_FIXED_HOLIDAYS = [
    (1, 1,  "Jour de l'An"),
    (5, 1,  "Fête du Travail"),
    (8, 7,  "Fête de l'Indépendance"),
    (8, 15, "Assomption"),
    (11, 1, "Toussaint"),
    (12, 25, "Noël"),
]

# Année de référence stockée dans le champ `date` (recurrent_annuel=True →
# seuls le mois + le jour sont utilisés par les helpers).
_REF_YEAR = 2024

PAYS = 'CI'


class Command(BaseCommand):
    help = (
        "Seed les 6 jours fériés fixes ivoiriens pour toutes les sociétés "
        "(ou une seule si --company-id est fourni). Idempotent + additif."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--company-id', type=int, default=None,
            help="ID de la société à seeder (défaut : toutes les sociétés).")

    def handle(self, *args, **options):
        from authentication.models import Company
        from apps.notifications.models import Holiday

        company_id = options.get('company_id')
        if company_id:
            companies = Company.objects.filter(pk=company_id)
            if not companies.exists():
                self.stderr.write(self.style.ERROR(
                    f'Société {company_id} introuvable.'))
                return
        else:
            companies = Company.objects.all()

        created_total = 0
        skipped_total = 0

        for company in companies:
            for month, day, name in CI_FIXED_HOLIDAYS:
                ref_date = datetime.date(_REF_YEAR, month, day)
                _, created = Holiday.objects.get_or_create(
                    company=company,
                    date=ref_date,
                    nom=name,
                    defaults={'recurrent_annuel': True, 'pays': PAYS},
                )
                if created:
                    created_total += 1
                else:
                    skipped_total += 1

        self.stdout.write(self.style.SUCCESS(
            f"seed_holidays_ci : {created_total} jour(s) créé(s), "
            f"{skipped_total} déjà présent(s). "
            f"Note : les fêtes mobiles (islamiques et chrétiennes calées "
            f"sur Pâques) doivent être saisies manuellement."
        ))
