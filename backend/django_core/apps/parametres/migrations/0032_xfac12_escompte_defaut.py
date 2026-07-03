# XFAC12 — Escompte pour règlement anticipé : défauts proposés par société.
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("parametres", "0031_xfac7_rappel_pre_echeance"),
    ]

    operations = [
        migrations.AddField(
            model_name="companyprofile",
            name="escompte_pct_defaut",
            field=models.DecimalField(
                blank=True, decimal_places=2, max_digits=5, null=True,
                help_text="Taux d'escompte (%) proposé par défaut sur les "
                          "nouvelles factures."),
        ),
        migrations.AddField(
            model_name="companyprofile",
            name="escompte_jours_defaut",
            field=models.PositiveIntegerField(
                blank=True, null=True,
                help_text="Délai (jours) proposé par défaut pour l'escompte."),
        ),
    ]
