# Generated for XFLT14 — Garanties véhicule & pièces + alerte réparation sous
# garantie. Crée ``GarantieFlotte`` et ajoute ``OrdreReparation.sous_garantie``
# (additif). Multi-société.

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("flotte", "0038_inspectionvehicule"),
    ]

    operations = [
        migrations.AddField(
            model_name="ordrereparation",
            name="sous_garantie",
            field=models.BooleanField(
                default=False, verbose_name="Sous garantie (possiblement)"
            ),
        ),
        migrations.CreateModel(
            name="GarantieFlotte",
            fields=[
                ("id", models.BigAutoField(
                    auto_created=True, primary_key=True, serialize=False,
                    verbose_name="ID")),
                ("composant", models.CharField(
                    default="vehicule",
                    help_text="Texte libre, ou 'vehicule' pour une garantie "
                    "couvrant l'actif entier.",
                    max_length=120, verbose_name="Composant")),
                ("duree_mois", models.PositiveIntegerField(
                    blank=True, null=True, verbose_name="Durée (mois)")),
                ("duree_km", models.PositiveIntegerField(
                    blank=True, null=True, verbose_name="Durée (km)")),
                ("date_debut", models.DateField(verbose_name="Date de début")),
                ("fournisseur", models.CharField(
                    blank=True, max_length=150, verbose_name="Fournisseur")),
                ("notes", models.TextField(blank=True, verbose_name="Notes")),
                ("date_creation", models.DateTimeField(
                    auto_now_add=True, verbose_name="Créé le")),
                ("actif_flotte", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="flotte_garanties", to="flotte.actifflotte",
                    verbose_name="Actif (véhicule ou engin)")),
                ("company", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="flotte_garanties",
                    to="authentication.company", verbose_name="Société")),
            ],
            options={
                "verbose_name": "Garantie flotte",
                "verbose_name_plural": "Garanties flotte",
                "ordering": ["-date_debut", "-id"],
            },
        ),
        migrations.AddIndex(
            model_name="garantieflotte",
            index=models.Index(
                fields=["company", "actif_flotte"],
                name="flotte_gar_co_actif_idx"),
        ),
    ]
