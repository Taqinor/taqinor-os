# Generated for FLOTTE18 — Pneumatique + PieceFlotte (suivi pneus & pièces de
# la flotte : inventaire + montage/dépose par véhicule).

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("authentication", "0013_customuser_poste_ref"),
        ("flotte", "0015_garage_ordrereparation"),
    ]

    operations = [
        migrations.CreateModel(
            name="Pneumatique",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "position",
                    models.CharField(
                        choices=[
                            ("av_g", "Avant gauche"),
                            ("av_d", "Avant droite"),
                            ("ar_g", "Arrière gauche"),
                            ("ar_d", "Arrière droite"),
                            ("secours", "Roue de secours"),
                        ],
                        default="av_g",
                        max_length=10,
                        verbose_name="Position",
                    ),
                ),
                (
                    "marque",
                    models.CharField(
                        blank=True, max_length=80, verbose_name="Marque"
                    ),
                ),
                (
                    "dimension",
                    models.CharField(
                        blank=True,
                        help_text="Ex. : 205/55 R16",
                        max_length=40,
                        verbose_name="Dimension",
                    ),
                ),
                (
                    "date_montage",
                    models.DateField(
                        blank=True, null=True, verbose_name="Date de montage"
                    ),
                ),
                (
                    "km_montage",
                    models.PositiveIntegerField(
                        blank=True,
                        null=True,
                        verbose_name="Kilométrage au montage",
                    ),
                ),
                (
                    "date_depose",
                    models.DateField(
                        blank=True, null=True, verbose_name="Date de dépose"
                    ),
                ),
                (
                    "statut",
                    models.CharField(
                        choices=[
                            ("monte", "Monté"),
                            ("depose", "Déposé"),
                            ("use", "Usé"),
                        ],
                        default="monte",
                        max_length=10,
                        verbose_name="Statut",
                    ),
                ),
                (
                    "cout",
                    models.DecimalField(
                        decimal_places=2,
                        default=0,
                        max_digits=12,
                        verbose_name="Coût d'achat (MAD)",
                    ),
                ),
                ("notes", models.TextField(blank=True, verbose_name="Notes")),
                (
                    "date_creation",
                    models.DateTimeField(
                        auto_now_add=True, verbose_name="Créé le"
                    ),
                ),
                (
                    "company",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="flotte_pneumatiques",
                        to="authentication.company",
                        verbose_name="Société",
                    ),
                ),
                (
                    "vehicule",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="flotte_pneumatiques",
                        to="flotte.vehicule",
                        verbose_name="Véhicule",
                    ),
                ),
            ],
            options={
                "verbose_name": "Pneumatique",
                "verbose_name_plural": "Pneumatiques",
                "ordering": ["vehicule", "position", "-date_montage", "-id"],
            },
        ),
        migrations.CreateModel(
            name="PieceFlotte",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "designation",
                    models.CharField(
                        max_length=160, verbose_name="Désignation"
                    ),
                ),
                (
                    "reference",
                    models.CharField(
                        blank=True, max_length=80, verbose_name="Référence"
                    ),
                ),
                (
                    "quantite",
                    models.PositiveIntegerField(
                        default=1, verbose_name="Quantité"
                    ),
                ),
                (
                    "cout_unitaire",
                    models.DecimalField(
                        decimal_places=2,
                        default=0,
                        max_digits=12,
                        verbose_name="Coût unitaire (MAD)",
                    ),
                ),
                (
                    "date_pose",
                    models.DateField(
                        blank=True, null=True, verbose_name="Date de pose"
                    ),
                ),
                ("notes", models.TextField(blank=True, verbose_name="Notes")),
                (
                    "date_creation",
                    models.DateTimeField(
                        auto_now_add=True, verbose_name="Créé le"
                    ),
                ),
                (
                    "company",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="flotte_pieces",
                        to="authentication.company",
                        verbose_name="Société",
                    ),
                ),
                (
                    "vehicule",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="flotte_pieces",
                        to="flotte.vehicule",
                        verbose_name="Véhicule",
                    ),
                ),
                (
                    "ordre_reparation",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="flotte_pieces",
                        to="flotte.ordrereparation",
                        verbose_name="Ordre de réparation lié",
                    ),
                ),
            ],
            options={
                "verbose_name": "Pièce de flotte",
                "verbose_name_plural": "Pièces de flotte",
                "ordering": ["vehicule", "-date_pose", "-id"],
            },
        ),
        migrations.AddIndex(
            model_name="pneumatique",
            index=models.Index(
                fields=["company", "vehicule"],
                name="flotte_pneu_co_veh_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="pneumatique",
            index=models.Index(
                fields=["company", "statut"],
                name="flotte_pneu_co_stat_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="pieceflotte",
            index=models.Index(
                fields=["company", "vehicule"],
                name="flotte_piece_co_veh_idx",
            ),
        ),
    ]
