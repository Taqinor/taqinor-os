# VREF (fondateur 07/09/2026) — ville ERP de rattachement d'un lead dont la
# ville tapée n'est pas au gazetier (écran « Vérifier la ville »).
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('crm', '0094_lead_lien_maps'),
    ]

    operations = [
        migrations.AddField(
            model_name='lead',
            name='ville_reference',
            field=models.CharField(
                blank=True, default='', max_length=120,
                verbose_name='Ville ERP de rattachement'),
        ),
    ]
