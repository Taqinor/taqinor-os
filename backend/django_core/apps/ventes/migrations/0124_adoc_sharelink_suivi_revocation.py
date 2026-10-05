from django.db import migrations, models

# ADOC131 (D-ADOC-4) — suivi public prolongé jusqu'à la réception + 90 jours,
# et révocable. Deux DateTimeField nullables : additif, aucun backfill, aucun
# lien existant modifié. Revert : ``migrate ventes 0123``.


class Migration(migrations.Migration):

    dependencies = [
        ('ventes', '0123_agr603_regime_hors_reseau'),
    ]

    operations = [
        migrations.AddField(
            model_name='sharelink',
            name='suivi_prolonge_le',
            field=models.DateTimeField(
                blank=True, null=True,
                verbose_name='Suivi prolongé depuis (acceptation)'),
        ),
        migrations.AddField(
            model_name='sharelink',
            name='revoque_le',
            field=models.DateTimeField(
                blank=True, null=True, verbose_name='Lien révoqué le'),
        ),
    ]
