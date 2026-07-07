# XMKT22 - politique "sunset" d'engagement : StatutEngagementContact
# (actif/dormant par destinataire). Additif, nouvelle table.
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("compta", "0085_xmkt19_action_crm_etape_sequence"),
    ]

    operations = [
        migrations.CreateModel(
            name="StatutEngagementContact",
            fields=[
                ("id", models.BigAutoField(
                    auto_created=True, primary_key=True, serialize=False,
                    verbose_name="ID")),
                ("destinataire", models.CharField(
                    max_length=255,
                    verbose_name="Destinataire (email/téléphone normalisé)")),
                ("statut", models.CharField(
                    choices=[("actif", "Actif"), ("dormant", "Dormant")],
                    default="actif", max_length=10, verbose_name="Statut")),
                ("date_maj", models.DateTimeField(
                    auto_now=True, verbose_name="Mis à jour le")),
                ("company", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="statuts_engagement",
                    to="authentication.company", verbose_name="Société")),
            ],
            options={
                "verbose_name": "Statut d'engagement (contact)",
                "verbose_name_plural": "Statuts d'engagement (contacts)",
                "ordering": ["-date_maj"],
            },
        ),
        migrations.AddConstraint(
            model_name="statutengagementcontact",
            constraint=models.UniqueConstraint(
                fields=("company", "destinataire"),
                name="uniq_statut_engagement_par_destinataire"),
        ),
    ]
