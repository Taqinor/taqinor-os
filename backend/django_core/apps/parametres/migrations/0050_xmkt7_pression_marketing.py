# XMKT7 - reglages societe de pression marketing (plafond de messages par
# contact + periode de la fenetre glissante). Additif : NULL/defaut 7 =
# aucune limite active tant que le founder ne configure rien.
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("parametres", "0049_xmkt4_cndp_double_optin"),
    ]

    operations = [
        migrations.AddField(
            model_name="companyprofile",
            name="pression_marketing_max_par_contact",
            field=models.PositiveIntegerField(
                blank=True, null=True,
                help_text=(
                    "Nombre maximum de messages marketing (campagnes + "
                    "séquences, tous canaux) par contact sur la période. "
                    "Vide = aucune limite (comportement actuel)."),
            ),
        ),
        migrations.AddField(
            model_name="companyprofile",
            name="pression_marketing_periode_jours",
            field=models.PositiveIntegerField(
                default=7,
                help_text=(
                    "Fenêtre glissante (jours) sur laquelle le plafond de "
                    "pression marketing est évalué."),
            ),
        ),
    ]
