from django.db import migrations, models


class Migration(migrations.Migration):
    """CRX2 — marqueur de source sur ``WebsiteLeadPayload``.

    Le modèle stockait déjà « la charge utile brute AVANT tout mapping » pour
    le seul intake site web. Le webhook Meta Lead Ads, lui, ne persistait
    RIEN : un échec du Graph API (ou du mapping) perdait le lead
    définitivement, sans trace ni rejeu — l'exact contraire de la garantie
    « jamais perdre un lead » que le site possède depuis QX16.

    Plutôt qu'un jumeau (deuxième table, deuxième viewset, deuxième écran),
    on réutilise CE modèle avec un discriminant. Migration purement ADDITIVE
    et sans risque : une colonne avec défaut, aucune donnée retouchée — toutes
    les lignes existantes viennent du site (seul émetteur avant CRX2) et
    prennent donc le bon défaut ``website``.

    Réversible : la migration inverse retire simplement la colonne.
    """

    dependencies = [
        ('crm', '0088_crx35_retrait_playbook_bloquant'),
    ]

    operations = [
        migrations.AddField(
            model_name='websiteleadpayload',
            name='source',
            field=models.CharField(
                choices=[('website', 'Site web'),
                         ('meta_lead_ads', 'Meta Lead Ads')],
                db_index=True, default='website', max_length=32),
        ),
        migrations.AlterModelOptions(
            name='websiteleadpayload',
            options={'ordering': ['-received_at'],
                     'verbose_name': 'Payload lead entrant',
                     'verbose_name_plural': 'Payloads leads entrants'},
        ),
    ]
