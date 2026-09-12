"""NTCON27 — archivage (jamais suppression) des réserves levées anciennes.

Migration ADDITIVE : deux colonnes sur ``ReserveChantier`` (drapeau + date) et
un réglage de durée sur ``ParametresBtpChantier``. Les défauts (``False`` /
``NULL`` / 24 mois) reproduisent exactement le comportement actuel tant que le
balayage n'a pas tourné — aucun changement au déploiement.
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('btp_chantier', '0011_ntcon25_parametres_btp'),
    ]

    operations = [
        migrations.AddField(
            model_name='reservechantier',
            name='archivee',
            field=models.BooleanField(
                default=False, verbose_name='Archivée'),
        ),
        migrations.AddField(
            model_name='reservechantier',
            name='archivee_le',
            field=models.DateTimeField(
                blank=True, null=True, verbose_name='Archivée le'),
        ),
        migrations.AddField(
            model_name='parametresbtpchantier',
            name='delai_archivage_reserves_levees_mois',
            field=models.PositiveIntegerField(
                default=24,
                verbose_name='Archiver les réserves levées après (mois)'),
        ),
    ]
