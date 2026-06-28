# Generated for FLOTTE9 — catégorie de permis requise par véhicule
# (contrôle « permis valide / catégorie » à l'affectation).

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("flotte", "0007_affectationconducteur"),
    ]

    operations = [
        migrations.AddField(
            model_name="vehicule",
            name="categorie_permis_requise",
            field=models.CharField(
                blank=True,
                help_text="Ex. : B, C, CE, D… Vide = aucune exigence de "
                "catégorie.",
                max_length=30,
                verbose_name="Catégorie de permis requise",
            ),
        ),
    ]
