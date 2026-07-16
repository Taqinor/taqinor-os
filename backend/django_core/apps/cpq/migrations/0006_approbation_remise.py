import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("authentication", "0023_yhard1_encrypt_totp_secret"),
        ("ventes", "0087_ntcpq4_listeprix_segment"),
        ("cpq", "0005_seuilmargefamille"),
    ]

    operations = [
        migrations.CreateModel(
            name="RegleApprobationRemise",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True, primary_key=True,
                        serialize=False, verbose_name="ID"),
                ),
                ("libelle", models.CharField(
                    blank=True, default="", max_length=200)),
                ("remise_min_pct", models.DecimalField(
                    blank=True, decimal_places=2, max_digits=5, null=True)),
                ("remise_max_pct", models.DecimalField(
                    blank=True, decimal_places=2, max_digits=5, null=True)),
                ("niveau_approbation", models.CharField(
                    choices=[
                        ("responsable", "Responsable"),
                        ("administrateur", "Administrateur"),
                        ("direction", "Direction"),
                    ],
                    default="responsable", max_length=20)),
                ("nombre_approbateurs", models.PositiveIntegerField(default=1)),
                ("priorite", models.PositiveIntegerField(default=0)),
                ("actif", models.BooleanField(default=True)),
                ("date_creation", models.DateTimeField(auto_now_add=True)),
                (
                    "company",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="cpq_regles_approbation_remise",
                        to="authentication.company"),
                ),
            ],
            options={
                "verbose_name": "Règle d'approbation de remise",
                "verbose_name_plural": "Règles d'approbation de remise",
                "ordering": ["-priorite", "id"],
            },
        ),
        migrations.CreateModel(
            name="EtapeApprobationDevis",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True, primary_key=True,
                        serialize=False, verbose_name="ID"),
                ),
                ("niveau", models.PositiveIntegerField(default=1)),
                ("niveau_approbation", models.CharField(
                    choices=[
                        ("responsable", "Responsable"),
                        ("administrateur", "Administrateur"),
                        ("direction", "Direction"),
                    ],
                    default="responsable", max_length=20)),
                ("statut", models.CharField(
                    choices=[
                        ("en_attente", "En attente"),
                        ("approuve", "Approuvé"),
                        ("rejete", "Rejeté"),
                    ],
                    default="en_attente", max_length=20)),
                ("decision_le", models.DateTimeField(blank=True, null=True)),
                ("commentaire", models.TextField(blank=True, default="")),
                ("date_creation", models.DateTimeField(auto_now_add=True)),
                (
                    "approbateur",
                    models.ForeignKey(
                        blank=True, null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="cpq_etapes_devis_decidees",
                        to=settings.AUTH_USER_MODEL),
                ),
                (
                    "company",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="cpq_etapes_approbation_devis",
                        to="authentication.company"),
                ),
                (
                    "devis",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="cpq_etapes_approbation",
                        to="ventes.devis"),
                ),
                (
                    "regle",
                    models.ForeignKey(
                        blank=True, null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="etapes",
                        to="cpq.regleapprobationremise"),
                ),
            ],
            options={
                "verbose_name": "Étape d'approbation de devis",
                "verbose_name_plural": "Étapes d'approbation de devis",
                "ordering": ["devis_id", "niveau", "id"],
            },
        ),
        migrations.AddIndex(
            model_name="regleapprobationremise",
            index=models.Index(
                fields=["company", "actif"], name="cpq_regleremise_co_act"),
        ),
        migrations.AddIndex(
            model_name="etapeapprobationdevis",
            index=models.Index(
                fields=["company", "statut"], name="cpq_etapedev_co_sta"),
        ),
        migrations.AddIndex(
            model_name="etapeapprobationdevis",
            index=models.Index(
                fields=["devis", "niveau"], name="cpq_etapedev_dv_niv"),
        ),
    ]
