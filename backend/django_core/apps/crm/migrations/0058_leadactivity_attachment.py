# VX111 — pièce jointe optionnelle sur une note manuelle (LeadActivity.NOTE),
# ex. photo prise depuis mobile. Réutilise records.Attachment (déjà
# whitelisté ('crm','lead')) — additive, jamais un second magasin de fichiers.
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("records", "0012_activity_snoozed_until"),
        ("crm", "0057_zsal9_client_avertissement_vente"),
    ]

    operations = [
        migrations.AddField(
            model_name="leadactivity",
            name="attachment",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="lead_notes",
                to="records.attachment",
                verbose_name="Pièce jointe",
            ),
        ),
    ]
