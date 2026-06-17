# N52 — règle de sous-performance (suivi de production). Additif, désactivé par
# défaut (seuil NULL, auto-ticket False) → comportement inchangé.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("parametres", "0016_companyprofile_referral"),
    ]

    operations = [
        migrations.AddField(
            model_name="companyprofile",
            name="seuil_sous_performance_pct",
            field=models.DecimalField(
                blank=True, decimal_places=2, max_digits=5, null=True
            ),
        ),
        migrations.AddField(
            model_name="companyprofile",
            name="auto_ticket_sous_performance",
            field=models.BooleanField(default=False),
        ),
    ]
