# GPS7 (fondateur 07/09/2026) — lien Google Maps du lead (provenance GPS).
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('crm', '0093_mry11_tag_injoignable_6_appels'),
    ]

    operations = [
        migrations.AddField(
            model_name='lead',
            name='lien_maps',
            field=models.URLField(
                blank=True, default='', max_length=500,
                verbose_name='Lien Google Maps'),
        ),
    ]
