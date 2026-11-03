from django.db import migrations, models


class Migration(migrations.Migration):
    """ACVI66 — l'état ``annulee`` d'une visite. Aucune reprise : les visites
    déjà annulées (brouillon sans date) restent telles quelles."""

    dependencies = [
        ('visites', '0008_visiteterrain_retour_terrain'),
    ]

    operations = [
        migrations.AlterField(
            model_name='visiteterrain',
            name='statut',
            field=models.CharField(
                choices=[
                    ('brouillon', 'Brouillon'),
                    ('en_cours', 'En cours'),
                    ('terminee', 'Terminée'),
                    ('validee', 'Validée (feu vert)'),
                    ('a_refaire', 'À refaire'),
                    ('annulee', 'Annulée'),
                ],
                default='brouillon', max_length=12,
                verbose_name='Statut de la visite'),
        ),
    ]
