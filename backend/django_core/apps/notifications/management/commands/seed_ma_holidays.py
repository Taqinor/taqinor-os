"""FG5 — Commande de seed des jours fériés fixes marocains.

Usage :
    python manage.py seed_ma_holidays
    python manage.py seed_ma_holidays --company-id 3   # une société précise

Idempotente + additive : ne crée une ligne que si elle n'existe pas déjà
(basé sur la contrainte unique company + date + nom). Ne modifie jamais
les lignes existantes (prix, noms, etc. laissés intacts).

Fêtes islamiques (Id al-Fitr, Id al-Adha, Mawlid, etc.) : calendrier LUNAIRE
— leur date varie chaque année grégorienne. Elles sont DÉLIBÉRÉMENT EXCLUES
du seed automatique et doivent être saisies manuellement via l'API ou l'admin.
"""
import datetime
import logging

from django.core.management.base import BaseCommand

logger = logging.getLogger(__name__)

# 9 jours fériés FIXES marocains (mois, jour, libellé).
# Source : https://www.mmsp.gov.ma/fr/calendrier-feries.aspx
MA_FIXED_HOLIDAYS = [
    (1, 1,  "Jour de l'An"),
    (1, 11, "Manifeste de l'Indépendance"),
    (5, 1,  "Fête du Travail"),
    (7, 30, "Fête du Trône"),
    (8, 14, "Oued Ed-Dahab"),
    (8, 20, "Révolution du Roi et du Peuple"),
    (8, 21, "Fête de la Jeunesse"),
    (11, 6, "Marche Verte"),
    (11, 18, "Fête de l'Indépendance"),
]

# Année de référence stockée dans le champ `date` (recurrent_annuel=True →
# seuls le mois + le jour sont utilisés par les helpers).
_REF_YEAR = 2024


class Command(BaseCommand):
    help = (
        "Seed les 9 jours fériés fixes marocains pour toutes les sociétés "
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
            for month, day, name in MA_FIXED_HOLIDAYS:
                ref_date = datetime.date(_REF_YEAR, month, day)
                _, created = Holiday.objects.get_or_create(
                    company=company,
                    date=ref_date,
                    nom=name,
                    defaults={'recurrent_annuel': True},
                )
                if created:
                    created_total += 1
                else:
                    skipped_total += 1

        self.stdout.write(self.style.SUCCESS(
            f"seed_ma_holidays : {created_total} jour(s) créé(s), "
            f"{skipped_total} déjà présent(s). "
            f"Note : les fêtes islamiques (lunaires) doivent être saisies manuellement."
        ))
