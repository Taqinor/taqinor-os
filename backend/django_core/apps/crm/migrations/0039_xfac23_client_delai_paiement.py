# XFAC23 — Conditions de paiement par client (délai en jours + report fin de
# mois). Additif, nullable/défaut False : aucun client existant ne change de
# comportement tant que le champ n'est pas renseigné.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("crm", "0038_xfac25_releve_mensuel_auto"),
    ]

    operations = [
        migrations.AddField(
            model_name="client",
            name="delai_paiement_jours",
            field=models.PositiveSmallIntegerField(
                blank=True, null=True,
                help_text="Vide = comportement par défaut (+30 j depuis émission).",
                verbose_name="Délai de paiement (jours)",
            ),
        ),
        migrations.AddField(
            model_name="client",
            name="fin_de_mois",
            field=models.BooleanField(
                default=False,
                help_text=(
                    "Si coché, l'échéance calculée depuis le délai est "
                    "reportée au dernier jour de son mois (ex. « 60 jours "
                    "fin de mois »)."
                ),
                verbose_name="Échéance reportée en fin de mois",
            ),
        ),
    ]
