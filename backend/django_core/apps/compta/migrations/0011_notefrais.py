# Generated for FG135 — notes de frais & remboursements employés.

import django.db.models.deletion
from decimal import Decimal
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("authentication", "0012_customuser_must_change_password_and_more"),
        ("compta", "0010_paymentrun_paymentrunline"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="NoteFrais",
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
                    "date_frais",
                    models.DateField(verbose_name="Date de la dépense"),
                ),
                (
                    "categorie",
                    models.CharField(
                        choices=[
                            ("deplacement", "Déplacement / transport"),
                            ("carburant", "Carburant"),
                            ("repas", "Repas / restauration"),
                            ("hebergement", "Hébergement"),
                            ("fournitures", "Petites fournitures"),
                            ("peage", "Péage / stationnement"),
                            ("autre", "Autre"),
                        ],
                        default="autre",
                        max_length=15,
                        verbose_name="Catégorie",
                    ),
                ),
                (
                    "montant",
                    models.DecimalField(
                        decimal_places=2,
                        default=Decimal("0"),
                        max_digits=14,
                        verbose_name="Montant (TTC)",
                    ),
                ),
                (
                    "motif",
                    models.CharField(max_length=255, verbose_name="Motif"),
                ),
                (
                    "justificatif",
                    models.FileField(
                        blank=True,
                        null=True,
                        upload_to="notes_frais/justificatifs/%Y/%m/",
                        verbose_name="Justificatif (photo)",
                    ),
                ),
                (
                    "statut",
                    models.CharField(
                        choices=[
                            ("brouillon", "Brouillon"),
                            ("soumise", "Soumise"),
                            ("validee", "Validée"),
                            ("rejetee", "Rejetée"),
                            ("remboursee", "Remboursée"),
                        ],
                        default="brouillon",
                        max_length=12,
                        verbose_name="Statut",
                    ),
                ),
                (
                    "date_validation",
                    models.DateTimeField(
                        blank=True, null=True, verbose_name="Validée le"
                    ),
                ),
                (
                    "motif_rejet",
                    models.CharField(
                        blank=True, default="", max_length=255,
                        verbose_name="Motif de rejet",
                    ),
                ),
                (
                    "mode_remboursement",
                    models.CharField(
                        choices=[
                            ("virement", "Virement bancaire"),
                            ("especes", "Espèces"),
                            ("cheque", "Chèque"),
                        ],
                        default="virement",
                        max_length=10,
                        verbose_name="Mode de remboursement",
                    ),
                ),
                (
                    "date_remboursement",
                    models.DateField(
                        blank=True, null=True,
                        verbose_name="Date de remboursement",
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
                        related_name="notes_frais",
                        to="authentication.company",
                        verbose_name="Société",
                    ),
                ),
                (
                    "employe",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="notes_frais",
                        to=settings.AUTH_USER_MODEL,
                        verbose_name="Employé",
                    ),
                ),
                (
                    "compte_charge",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="notes_frais_charge",
                        to="compta.comptecomptable",
                        verbose_name="Compte de charge",
                    ),
                ),
                (
                    "valide_par",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="notes_frais_validees",
                        to=settings.AUTH_USER_MODEL,
                        verbose_name="Validée par",
                    ),
                ),
                (
                    "ecriture_charge",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="notes_frais_charge",
                        to="compta.ecriturecomptable",
                        verbose_name="Écriture de charge",
                    ),
                ),
                (
                    "compte_tresorerie",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="notes_frais",
                        to="compta.comptetresorerie",
                        verbose_name="Compte de trésorerie (payeur)",
                    ),
                ),
                (
                    "rembourse_par",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="notes_frais_remboursees",
                        to=settings.AUTH_USER_MODEL,
                        verbose_name="Remboursée par",
                    ),
                ),
                (
                    "ecriture_remboursement",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="notes_frais_remboursement",
                        to="compta.ecriturecomptable",
                        verbose_name="Écriture de remboursement",
                    ),
                ),
                (
                    "created_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="notes_frais_creees",
                        to=settings.AUTH_USER_MODEL,
                        verbose_name="Saisie par",
                    ),
                ),
            ],
            options={
                "verbose_name": "Note de frais",
                "verbose_name_plural": "Notes de frais",
                "ordering": ["-date_frais", "-id"],
            },
        ),
        migrations.AddConstraint(
            model_name="notefrais",
            constraint=models.UniqueConstraint(
                condition=models.Q(("reference__gt", "")),
                fields=("company", "reference"),
                name="uniq_note_frais_reference",
            ),
        ),
    ]
