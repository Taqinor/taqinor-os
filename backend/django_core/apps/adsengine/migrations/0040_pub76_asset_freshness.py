# PUB76 — Expiration / rafraîchissement des assets : champs additifs de
# fraîcheur (version de faits citée, dates de revue, drapeau « à revoir »)
# posés par le job hebdo quand un chiffre cité devient périmé (FactTable révisée)
# ou qu'une créa saisonnière sort de sa fenêtre.
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('adsengine', '0039_pub75_consent_record'),
    ]

    operations = [
        migrations.AddField(
            model_name='creativeasset',
            name='facts_version',
            field=models.PositiveIntegerField(blank=True, null=True, verbose_name='Version de faits citée'),
        ),
        migrations.AddField(
            model_name='creativeasset',
            name='expires_at',
            field=models.DateField(blank=True, null=True, verbose_name="Date d'expiration"),
        ),
        migrations.AddField(
            model_name='creativeasset',
            name='review_after',
            field=models.DateField(blank=True, null=True, verbose_name='À revoir après le'),
        ),
        migrations.AddField(
            model_name='creativeasset',
            name='needs_review',
            field=models.BooleanField(default=False, verbose_name='À revoir'),
        ),
        migrations.AddField(
            model_name='creativeasset',
            name='review_reason',
            field=models.CharField(blank=True, default='', max_length=40, verbose_name='Motif de revue'),
        ),
    ]
