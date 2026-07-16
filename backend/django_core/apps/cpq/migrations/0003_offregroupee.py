import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("authentication", "0023_yhard1_encrypt_totp_secret"),
        ("stock", "0080_odx19_achats_split_repoint"),
        ("cpq", "0002_regleproduitcpq"),
    ]

    operations = [
        migrations.CreateModel(
            name="OffreGroupee",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True, primary_key=True,
                        serialize=False, verbose_name="ID"),
                ),
                ("nom", models.CharField(max_length=150)),
                ("prix_total", models.DecimalField(
                    blank=True, decimal_places=2, max_digits=12, null=True,
                    help_text="Prix fixe du bundle (mode FIXE) réparti au prorata.")),
                ("actif", models.BooleanField(default=True)),
                ("date_creation", models.DateTimeField(auto_now_add=True)),
                (
                    "company",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="cpq_offres_groupees",
                        to="authentication.company"),
                ),
            ],
            options={
                "verbose_name": "Offre groupée",
                "verbose_name_plural": "Offres groupées",
                "ordering": ["-date_creation", "id"],
            },
        ),
        migrations.CreateModel(
            name="LigneOffreGroupee",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True, primary_key=True,
                        serialize=False, verbose_name="ID"),
                ),
                ("quantite", models.DecimalField(
                    decimal_places=2, default=1, max_digits=10)),
                ("mode_prix", models.CharField(
                    choices=[
                        ("FIXE", "Prix fixe (bundle)"),
                        ("REMISE_PCT", "Remise %"),
                        ("PRIX_COMPOSANT", "Prix composant imposé"),
                    ],
                    default="FIXE", max_length=20)),
                ("valeur", models.DecimalField(
                    blank=True, decimal_places=2, max_digits=10, null=True,
                    help_text="% de remise (REMISE_PCT) ou prix imposé (PRIX_COMPOSANT).")),
                (
                    "offre",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="lignes", to="cpq.offregroupee"),
                ),
                (
                    "produit",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="cpq_lignes_offre", to="stock.produit"),
                ),
            ],
            options={
                "verbose_name": "Ligne offre groupée",
                "verbose_name_plural": "Lignes offre groupée",
                "ordering": ["offre_id", "id"],
            },
        ),
        migrations.AddIndex(
            model_name="offregroupee",
            index=models.Index(
                fields=["company", "actif"], name="cpq_offre_co_actif"),
        ),
    ]
