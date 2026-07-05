# XMKT7 - planification (envoi differe via Celery beat) + debit max par
# heure sur Campagne. Additif : les deux champs sont NULL/optionnels, le
# comportement d'envoi immediat sans limite reste inchange par defaut.
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("compta", "0078_alter_chargeconstateeavance_montant_total_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="campagne",
            name="planifiee_le",
            field=models.DateTimeField(
                blank=True, null=True,
                verbose_name="Envoi planifié le (Celery beat)"),
        ),
        migrations.AddField(
            model_name="campagne",
            name="debit_max_par_heure",
            field=models.PositiveIntegerField(
                blank=True, null=True,
                verbose_name="Débit max par heure (envoi par lots)"),
        ),
    ]
