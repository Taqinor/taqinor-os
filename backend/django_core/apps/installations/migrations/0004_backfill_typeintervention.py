"""Backfill TypeIntervention depuis l'ancien enum Intervention.Type.

Additif : crée la liste de référence éditable par société. On seede les
libellés de l'ancien enum et on ajoute tout `type_intervention` distinct déjà
présent sur des ordres de travail mais absent du seed (rien perdu).
"""
from django.db import migrations

# Miroir de l'ancien Intervention.Type (clé → libellé FR), ordre de l'enum.
LEGACY_TYPES = [
    ('pose', 'Pose'),
    ('raccordement', 'Raccordement'),
    ('mise_en_service', 'Mise en service'),
    ('controle', 'Contrôle'),
    ('depannage', 'Dépannage'),
]


def backfill(apps, schema_editor):
    Company = apps.get_model('authentication', 'Company')
    Intervention = apps.get_model('installations', 'Intervention')
    TypeIntervention = apps.get_model('installations', 'TypeIntervention')

    company_ids = set(Company.objects.values_list('id', flat=True))
    if Intervention.objects.filter(company__isnull=True).exists():
        company_ids.add(None)

    for cid in company_ids:
        ordre = 0
        seen = set()
        for key, label in LEGACY_TYPES:
            ordre += 10
            TypeIntervention.objects.get_or_create(
                company_id=cid, key=key,
                defaults={'label': label, 'ordre': ordre},
            )
            seen.add(key)
        distinct = (
            Intervention.objects.filter(company_id=cid)
            .exclude(type_intervention__isnull=True)
            .exclude(type_intervention='')
            .values_list('type_intervention', flat=True).distinct()
        )
        for t in distinct:
            if t in seen:
                continue
            ordre += 10
            TypeIntervention.objects.get_or_create(
                company_id=cid, key=t,
                defaults={'label': t, 'ordre': ordre},
            )
            seen.add(t)


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('installations', '0003_typeintervention'),
        ('authentication', '0008_customuser_avatar_key_customuser_poste'),
    ]

    operations = [
        migrations.RunPython(backfill, noop),
    ]
