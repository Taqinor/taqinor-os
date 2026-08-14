# NTRET25 — Arrondi caisse (espèces) : écart tracé sur la vente comptoir pour
# affichage en ligne distincte sur le ticket. Additif — NULL = non
# applicable (comportement historique inchangé).
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("pos", "0007_ntret23_commanderetrait_expiration"),
    ]

    operations = [
        migrations.AddField(
            model_name="ventecomptoir",
            name="ecart_arrondi_especes",
            field=models.DecimalField(
                blank=True, decimal_places=2, max_digits=6, null=True,
                help_text="NTRET25 — écart d'arrondi caisse (espèces), tracé "
                          "séparément sur le ticket."),
        ),
    ]
