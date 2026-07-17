import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("authentication", "0023_yhard1_encrypt_totp_secret"),
        ("stock", "0080_odx19_achats_split_repoint"),
        ("cpq", "0004_prixcontractuel"),
    ]

    operations = [
        migrations.CreateModel(
            name="SeuilMargeFamille",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True, primary_key=True,
                        serialize=False, verbose_name="ID"),
                ),
                ("marge_min_pct", models.DecimalField(
                    decimal_places=2, max_digits=5,
                    help_text="Marge minimale attendue (%) pour cette famille.")),
                (
                    "company",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="cpq_seuils_marge",
                        to="authentication.company"),
                ),
                (
                    "categorie",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="cpq_seuils_marge",
                        to="stock.categorie"),
                ),
            ],
            options={
                "verbose_name": "Seuil de marge par famille",
                "verbose_name_plural": "Seuils de marge par famille",
                "ordering": ["id"],
            },
        ),
        migrations.AddConstraint(
            model_name="seuilmargefamille",
            constraint=models.UniqueConstraint(
                fields=["company", "categorie"],
                name="cpq_seuilmarge_unique_co_cat"),
        ),
    ]
