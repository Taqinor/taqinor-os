# Generated for FG145 — retenue de garantie & cautions bancaires sur marchés.

import django.db.models.deletion
from decimal import Decimal
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("compta", "0015_timbrefiscal"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="RetenueGarantie",
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
                    "reference",
                    models.CharField(
                        blank=True, default="", max_length=50,
                        verbose_name="Référence",
                    ),
                ),
                (
                    "marche_ref",
                    models.CharField(
                        blank=True, default="", max_length=120,
                        verbose_name="Marché / contrat",
                    ),
                ),
                (
                    "facture_id",
                    models.PositiveIntegerField(
                        blank=True, null=True,
                        verbose_name="ID de la facture",
                    ),
                ),
                (
                    "facture_ref",
                    models.CharField(
                        blank=True, default="", max_length=80,
                        verbose_name="Facture / décompte",
                    ),
                ),
                (
                    "tiers_type",
                    models.CharField(
                        blank=True, default="", max_length=20,
                        verbose_name="Type de tiers",
                    ),
                ),
                (
                    "tiers_id",
                    models.PositiveIntegerField(
                        blank=True, null=True, verbose_name="ID du tiers",
                    ),
                ),
                (
                    "tiers_nom",
                    models.CharField(
                        blank=True, default="", max_length=200,
                        verbose_name="Maître d'ouvrage / client",
                    ),
                ),
                (
                    "base",
                    models.DecimalField(
                        decimal_places=2,
                        default=Decimal("0"),
                        max_digits=14,
                        verbose_name="Base du décompte",
                    ),
                ),
                (
                    "taux",
                    models.DecimalField(
                        decimal_places=2,
                        default=Decimal("10.00"),
                        max_digits=5,
                        verbose_name="Taux de RG (%)",
                    ),
                ),
                (
                    "montant",
                    models.DecimalField(
                        decimal_places=2,
                        default=Decimal("0"),
                        max_digits=14,
                        verbose_name="Montant retenu",
                    ),
                ),
                (
                    "date_constitution",
                    models.DateField(verbose_name="Date de constitution"),
                ),
                (
                    "date_levee_prevue",
                    models.DateField(
                        blank=True, null=True,
                        verbose_name="Date de levée prévue",
                    ),
                ),
                (
                    "statut",
                    models.CharField(
                        choices=[
                            ("retenue", "Retenue"),
                            ("liberee", "Libérée"),
                        ],
                        default="retenue",
                        max_length=10,
                        verbose_name="Statut",
                    ),
                ),
                (
                    "date_liberation",
                    models.DateField(
                        blank=True, null=True,
                        verbose_name="Date de libération",
                    ),
                ),
                (
                    "libelle",
                    models.CharField(
                        blank=True, default="", max_length=200,
                        verbose_name="Libellé",
                    ),
                ),
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
                        related_name="retenues_garantie",
                        to="authentication.company",
                        verbose_name="Société",
                    ),
                ),
                (
                    "created_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="retenues_garantie_creees",
                        to=settings.AUTH_USER_MODEL,
                        verbose_name="Enregistrée par",
                    ),
                ),
            ],
            options={
                "verbose_name": "Retenue de garantie",
                "verbose_name_plural": "Retenues de garantie",
                "ordering": ["-date_constitution", "-id"],
            },
        ),
        migrations.CreateModel(
            name="CautionBancaire",
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
                    "reference",
                    models.CharField(
                        blank=True, default="", max_length=50,
                        verbose_name="Référence",
                    ),
                ),
                (
                    "type_caution",
                    models.CharField(
                        choices=[
                            ("provisoire", "Caution provisoire"),
                            ("definitive", "Caution définitive"),
                            (
                                "retenue_garantie",
                                "Caution de retenue de garantie",
                            ),
                            (
                                "restitution",
                                "Caution de restitution d'acompte",
                            ),
                        ],
                        default="definitive",
                        max_length=20,
                        verbose_name="Type de caution",
                    ),
                ),
                (
                    "marche_ref",
                    models.CharField(
                        blank=True, default="", max_length=120,
                        verbose_name="Marché / contrat",
                    ),
                ),
                (
                    "tiers_nom",
                    models.CharField(
                        blank=True, default="", max_length=200,
                        verbose_name="Bénéficiaire (maître d'ouvrage)",
                    ),
                ),
                (
                    "banque",
                    models.CharField(
                        blank=True, default="", max_length=120,
                        verbose_name="Banque émettrice",
                    ),
                ),
                (
                    "montant",
                    models.DecimalField(
                        decimal_places=2,
                        default=Decimal("0"),
                        max_digits=14,
                        verbose_name="Montant de la caution",
                    ),
                ),
                (
                    "date_emission",
                    models.DateField(verbose_name="Date d'émission"),
                ),
                (
                    "date_echeance",
                    models.DateField(
                        blank=True, null=True,
                        verbose_name="Date d'échéance",
                    ),
                ),
                (
                    "statut",
                    models.CharField(
                        choices=[
                            ("active", "Active"),
                            ("levee", "Mainlevée"),
                            ("restituee", "Restituée"),
                        ],
                        default="active",
                        max_length=10,
                        verbose_name="Statut",
                    ),
                ),
                (
                    "date_mainlevee",
                    models.DateField(
                        blank=True, null=True,
                        verbose_name="Date de mainlevée",
                    ),
                ),
                (
                    "libelle",
                    models.CharField(
                        blank=True, default="", max_length=200,
                        verbose_name="Libellé",
                    ),
                ),
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
                        related_name="cautions_bancaires",
                        to="authentication.company",
                        verbose_name="Société",
                    ),
                ),
                (
                    "created_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="cautions_bancaires_creees",
                        to=settings.AUTH_USER_MODEL,
                        verbose_name="Enregistrée par",
                    ),
                ),
            ],
            options={
                "verbose_name": "Caution bancaire",
                "verbose_name_plural": "Cautions bancaires",
                "ordering": ["-date_emission", "-id"],
            },
        ),
        migrations.AddConstraint(
            model_name="retenuegarantie",
            constraint=models.UniqueConstraint(
                condition=models.Q(("reference__gt", "")),
                fields=("company", "reference"),
                name="uniq_rg_reference",
            ),
        ),
        migrations.AddConstraint(
            model_name="cautionbancaire",
            constraint=models.UniqueConstraint(
                condition=models.Q(("reference__gt", "")),
                fields=("company", "reference"),
                name="uniq_caution_reference",
            ),
        ),
    ]
