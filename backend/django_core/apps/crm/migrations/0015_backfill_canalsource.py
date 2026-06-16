"""Backfill CanalSource depuis l'ancien enum Lead.Canal + valeurs distinctes.

Additif : crée la liste de référence éditable par société. On seede les
libellés de l'ancien enum (dont `site_web`, protégé) et on ajoute tout `canal`
distinct déjà présent sur des leads mais absent du seed (rien perdu).
"""
from django.db import migrations

# Miroir de l'ancien Lead.Canal (clé → libellé FR), dans l'ordre de l'enum.
LEGACY_CANALS = [
    ('meta_ads', 'Publicité Meta'),
    ('whatsapp_ctwa', 'WhatsApp/CTWA'),
    ('site_web', 'Site web'),
    ('reference', 'Référence'),
    ('telephone', 'Téléphone'),
    ('walk_in', 'Visite/Walk-in'),
    ('autre', 'Autre'),
]


def backfill(apps, schema_editor):
    Company = apps.get_model('authentication', 'Company')
    Lead = apps.get_model('crm', 'Lead')
    CanalSource = apps.get_model('crm', 'CanalSource')

    # Sociétés explicites + le bucket "sans société" (company=None) si des
    # leads y vivent.
    company_ids = set(Company.objects.values_list('id', flat=True))
    if Lead.objects.filter(company__isnull=True).exists():
        company_ids.add(None)

    for cid in company_ids:
        ordre = 0
        seen_keys = set()
        for key, label in LEGACY_CANALS:
            ordre += 10
            obj, created = CanalSource.objects.get_or_create(
                company_id=cid, key=key,
                defaults={'label': label, 'ordre': ordre},
            )
            seen_keys.add(key)
        # Valeurs `canal` distinctes déjà sur des leads mais hors seed.
        distinct = (
            Lead.objects.filter(company_id=cid)
            .exclude(canal__isnull=True).exclude(canal='')
            .values_list('canal', flat=True).distinct()
        )
        for canal in distinct:
            if canal in seen_keys:
                continue
            ordre += 10
            CanalSource.objects.get_or_create(
                company_id=cid, key=canal,
                defaults={'label': canal, 'ordre': ordre},
            )
            seen_keys.add(canal)


def noop(apps, schema_editor):
    # Réversible sans perte : on ne supprime pas la liste (additif).
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('crm', '0014_canalsource'),
        ('authentication', '0008_customuser_avatar_key_customuser_poste'),
    ]

    operations = [
        migrations.RunPython(backfill, noop),
    ]
