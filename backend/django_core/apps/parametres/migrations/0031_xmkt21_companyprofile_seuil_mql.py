# XMKT21 — seuil de score MQL (Marketing Qualified Lead) par société.
# Additive + nullable, réversible. NULL/0 = désactivé (comportement inchangé).

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("parametres", "0030_qg9_variante_pct"),
    ]

    operations = [
        migrations.AddField(
            model_name="companyprofile",
            name="seuil_mql",
            field=models.PositiveSmallIntegerField(
                blank=True,
                null=True,
                help_text="Score (0–100) au-delà duquel un lead est "
                          "automatiquement assigné et le commercial notifié. "
                          "Vide/0 = désactivé.",
                verbose_name="Seuil de score MQL",
            ),
        ),
    ]
