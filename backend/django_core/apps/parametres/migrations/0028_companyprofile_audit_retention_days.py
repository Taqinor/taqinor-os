# FG26 — fenêtre de rétention du journal d'audit (RGPD).

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("parametres", "0027_approvalpolicy"),
    ]

    operations = [
        migrations.AddField(
            model_name="companyprofile",
            name="audit_retention_days",
            field=models.PositiveIntegerField(
                default=0,
                help_text="Rétention du journal d'audit en jours "
                          "(0 = illimité).",
            ),
        ),
    ]
