# CADV11 — date de rappel convenue sur la touche (additif, réversible).

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('crm', '0152_parc_champs_lead'),
    ]

    operations = [
        migrations.AddField(
            model_name='relanceetape',
            name='rappel_convenu_le',
            field=models.DateField(blank=True, null=True, verbose_name='Date de rappel convenue'),
        ),
    ]
