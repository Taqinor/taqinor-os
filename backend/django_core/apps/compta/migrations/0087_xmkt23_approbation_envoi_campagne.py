# XMKT23 - approbation avant envoi de masse : ApprobationEnvoiCampagne
# (pending/approved/rejected, pattern automation.AutomationApproval, local a
# compta). Additif, nouvelle table.
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("compta", "0086_xmkt22_statutengagementcontact"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="ApprobationEnvoiCampagne",
            fields=[
                ("id", models.BigAutoField(
                    auto_created=True, primary_key=True, serialize=False,
                    verbose_name="ID")),
                ("nb_destinataires_demandes", models.PositiveIntegerField(
                    default=0, verbose_name="Nb destinataires demandés")),
                ("statut", models.CharField(
                    choices=[
                        ("en_attente", "En attente"),
                        ("approuve", "Approuvé"), ("rejete", "Rejeté"),
                    ],
                    default="en_attente", max_length=12,
                    verbose_name="Statut")),
                ("motif_rejet", models.CharField(
                    blank=True, default="", max_length=255,
                    verbose_name="Motif de rejet")),
                ("date_creation", models.DateTimeField(
                    auto_now_add=True, verbose_name="Créée le")),
                ("date_decision", models.DateTimeField(
                    blank=True, null=True, verbose_name="Décidée le")),
                ("campagne", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="approbations_envoi", to="compta.campagne",
                    verbose_name="Campagne")),
                ("company", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="approbations_envoi_campagne",
                    to="authentication.company", verbose_name="Société")),
                ("demande_par", models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name="approbations_envoi_demandees",
                    to=settings.AUTH_USER_MODEL,
                    verbose_name="Demandé par")),
                ("decide_par", models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name="approbations_envoi_decidees",
                    to=settings.AUTH_USER_MODEL,
                    verbose_name="Décidé par")),
            ],
            options={
                "verbose_name": "Approbation d'envoi de campagne",
                "verbose_name_plural": "Approbations d'envoi de campagne",
                "ordering": ["-date_creation"],
            },
        ),
    ]
