import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("authentication", "0023_yhard1_encrypt_totp_secret"),
        ("cpq", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="RegleProduitCPQ",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True, primary_key=True,
                        serialize=False, verbose_name="ID"),
                ),
                ("nom", models.CharField(max_length=150)),
                ("condition_group", models.JSONField(
                    blank=True, default=dict,
                    help_text="Arbre de conditions ET/OU/NON (core.rules).")),
                ("actions", models.JSONField(
                    blank=True, default=list,
                    help_text="Liste d'actions déclenchées quand la règle est vraie.")),
                ("actif", models.BooleanField(default=True)),
                ("date_creation", models.DateTimeField(auto_now_add=True)),
                (
                    "company",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="cpq_regles_produit",
                        to="authentication.company"),
                ),
            ],
            options={
                "verbose_name": "Règle produit CPQ",
                "verbose_name_plural": "Règles produit CPQ",
                "ordering": ["-date_creation", "id"],
            },
        ),
        migrations.AddIndex(
            model_name="regleproduitcpq",
            index=models.Index(
                fields=["company", "actif"], name="cpq_regle_co_actif"),
        ),
    ]
