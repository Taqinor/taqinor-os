# Generated manually — XPAI20 provisions gratification (13e mois) & IFC,
# auditables par employé et par mois, postées en écriture réversible.

import django.db.models.deletion
from decimal import Decimal
from django.db import migrations, models


class Migration(migrations.Migration):
    """XPAI20 — ProvisionPaieMensuelle (gratification / IFC)."""

    dependencies = [
        ("paie", "0031_xpai18_regimes_exoneration"),
    ]

    operations = [
        migrations.CreateModel(
            name="ProvisionPaieMensuelle",
            fields=[
                ("id", models.BigAutoField(
                    auto_created=True, primary_key=True, serialize=False,
                    verbose_name="ID")),
                ("type_provision", models.CharField(
                    choices=[
                        ("gratification", "13e mois / prime de bilan"),
                        ("ifc", "Indemnité de fin de carrière"),
                    ],
                    max_length=14, verbose_name="Type de provision")),
                ("montant", models.DecimalField(
                    decimal_places=2, default=Decimal("0"), max_digits=14,
                    verbose_name="Montant provisionné")),
                ("ecriture_id", models.PositiveIntegerField(
                    blank=True, null=True,
                    verbose_name="Écriture (ID, compta)")),
                ("extournee", models.BooleanField(
                    default=False, verbose_name="Extournée (reprise)")),
                ("date_extourne", models.DateTimeField(
                    blank=True, null=True, verbose_name="Extournée le")),
                ("date_creation", models.DateTimeField(
                    auto_now_add=True, verbose_name="Créée le")),
                ("company", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="paie_provisions_mensuelles",
                    to="authentication.company", verbose_name="Société")),
                ("periode", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="provisions_mensuelles",
                    to="paie.periodepaie", verbose_name="Période")),
                ("profil", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="provisions_mensuelles",
                    to="paie.profilpaie", verbose_name="Profil de paie")),
            ],
            options={
                "verbose_name": "Provision mensuelle (13e mois / IFC)",
                "verbose_name_plural": "Provisions mensuelles (13e mois / IFC)",
                "ordering": ["-periode__annee", "-periode__mois", "profil"],
                "unique_together": {
                    ("company", "profil", "periode", "type_provision")},
            },
        ),
    ]
