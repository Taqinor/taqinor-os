# XMKT4 - numero de declaration CNDP (informatif, footer emails marketing) +
# toggle double opt-in des inscriptions publiques. Additif : les deux
# defauts (chaine vide / False) preservent le comportement actuel.
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("parametres", "0048_zstk2_jours_alerte_peremption"),
    ]

    operations = [
        migrations.AddField(
            model_name="companyprofile",
            name="numero_declaration_cndp",
            field=models.CharField(
                blank=True, default="", max_length=60,
                help_text=(
                    "Numéro de déclaration CNDP (loi 09-08), affiché dans "
                    "le pied des emails marketing s'il est renseigné."),
            ),
        ),
        migrations.AddField(
            model_name="companyprofile",
            name="double_optin_actif",
            field=models.BooleanField(
                default=False,
                help_text=(
                    "Active le double opt-in (email de confirmation, "
                    "mailable seulement après clic) pour les inscriptions "
                    "publiques marketing. Désactivé par défaut."),
            ),
        ),
    ]
