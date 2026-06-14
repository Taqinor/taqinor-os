"""Types d'activité par défaut (style Odoo) pour chaque société existante.

Idempotent : get_or_create par (company, nom). Réversible (no-op au retour).
"""
from django.db import migrations

DEFAULTS = [
    ('Appel', '📞', 10, 0),
    ('Email', '✉️', 20, 0),
    ('Réunion', '👥', 30, 0),
    ('Relance', '📅', 40, 3),
    ('À faire', '✔️', 50, 0),
]


def seed(apps, schema_editor):
    Company = apps.get_model('authentication', 'Company')
    ActivityType = apps.get_model('records', 'ActivityType')
    companies = list(Company.objects.all()) or [None]
    for company in companies:
        for nom, icone, ordre, delai in DEFAULTS:
            ActivityType.objects.get_or_create(
                company=company, nom=nom,
                defaults={'icone': icone, 'ordre': ordre,
                          'delai_defaut_jours': delai, 'est_systeme': True})


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('records', '0001_initial'),
        ('authentication', '0001_initial'),
    ]

    operations = [migrations.RunPython(seed, noop)]
