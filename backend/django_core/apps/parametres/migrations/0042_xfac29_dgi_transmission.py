# XFAC29 — Facturation électronique DGI SORTANTE : interrupteur maître de
# transmission (distinct de l'export local N105) + choix de fournisseur.
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("parametres", "0041_xfsm1_taux_horaire_sav"),
    ]

    operations = [
        migrations.AddField(
            model_name="companyprofile",
            name="dgi_transmission_actif",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="companyprofile",
            name="dgi_transmission_provider",
            field=models.CharField(blank=True, default="noop", max_length=30),
        ),
    ]
