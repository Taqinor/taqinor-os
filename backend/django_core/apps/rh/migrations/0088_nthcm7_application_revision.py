# NTHCM7 — application d'un cycle de révision clos vers `Remuneration`.
#
# ADDITIF : `date_effet` sur le cycle + les deux marqueurs d'idempotence de la
# proposition. Aucun champ existant n'est touché ; les lignes existantes
# restent `appliquee=False` / `date_application=NULL`.
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('rh', '0087_nthcm5_cycle_revision_salariale'),
    ]

    operations = [
        migrations.AddField(
            model_name='cyclerevisionsalariale',
            name='date_effet',
            field=models.DateField(
                blank=True, null=True,
                verbose_name="Date d'effet des révisions"),
        ),
        migrations.AddField(
            model_name='propositionrevision',
            name='appliquee',
            field=models.BooleanField(
                default=False, verbose_name='Appliquée'),
        ),
        migrations.AddField(
            model_name='propositionrevision',
            name='date_application',
            field=models.DateTimeField(
                blank=True, null=True, verbose_name="Date d'application"),
        ),
    ]
