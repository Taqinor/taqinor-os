# XFAC12 — Escompte pour règlement anticipé (ex. 2/10 net 30). Additif :
# deux champs nullable sur Facture → comportement historique inchangé tant
# qu'ils ne sont pas renseignés.
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("ventes", "0054_xfac11_facture_source"),
    ]

    operations = [
        migrations.AddField(
            model_name="facture",
            name="escompte_pct",
            field=models.DecimalField(
                blank=True, decimal_places=2, max_digits=5, null=True,
                help_text="Taux d'escompte (%) si réglé sous escompte_jours."),
        ),
        migrations.AddField(
            model_name="facture",
            name="escompte_jours",
            field=models.PositiveIntegerField(
                blank=True, null=True,
                help_text="Nombre de jours depuis l'émission pour "
                          "bénéficier de l'escompte."),
        ),
        migrations.AddField(
            model_name="paiement",
            name="escompte_montant",
            field=models.DecimalField(
                blank=True, decimal_places=2, default=0, max_digits=12,
                null=True),
        ),
    ]
