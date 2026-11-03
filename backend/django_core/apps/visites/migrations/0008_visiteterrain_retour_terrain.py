from django.db import migrations, models


class Migration(migrations.Migration):
    """ACVI55 — le retour terrain séparé des notes de planification. Aucune
    reprise : ``notes`` n'a jamais été saisi depuis un écran terrain."""

    dependencies = [
        ('visites', '0007_ciq604_validation_horodatee'),
    ]

    operations = [
        migrations.AddField(
            model_name='visiteterrain',
            name='retour_terrain',
            field=models.TextField(
                blank=True, default='', verbose_name='Retour terrain'),
        ),
    ]
