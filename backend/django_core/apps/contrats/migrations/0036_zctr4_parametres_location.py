# ZCTR4 — Réglages de location : durée minimale, temps de sécurité (padding)
# & frais de retard par défaut. Nouveau modèle `ParametresLocation`, singleton
# par société (OneToOne). Purement additif : une société sans ligne créée
# conserve exactement le comportement XCTR17/19 (toutes les valeurs NULL/0).

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("authentication", "0001_initial"),
        ("contrats", "0035_zctr3_motif_resiliation"),
    ]

    operations = [
        migrations.CreateModel(
            name="ParametresLocation",
            fields=[
                ("id", models.BigAutoField(
                    auto_created=True, primary_key=True,
                    serialize=False, verbose_name="ID")),
                ("duree_minimale_jours", models.PositiveIntegerField(
                    blank=True, null=True,
                    verbose_name="Durée minimale (jours)")),
                ("temps_securite_heures", models.PositiveIntegerField(
                    default=0,
                    verbose_name="Temps de sécurité / padding (heures)")),
                ("frais_retard_jour_defaut", models.DecimalField(
                    blank=True, decimal_places=2, max_digits=10, null=True,
                    verbose_name="Frais de retard / jour par défaut")),
                ("date_creation", models.DateTimeField(
                    auto_now_add=True, verbose_name="Créé le")),
                ("date_modification", models.DateTimeField(
                    auto_now=True, verbose_name="Modifié le")),
                ("company", models.OneToOneField(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="parametres_location",
                    to="authentication.company", verbose_name="Société")),
            ],
            options={
                "verbose_name": "Paramètres de location",
                "verbose_name_plural": "Paramètres de location",
            },
        ),
    ]
