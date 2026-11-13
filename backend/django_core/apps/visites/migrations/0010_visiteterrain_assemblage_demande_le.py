from django.db import migrations, models


class Migration(migrations.Migration):
    """ACEL77 — horodatage de la demande d'assemblage des photos du toit."""

    dependencies = [
        ('visites', '0009_visiteterrain_statut_annulee'),
    ]

    operations = [
        migrations.AddField(
            model_name='visiteterrain',
            name='assemblage_demande_le',
            field=models.DateTimeField(
                blank=True, null=True,
                verbose_name='Assemblage demandé le'),
        ),
    ]
