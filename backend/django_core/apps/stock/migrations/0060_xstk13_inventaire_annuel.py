# XSTK13 — Valorisation a date (as-of) + inventaire annuel legal (CGNC).
# Additif : nouveau modele InventaireAnnuel, snapshot immuable de la
# valorisation figee au 31/12 d'un exercice.
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("stock", "0059_xstk19_code_sh_pays_origine"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("authentication", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="InventaireAnnuel",
            fields=[
                ("id", models.BigAutoField(
                    auto_created=True, primary_key=True,
                    serialize=False, verbose_name="ID")),
                ("exercice", models.PositiveIntegerField(
                    help_text="Année de l'exercice comptable (ex. 2026).")),
                ("date_reference", models.DateField(
                    help_text="Date de référence du figement (31/12 de "
                              "l'exercice).")),
                ("total_valeur", models.DecimalField(
                    decimal_places=2, max_digits=16)),
                ("nb_lignes", models.PositiveIntegerField(default=0)),
                ("donnees", models.JSONField(
                    help_text="Snapshot complet et immuable de la "
                              "valorisation.")),
                ("date_creation", models.DateTimeField(auto_now_add=True)),
                ("company", models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="inventaires_annuels",
                    to="authentication.company")),
                ("created_by", models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name="inventaires_annuels_crees",
                    to=settings.AUTH_USER_MODEL)),
            ],
            options={
                "verbose_name": "Inventaire annuel",
                "verbose_name_plural": "Inventaires annuels",
                "ordering": ["-exercice"],
                "unique_together": {("company", "exercice")},
            },
        ),
    ]
