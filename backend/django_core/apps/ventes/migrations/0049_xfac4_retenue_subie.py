# XFAC4 — Retenue à la source SUBIE (RAS TVA/RAS IS) sur factures clients.
# Additif : nouveau modèle uniquement, aucun champ existant modifié.
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("ventes", "0048_xfac1_avances_affectation"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="RetenueSubie",
            fields=[
                ("id", models.AutoField(auto_created=True, primary_key=True,
                                        serialize=False, verbose_name="ID")),
                ("type_retenue", models.CharField(
                    choices=[("ras_tva", "RAS TVA"), ("ras_is", "RAS IS")],
                    default="ras_tva", max_length=10)),
                ("taux", models.DecimalField(decimal_places=2, max_digits=5)),
                ("base", models.DecimalField(decimal_places=2, max_digits=12)),
                ("montant", models.DecimalField(decimal_places=2, max_digits=12)),
                ("attestation_recue", models.BooleanField(default=False)),
                ("attestation_date", models.DateField(blank=True, null=True)),
                ("attestation_fichier", models.CharField(
                    blank=True, max_length=500, null=True)),
                ("note", models.TextField(blank=True, default="")),
                ("date_creation", models.DateTimeField(auto_now_add=True)),
                ("company", models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="retenues_subies", to="authentication.company")),
                ("created_by", models.ForeignKey(
                    null=True, on_delete=django.db.models.deletion.SET_NULL,
                    related_name="retenues_subies_creees",
                    to=settings.AUTH_USER_MODEL)),
                ("facture", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="retenues_subies", to="ventes.facture")),
                ("paiement", models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name="retenues_subies", to="ventes.paiement")),
            ],
            options={
                "verbose_name": "Retenue à la source subie",
                "verbose_name_plural": "Retenues à la source subies",
                "ordering": ["-date_creation"],
            },
        ),
    ]
