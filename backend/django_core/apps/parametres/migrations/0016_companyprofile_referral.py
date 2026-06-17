# N98 — programme de parrainage : activation + récompense par défaut. Additif,
# désactivé par défaut (referral_enabled=False) → comportement inchangé.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("parametres", "0015_companyprofile_default_installer"),
    ]

    operations = [
        migrations.AddField(
            model_name="companyprofile",
            name="referral_enabled",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="companyprofile",
            name="referral_reward",
            field=models.DecimalField(
                blank=True, decimal_places=2, max_digits=10, null=True
            ),
        ),
    ]
