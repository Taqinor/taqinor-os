"""FG5 — Commande de seed des jours fériés fixes marocains.

Usage :
    python manage.py seed_ma_holidays
    python manage.py seed_ma_holidays --company-id 3   # une société précise

Idempotente + additive : ne crée une ligne que si elle n'existe pas déjà
(basé sur la contrainte unique company + date + nom). Ne modifie jamais
les lignes existantes (prix, noms, etc. laissés intacts).

CAD40 — les fêtes MOBILES (Aïd al-Fitr, Aïd al-Adha, Nouvel An hégirien,
Aïd al-Mawlid) ne sont plus muettes : le seeder pose celles que
``core.calendar`` CONNAÎT pour l'année demandée, en ``recurrent_annuel=
False`` (une date lunaire ne se répète JAMAIS au même jour grégorien).
Rien n'est calculé — une année sans dates connues n'en reçoit aucune, et la
commande le DIT, pour qu'un humain les saisisse (Paramètres → Localisation →
Fêtes mobiles). C'est la différence entre « pas encore saisi » et « deviné ».
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


def seed_holidays_for_company(company, *, annee=None):
    """CAD40 — pose les 9 fériés FIXES + les fêtes MOBILES connues de
    ``annee`` sur une société. Idempotent, additif, jamais destructif.

    Renvoie ``(crees, deja_presents, mobiles_manquantes)`` :
    ``mobiles_manquantes`` vaut ``True`` quand aucune date mobile n'est
    connue pour cette année — il faut alors les SAISIR, jamais les deviner.
    """
    from core.calendar import movable_holidays

    from apps.notifications.models import Holiday

    if annee is None:
        from core.dates import aujourd_hui_local
        annee = aujourd_hui_local().year

    crees = deja = 0
    for month, day, name in MA_FIXED_HOLIDAYS:
        _, created = Holiday.objects.get_or_create(
            company=company,
            date=datetime.date(_REF_YEAR, month, day),
            nom=name,
            defaults={'recurrent_annuel': True},
        )
        crees, deja = (crees + 1, deja) if created else (crees, deja + 1)

    mobiles = movable_holidays(annee)
    for jour, name in sorted(mobiles.items()):
        # `recurrent_annuel=False` : une date lunaire ne retombe JAMAIS au
        # même jour grégorien l'année suivante (CAD42).
        _, created = Holiday.objects.get_or_create(
            company=company, date=jour, nom=name,
            defaults={'recurrent_annuel': False},
        )
        crees, deja = (crees + 1, deja) if created else (crees, deja + 1)

    return crees, deja, not mobiles


class Command(BaseCommand):
    help = (
        "Seed les 9 jours fériés fixes marocains + les fêtes mobiles CONNUES "
        "de l'année pour toutes les sociétés (ou une seule si --company-id "
        "est fourni). Idempotent + additif."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--company-id', type=int, default=None,
            help="ID de la société à seeder (défaut : toutes les sociétés).")
        parser.add_argument(
            '--annee', type=int, default=None,
            help="Année des fêtes MOBILES à poser (défaut : l'année en "
                 "cours). Aucune date n'est calculée : une année inconnue "
                 "n'en reçoit aucune.")

    def handle(self, *args, **options):
        from authentication.models import Company

        company_id = options.get('company_id')
        if company_id:
            companies = Company.objects.filter(pk=company_id)
            if not companies.exists():
                self.stderr.write(self.style.ERROR(
                    f'Société {company_id} introuvable.'))
                return
        else:
            companies = Company.objects.all()

        annee = options.get('annee')
        if annee is None:
            from core.dates import aujourd_hui_local
            annee = aujourd_hui_local().year

        created_total = 0
        skipped_total = 0
        mobiles_manquantes = False

        for company in companies:
            crees, deja, manquantes = seed_holidays_for_company(
                company, annee=annee)
            created_total += crees
            skipped_total += deja
            mobiles_manquantes = mobiles_manquantes or manquantes

        self.stdout.write(self.style.SUCCESS(
            f"seed_ma_holidays : {created_total} jour(s) créé(s), "
            f"{skipped_total} déjà présent(s) (fixes + fêtes mobiles "
            f"connues de {annee})."
        ))
        if mobiles_manquantes:
            # CAD40 — on ne devine JAMAIS une date hégirienne : on réclame.
            self.stdout.write(self.style.WARNING(
                f"Aucune fête mobile connue pour {annee} : saisissez-les à "
                f"la main (Paramètres → Localisation → Fêtes mobiles). Tant "
                f"qu'elles manquent, une touche de cadence peut tomber le "
                f"jour de l'Aïd."
            ))
