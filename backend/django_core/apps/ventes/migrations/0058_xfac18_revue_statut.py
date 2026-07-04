# XFAC18 — Workflow de revue facture (ségrégation des tâches, style Odoo
# 19). Additif : champ blank/default='' → comportement historique inchangé
# tant que le réglage société n'est pas activé.
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("ventes", "0057_xfac13_abandon_creance"),
    ]

    operations = [
        migrations.AddField(
            model_name="facture",
            name="revue_statut",
            field=models.CharField(
                blank=True, default="", max_length=15,
                choices=[
                    ("a_valider", "À valider"),
                    ("validee", "Validée"),
                ]),
        ),
    ]
