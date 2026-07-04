# XFSM1 — Facturation SAV hors garantie : taux horaire main-d'œuvre
# configurable par société (vide par défaut, aucune valeur inventée).
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("parametres", "0039_xfac28_credit_hold"),
    ]

    operations = [
        migrations.AddField(
            model_name="companyprofile",
            name="taux_horaire_sav",
            field=models.DecimalField(
                decimal_places=2, max_digits=10, null=True, blank=True,
                help_text="Taux horaire main-d'œuvre SAV (MAD/heure), "
                          "utilisé pour facturer un ticket hors garantie "
                          "depuis son temps passé."),
        ),
    ]
