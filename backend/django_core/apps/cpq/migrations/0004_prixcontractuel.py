import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("authentication", "0023_yhard1_encrypt_totp_secret"),
        ("crm", "0062_lead_web_questionnaire_estimate"),
        ("stock", "0080_odx19_achats_split_repoint"),
        ("cpq", "0003_offregroupee"),
    ]

    operations = [
        migrations.CreateModel(
            name="PrixContractuel",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True, primary_key=True,
                        serialize=False, verbose_name="ID"),
                ),
                ("prix_ht", models.DecimalField(
                    decimal_places=2, max_digits=12)),
                ("date_debut", models.DateField(blank=True, null=True)),
                ("date_fin", models.DateField(blank=True, null=True)),
                ("motif", models.TextField(blank=True, default="")),
                ("date_creation", models.DateTimeField(auto_now_add=True)),
                (
                    "client",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="cpq_prix_contractuels",
                        to="crm.client"),
                ),
                (
                    "company",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="cpq_prix_contractuels",
                        to="authentication.company"),
                ),
                (
                    "created_by",
                    models.ForeignKey(
                        blank=True, null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="cpq_prix_contractuels_crees",
                        to=settings.AUTH_USER_MODEL),
                ),
                (
                    "produit",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="cpq_prix_contractuels",
                        to="stock.produit"),
                ),
            ],
            options={
                "verbose_name": "Prix contractuel",
                "verbose_name_plural": "Prix contractuels",
                "ordering": ["-date_creation", "id"],
            },
        ),
        migrations.AddIndex(
            model_name="prixcontractuel",
            index=models.Index(
                fields=["company", "client", "produit"],
                name="cpq_prixctr_co_cl_pr"),
        ),
    ]
