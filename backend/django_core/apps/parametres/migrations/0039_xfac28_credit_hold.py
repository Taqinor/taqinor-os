# XFAC28 — Blocage crédit dur configurable avec déblocage autorisé (étend
# FG41).
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("parametres", "0038_xfac24_factures_immuables"),
    ]

    operations = [
        migrations.AddField(
            model_name="companyprofile",
            name="credit_hold_actif",
            field=models.BooleanField(
                default=False,
                help_text="Bloque (403) les nouveaux devis acceptés/"
                          "factures d'un client en dépassement de crédit, "
                          "au lieu du seul avertissement FG41. Désactivé "
                          "par défaut."),
        ),
        migrations.AddField(
            model_name="companyprofile",
            name="credit_hold_retard_jours",
            field=models.PositiveIntegerField(
                default=0,
                help_text="Jours de retard sur facture(s) ouvertes au-delà "
                          "desquels le hold s'applique aussi "
                          "(indépendamment du plafond). 0 = ce critère est "
                          "ignoré (seul le dépassement de plafond FG41 "
                          "déclenche le hold)."),
        ),
    ]
