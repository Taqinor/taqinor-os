# XPUR8 — Acomptes / avances fournisseur sur BCF. Additif : nouveau modèle
# AcompteFournisseur (pattern PaiementFournisseur, rattaché au BCF).
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("stock", "0035_xpur7_otd_livraison"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="AcompteFournisseur",
            fields=[
                ("id", models.BigAutoField(
                    auto_created=True, primary_key=True, serialize=False,
                    verbose_name="ID")),
                ("montant", models.DecimalField(
                    decimal_places=2, max_digits=14)),
                ("date_versement", models.DateField(blank=True, null=True)),
                ("mode", models.CharField(
                    choices=[
                        ("virement", "Virement"),
                        ("cheque", "Chèque"),
                        ("especes", "Espèces"),
                        ("carte", "Carte"),
                        ("effet", "Effet / traite"),
                        ("autre", "Autre"),
                    ],
                    default="virement", max_length=20)),
                ("montant_consomme", models.DecimalField(
                    decimal_places=2, default=0, max_digits=14)),
                ("note", models.TextField(blank=True, null=True)),
                ("date_creation", models.DateTimeField(auto_now_add=True)),
                ("company", models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="acomptes_fournisseur",
                    to="authentication.company")),
                ("bon_commande", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="acomptes", to="stock.boncommandefournisseur")),
                ("facture_imputee", models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name="acomptes_imputes",
                    to="stock.facturefournisseur")),
                ("created_by", models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name="acomptes_fournisseur",
                    to=settings.AUTH_USER_MODEL)),
            ],
            options={
                "verbose_name": "Acompte fournisseur",
                "verbose_name_plural": "Acomptes fournisseur",
                "ordering": ["-date_versement", "-date_creation"],
            },
        ),
    ]
