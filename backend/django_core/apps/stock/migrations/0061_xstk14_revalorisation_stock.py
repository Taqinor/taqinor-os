# XSTK14 — Revalorisation manuelle du stock (document trace).
# Additif : nouveau modele RevalorisationStock.
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("stock", "0060_xstk13_inventaire_annuel"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("authentication", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="RevalorisationStock",
            fields=[
                ("id", models.BigAutoField(
                    auto_created=True, primary_key=True,
                    serialize=False, verbose_name="ID")),
                ("ancien_cout", models.DecimalField(
                    decimal_places=2, max_digits=10,
                    help_text="Snapshot du coût moyen AVANT "
                              "revalorisation.")),
                ("nouveau_cout", models.DecimalField(
                    decimal_places=2, max_digits=10)),
                ("quantite_snapshot", models.IntegerField(
                    help_text="Quantité en stock au moment de la "
                              "revalorisation.")),
                ("delta_valeur", models.DecimalField(
                    decimal_places=2, max_digits=14,
                    help_text="(nouveau_cout - ancien_cout) × "
                              "quantite_snapshot.")),
                ("motif", models.TextField(
                    help_text="Motif obligatoire.")),
                ("statut", models.CharField(
                    choices=[("brouillon", "Brouillon"),
                             ("validee", "Validée")],
                    default="brouillon", max_length=20)),
                ("date_creation", models.DateTimeField(auto_now_add=True)),
                ("date_validation", models.DateTimeField(
                    blank=True, null=True)),
                ("company", models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="revalorisations_stock",
                    to="authentication.company")),
                ("produit", models.ForeignKey(
                    on_delete=django.db.models.deletion.PROTECT,
                    related_name="revalorisations", to="stock.produit")),
                ("auteur", models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name="revalorisations_stock",
                    to=settings.AUTH_USER_MODEL)),
            ],
            options={
                "verbose_name": "Revalorisation de stock",
                "verbose_name_plural": "Revalorisations de stock",
                "ordering": ["-date_creation"],
            },
        ),
    ]
