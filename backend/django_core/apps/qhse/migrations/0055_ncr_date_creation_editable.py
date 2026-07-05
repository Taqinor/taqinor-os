import django.utils.timezone
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('qhse', '0054_xqhs26_veille_reglementaire'),
    ]

    operations = [
        migrations.AlterField(
            model_name='nonconformite',
            name='date_creation',
            field=models.DateTimeField(
                default=django.utils.timezone.now, verbose_name='Créé le'),
        ),
    ]
